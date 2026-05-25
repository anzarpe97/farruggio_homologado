import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _create_payments(self):
        """Enganche después de crear los pagos desde el wizard"""
        payments = super()._create_payments()

        DiscountConfig = self.env["discount.config"]

        # Configuración para pronto pago
        config_early = DiscountConfig.search([
            ("discount_type", "=", "early_payment"),
            ("apply_to", "in", ["all", "customers"]),
        ], limit=1)

        # Configuración para negociación
        config_negotiation = DiscountConfig.search([
            ("discount_type", "=", "negotiation")
        ], limit=1)

        for payment in payments:
            try:
                _logger.info("[PRONTO PAGO WIZARD] Procesando pago ID %s - Monto total pago: %s - Moneda: %s",
                            payment.id, payment.amount, payment.currency_id.display_name)

                # 🔹 OBTENER TODAS LAS FACTURAS RECONCILIADAS (incluyendo parciales)
                # Buscar todas las reconciliaciones parciales donde este pago es el crédito
                partial_reconciles = self.env['account.partial.reconcile'].search([
                    ('credit_move_id.move_id', '=', payment.move_id.id)
                ])
                
                # Obtener las facturas desde las reconciliaciones
                invoice_ids = partial_reconciles.mapped('debit_move_id.move_id').filtered(
                    lambda m: m.move_type == 'out_invoice' and m.state == 'posted'
                )
                
                invoices = invoice_ids
                
                _logger.info("[PRONTO PAGO WIZARD] Facturas encontradas para pago ID %s: %s",
                            payment.id, invoices.ids)

                # 🔹 CALCULAR EL TOTAL ESPERADO CON DESCUENTOS PARA TODAS LAS FACTURAS
                total_expected_with_discounts = 0.0
                invoice_discount_data = {}

                for invoice in invoices:
                    # 🔹 VALIDAR QUE LA FACTURA PERTENEZCA AL DIARIO "FACTURAS DE CLIENTES"
                    invoice_journal_name = invoice.journal_id.name if invoice.journal_id else ""
                    if invoice_journal_name != "FACTURAS DE CLIENTES":
                        _logger.info("[PRONTO PAGO WIZARD] Factura ID %s NO pertenece al diario 'FACTURAS DE CLIENTES' (Diario: %s). No se aplicarán descuentos.", 
                                    invoice.id, invoice_journal_name)
                        continue
                    
                    # 🔹 VALIDAR QUE EL CLIENTE NO ESTÉ EN LA LISTA DE EXCLUSIÓN
                    partner_name = invoice.partner_id.name if invoice.partner_id else ""
                    excluded_partners = [
                        "ALIMENTOS DISPROCAR, C.A",
                        "FUNDACION AMIGOS DEL NINO CON CANCER ZULIA (FUNDACION AMIGOS DEL NIÑO CON CANCER ZULIA)"
                    ]
                    if partner_name in excluded_partners:
                        _logger.info("[PRONTO PAGO WIZARD] Factura ID %s pertenece al cliente excluido '%s'. No se aplicarán descuentos.", 
                                    invoice.id, partner_name)
                        continue
                    
                    # Verificar que todos los pagos estén dentro del período de pronto pago
                    all_payments_in_early_period = self._check_all_payments_in_early_period(invoice, config_early, payment.date)
                    
                    # 🔹 Determinar si aplica descuento de pronto pago
                    apply_early_payment = all_payments_in_early_period
                    
                    if not all_payments_in_early_period:
                        _logger.info("[PRONTO PAGO WIZARD] Factura ID %s tiene pagos fuera del período de PP, NO aplicará descuento de pronto pago", invoice.id)
                    else:
                        _logger.info("[PRONTO PAGO WIZARD] Factura ID %s tiene todos los pagos dentro del período de PP", invoice.id)

                    # Verificar si aplica negociación para ESTE pago
                    apply_negotiation = False
                    if config_negotiation:
                        journal_name = payment.journal_id.name if payment.journal_id else ""
                        if journal_name in ["CAJA CHICA", "CAJA CHICA 2"]:
                            apply_negotiation = True

                    # 🔹 PASO 1: DETECTAR NC PREVIAS NO REPETIBLES
                    # Estas NC (devoluciones, ajustes, etc.) NO deben generar nuevas NC de descuento
                    credit_notes = self.env["account.move"].search([
                        ("reversed_entry_id", "=", invoice.id),
                        ("move_type", "=", "out_refund"),
                        ("state", "!=", "cancel"),
                    ])
                    
                    # Filtrar NC que NO son de descuento (ni PP ni Negociación)
                    non_discount_nc = credit_notes.filtered(lambda nc: not nc.is_discount_credit_note)
                    
                    # Calcular el monto total de NC no repetibles en USD
                    nc_amount_usd = 0.0
                    for nc in non_discount_nc:
                        nc_amount_usd += nc.amount_total_usd
                    
                    if nc_amount_usd > 0:
                        _logger.info("[PRONTO PAGO WIZARD] Factura ID %s tiene NC(s) no repetibles por %s USD",
                                    invoice.id, nc_amount_usd)

                    # 🔹 PASO 2: CALCULAR DESCUENTOS SOBRE EL RESIDUAL DESPUÉS DE NC PREVIAS
                    # Lógica:
                    # - Factura: 1000 USD
                    # - NC devolución: 300 USD
                    # - Base para descuentos: 700 USD (residual después de NC)
                    # - Descuento PP 3%: 21 USD (3% de 700) - SOLO si está dentro del período
                    # - A pagar: 679 USD (o 700 USD si no aplica PP)
                    
                    # 1. Descuento de Pronto Pago: SOLO si está dentro del período
                    discount_pp_usd = 0.0
                    if apply_early_payment and config_early:
                        discount_pp_usd = self._calculate_early_payment_discount(invoice, config_early)
                    
                    # 2. Calcular cuánto se ha pagado ANTES de este pago (sin contar NC de descuento)
                    previous_payments_usd = self._get_previous_payments_amount(invoice, payment)
                    
                    # 3. Calcular el residual a pagar
                    # Residual = Total factura - NC previas - Descuento PP - Pagos anteriores
                    base_after_nc = invoice.amount_total_usd - nc_amount_usd
                    base_after_pp = base_after_nc - discount_pp_usd
                    residual_to_pay = base_after_pp - previous_payments_usd
                    
                    _logger.info("[PRONTO PAGO WIZARD] Factura ID %s - Total: %s USD - NC previas: %s USD - Base después NC: %s USD - Descuento PP: %s USD - Pagos anteriores: %s USD - Residual a pagar: %s USD",
                                invoice.id, invoice.amount_total_usd, nc_amount_usd, base_after_nc, discount_pp_usd, previous_payments_usd, residual_to_pay)
                    
                    # 4. Descuento de Negociación: sobre el residual que se paga
                    discount_neg_usd = 0.0
                    if apply_negotiation and residual_to_pay > 0:
                        # Calcular el descuento sobre el residual a pagar
                        discount_neg_usd = self._calculate_negotiation_discount(invoice, config_negotiation, residual_to_pay)
                        _logger.info("[PRONTO PAGO WIZARD] Descuento negociación calculado: %s USD sobre residual de %s USD",
                                    discount_neg_usd, residual_to_pay)
                    
                    # 🔹 CALCULAR TOTAL PAGADO (incluyendo este pago y anteriores)
                    # Calcular cuánto se aplica de ESTE pago a esta factura
                    partials_this_payment = self.env["account.partial.reconcile"].search([
                        ("credit_move_id.move_id", "=", payment.move_id.id),
                        ("debit_move_id.move_id", "=", invoice.id),
                    ])
                    # Calcular el monto aplicado en USD usando la misma heurística de pagos anteriores:
                    # 1) Si el payment tiene amount_ref, usarlo (valor más preciso)
                    # 2) Si la línea del crédito está en USD, usar amount_currency
                    # 3) Si viene en otra moneda (VEF/Bs), convertir usando la tasa de la factura
                    current_payment_amount_usd = 0.0
                    # Si el pago tiene amount_ref en el registro del payment (valor en USD),
                    # preferimos repartir ese amount_ref entre los partials proporcionalmente
                    # al monto parcial (en la moneda del pago). Esto evita inconsistencias cuando
                    # las líneas parciales se muestran en Bs y la conversión iguala al total.
                    payment_ref_total = getattr(payment, 'amount_ref', 0.0) or 0.0
                    total_partial_amount = sum(abs(p.amount) for p in partials_this_payment) if partials_this_payment else 0.0

                    for partial in partials_this_payment:
                        credit_line = partial.credit_move_id
                        payment_move = credit_line.move_id
                        payment_usd = 0.0

                        if payment_ref_total and total_partial_amount > 0:
                            # Repartir amount_ref proporcionalmente
                            share = abs(partial.amount) / total_partial_amount
                            payment_usd = payment_ref_total * share
                            _logger.info("[PRONTO PAGO WIZARD] Usando payment.amount_ref repartido (share=%s) => %s USD para este partial", share, payment_usd)
                        elif payment_move.payment_id and hasattr(payment_move.payment_id, 'amount_ref') and payment_move.payment_id.amount_ref:
                            payment_usd = payment_move.payment_id.amount_ref
                            _logger.info("[PRONTO PAGO WIZARD] Usando amount_ref del pago (current): %s USD", payment_usd)
                        elif credit_line.currency_id and credit_line.currency_id.name == 'USD':
                            payment_usd = abs(credit_line.amount_currency)
                            _logger.info("[PRONTO PAGO WIZARD] Usando amount_currency (USD) del partial (current): %s USD", payment_usd)
                        else:
                            payment_usd = partial.amount / invoice.tax_today if invoice.tax_today else 0
                            _logger.info("[PRONTO PAGO WIZARD] Convirtiendo partial.amount (Bs) con tasa factura: %s / %s = %s USD", partial.amount, invoice.tax_today, payment_usd)

                        current_payment_amount_usd += payment_usd
                    
                    # Total pagado = pagos anteriores + este pago
                    total_paid_usd = previous_payments_usd + current_payment_amount_usd
                    
                    # 🔹 CALCULAR CUÁNTO DEBERÍA HABERSE PAGADO EN TOTAL (con descuentos y NC previas)
                    # Fórmula: Total factura - NC previas - Descuento PP - Descuento Negociación
                    expected_total_payment = invoice.amount_total_usd - nc_amount_usd - discount_pp_usd - discount_neg_usd
                    
                    _logger.info("[PRONTO PAGO WIZARD] Factura ID %s - Total pagado: %s USD - Esperado con descuentos: %s USD",
                                invoice.id, total_paid_usd, expected_total_payment)
                    
                    # 5. Monto que se espera pagar en ESTE pago
                    expected_payment_for_invoice = residual_to_pay - discount_neg_usd
                    total_expected_with_discounts += expected_payment_for_invoice

                    # 🔹 VERIFICAR SI LA FACTURA ESTÁ COMPLETAMENTE PAGADA
                    # Una factura está completamente pagada si:
                    # 1. Se pagó EXACTAMENTE lo esperado (con tolerancia por redondeo/tasa)
                    # 2. O se pagó MÁS de lo esperado (hay un excedente)
                    # Tolerancia de 5 USD para manejar diferencias de tasa de cambio y redondeos
                    payment_difference = total_paid_usd - expected_total_payment
                    is_fully_paid = payment_difference >= -5.00  # Permite pagar de más, o de menos con tolerancia de 5 USD
                    
                    if is_fully_paid:
                        if payment_difference > 5.00:
                            _logger.info("[PRONTO PAGO WIZARD] ✅ Factura ID %s SOBREPAGADA (excedente: %s USD), generando NC de descuento",
                                        invoice.id, payment_difference)
                        elif payment_difference < -0.01:
                            _logger.info("[PRONTO PAGO WIZARD] ✅ Factura ID %s pagada con pequeña diferencia aceptable (%s USD), generando NC de descuento",
                                        invoice.id, payment_difference)
                        else:
                            _logger.info("[PRONTO PAGO WIZARD] ✅ Factura ID %s pagada exactamente", invoice.id)
                    
                    # Guardar datos para crear las NC después
                    invoice_discount_data[invoice.id] = {
                        'invoice': invoice,
                        'discount_pp_usd': discount_pp_usd,
                        'discount_neg_usd': discount_neg_usd,
                        'apply_negotiation': apply_negotiation,
                        'apply_early_payment': apply_early_payment,  # Nueva bandera
                        'total_with_discounts': expected_payment_for_invoice,
                        'previous_payments_usd': previous_payments_usd,
                        'total_paid_usd': total_paid_usd,
                        'current_payment_amount_usd': current_payment_amount_usd,
                        'expected_total_payment': expected_total_payment,
                        'nc_amount_usd': nc_amount_usd,
                        'has_non_discount_nc': nc_amount_usd > 0,
                        'is_fully_paid': is_fully_paid,
                        'payment_difference': payment_difference
                    }

                    _logger.info("[PRONTO PAGO WIZARD] Factura ID %s - Pago esperado en este pago: %s USD - ¿Completamente pagada?: %s (Diferencia: %s USD)",
                                invoice.id, expected_payment_for_invoice, is_fully_paid, payment_difference)

                # 🔹 GENERAR NC SOLO PARA FACTURAS COMPLETAMENTE PAGADAS
                # No importa si el pago actual cubre todo, lo que importa es que cada factura
                # individualmente esté completamente pagada (con sus descuentos)
                # --- Verificación global para pagos a múltiples facturas ---
                try:
                    # Preferir el amount_ref total del pago (si existe) como el monto aplicado en USD,
                    # ya que refleja el importe real en la moneda de referencia y evita inconsistencias
                    # por conversiones desde Bs en líneas parciales.
                    payment_ref_total = getattr(payment, 'amount_ref', 0.0) or 0.0
                    if payment_ref_total:
                        total_applied_usd = payment_ref_total
                        _logger.info("[PRONTO PAGO WIZARD] Usando payment.amount_ref total=%s USD como Total aplicado por este pago (prefiere amount_ref)", total_applied_usd)
                    else:
                        total_applied_usd = sum(d.get('current_payment_amount_usd', 0.0) for d in invoice_discount_data.values())
                        _logger.info("[PRONTO PAGO WIZARD] Total aplicado por este pago (USD calculado por partials): %s - Total esperado con descuentos (USD): %s",
                                    total_applied_usd, total_expected_with_discounts)

                    # Si la suma aplicada coincide con la suma esperada (dentro de tolerancia),
                    # entonces todos los invoices incluidos deben generar sus NCs correspondientes
                    GLOBAL_TOLERANCE = 5.00
                    if abs(total_applied_usd - total_expected_with_discounts) <= GLOBAL_TOLERANCE:
                        _logger.info("[PRONTO PAGO WIZARD] Pago cubre la suma total esperada con descuentos (dentro de tolerancia %s USD). Aplicando NCs a las facturas involucradas.", GLOBAL_TOLERANCE)
                        for d in invoice_discount_data.values():
                            inv = d['invoice']
                            curr = d.get('current_payment_amount_usd', 0.0)
                            # Si el cliente pagó el total de la factura (sin descontar), NO debe aplicarse el descuento para esa factura
                            if abs(curr - inv.amount_total_usd) < 0.01:
                                expected = d.get('total_with_discounts', 0.0)
                                disc_pp = d.get('discount_pp_usd', 0.0)
                                # Primera opción: si existe payment.amount_ref úsalo para decidir
                                payment_ref = getattr(payment, 'amount_ref', 0.0) or 0.0
                                if payment_ref:
                                    paid_value = payment_ref
                                    _logger.info("[PRONTO PAGO WIZARD] Usando payment.amount_ref=%s USD para decidir aplicabilidad de NC en factura %s", payment_ref, inv.id)
                                else:
                                    paid_value = curr
                                    _logger.info("[PRONTO PAGO WIZARD] No existe payment.amount_ref; usando importe convertido curr=%s USD para factura %s", curr, inv.id)

                                # Si la diferencia entre lo pagado y lo esperado coincide con el PP, conservar la NC
                                # (evita falsos negativos por conversiones de moneda)
                                if abs((paid_value - expected) - disc_pp) <= 1.5 and disc_pp > 0:
                                    _logger.info("[PRONTO PAGO WIZARD] Factura ID %s: la diferencia pagado-esperado (%s USD) coincide con PP (%s USD); se mantendrá la NC de descuento", inv.id, paid_value - expected, disc_pp)
                                else:
                                    _logger.info("[PRONTO PAGO WIZARD] Factura ID %s fue pagada por el total (sin descuento). No se aplicará NC de descuento para esta factura.", inv.id)
                                    d['apply_early_payment'] = False
                                    d['discount_pp_usd'] = 0.0
                                    d['discount_neg_usd'] = 0.0
                            d['is_fully_paid'] = True
                    else:
                        _logger.info("[PRONTO PAGO WIZARD] Pago NO cubre la suma total esperada con descuentos. Se procederá con evaluación por factura individual.")
                        # Heurística de asignación: repartimos el total aplicado entre facturas en el orden
                        # en que aparecen y marcamos como pagadas aquellas cuya cantidad esperada con
                        # descuento quede cubierta por el remanente.
                        try:
                            remaining = sum(d.get('current_payment_amount_usd', 0.0) for d in invoice_discount_data.values())
                            _logger.info("[PRONTO PAGO WIZARD] Asignando pago total (USD) entre facturas: %s", remaining)
                            TOL = 0.01
                            # Procesar en orden de aparición (ya es el orden de invoice_discount_data)
                            for d in invoice_discount_data.values():
                                inv = d['invoice']
                                expected = d.get('total_with_discounts', 0.0)
                                curr_applied = d.get('current_payment_amount_usd', 0.0)
                                # Si el pago aplicado individual muestra que se pagó el total de la factura
                                # (sin descuento), entonces esa factura no recibe NC de descuento
                                if abs(curr_applied - inv.amount_total_usd) < 0.01:
                                    expected = d.get('total_with_discounts', 0.0)
                                    disc_pp = d.get('discount_pp_usd', 0.0)
                                    # Si la diferencia entre lo aplicado y lo esperado coincide con PP,
                                    # conservar la NC (maneja conversiones y redondeos)
                                    if abs((curr_applied - expected) - disc_pp) <= 1.5 and disc_pp > 0:
                                        _logger.info("[PRONTO PAGO WIZARD] Factura ID %s muestra pago igual al total pero la diferencia (%s USD) coincide con PP (%s USD); se mantendrá la NC", inv.id, curr_applied - expected, disc_pp)
                                    else:
                                        _logger.info("[PRONTO PAGO WIZARD] Factura ID %s muestra pago individual igual al total de la factura. No se aplicará descuento.", inv.id)
                                        d['apply_early_payment'] = False
                                        d['discount_pp_usd'] = 0.0
                                        d['discount_neg_usd'] = 0.0
                                    d['is_fully_paid'] = True
                                    # Reducir remaining por el monto realmente aplicado a esta factura
                                    remaining -= curr_applied
                                    continue

                                # Si el remanente alcanza para cubrir la cantidad esperada con descuento, marcarla como pagada
                                if remaining + TOL >= expected and expected > 0:
                                    d['is_fully_paid'] = True
                                    remaining -= expected
                                    _logger.info("[PRONTO PAGO WIZARD] Se cubre factura ID %s con %s USD (esperado %s). Remanente: %s USD", inv.id, expected, expected, remaining)
                                else:
                                    d['is_fully_paid'] = False
                                    _logger.info("[PRONTO PAGO WIZARD] No se cubre factura ID %s con el remanente %s USD (esperado %s).", inv.id, remaining, expected)
                        except Exception:
                            _logger.exception("[PRONTO PAGO WIZARD] Error asignando pagos entre facturas")
                except Exception:
                    _logger.exception("[PRONTO PAGO WIZARD] Error en verificación global de pagos múltiples")

                for invoice_id, data in invoice_discount_data.items():
                    invoice = data['invoice']
                    discount_pp_usd = data['discount_pp_usd']
                    discount_neg_usd = data['discount_neg_usd']
                    apply_negotiation = data['apply_negotiation']
                    apply_early_payment = data['apply_early_payment']
                    is_fully_paid = data['is_fully_paid']
                    
                    if not is_fully_paid:
                        _logger.info("[PRONTO PAGO WIZARD] ⏳ Factura ID %s NO está completamente pagada aún (Pagado: %s USD, Esperado: %s USD), esperando más pagos",
                                    invoice.id, data['total_paid_usd'], data['expected_total_payment'])
                        continue
                    
                    _logger.info("[PRONTO PAGO WIZARD] ✅ Factura ID %s está completamente pagada, generando NC", invoice.id)

                    # Crear NC de pronto pago - SOLO si aplica
                    if apply_early_payment and discount_pp_usd > 0:
                        existing_nc_early = self.env["account.move"].search([
                            ("reversed_entry_id", "=", invoice.id),
                            ("is_discount_credit_note", "=", True),
                            ("invoice_line_ids.product_id.default_code", "=", "DESCUENTO_PP"),
                            ("state", "!=", "cancel"),
                        ], limit=1)

                        if not existing_nc_early:
                            _logger.info("[PRONTO PAGO WIZARD] Creando NC de pronto pago para factura ID %s - Monto: %s USD", invoice.id, discount_pp_usd)
                            self._create_early_payment_credit_note(invoice, discount_pp_usd, config_early)
                        else:
                            _logger.info("[PRONTO PAGO WIZARD] Factura ID %s ya tiene NC de pronto pago", invoice.id)
                    elif not apply_early_payment:
                        _logger.info("[PRONTO PAGO WIZARD] Factura ID %s NO aplica descuento de pronto pago (fuera de período)", invoice.id)

                    # Crear NC de negociación
                    if discount_neg_usd > 0:
                        existing_nc_neg = self.env["account.move"].search([
                            ("reversed_entry_id", "=", invoice.id),
                            ("is_discount_credit_note", "=", True),
                            ("invoice_line_ids.product_id.default_code", "=", "DESCUENTO_PN"),
                            ("state", "!=", "cancel"),
                        ], limit=1)

                        if not existing_nc_neg:
                            _logger.info("[PRONTO PAGO WIZARD] Creando NC de negociación para factura ID %s - Monto: %s USD", invoice.id, discount_neg_usd)
                            self._create_negotiation_credit_note(invoice, discount_neg_usd, config_negotiation)
                        else:
                            _logger.info("[PRONTO PAGO WIZARD] Factura ID %s ya tiene NC de negociación", invoice.id)

            except Exception as e:
                _logger.error("[PRONTO PAGO WIZARD] Error procesando pago ID %s: %s",
                            payment.id, str(e), exc_info=True)

        return payments

    def _process_individual_payment_logic(self, payment, invoice, applied_amount_usd, config_early, config_negotiation):
        """Procesa la lógica original de pagos individuales para casos fuera del período acumulativo"""
        # 🔹 VALIDAR QUE LA FACTURA PERTENEZCA AL DIARIO "FACTURAS DE CLIENTES"
        invoice_journal_name = invoice.journal_id.name if invoice.journal_id else ""
        if invoice_journal_name != "FACTURAS DE CLIENTES":
            _logger.info("[PRONTO PAGO WIZARD] Factura ID %s NO pertenece al diario 'FACTURAS DE CLIENTES' (Diario: %s). No se aplicarán descuentos.", 
                        invoice.id, invoice_journal_name)
            return
        
        # 🔹 VALIDAR QUE EL CLIENTE NO ESTÉ EN LA LISTA DE EXCLUSIÓN
        partner_name = invoice.partner_id.name if invoice.partner_id else ""
        excluded_partners = [
            "ALIMENTOS DISPROCAR, C.A",
            "FUNDACION AMIGOS DEL NINO CON CANCER ZULIA (FUNDACION AMIGOS DEL NIÑO CON CANCER ZULIA)"
        ]
        if partner_name in excluded_partners:
            _logger.info("[PRONTO PAGO WIZARD] Factura ID %s pertenece al cliente excluido '%s'. No se aplicarán descuentos.", 
                        invoice.id, partner_name)
            return
        
        # 🔹 VERIFICAR SI EL PAGO CUBRE EL 100% DE LA FACTURA (en USD)
        if abs(applied_amount_usd - invoice.amount_total_usd) < 0.01:
            _logger.info("[PRONTO PAGO WIZARD] Pago cubre el 100%% de la factura ID %s, no se aplican descuentos", invoice.id)
            return

        # Variables para controlar qué descuentos aplicar
        apply_early_individual = False
        apply_negotiation_individual = False

        # 🔹 VERIFICAR PRONTO PAGO INDIVIDUAL (por días)
        if config_early:
            dias_transcurridos = (payment.date - invoice.invoice_date).days
            if dias_transcurridos <= config_early.early_payment_days:
                _logger.info("[PRONTO PAGO WIZARD] Factura ID %s aplica descuento pronto pago (%s días <= %s días)",
                            invoice.id, dias_transcurridos, config_early.early_payment_days)
                apply_early_individual = True
            else:
                _logger.info("[PRONTO PAGO WIZARD] Factura ID %s NO aplica pronto pago (%s días > %s días)",
                            invoice.id, dias_transcurridos, config_early.early_payment_days)

        # 🔹 VERIFICAR NEGOCIACIÓN INDIVIDUAL
        if config_negotiation:
            # Verificar condiciones para negociación
            journal_name = payment.journal_id.name if payment.journal_id else ""
            if journal_name in ["CAJA CHICA", "CAJA CHICA 2"]:
                apply_negotiation_individual = True

        # 🔹 APLICAR DESCUENTOS INDIVIDUALES
        discount_pp = 0.0
        if apply_early_individual:
            discount_pp = self._apply_early_payment_discount(payment, invoice)
            _logger.info("[PRONTO PAGO WIZARD] Descuento pronto pago aplicado: %s USD", discount_pp)

            # 🔹 VERIFICAR SI TAMBIÉN APLICA NEGOCIACIÓN DESPUÉS DE PRONTO PAGO
            if config_negotiation and payment.currency_id.name == "USD":
                journal_name = payment.journal_id.name if payment.journal_id else ""
                if journal_name in ["CAJA CHICA", "CAJA CHICA 2"]:
                    # Calcular el monto restante después del pronto pago
                    discount_pp_with_tax = discount_pp * invoice.tax_today
                    remaining_amount = (invoice.amount_total_usd * invoice.tax_today) - discount_pp_with_tax
                    _logger.info("[PRONTO PAGO WIZARD] Monto restante después de pronto pago: %s USD", remaining_amount)
                    if remaining_amount > 0:
                        self._apply_negotiation_discount(payment, invoice, amount_base=remaining_amount)
                    else:
                        _logger.info("[PRONTO PAGO WIZARD] No hay monto restante para negociación después del pronto pago")

        elif apply_negotiation_individual:
            # Aplicar negociación normal
            self._apply_negotiation_discount(payment, invoice)

    def _check_all_payments_in_early_period(self, invoice, config_early, current_payment_date):
        """Verifica que todos los pagos de la factura estén dentro del período de pronto pago"""
        if not config_early:
            return False

        # Obtener todos los pagos reconciliados con esta factura
        reconciled_payments = self.env['account.partial.reconcile'].search([
            ('debit_move_id.move_id', '=', invoice.id)
        ]).mapped('credit_move_id.move_id')

        # Filtrar solo pagos que están reconciliados con esta factura
        payments = reconciled_payments.filtered(lambda p: p.payment_id and p.payment_id.state == 'posted')

        # Para cada pago, verificar si está dentro del período
        for payment_move in payments:
            payment = payment_move.payment_id
            dias_transcurridos = (payment.date - invoice.invoice_date).days

            if dias_transcurridos > config_early.early_payment_days:
                _logger.info("[PRONTO PAGO WIZARD] Pago ID %s fuera de período (%s días > %s días)",
                            payment.id, dias_transcurridos, config_early.early_payment_days)
                return False

        _logger.info("[PRONTO PAGO WIZARD] Todos los pagos de factura ID %s están dentro del período de pronto pago", invoice.id)
        return True

    def _get_previous_payments_amount(self, invoice, current_payment):
        """
        Calcula el monto total PAGADO a la factura ANTES del pago actual en USD.
        Excluye TODAS las notas de crédito (descuento y no-descuento), ya que las NC son ajustes, no pagos.
        Solo cuenta pagos reales (tipo 'entry' con payment_id).
        """
        try:
            # Buscar todas las reconciliaciones de la factura
            all_reconciles = self.env['account.partial.reconcile'].search([
                ('debit_move_id.move_id', '=', invoice.id)
            ])
            
            total_previous_payments_usd = 0.0
            
            for reconcile in all_reconciles:
                payment_move = reconcile.credit_move_id.move_id
                
                # Saltar el pago actual
                if payment_move.id == current_payment.move_id.id:
                    continue
                
                # 🔹 SALTAR TODAS LAS NC (no son pagos, son ajustes)
                if payment_move.move_type == 'out_refund':
                    _logger.info("[PRONTO PAGO WIZARD] Saltando NC ID %s - %s (no es un pago)", payment_move.id, payment_move.name)
                    continue
                
                # 🔹 SOLO CONTAR MOVIMIENTOS QUE SEAN PAGOS REALES
                if not payment_move.payment_id:
                    _logger.info("[PRONTO PAGO WIZARD] Saltando move ID %s - %s (no tiene payment_id)", payment_move.id, payment_move.name)
                    continue
                
                # 🔹 CALCULAR EL MONTO EN USD CORRECTAMENTE
                payment_usd = 0.0
                
                # Buscar la línea del pago que tiene el amount_currency
                credit_line = reconcile.credit_move_id
                
                # Si el pago tiene payment_id y amount_ref, usar ese valor (es el más preciso)
                if payment_move.payment_id and hasattr(payment_move.payment_id, 'amount_ref') and payment_move.payment_id.amount_ref:
                    payment_usd = payment_move.payment_id.amount_ref
                    _logger.info("[PRONTO PAGO WIZARD] Usando amount_ref del pago: %s USD", payment_usd)
                # Si la moneda del pago es USD, usar amount_currency
                elif credit_line.currency_id and credit_line.currency_id.name == 'USD':
                    # Es un pago en USD, usar el amount_currency (que es negativo en pagos)
                    payment_usd = abs(credit_line.amount_currency)
                    _logger.info("[PRONTO PAGO WIZARD] Usando amount_currency (USD): %s USD", payment_usd)
                else:
                    # Es un pago en otra moneda (VEF/Bs), convertir usando la tasa de la factura
                    payment_usd = reconcile.amount / invoice.tax_today if invoice.tax_today else 0
                    _logger.info("[PRONTO PAGO WIZARD] Convirtiendo con tasa factura: %s Bs / %s = %s USD", 
                                reconcile.amount, invoice.tax_today, payment_usd)
                
                total_previous_payments_usd += payment_usd
                
                _logger.info("[PRONTO PAGO WIZARD] Pago anterior - Move: %s, Moneda: %s, Amount_ref: %s, Reconcile amount (Bs): %s, USD calculado: %s",
                            payment_move.name, 
                            credit_line.currency_id.name if credit_line.currency_id else 'Bs',
                            payment_move.payment_id.amount_ref if payment_move.payment_id and hasattr(payment_move.payment_id, 'amount_ref') else 'N/A',
                            reconcile.amount, 
                            payment_usd)
            
            _logger.info("[PRONTO PAGO WIZARD] Total pagos anteriores para factura ID %s: %s USD",
                        invoice.id, total_previous_payments_usd)
            
            return total_previous_payments_usd
            
        except Exception as e:
            _logger.error("[PRONTO PAGO WIZARD] Error calculando pagos anteriores para factura ID %s: %s",
                        invoice.id, str(e), exc_info=True)
            return 0.0

    def _get_total_paid_amount_usd(self, invoice):
        """Obtiene el monto total pagado de la factura en USD"""
        try:
            # Método más confiable: usar amount_total_usd - amount_residual_usd
            total_paid_usd = invoice.amount_total_usd - invoice.amount_residual_usd

            _logger.info("[PRONTO PAGO WIZARD] Monto pagado USD calculado: %s (Total USD: %s, Residual USD: %s)",
                        total_paid_usd, invoice.amount_total_usd, invoice.amount_residual_usd)

            return total_paid_usd

        except Exception as e:
            _logger.error("[PRONTO PAGO WIZARD] Error calculando monto pagado USD para factura ID %s: %s",
                        invoice.id, str(e))
            # Fallback: calcular basado en el residual
            return invoice.amount_total_usd - invoice.amount_residual_usd

    def _get_discount_base_amount_usd(self, invoice):
        """
        Retorna la base sobre la cual calcular descuentos.
        
        LÓGICA CORRECTA:
        - Si la factura tiene NC previas no repetibles (devoluciones, ajustes, etc.),
          el descuento se calcula sobre el RESIDUAL (después de restar esas NC)
        - Si no tiene NC previas, se calcula sobre el total original de la factura
        
        Ejemplo:
        - Factura: 1000 USD
        - NC devolución: 300 USD  
        - Base para descuento: 700 USD (residual)
        - Descuento PP 3%: 21 USD (3% de 700)
        """
        try:
            # Buscar NC previas que NO son de descuento
            credit_notes = self.env["account.move"].search([
                ("reversed_entry_id", "=", invoice.id),
                ("move_type", "=", "out_refund"),
                ("state", "!=", "cancel"),
            ])
            
            non_discount_nc = credit_notes.filtered(lambda nc: not nc.is_discount_credit_note)
            
            if non_discount_nc:
                # Calcular el monto total de NC no repetibles
                nc_amount_usd = sum(nc.amount_total_usd for nc in non_discount_nc)
                base_amount = invoice.amount_total_usd - nc_amount_usd
                _logger.info("[PRONTO PAGO WIZARD] Base de descuento para factura ID %s: %s USD (Total: %s - NC previas: %s)",
                            invoice.id, base_amount, invoice.amount_total_usd, nc_amount_usd)
                return base_amount
            
            # Si no hay NC previas, usar el total de la factura
            return invoice.amount_total_usd

        except Exception as e:
            _logger.error("[PRONTO PAGO WIZARD] Error obteniendo base de cálculo para factura ID %s: %s",
                          invoice.id, str(e), exc_info=True)
            return invoice.amount_total_usd

    def _calculate_early_payment_discount(self, invoice, config_early):
        """
        Calcula el monto del descuento por pronto pago (en USD)
        
        El descuento se calcula sobre el residual después de NC previas no repetibles.
        """
        if not config_early:
            return 0.0

        # Obtener la base de descuento (considerando NC previas)
        discount_base = self._get_discount_base_amount_usd(invoice)
        discount_percent = config_early.discount_percent
        discount_amount = discount_base * (discount_percent / 100.0)

        _logger.info("[PRONTO PAGO WIZARD] Descuento PP calculado: %s USD (%s%% de %s USD)",
                     discount_amount, discount_percent, discount_base)

        return discount_amount

    def _calculate_negotiation_discount(self, invoice, config_negotiation, base_amount=None):
        """
        Calcula el monto del descuento por negociación sobre el monto base (en USD)
        
        Si se proporciona base_amount, se usa ese valor (para pagos parciales/residuales).
        Si no, se calcula sobre el residual después de NC previas.
        """
        if not config_negotiation:
            return 0.0

        # Si no se proporciona base_amount, usar el residual después de NC previas
        if base_amount is None:
            base_amount = self._get_discount_base_amount_usd(invoice)

        discount_percent = config_negotiation.discount_percent
        discount_amount = base_amount * (discount_percent / 100.0)
        
        _logger.info("[PRONTO PAGO WIZARD] Descuento negociación calculado: %s USD (%s%% de %s USD)",
                    discount_amount, discount_percent, base_amount)

        return discount_amount

    def _create_early_payment_credit_note(self, invoice, discount_amount_usd, config_early):
        """Crea la nota de crédito por pronto pago"""
        try:
            # Convertir a moneda de la compañía si es necesario
            discount_amount_final = discount_amount_usd * invoice.tax_today

            product = self.env["product.product"].search([("default_code", "=", "DESCUENTO_PP")], limit=1)
            if not product:
                raise UserError(_("Debe crear un producto con código 'DESCUENTO_PP' para las notas de crédito."))

            journal = self.env['account.journal'].search([
                ('name', '=', 'NOTAS DE CREDITO DE CLIENTE'),
                ('company_id', '=', invoice.company_id.id)
            ], limit=1)
            if not journal:
                raise UserError(_("No se encontró el diario 'NOTAS DE CREDITO DE CLIENTE' para la compañía de la factura."))

            refund_vals = {
                "move_type": "out_refund",
                "journal_id": journal.id,
                "partner_id": invoice.partner_id.id,
                "tax_today": invoice.tax_today,
                "reversed_entry_id": invoice.id,
                "x_studio_selection_field_Q69ft": "Ventas (ADMON)",
                "x_studio_motivo_de_devolucin": f"Descuento 3%",
                "x_studio_motivo": f"Descuento de {discount_amount_usd:.2f} USD ({config_early.discount_percent}%) sobre {invoice.amount_total_usd:.2f} USD",
                "is_discount_credit_note": True,
                "invoice_line_ids": [(0, 0, {
                    "product_id": product.id,
                    "name": _("Descuento por pronto pago"),
                    "quantity": 1,
                    "price_unit": discount_amount_final,
                    "account_id": product.property_account_income_id.id or product.categ_id.property_account_income_categ_id.id,
                })],
            }

            refund = self.env["account.move"].create(refund_vals)
            # refund.action_post()  # Validar la nota de crédito

            _logger.info("[PRONTO PAGO WIZARD] NC creada ID %s - Monto: %s USD - Aplicada contra Factura ID %s",
                        refund.id, discount_amount_usd, invoice.id)

            # Mensaje en el chatter para auditar la creación de la NC
            try:
                refund.message_post(body=_(
                    'Esta Nota de Crédito se generó a partir de la factura '
                    '<a href="#" data-oe-model="account.move" data-oe-id="%s">%s</a>'
                ) % (invoice.id, invoice.name))
            except Exception:
                _logger.exception("[PRONTO PAGO WIZARD] Error posteando mensaje en chatter para NC ID %s", refund.id)

            return discount_amount_usd

        except Exception as e:
            _logger.error("[PRONTO PAGO WIZARD] Error creando NC para factura ID %s: %s",
                         invoice.id, str(e), exc_info=True)
            return 0.0

    def _create_negotiation_credit_note(self, invoice, discount_amount_usd, config_negociacion):
        """Crea la nota de crédito por negociación"""
        try:
            # Convertir a moneda de la compañía si es necesario
            discount_amount_final = discount_amount_usd * invoice.tax_today

            product = self.env["product.product"].search([("default_code", "=", "DESCUENTO_PN")], limit=1)
            if not product:
                raise UserError(_("Debe crear un producto con código 'DESCUENTO_PN' para las notas de crédito."))

            journal = self.env['account.journal'].search([
                ('name', '=', 'NOTAS DE CREDITO DE CLIENTE'),
                ('company_id', '=', invoice.company_id.id)
            ], limit=1)
            if not journal:
                raise UserError(_("No se encontró el diario 'NOTAS DE CREDITO DE CLIENTE' para la compañía de la factura."))

            refund_vals = {
                "move_type": "out_refund",
                "journal_id": journal.id,
                "partner_id": invoice.partner_id.id,
                "tax_today": invoice.tax_today,
                "reversed_entry_id": invoice.id,
                "x_studio_selection_field_Q69ft": "Ventas (ADMON)",
                "x_studio_motivo_de_devolucin": f"Descuento por Negociación",
                "x_studio_motivo": f"Descuento de {discount_amount_usd:.2f} USD ({config_negociacion.discount_percent}%) sobre {invoice.amount_total_usd:.2f} USD",
                "is_discount_credit_note": True,
                "invoice_line_ids": [(0, 0, {
                    "product_id": product.id,
                    "name": _("Descuento por Negociación"),
                    "quantity": 1,
                    "price_unit": discount_amount_final,
                    "account_id": product.property_account_income_id.id or product.categ_id.property_account_income_categ_id.id,
                })],
            }

            refund = self.env["account.move"].create(refund_vals)
            # refund.action_post()  # Validar la nota de crédito

            _logger.info("[PRONTO PAGO WIZARD] NC negociación creada ID %s - Monto: %s USD - Aplicada contra Factura ID %s",
                        refund.id, discount_amount_usd, invoice.id)

            return discount_amount_usd

        except Exception as e:
            _logger.error("[PRONTO PAGO WIZARD] Error creando NC de negociación para factura ID %s: %s",
                         invoice.id, str(e), exc_info=True)
            return 0.0

    def _apply_early_payment_discount(self, payment, invoice):
        """Aplica descuento por pronto pago si cumple condiciones (para pagos individuales)"""
        # 🔹 VALIDAR QUE LA FACTURA PERTENEZCA AL DIARIO "FACTURAS DE CLIENTES"
        invoice_journal_name = invoice.journal_id.name if invoice.journal_id else ""
        if invoice_journal_name != "FACTURAS DE CLIENTES":
            _logger.info("[PRONTO PAGO WIZARD] Factura ID %s NO pertenece al diario 'FACTURAS DE CLIENTES' (Diario: %s). No se aplicará descuento de pronto pago.", 
                        invoice.id, invoice_journal_name)
            return 0.0
        
        # 🔹 VALIDAR QUE EL CLIENTE NO ESTÉ EN LA LISTA DE EXCLUSIÓN
        partner_name = invoice.partner_id.name if invoice.partner_id else ""
        excluded_partners = [
            "ALIMENTOS DISPROCAR, C.A",
            "FUNDACION AMIGOS DEL NINO CON CANCER ZULIA (FUNDACION AMIGOS DEL NIÑO CON CANCER ZULIA)"
        ]
        if partner_name in excluded_partners:
            _logger.info("[PRONTO PAGO WIZARD] Factura ID %s pertenece al cliente excluido '%s'. No se aplicará descuento de pronto pago.", 
                        invoice.id, partner_name)
            return 0.0
        
        # 🔹 VERIFICAR SI EL PAGO CUBRE EL 100% DE LA FACTURA
        partials = self.env["account.partial.reconcile"].search([
            ("credit_move_id.move_id", "=", payment.move_id.id),
            ("debit_move_id.move_id", "=", invoice.id),
        ])
        applied_amount = sum(partial.amount for partial in partials)

        if abs(applied_amount - invoice.amount_total_usd) < 0.01:
            _logger.info("[PRONTO PAGO WIZARD] Pago cubre el 100%% de la factura ID %s, no se crea NC de pronto pago", invoice.id)
            return 0.0

        DiscountConfig = self.env["discount.config"]

        configs = DiscountConfig.search([
            ("discount_type", "=", "early_payment"),
            ("apply_to", "in", ["all", "customers"]),
        ])

        applied_discount = 0.0

        for config in configs:
            if config.apply_to == "customers" and invoice.partner_id not in config.partner_ids:
                _logger.info("[PRONTO PAGO WIZARD] Configuración %s no aplica al cliente %s",
                             config.name, invoice.partner_id.display_name)
                continue

            # Validar moneda
            if config.currency_payment != "any" and config.currency_payment != invoice.currency_id.name:
                _logger.info("[PRONTO PAGO WIZARD] Configuración %s no aplica por moneda. Config=%s, Factura=%s",
                             config.name, config.currency_payment, invoice.currency_id.name)
                continue

            dias_transcurridos = (payment.date - invoice.invoice_date).days
            _logger.info("[PRONTO PAGO WIZARD] Factura ID %s - Días transcurridos: %s - Límite: %s",
                         invoice.id, dias_transcurridos, config.early_payment_days)

            if dias_transcurridos <= config.early_payment_days:
                existing_nc = self.env["account.move"].search([
                    ("move_type", "=", "out_refund"),
                    ("reversed_entry_id", "=", invoice.id),
                    ("invoice_line_ids.product_id.default_code", "=", "DESCUENTO_PP"),
                    ("state", "!=", "cancel"),
                ])
                if existing_nc:
                    _logger.warning("[PRONTO PAGO WIZARD] Ya existe una NC de pronto pago para factura ID %s, se omite duplicado",
                                    invoice.id)
                    continue

                # Usar la nueva lógica de base (residual si existen NC no-descto)
                discount_base = self._get_discount_base_amount_usd(invoice)

                # 🔹 Si existen NC no-descto -> calcular descuento sobre el residual
                credit_notes = self.env["account.move"].search([
                    ("reversed_entry_id", "=", invoice.id),
                    ("move_type", "=", "out_refund"),
                    ("state", "!=", "cancel"),
                ])
                non_discount_nc = credit_notes.filtered(lambda nc: not nc.is_discount_credit_note)

                # Siempre calcular el descuento como porcentaje de la base
                discount_amount_usd = discount_base * (config.discount_percent / 100.0)
                
                if non_discount_nc:
                    _logger.info("[PRONTO PAGO WIZARD] (Regla) NC no-descuento → aplicando descuento sobre residual: %s USD (%s%% de %s USD)",
                                discount_amount_usd, config.discount_percent, discount_base)

                # Convertir a la moneda local al crear la NC (aquí multiplicas por tax_today)
                discount_amount = discount_amount_usd * invoice.tax_today

                _logger.info("[PRONTO PAGO WIZARD] Creando NC por pronto pago. Factura=%s, Descuento=%s%%, Monto USD=%s",
                             invoice.id, config.discount_percent, discount_amount_usd)

                product = self.env["product.product"].search([("default_code", "=", "DESCUENTO_PP")], limit=1)
                if not product:
                    raise UserError(_("Debe crear un producto con código 'DESCUENTO_PP' para las notas de crédito."))

                journal = self.env['account.journal'].search([
                    ('name', '=', 'NOTAS DE CREDITO DE CLIENTE'),
                    ('company_id', '=', invoice.company_id.id)
                ], limit=1)
                if not journal:
                    raise UserError(_("No se encontró el diario 'NOTAS DE CREDITO DE CLIENTE' para la compañía de la factura."))

                refund_vals = {
                    "move_type": "out_refund",
                    "journal_id": journal.id,
                    "partner_id": invoice.partner_id.id,
                    "tax_today": invoice.tax_today,
                    "reversed_entry_id": invoice.id,
                    "x_studio_selection_field_Q69ft": "Ventas (ADMON)",
                    "x_studio_motivo_de_devolucin": "Descuento 3%",
                    "x_studio_motivo": f"Descuento de {discount_amount_usd:.2f} USD del {config.discount_percent}% sobre {invoice.amount_total_usd:.2f}",
                    "is_discount_credit_note": True,
                    "invoice_line_ids": [(0, 0, {
                        "product_id": product.id,
                        "name": _("Descuento por pronto pago"),
                        "quantity": 1,
                        "price_unit": discount_amount,
                    })],
                }
                refund = self.env["account.move"].create(refund_vals)
                _logger.info("[PRONTO PAGO WIZARD] NC creada ID %s - Monto: %s - Aplicada contra Factura ID %s",
                            refund.id, discount_amount, invoice.id)

                # 🔹 RETORNAR EL MONTO DEL DESCUENTO EN USD (SIN tax_today para cálculos posteriores)
                applied_discount = discount_amount_usd
                _logger.info("[PRONTO PAGO WIZARD] Monto de descuento retornado: %s USD", applied_discount)

            else:
                _logger.info("[PRONTO PAGO WIZARD] Factura ID %s fuera de rango de días (%s > %s), no aplica descuento",
                            invoice.id, dias_transcurridos, config.early_payment_days)

        return applied_discount

    def _apply_negotiation_discount(self, payment, invoice, amount_base=None):
        """Aplica descuento por negociación sobre un monto base, si se da."""
        # 🔹 VALIDAR QUE LA FACTURA PERTENEZCA AL DIARIO "FACTURAS DE CLIENTES"
        invoice_journal_name = invoice.journal_id.name if invoice.journal_id else ""
        if invoice_journal_name != "FACTURAS DE CLIENTES":
            _logger.info("[PRONTO PAGO WIZARD] Factura ID %s NO pertenece al diario 'FACTURAS DE CLIENTES' (Diario: %s). No se aplicará descuento de negociación.", 
                        invoice.id, invoice_journal_name)
            return
        
        # 🔹 VALIDAR QUE EL CLIENTE NO ESTÉ EN LA LISTA DE EXCLUSIÓN
        partner_name = invoice.partner_id.name if invoice.partner_id else ""
        excluded_partners = [
            "ALIMENTOS DISPROCAR, C.A",
            "FUNDACION AMIGOS DEL NINO CON CANCER ZULIA (FUNDACION AMIGOS DEL NIÑO CON CANCER ZULIA)"
        ]
        if partner_name in excluded_partners:
            _logger.info("[PRONTO PAGO WIZARD] Factura ID %s pertenece al cliente excluido '%s'. No se aplicará descuento de negociación.", 
                        invoice.id, partner_name)
            return
        
        # 🔹 VERIFICAR SI EL PAGO CUBRE EL 100% DE LA FACTURA
        partials = self.env["account.partial.reconcile"].search([
            ("credit_move_id.move_id", "=", payment.move_id.id),
            ("debit_move_id.move_id", "=", invoice.id),
        ])
        applied_amount = sum(partial.amount for partial in partials)

        if abs(applied_amount - invoice.amount_total_usd) < 0.01:
            _logger.info("[PRONTO PAGO WIZARD] Pago cubre el 100%% de la factura ID %s, no se crea NC de negociación", invoice.id)
            return

        _logger.info("[PRONTO PAGO WIZARD] Evaluando descuento por negociación para Factura=%s", invoice.id)

        config = self.env["discount.config"].search([("discount_type", "=", "negotiation")], limit=1)
        if not config:
            _logger.info("[PRONTO PAGO WIZARD] No hay configuración encontrada para descuento por negociación")
            return

        journal_name = payment.journal_id.name if payment.journal_id else ""
        _logger.info("[PRONTO PAGO WIZARD] Nombre del diario: %s", journal_name)

        if journal_name not in ["CAJA CHICA", "CAJA CHICA 2"]:
            _logger.info("[PRONTO PAGO WIZARD] No aplica descuento por negociación (diario no es CAJA CHICA o CAJA CHICA 2)")
            return

        # 🔹 CORRECCIÓN: Calcular base_amount correctamente
        if amount_base is not None:
            # Si se proporciona amount_base, usarlo directamente (ya viene calculado)
            base_amount = amount_base
        else:
            base_amount = self._get_discount_base_amount_usd(invoice)

        # Re-evaluar NC no-descuento para decidir la base de cálculo
        credit_notes = self.env["account.move"].search([
            ("reversed_entry_id", "=", invoice.id),
            ("move_type", "=", "out_refund"),
            ("state", "!=", "cancel"),
        ])
        non_discount_nc = credit_notes.filtered(lambda nc: not nc.is_discount_credit_note)

        # Siempre calcular como porcentaje de la base
        discount_amount = base_amount * (config.discount_percent / 100.0)
        
        if non_discount_nc:
            _logger.info("[PRONTO PAGO WIZARD] Descuento negociación (con NC previa) aplicado: %s USD (%s%% de %s USD)",
                        discount_amount, config.discount_percent, base_amount)
        else:
            _logger.info("[PRONTO PAGO WIZARD] Creando NC por negociación. Factura=%s, Descuento=%.2f%%, Monto=%s, Base=%s",
                        invoice.id, config.discount_percent, discount_amount, base_amount)

        product = self.env["product.product"].search([("default_code", "=", "DESCUENTO_PN")], limit=1)
        if not product:
            _logger.error("[PRONTO PAGO WIZARD] Producto DESCUENTO_PN no encontrado, no se puede crear NC")
            return

        journal = self.env['account.journal'].search([
            ('name', '=', 'NOTAS DE CREDITO DE CLIENTE'),
            ('company_id', '=', invoice.company_id.id)
        ], limit=1)
        if not journal:
            raise UserError(_("No se encontró el diario 'NOTAS DE CREDITO DE CLIENTE' para la compañía de la factura."))

        move_vals = {
            "move_type": "out_refund",
            "journal_id": journal.id,
            "partner_id": invoice.partner_id.id,
            "tax_today": invoice.tax_today,
            "reversed_entry_id": invoice.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": product.id,
                "quantity": 1,
                "price_unit": discount_amount * invoice.tax_today,
                "name": _("Descuento por Negociación"),
            })],
            "x_studio_selection_field_Q69ft": "Ventas (ADMON)",
            "x_studio_motivo_de_devolucin": "Descuento por Negociación",
            "x_studio_motivo": f"Descuento de {discount_amount:.2f} ({config.discount_percent}%) sobre {base_amount:.2f}",
            "is_discount_credit_note": True,
        }

        credit_note = self.env["account.move"].create(move_vals)
        _logger.info("[PRONTO PAGO WIZARD] NC creada ID %s - Monto: %s - Aplicada contra Factura ID %s",
                    credit_note.id, discount_amount, invoice.id)

        # Mensaje en el chatter para auditar la creación de la NC de negociación
        try:
            credit_note.message_post(body=_(
                'Esta Nota de Crédito se generó a partir de la factura '
                '<a href="#" data-oe-model="account.move" data-oe-id="%s">%s</a>'
            ) % (invoice.id, invoice.name))
        except Exception:
            _logger.exception("[PRONTO PAGO WIZARD] Error posteando mensaje en chatter para NC ID %s", credit_note.id)
