
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, date
from io import BytesIO
import base64
import xlsxwriter

class CashClosureReportWizard(models.TransientModel):
    report_section_ids = fields.Many2many(
        'cash.closure.report.section',
        string='Secciones a mostrar',
        help='Seleccione las secciones que desea visualizar en el reporte.'
    )

    def _instrument_amount_from_move(self, move):
        """Return Instrumento de Pago for a move when is_cruce=True.

        Per requirement: use account.move.amount_total_div_rate.
        Fallback to previous USD-line sum if the field were unavailable.
        """
        if not move:
            return 0.0
        # Preferred value
        val = float(getattr(move, 'amount_total_div_rate', 0.0) or 0.0)
        if val:
            return val
        # Fallback for edge cases: sum USD lines
        MoveLine = self.env['account.move.line']
        debit_sum = 0.0
        credit_sum = 0.0
        if 'debit_usd' in MoveLine._fields:
            debit_sum = sum((l.debit_usd or 0.0) for l in move.line_ids)
        if not debit_sum and 'credit_usd' in MoveLine._fields:
            credit_sum = sum((l.credit_usd or 0.0) for l in move.line_ids)
        return debit_sum or credit_sum or 0.0

    def _is_customer_cross_payment(self, pay):
        """
        Determina si un pago corresponde a un cruce de cuentas según el nuevo flag.

        Criterio actualizado (Odoo 16):
        - El asiento contable del pago (pay.move_id) tiene el booleano 'is_cruce' en True.

        Nota: Se deja este helper para centralizar la condición, aunque la
        lógica principal ya consulta directamente pay.move_id.is_cruce
        donde impacta montos (para usar debit_usd).
        """

        move = getattr(pay, 'move_id', False)
        return bool(getattr(move, 'is_cruce', False))

    def _get_general_summary(self):
        """
        Calcula los totales y métricas para el resumen general de ingresos (ventas y caja).
        Devuelve un diccionario con todos los campos requeridos para el bloque de ventas y el bloque de caja.
        """
        Move = self.env['account.move']
        Payment = self.env['account.payment']
        # --- VENTAS ---
        domain = self._domain_base()
        moves = Move.search(domain)
        total_ventas = 0.0
        total_iva = 0.0
        total_oper = 0.0
        total_contado = 0.0
        total_credito = 0.0
        total_ventas_productos = 0.0
        total_ventas_servicios = 0.0
        total_ventas_exentas = 0.0
        total_devoluciones = 0.0
        num_facturas = 0
        num_devoluciones = 0

        for mv in moves:
            # Excluir del conteo de facturas aquellas cuyo número contenga "CXCF"
            is_cxcf = 'CXCF' in ((mv.name or '').upper())
            if mv.move_type == 'out_invoice':
                if not is_cxcf:
                    num_facturas += 1
                amount_total_usd = float(getattr(mv, 'amount_total_usd', 0.0) or 0.0)
                amount_tax_usd = float(getattr(mv, 'amount_tax_usd', 0.0) or 0.0)
                amount_untaxed_usd = float(getattr(mv, 'amount_untaxed_usd', 0.0) or 0.0)
                amount_exempt_usd = float(getattr(mv, 'amount_exempt_usd', 0.0) or 0.0)
                total_ventas += amount_total_usd
                total_iva += amount_tax_usd
                total_oper += amount_total_usd
                if mv.invoice_payment_term_id and mv.invoice_payment_term_id.name in ("Pago de Contado", "Contado"):
                    total_contado += amount_total_usd
                else:
                    total_credito += amount_total_usd

                # Repartir el total de la factura entre Productos (almacenables) y Servicios
                prod_subtotal_usd = 0.0
                serv_subtotal_usd = 0.0
                if hasattr(mv, 'invoice_line_ids'):
                    for line in mv.invoice_line_ids:
                        prod = getattr(line, 'product_id', False)
                        if not prod:
                            continue
                        # Subtotal en divisa de referencia por línea.
                        # Preferir price_subtotal_ref (solicitado) y hacer fallback seguro si no existe.
                        line_subtotal = getattr(line, 'price_subtotal_ref', None)
                        if line_subtotal is None:
                            # Fallback 1: price_subtotal_usd si existiera en alguna base
                            line_subtotal = getattr(line, 'price_subtotal_usd', None)
                        if line_subtotal is None:
                            # Fallback 2: convertir price_subtotal desde moneda de factura a referencia usando tasa
                            line_subtotal = float(getattr(line, 'price_subtotal', 0.0) or 0.0)
                            invoice_currency = getattr(mv, 'currency_id', False)
                            company_currency = getattr(mv, 'company_currency_id', False)
                            tasa = float(getattr(mv, 'tax_today', 0.0) or 0.0)
                            if invoice_currency and company_currency and invoice_currency != company_currency and tasa:
                                line_subtotal = line_subtotal / tasa
                        # Clasificación por detailed_type
                        detailed_type = getattr(prod, 'detailed_type', getattr(prod, 'type', ''))
                        if detailed_type == 'product':
                            prod_subtotal_usd += line_subtotal
                        elif detailed_type == 'service':
                            serv_subtotal_usd += line_subtotal

                # Asignar los impuestos de la factura proporcionalmente a cada grupo
                selected_base = prod_subtotal_usd + serv_subtotal_usd
                tax_for_prod = (amount_tax_usd * (prod_subtotal_usd / selected_base)) if selected_base else 0.0
                tax_for_serv = (amount_tax_usd * (serv_subtotal_usd / selected_base)) if selected_base else 0.0

                total_ventas_productos += (prod_subtotal_usd + tax_for_prod)
                total_ventas_servicios += (serv_subtotal_usd + tax_for_serv)

                # Exentas
                total_ventas_exentas += amount_exempt_usd
            elif mv.move_type == 'out_refund':
                num_devoluciones += 1
                amount_total_usd = getattr(mv, 'amount_total_usd', 0.0) or 0.0
                total_devoluciones += amount_total_usd

        # --- CAJA ---
        # Pagos por tipo
        domain_pay = [('state', '=', 'posted')]
        if self.start_date:
            domain_pay.append(('date', '>=', self.start_date))
        if self.end_date:
            domain_pay.append(('date', '<=', self.end_date))
        if self.partner_id:
            domain_pay.append(('partner_id', '=', self.partner_id.id))
        # Contar solo pagos de entrada de clientes si los campos existen en este Odoo
        if 'payment_type' in Payment._fields:
            domain_pay.append(('payment_type', '=', 'inbound'))
        if 'partner_type' in Payment._fields:
            domain_pay.append(('partner_type', '=', 'customer'))
        # Excluir pagos del diario "CUENTAS POR COBRAR FINANCIERAS"
        Journal = self.env['account.journal']
        excluded_journal_ids = Journal.search([('name', '=', 'CUENTAS POR COBRAR FINANCIERAS')]).ids
        if excluded_journal_ids:
            domain_pay.append(('journal_id', 'not in', excluded_journal_ids))
        # Solo considerar pagos relacionados a las facturas filtradas (pagadas/en pago y en rango)
        if moves:
            domain_pay.append(('reconciled_invoice_ids', 'in', moves.ids))
            payments = Payment.search(domain_pay)
        else:
            payments = Payment.browse([])

        ingresos_efectivo = 0.0
        ingresos_transferencia = 0.0
        ingresos_instrumento = 0.0
        ingresos_adelantos_aplicados = 0.0
        total_ingresos_efectivo = 0.0
        total_ingresos_transferencia = 0.0
        total_ingresos_instrumento = 0.0
        total_ingresos = 0.0
        adelantos_aplicados = 0.0
        notas_credito_aplicadas = 0.0

        for pay in payments:
            monto = getattr(pay, 'amount_ref', None)
            if monto is None:
                monto = pay.amount
            journal = pay.journal_id
            j_type = journal.type if journal else ''
            j_name = (journal.name or '').strip().upper() if journal else ''
            # Si el asiento relacionado al pago está marcado como Cruce,
            # usar amount_total_div_rate del asiento como Instrumento de Pago.
            if getattr(pay, 'move_id', False) and getattr(pay.move_id, 'is_cruce', False):
                # Si es un Cruce, usar el monto del asiento en divisa de referencia (Total / Tasa)
                aporte = float(getattr(pay.move_id, 'amount_total_div_rate', 0.0) or 0.0)
                ingresos_instrumento += aporte
                total_ingresos_instrumento += aporte
            else:
                # Ingresos por ventas EFECTIVO: cualquier diario de tipo 'cash'
                if j_type == 'cash':
                    ingresos_efectivo += monto
                    total_ingresos_efectivo += monto
                # Ingresos por ventas TRANSFERENCIA: diarios tipo 'bank'
                elif j_type == 'bank':
                    ingresos_transferencia += monto
                    total_ingresos_transferencia += monto
            if 'NOTAS DE CREDITO DE CLIENTE' in j_name:
                notas_credito_aplicadas += monto
            total_ingresos += monto

        adv_domain = [('state', '=', 'posted')]
        if self.start_date:
            adv_domain.append(('date', '>=', self.start_date))
        if self.end_date:
            adv_domain.append(('date', '<=', self.end_date))
        if self.partner_id:
            adv_domain.append(('partner_id', '=', self.partner_id.id))
        if 'payment_type' in Payment._fields:
            adv_domain.append(('payment_type', '=', 'inbound'))
        if 'partner_type' in Payment._fields:
            adv_domain.append(('partner_type', '=', 'customer'))
        if excluded_journal_ids:
            adv_domain.append(('journal_id', 'not in', excluded_journal_ids))
        adv_candidates = Payment.search(adv_domain)

        adv_total_usd = 0.0
        for ap in adv_candidates:
            # Solo pagos sin facturas asociadas (no reconciliados con ninguna factura)
            if not getattr(ap, 'reconciled_invoice_ids', False):
                amt_ccy_signed = float(getattr(ap, 'amount_company_currency_signed', 0.0) or 0.0)
                rate = float(getattr(ap, 'tax_today', 0.0) or 0.0)
                adv_total_usd += (amt_ccy_signed / rate) if rate else 0.0

        ingresos_adelantos_aplicados = adv_total_usd
        adelantos_aplicados = adv_total_usd

        try:
            _c_lines, _c_totals = self._get_cobros_summary()
            ingresos_efectivo = float(_c_totals.get('efectivo', 0.0) or 0.0)
            ingresos_transferencia = float(_c_totals.get('transferencia', 0.0) or 0.0)
            ingresos_instrumento = float(_c_totals.get('instru_pag', 0.0) or 0.0)
            # Mantener coherencia también en los totales por tipo
            total_ingresos_efectivo = ingresos_efectivo
            total_ingresos_transferencia = ingresos_transferencia
            total_ingresos_instrumento = ingresos_instrumento
        except Exception:
            # Si algo falla, conservar los acumulados calculados arriba
            pass
        # Asegurar que el TOTAL DE INGRESOS refleje solo los tipos incluidos (excluyendo el diario omitido)
        total_ingresos = (ingresos_efectivo or 0.0) + (ingresos_transferencia or 0.0) + (ingresos_instrumento or 0.0)

        try:
            _lines_cc, _totals_cc = self._compute_lines()
            total_contado = float(_totals_cc.get('contado', total_contado) or 0.0)
            total_credito = float(_totals_cc.get('credito', total_credito) or 0.0)
            # Alinear también Total VENTAS y Total OPERACION con el Total de Operación de Cierre de Caja
            cc_total_oper = float(_totals_cc.get('total_oper', total_oper) or 0.0)
            total_oper = cc_total_oper
            total_ventas = cc_total_oper
        except Exception:
            pass

        return {
            # Bloque RESUMEN DE VENTAS
            'total_ventas': total_ventas,
            'total_iva': total_iva,
            'total_oper': total_oper, 
            'total_contado': total_contado,
            'total_credito': total_credito,
            'total_ventas_productos': total_ventas_productos,
            'total_ventas_servicios': total_ventas_servicios,
            # Bloque RESUMEN DE CAJA
            'ingresos_efectivo': ingresos_efectivo,
            'ingresos_transferencia': ingresos_transferencia,
            'ingresos_instrumento': ingresos_instrumento,
            'ingresos_adelantos_aplicados': ingresos_adelantos_aplicados,
            'total_ingresos_efectivo': total_ingresos_efectivo,
            'total_ingresos_transferencia': total_ingresos_transferencia,
            'total_ingresos_instrumento': total_ingresos_instrumento,
            'total_ingresos': total_ingresos,
            'num_facturas': num_facturas,
            'num_devoluciones': num_devoluciones,
            'adelantos_aplicados': adelantos_aplicados,
            'notas_credito_aplicadas': notas_credito_aplicadas,
            'total_ventas_exentas': total_ventas_exentas,
            'total_devoluciones': total_devoluciones,
        }

    def _get_cobros_summary(self):
        Payment = self.env['account.payment']
        Partner = self.env['res.partner']
        Move = self.env['account.move']
        # Limitar a pagos relacionados con las facturas del dominio base (pagadas/en pago en el rango)
        inv_domain = self._domain_base()
        allowed_invoices = Move.search(inv_domain)
        # Si no hay facturas permitidas, devolvemos vacío
        if not allowed_invoices:
            return [], {'monto': 0.0, 'retencion': 0.0, 'total_ingreso': 0.0, 'efectivo': 0.0, 'transferencia': 0.0, 'instru_pag': 0.0}
        # Filtrar pagos por fecha y cliente si aplica
        domain = [('state', '=', 'posted')]
        # Filtrar por el rango de fechas seleccionado (inclusive) para alinear con el filtro del sistema
        if self.start_date:
            domain.append(('date', '>=', self.start_date))
        if self.end_date:
            domain.append(('date', '<=', self.end_date))
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        # Solo pagos entrantes de clientes si los campos existen
        Payment = self.env['account.payment']
        if 'payment_type' in Payment._fields:
            domain.append(('payment_type', '=', 'inbound'))
        if 'partner_type' in Payment._fields:
            domain.append(('partner_type', '=', 'customer'))
        # Y que estén conciliados con alguna de las facturas permitidas
        domain.append(('reconciled_invoice_ids', 'in', allowed_invoices.ids))
        # Excluir pagos del diario "CUENTAS POR COBRAR FINANCIERAS"
        Journal = self.env['account.journal']
        excluded_journal_ids = Journal.search([('name', '=', 'CUENTAS POR COBRAR FINANCIERAS')]).ids
        if excluded_journal_ids:
            domain.append(('journal_id', 'not in', excluded_journal_ids))
        payments = Payment.search(domain, order="date asc, name asc")

        lines = []
        total_monto = 0.0
        total_retencion = 0.0
        total_total_ingreso = 0.0
        total_efectivo = 0.0
        total_transferencia = 0.0
        total_instru_pag = 0.0

        for pay in payments:
            # Fecha
            fecha = pay.date
            # Cliente
            cliente = pay.partner_id.display_name if pay.partner_id else ''
            # Vendedor (equipo de ventas del cliente)
            vendedor = ''
            if pay.partner_id and pay.partner_id.team_id:
                vendedor = pay.partner_id.team_id.name
            # Referencia
            referencia = pay.ref or ''
            # Detalle
            detalle = pay.name or ''
            # Monto USD: amount_company_currency_signed / tax_today
            amt_ccy_signed = float(getattr(pay, 'amount_company_currency_signed', 0.0) or 0.0)
            rate = float(getattr(pay, 'tax_today', 0.0) or 0.0)
            monto = (amt_ccy_signed / rate) if rate else 0.0

            # Retención: si el diario es tipo general y nombre es uno de los dos
            retencion = 0.0
            if pay.journal_id and pay.journal_id.type == 'general':
                jname = (pay.journal_id.name or '').strip().upper()
                if jname in ['RETENCION DE ISLR CLIENTES', 'RETENCIÓN DE IMPUESTOS MUNICIPALES CLIENTES']:
                    retencion = monto

            # Total ingreso
            total_ingreso = monto - retencion

            # Efectivo / Transferencia / Instrumento de pago
            efectivo = 0.0
            transferencia = 0.0
            instru_pag = 0.0
            if getattr(getattr(pay, 'move_id', False), 'is_cruce', False):
                # Cuando el pago es Cruce, mostrar el total USD del asiento
                instru_pag = self._instrument_amount_from_move(pay.move_id)
            else:
                # Efectivo: diario tipo cash y nombre contiene CAJA CHICA
                if pay.journal_id and pay.journal_id.type == 'cash' and 'CAJA CHICA' in (pay.journal_id.name or '').upper():
                    efectivo = monto
                # Transferencia: diario tipo bank
                if pay.journal_id and pay.journal_id.type == 'bank':
                    transferencia = monto
                # Instrumento de pago: cruces por flag en diario
                if self._is_customer_cross_payment(pay):
                    instru_pag = monto

            lines.append({
                'fecha': fecha,
                'vendedor': vendedor,
                'cliente': cliente,
                'referencia': referencia,
                'detalle': detalle,
                'monto': monto,
                'retencion': retencion,
                'total_ingreso': total_ingreso,
                'efectivo': efectivo,
                'transferencia': transferencia,
                'instru_pag': instru_pag,
            })

            total_monto += monto
            total_retencion += retencion
            total_total_ingreso += total_ingreso
            total_efectivo += efectivo
            total_transferencia += transferencia
            total_instru_pag += instru_pag

        totals = {
            'monto': total_monto,
            'retencion': total_retencion,
            'total_ingreso': total_total_ingreso,
            'efectivo': total_efectivo,
            'transferencia': total_transferencia,
            'instru_pag': total_instru_pag,
        }
        return lines, totals
    _name = "cash.closure.report.wizard"
    _description = "Reporte de Cierre de Caja (PDF/XLSX)"

    start_date = fields.Date(string="Fecha inicio", required=True, default=fields.Date.context_today)
    end_date = fields.Date(string="Fecha fin", required=True, default=fields.Date.context_today)
    partner_id = fields.Many2one('res.partner', string="Cliente")
    user_id = fields.Many2one('res.users', string="Comercial")
    team_id = fields.Many2one('crm.team', string="Equipo de ventas")

    file_data = fields.Binary(string="Archivo", readonly=True)
    file_name = fields.Char(string="Nombre de archivo", readonly=True)

    def _domain_base(self):
        self.ensure_one()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise UserError(_("La fecha fin no puede ser menor a la fecha inicio."))

        domain = [
            # Dominio base para consultas generales (Resumen de ingresos, etc.)
            # Incluir facturas y devoluciones publicadas
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
        ]
        # Solicitud: mostrar solo facturas pagadas o en proceso de pago dentro del rango.
        # Si el campo existe (Odoo 14+), filtramos por payment_state en ('paid', 'in_payment').
        Move = self.env['account.move']
        if 'payment_state' in Move._fields:
            domain.append(('payment_state', 'in', ['paid', 'in_payment']))
        if self.start_date:
            domain.append(('invoice_date', '>=', self.start_date))
        if self.end_date:
            domain.append(('invoice_date', '<=', self.end_date))
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.user_id:
            domain.append(('invoice_user_id', '=', self.user_id.id))
        if self.team_id:
            # account.move usually has 'team_id' for sales team
            domain.append(('team_id', '=', self.team_id.id))
        return domain

    def _compute_lines(self):
        """Build the report lines from account.move, applying filters."""
        Move = self.env['account.move']
        # Filtrar por la fecha contable ('date') del asiento de la factura para alinear con el sistema
        # y EXCLUIR facturas rectificativas (notas de crédito) del Cierre de Caja
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ]
        if 'payment_state' in Move._fields:
            domain.append(('payment_state', 'in', ['paid', 'in_payment']))
        # Excluir facturas cuyo número contenga 'CXCF' del Cierre de Caja
        domain.append(('name', 'not ilike', 'CXCF'))
        if self.start_date:
            domain.append(('date', '>=', self.start_date))
        if self.end_date:
            domain.append(('date', '<=', self.end_date))
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.user_id:
            domain.append(('invoice_user_id', '=', self.user_id.id))
        if self.team_id:
            domain.append(('team_id', '=', self.team_id.id))

        moves = Move.search(domain, order="date asc, name asc")

        # Precomputar pagos asociados a las facturas (más confiable que payment_ids en algunos casos)
        payments_by_invoice = {}
        allocations_by_payment_usd = {}
        if moves:
            Payment = self.env['account.payment']
            all_payments = Payment.search([
                ('reconciled_invoice_ids', 'in', moves.ids),
                ('state', '=', 'posted')
            ])
            # Helper: monto aplicado (moneda compañía) desde un pago a una factura a través de conciliaciones parciales
            def _applied_company_amount(paym, inv):
                move = getattr(paym, 'move_id', None)
                if not move:
                    return 0.0
                applied = 0.0
                inv_line_ids = set(inv.line_ids.ids)
                for pl in move.line_ids:
                    # Partial reconciliations on this line
                    partials = pl.matched_debit_ids | pl.matched_credit_ids
                    for pr in partials:
                        # If either side of the partial reconcile belongs to the invoice, count it
                        if pr.debit_move_id.id in inv_line_ids or pr.credit_move_id.id in inv_line_ids:
                            applied += pr.amount
                return applied

            # Construir mapping factura->pagos y precomputar asignaciones por pago en USD
            for pay in all_payments:
                # Mapear pagos por factura filtrando al dominio actual
                for inv in pay.reconciled_invoice_ids:
                    if inv.id in moves.ids:
                        payments_by_invoice.setdefault(inv.id, []).append(pay)

                # Precomputar asignación en moneda compañía por cada factura relacionada con el pago
                alloc_ccy_by_inv = {}
                total_alloc_ccy = 0.0
                for inv in pay.reconciled_invoice_ids:
                    amt_ccy = _applied_company_amount(pay, inv)
                    if amt_ccy:
                        alloc_ccy_by_inv[inv.id] = alloc_ccy_by_inv.get(inv.id, 0.0) + amt_ccy
                        total_alloc_ccy += amt_ccy

                # Convertir a USD en proporción del monto USD del pago (amount_ref si existe)
                pay_amt_usd = getattr(pay, 'amount_ref', None)
                if pay_amt_usd is None:
                    pay_amt_usd = pay.amount

                alloc_usd_map = {}
                if total_alloc_ccy > 0:
                    for inv_id, cc in alloc_ccy_by_inv.items():
                        alloc_usd_map[inv_id] = pay_amt_usd * (cc / total_alloc_ccy)
                else:
                    # Fallback: si no se detectaron conciliaciones parciales (caso raro),
                    # distribuir por total compañía de las facturas relacionadas; si solo hay una, asignar todo.
                    linked_invs = pay.reconciled_invoice_ids
                    if len(linked_invs) == 1:
                        alloc_usd_map[linked_invs[0].id] = pay_amt_usd
                    else:
                        total_signed = sum(abs(getattr(inv, 'amount_total_signed', 0.0) or 0.0) for inv in linked_invs)
                        for inv in linked_invs:
                            base = abs(getattr(inv, 'amount_total_signed', 0.0) or 0.0)
                            alloc_usd_map[inv.id] = pay_amt_usd * (base / total_signed) if total_signed else 0.0

                allocations_by_payment_usd[pay.id] = alloc_usd_map

        lines = []
        total_total_oper = 0.0
        total_contado = 0.0
        total_credito = 0.0
        total_impuesto = 0.0

        total_efectivo = 0.0
        total_transferencia = 0.0
        total_instru_pag = 0.0
        for mv in moves:
            # Fecha-Hora: usar la fecha contable ('date') para coherencia con el filtro
            fecha_hora = mv.date

            numero = mv.name or ''

            # RIF + Cliente en una misma columna
            rif_val = ''
            if 'rif' in mv._fields:
                rif_val = (mv.rif or '') or ''
            if not rif_val and mv.partner_id:
                rif_val = mv.partner_id.vat or ''
            cliente = (rif_val + ' - ' if rif_val else '') + (mv.partner_id.display_name if mv.partner_id else '')

            # Totales en USD (campos personalizados)
            amount_total_usd = getattr(mv, 'amount_total_usd', 0.0) or 0.0
            total_oper = amount_total_usd
            impuesto = getattr(mv, 'amount_tax_usd', 0.0) or 0.0

            # Reglas Contado vs Crédito
            # 1) Contado solo si: término de pago es Contado, la factura está totalmente pagada,
            #    y TODOS los pagos asociados (posted, inbound si aplica) se realizaron en la misma fecha de emisión.
            # 2) Si el pago se hizo en fecha distinta a la emisión, va a Crédito.
            # 3) En cualquier otro caso (sin pagos, pagos parciales, término distinto), va a Crédito.

            # Determinar pagos relacionados (ya se arma más abajo pero aquí lo necesitamos para fechas)
            contado = 0.0
            credito = 0.0
            term_name = (mv.invoice_payment_term_id.name or '').strip() if mv.invoice_payment_term_id else ''
            is_term_contado = term_name in ("Pago de Contado", "Contado")
            # Estado de pago (Odoo 16)
            is_paid = False
            if 'payment_state' in mv._fields:
                is_paid = (mv.payment_state == 'paid')
            else:
                # Fallback si no existe payment_state
                residual = getattr(mv, 'amount_residual', None)
                is_paid = (residual is not None and abs(residual) < 1e-6)

            # Tomar pagos relacionados (se calculan luego, pero podemos recalcular aquí de forma segura)
            related_payments_for_terms = payments_by_invoice.get(mv.id)
            if related_payments_for_terms is None and hasattr(mv, 'payment_ids') and mv.payment_ids:
                related_payments_for_terms = mv.payment_ids.filtered(lambda p: p.state == 'posted')
            # Normalizar a recordset si vino como lista del mapeo precomputado
            if isinstance(related_payments_for_terms, list):
                related_payments_for_terms = self.env['account.payment'].browse([p.id for p in related_payments_for_terms])
            # Filtrar a inbound si aplica
            if related_payments_for_terms and 'payment_type' in self.env['account.payment']._fields:
                related_payments_for_terms = related_payments_for_terms.filtered(lambda p: p.payment_type == 'inbound')
            # Fechas de pago
            pay_dates = set()
            for p in (related_payments_for_terms or []):
                if p.date:
                    pay_dates.add(p.date)

            # Verificar condición de contado
            if is_term_contado and is_paid and pay_dates and all(d == mv.invoice_date for d in pay_dates):
                contado = amount_total_usd
            else:
                credito = total_oper

            # Nueva columna: Efectivo / Transferencia / Instrumento de pago
            efectivo = 0.0
            transferencia = 0.0
            instru_pag = 0.0

            # Si la factura/asiento está marcado como Cruce, forzar Instrumento de pago
            # a la suma de los débitos en USD de sus líneas contables.
            if getattr(mv, 'is_cruce', False):
                instru_pag = self._instrument_amount_from_move(mv)
            else:
                # Pagos relacionados: usar el mapeo precomputado (si no, fallback a payment_ids)
                related_payments = payments_by_invoice.get(mv.id)
                if related_payments is None and hasattr(mv, 'payment_ids') and mv.payment_ids:
                    # Fallback (caso de que reconciled_invoice_ids todavía no se haya actualizado)
                    related_payments = mv.payment_ids.filtered(lambda p: p.state == 'posted')
                for pay in (related_payments or []):
                    journal = pay.journal_id
                    if not journal:
                        continue
                    # Excluir pagos del diario "CUENTAS POR COBRAR FINANCIERAS"
                    if (journal.name or '').strip().upper() == 'CUENTAS POR COBRAR FINANCIERAS':
                        continue

                    # Si el asiento del pago está marcado como Cruce, tomar el total debit_usd como Instrumento.
                    if getattr(getattr(pay, 'move_id', False), 'is_cruce', False):
                        instru_pag += self._instrument_amount_from_move(pay.move_id)
                        continue

                    # Monto en USD preferido
                    pay_amt = getattr(pay, 'amount_ref', None)
                    if pay_amt is None:
                        pay_amt = pay.amount

                    j_type = journal.type
                    j_name = (journal.name or '').strip().upper()

                    # Efectivo: cualquier diario tipo 'cash'
                    if j_type == 'cash':
                        efectivo += pay_amt
                    # Transferencia: diarios tipo 'bank'
                    elif j_type == 'bank':
                        # Usar asignación proporcional del pago a esta factura
                        alloc_map = allocations_by_payment_usd.get(pay.id) or {}
                        transferencia += alloc_map.get(mv.id, 0.0)
                    # Instrucción de pago: SOLO cruces de cuentas entre clientes en diarios misceláneos
                    elif self._is_customer_cross_payment(pay):
                        # self._is_customer_cross_payment ya comprueba 
                        # 'pay.journal_id.x_studio_es_cruce'
                        instru_pag += pay_amt
            lines.append({
                'fecha_hora': fecha_hora,
                'numero': numero,
                'cliente': cliente,
                'total_oper': total_oper,
                'contado': contado,
                'credito': credito,
                'impuesto': impuesto,
                'efectivo': efectivo,
                'transferencia': transferencia,
                'instru_pag': instru_pag,
            })

            total_total_oper += total_oper
            total_contado += contado
            total_credito += credito
            total_impuesto += impuesto
            total_efectivo += efectivo

            total_transferencia += transferencia
            total_instru_pag += instru_pag
        totals = {
            'total_oper': total_total_oper,
            'contado': total_contado,
            'credito': total_credito,
            'impuesto': total_impuesto,
            'efectivo': total_efectivo,
            'transferencia': total_transferencia,
            'instru_pag': total_instru_pag,
        }
        return lines, totals

    def action_print_pdf(self):
        """Render QWeb PDF report."""
        self.ensure_one()
        return self.env.ref('account_cash_closure_report.report_cash_closure_pdf').report_action(self)

    def action_export_xlsx(self):
        self.ensure_one()
        lines, totals = self._compute_lines()
        cobros_lines, cobros_totals = self._get_cobros_summary()
        general_summary = self._get_general_summary()

        # Obtener los códigos de las secciones seleccionadas
        selected_section_codes = set(self.report_section_ids.mapped('code')) if self.report_section_ids else set()

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Formatos
        title_fmt = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'left'})
        hdr_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1})
        txt_fmt = workbook.add_format({'border': 1})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        date_fmt = workbook.add_format({'num_format': 'yyyy-mm-dd', 'border': 1})
        total_fmt = workbook.add_format({'bold': True, 'top':1, 'num_format': '#,##0.00', 'border':1})

        # RESUMEN DE INGRESOS
        if 'ingresos' in selected_section_codes or not selected_section_codes:
            sheet0 = workbook.add_worksheet('RESUMEN DE INGRESOS')
            row0 = 0
            company = self.env.company
            title = "RESUMEN DE INGRESOS - %s" % (company.name)
            sheet0.write(row0, 0, title, title_fmt); row0 += 1
            period = "Periodo: %s a %s" % (self.start_date or '', self.end_date or '')
            sheet0.write(row0, 0, period); row0 += 2
            sheet0.set_column(0, 0, 38)
            sheet0.set_column(1, 1, 18)
            # --- Bloque RESUMEN DE VENTAS ---
            sheet0.write(row0, 0, "RESUMEN DE VENTAS", hdr_fmt); row0 += 1
            sheet0.write(row0, 0, "Total VENTAS"); sheet0.write_number(row0, 1, general_summary['total_ventas'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "Total I.V.A."); sheet0.write_number(row0, 1, general_summary['total_iva'], money_fmt); row0 += 1
            row0 += 1
            sheet0.write(row0, 0, "Total OPERACION"); sheet0.write_number(row0, 1, general_summary['total_oper'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "Total ventas a CONTADO"); sheet0.write_number(row0, 1, general_summary['total_contado'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "Total ventas a CREDITO"); sheet0.write_number(row0, 1, general_summary['total_credito'], money_fmt); row0 += 1
            row0 += 1
            # Mostrar solo el monto de productos ALMACENABLES (storable): usar total_ventas_productos
            sheet0.write(row0, 0, "Total ventas Productos"); sheet0.write_number(row0, 1, general_summary['total_ventas_productos'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "Total ventas Servicios"); sheet0.write_number(row0, 1, general_summary['total_ventas_servicios'], money_fmt); row0 += 2
            # --- Bloque RESUMEN DE CAJA ---
            sheet0.write(row0, 0, "RESUMEN DE CAJA", hdr_fmt); row0 += 1
            sheet0.write(row0, 0, "Ingresos por ventas EFECTIVO"); sheet0.write_number(row0, 1, general_summary['ingresos_efectivo'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "Ingresos por ventas TRANSFERENCIA"); sheet0.write_number(row0, 1, general_summary['ingresos_transferencia'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "Ingresos por ventas INSTRUMENTO DE PAGO"); sheet0.write_number(row0, 1, general_summary['ingresos_instrumento'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "Ingresos por ventas ADELANTOS APLICADOS"); sheet0.write_number(row0, 1, general_summary['ingresos_adelantos_aplicados'], money_fmt); row0 += 1
            row0 += 1
            sheet0.write(row0, 0, "Total de Ingresos en EFECTIVO"); sheet0.write_number(row0, 1, general_summary['total_ingresos_efectivo'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "Total de Ingresos en TRANSFERENCIA"); sheet0.write_number(row0, 1, general_summary['total_ingresos_transferencia'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "Total de Ingresos en INSTRUMENTO DE PAGO"); sheet0.write_number(row0, 1, general_summary['total_ingresos_instrumento'], money_fmt); row0 += 1
            row0 += 1
            sheet0.write(row0, 0, "Total de INGRESOS"); sheet0.write_number(row0, 1, general_summary['total_ingresos'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "Número de facturas"); sheet0.write_number(row0, 1, general_summary['num_facturas'], txt_fmt); row0 += 1
            sheet0.write(row0, 0, "Número de devoluciones"); sheet0.write_number(row0, 1, general_summary['num_devoluciones'], txt_fmt); row0 += 1
            sheet0.write(row0, 0, "ADELANTOS APLICADOS"); sheet0.write_number(row0, 1, general_summary['adelantos_aplicados'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "NOTAS DE CRÉDITO APLICADAS"); sheet0.write_number(row0, 1, general_summary['notas_credito_aplicadas'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "TOTAL VENTAS EXENTAS"); sheet0.write_number(row0, 1, general_summary['total_ventas_exentas'], money_fmt); row0 += 1
            sheet0.write(row0, 0, "TOTAL DEVOLUCIONES"); sheet0.write_number(row0, 1, general_summary['total_devoluciones'], money_fmt); row0 += 2

        # CIERRE DE CAJA
        if 'caja' in selected_section_codes or not selected_section_codes:
            sheet = workbook.add_worksheet('Cierre de Caja')
            row = 0
            company = self.env.company
            title = "Cierre de Caja - %s" % (company.name)
            sheet.write(row, 0, title, title_fmt); row += 1
            period = "Periodo: %s a %s" % (self.start_date or '', self.end_date or '')
            sheet.write(row, 0, period); row += 1
            filters = []
            if self.partner_id: filters.append("Cliente: %s" % self.partner_id.display_name)
            if self.user_id: filters.append("Comercial: %s" % self.user_id.name)
            if self.team_id: filters.append("Equipo: %s" % self.team_id.name)
            sheet.write(row, 0, "Filtros: " + ("; ".join(filters) if filters else "Ninguno")); row += 2
            headers = ["Fecha-Hora", "N° Factura", "Cliente", "Total de Operación", "Contado", "Crédito", "Impuesto", "Efectivo", "Transferencia", "Instru. de pag."]
            for col, h in enumerate(headers):
                sheet.write(row, col, h, hdr_fmt)
            row += 1
            sheet.set_column(0, 0, 14)
            sheet.set_column(1, 1, 18)
            sheet.set_column(2, 2, 40)
            sheet.set_column(3, 9, 18)
            start_data_row = row
            for l in lines:
                if l['fecha_hora']:
                    sheet.write_datetime(row, 0, datetime.combine(l['fecha_hora'], datetime.min.time()), date_fmt)
                else:
                    sheet.write(row, 0, '', txt_fmt)
                sheet.write(row, 1, l['numero'], txt_fmt)
                sheet.write(row, 2, l['cliente'], txt_fmt)
                sheet.write_number(row, 3, l['total_oper'], money_fmt)
                sheet.write_number(row, 4, l['contado'], money_fmt)
                sheet.write_number(row, 5, l['credito'], money_fmt)
                sheet.write_number(row, 6, l['impuesto'], money_fmt)
                sheet.write_number(row, 7, l['efectivo'], money_fmt)
                sheet.write_number(row, 8, l['transferencia'], money_fmt)
                sheet.write_number(row, 9, l['instru_pag'], money_fmt)
                row += 1
            sheet.write(row, 0, "Totales", hdr_fmt)
            sheet.write(row, 1, "", hdr_fmt)
            sheet.write(row, 2, "", hdr_fmt)
            if row > start_data_row:
                sheet.write_formula(row, 3, f"=SUM(D{start_data_row+1}:D{row})", total_fmt)
                sheet.write_formula(row, 4, f"=SUM(E{start_data_row+1}:E{row})", total_fmt)
                sheet.write_formula(row, 5, f"=SUM(F{start_data_row+1}:F{row})", total_fmt)
                sheet.write_formula(row, 6, f"=SUM(G{start_data_row+1}:G{row})", total_fmt)
                sheet.write_formula(row, 7, f"=SUM(H{start_data_row+1}:H{row})", total_fmt)
                sheet.write_formula(row, 8, f"=SUM(I{start_data_row+1}:I{row})", total_fmt)
                sheet.write_formula(row, 9, f"=SUM(J{start_data_row+1}:J{row})", total_fmt)
            else:
                sheet.write_number(row, 3, 0.0, total_fmt)
                sheet.write_number(row, 4, 0.0, total_fmt)
                sheet.write_number(row, 5, 0.0, total_fmt)
                sheet.write_number(row, 6, 0.0, total_fmt)
                sheet.write_number(row, 7, 0.0, total_fmt)
                sheet.write_number(row, 8, 0.0, total_fmt)
                sheet.write_number(row, 9, 0.0, total_fmt)

        # RESUMEN DE COBROS
        if 'cobros' in selected_section_codes or not selected_section_codes:
            sheet2 = workbook.add_worksheet('Resumen de cobros')
            row2 = 0
            sheet2.write(row2, 0, "Resumen de cobros", title_fmt); row2 += 1
            period2 = "Periodo: %s a %s" % (self.start_date or '', self.end_date or '')
            sheet2.write(row2, 0, period2); row2 += 1
            filters2 = []
            if self.partner_id: filters2.append("Cliente: %s" % self.partner_id.display_name)
            if self.user_id: filters2.append("Comercial: %s" % self.user_id.name)
            if self.team_id: filters2.append("Equipo: %s" % self.team_id.name)
            sheet2.write(row2, 0, "Filtros: " + ("; ".join(filters2) if filters2 else "Ninguno")); row2 += 2
            headers2 = ["Fecha", "Vendedor", "Cliente", "Referencia", "Detalle", "Monto", "Retención", "Total ingreso", "Efectivo", "Transferencia", "Instrumento de pago"]
            for col, h in enumerate(headers2):
                sheet2.write(row2, col, h, hdr_fmt)
            row2 += 1
            sheet2.set_column(0, 0, 14)
            sheet2.set_column(1, 1, 20)
            sheet2.set_column(2, 2, 40)
            sheet2.set_column(3, 4, 18)
            sheet2.set_column(5, 10, 16)
            start_data_row2 = row2
            for l in cobros_lines:
                if l['fecha']:
                    sheet2.write_datetime(row2, 0, datetime.combine(l['fecha'], datetime.min.time()), date_fmt)
                else:
                    sheet2.write(row2, 0, '', txt_fmt)
                sheet2.write(row2, 1, l['vendedor'], txt_fmt)
                sheet2.write(row2, 2, l['cliente'], txt_fmt)
                sheet2.write(row2, 3, l['referencia'], txt_fmt)
                sheet2.write(row2, 4, l['detalle'], txt_fmt)
                sheet2.write_number(row2, 5, l['monto'], money_fmt)
                sheet2.write_number(row2, 6, l['retencion'], money_fmt)
                sheet2.write_number(row2, 7, l['total_ingreso'], money_fmt)
                sheet2.write_number(row2, 8, l['efectivo'], money_fmt)
                sheet2.write_number(row2, 9, l['transferencia'], money_fmt)
                sheet2.write_number(row2, 10, l['instru_pag'], money_fmt)
                row2 += 1
            sheet2.write(row2, 0, "Totales", hdr_fmt)
            for i in range(1, 5):
                sheet2.write(row2, i, '', hdr_fmt)
            if row2 > start_data_row2:
                sheet2.write_formula(row2, 5, f"=SUM(F{start_data_row2+1}:F{row2})", total_fmt)
                sheet2.write_formula(row2, 6, f"=SUM(G{start_data_row2+1}:G{row2})", total_fmt)
                sheet2.write_formula(row2, 7, f"=SUM(H{start_data_row2+1}:H{row2})", total_fmt)
                sheet2.write_formula(row2, 8, f"=SUM(I{start_data_row2+1}:I{row2})", total_fmt)
                sheet2.write_formula(row2, 9, f"=SUM(J{start_data_row2+1}:J{row2})", total_fmt)
                sheet2.write_formula(row2, 10, f"=SUM(K{start_data_row2+1}:K{row2})", total_fmt)
            else:
                for i in range(5, 11):
                    sheet2.write_number(row2, i, 0.0, total_fmt)

        workbook.close()
        output.seek(0)
        file_content = output.getvalue()
        filename = "cierre_caja_%s_a_%s.xlsx" % (self.start_date or '', self.end_date or '')
        self.file_name = filename
        self.file_data = base64.b64encode(file_content)

        url = '/web/content/?model=%s&id=%s&field=file_data&filename_field=file_name&download=true' % (self._name, self.id)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }
