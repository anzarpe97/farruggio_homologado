from odoo import models, api, _, fields
from odoo.exceptions import UserError
from odoo.tools import float_compare
import logging
import unicodedata

_logger = logging.getLogger(__name__)

# Motivos que NO deben afectar cantidades facturadas (insensible a mayúsculas)
NO_INVENTORY_MOTIVOS = {'faltante', 'sobrante', 'error en precio'}

def _is_no_inventory_motivo(raw):
    """Normalizar y comprobar si el texto contiene alguno de los motivos no logísticos."""
    if not raw:
        return False
    # normalizar unicode, remover acentos, trim y bajar a minúsculas
    txt = unicodedata.normalize('NFKD', str(raw)).encode('ASCII', 'ignore').decode('utf-8').strip().lower()
    for m in NO_INVENTORY_MOTIVOS:
        if m in txt:
            return True
    return False

class AccountMove(models.Model):
    _inherit = 'account.move'

    is_discount_credit_note = fields.Boolean(
        string="Nota de crédito por descuento",
        default=False,
        help="Indica si esta nota de crédito fue generada automáticamente como descuento (Pronto Pago o Negociación)."
    )


    def action_add_credit_note(self):
        self.ensure_one()

        # Solo mostrar advertencia si no viene del wizard
        if not self.env.context.get('skip_motivo_check'):
            credit_notes = self.env['account.move'].search([
                ('reversed_entry_id', '=', self.id),
                ('move_type', 'in', ['out_refund', 'in_refund']),
                ('state', '!=', 'cancel'),
            ])
            motivos = ', '.join(filter(None, credit_notes.mapped('x_studio_motivo_de_devolucin')))
            # Construir lista de NC asociadas y motivos
            credit_notes_info = []
            for nc in credit_notes:
                motivo = nc.x_studio_motivo_de_devolucin or ''
                if nc.state == 'draft':
                    nc_label = "PENDIENTE POR APROBACIÓN"
                else:
                    nc_label = nc.name
                credit_notes_info.append(f"{nc_label}: {motivo}")
            credit_notes_str = '\n'.join(credit_notes_info)
            if motivos:
                return {
                    'name': _('Advertencia de Motivos de NC'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'credit.note.motivo.confirm',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_motivo_list': motivos,
                        'default_move_id': self.id,
                        'default_credit_notes': credit_notes_str,  # <-- aquí pasas la lista
                    }
                }

        if self.state != 'posted':
            raise UserError("Solo se pueden crear notas de crédito desde facturas publicadas")

        _logger.info("🧾 Generando nota de crédito desde factura %s", self.name)

        is_customer_invoice = self.move_type == 'out_invoice'
        is_vendor_invoice = self.move_type == 'in_invoice'

        if not (is_customer_invoice or is_vendor_invoice):
            raise UserError("Este tipo de documento no permite crear notas de crédito.")

        # Determinar tipo de nota de crédito y diario
        move_type_refund = 'out_refund' if is_customer_invoice else 'in_refund'
        journal_type = 'sale' if is_customer_invoice else 'purchase'
        journal_code_filter = 'NC' if is_customer_invoice else 'NCPRO'
        journal_name_filter = 'NOTAS DE CRÉDITO DE CLIENTE' if is_customer_invoice else 'NOTAS DE CRÉDITO DE PROVEEDOR'

        credit_note_journal = self.env['account.journal'].search([
            ('type', '=', journal_type),
            '|',
            ('code', 'ilike', journal_code_filter),
            ('name', 'ilike', journal_name_filter),
        ], limit=1)

        if not credit_note_journal:
            credit_note_journal = self.journal_id  # fallback al diario original

        today = fields.Date.context_today(self)
        tasa_original = self.tax_today

        # PRuebas

        _logger.info("📆 Fecha asignada a la nota de crédito: %s", today)
        _logger.info("💱 Tasa (tax_today) de la factura original: %s", tasa_original)

        # Crear valores base
        credit_note_vals = {
            'move_type': move_type_refund,
            'partner_id': self.partner_id.id,
            'invoice_user_id': self.invoice_user_id.id,
            'reversed_entry_id': self.id,
            'journal_id': credit_note_journal.id,
            'currency_id': self.currency_id.id,
            'date': today,
            'invoice_line_ids': [],
            'tax_today': tasa_original,
        }

        # Construir líneas copiadas
        lines = []
        for line in self.invoice_line_ids:
            lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'account_id': line.account_id.id,
                # Vincular la línea de la NC con las líneas de pedido de venta originales
                # para que las cantidades facturadas en el pedido se reduzcan correctamente.
                'sale_line_ids': [(6, 0, line.sale_line_ids.ids)],
            }))
        credit_note_vals['invoice_line_ids'] = lines

        # Crear nota de crédito con contexto para evitar recalcular tasa
        credit_note = self.env['account.move'].with_context(
            skip_tax_today_update=True,
            credit_note_from_invoice=True,
            credit_note_tax_today=tasa_original,
            credit_note_date=today,
        ).create(credit_note_vals)

        # Forzar escritura de tasa y fecha sin disparar recálculo
        credit_note.with_context(skip_tax_today_update=True).write({
            'tax_today': tasa_original,
            'date': today,
        })

        _logger.info("✅ Tasa y fecha escritas en la nota de crédito (post-write): tax_today=%s, date=%s", credit_note.tax_today, credit_note.date)

        # Mensaje en el chatter
        credit_note.message_post(body=_(
            'Esta Nota de Crédito se generó a partir de la factura '
            '<a href="#" data-oe-model="account.move" data-oe-id="%s">%s</a>'
        ) % (self.id, self.name))

        return {
            'name': "Nota de Crédito creada",
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': credit_note.id,
            'target': 'current',
        }


    def action_post(self):
        _logger.info("action_post llamado para %s, contexto: %s", self.ids, self.env.context)
        for move in self:
            if self.env.context.get('skip_tax_today_update'):
                _logger.info("skip_tax_today_update detectado, no cambio tasa para move %s", move.id)
                continue

            if move.move_type in ('out_refund', 'in_refund'):
                _logger.info("No cambio tasa en nota de crédito %s", move.id)
                continue

            if not move.tax_today or move.tax_today == 1.0:
                fecha = move.invoice_date or move.date or fields.Date.context_today(self)
                move.tax_today = self._get_tasa_usd_by_date(fecha)
                _logger.info("Tasa actualizada a %s para move %s", move.tax_today, move.id)

        return super().action_post()


    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if self.env.context.get('credit_note_from_invoice'):
            if 'tax_today' in self._fields:
                defaults['tax_today'] = self.env.context.get('credit_note_tax_today')
            if 'date' in self._fields:
                defaults['date'] = self.env.context.get('credit_note_date')
        return defaults

    @api.model
    def cron_fix_credit_note_0027377(self):
        """
        Cron para corregir notas de crédito: procesa todas las notas de crédito y copia
        sale_line_ids desde la factura original cuando corresponde.

        Reglas adicionales:
        - Omitir NC cuyo campo x_studio_motivo_de_devolucin sea "Error en Precio".
        - Detectar corrección de precio (mismos productos y cantidades, pero distinto precio)
          y omitir (no debe tratarse como devolución de unidades).
        - Si las monedas difieren entre factura y NC y son VEF/USD, convertir el price_unit
          del documento en USD multiplicándolo por su tax_today y comparar en VEF.
        """
        _logger.info("Cron: inicio de corrección masiva de notas de crédito")

        credit_notes = self.env['account.move'].sudo().search([
            ('move_type', 'in', ('out_refund', 'in_refund')),
            ('state', '!=', 'cancel'),
            ('reversed_entry_id', '!=', False),
        ])
        if not credit_notes:
            _logger.info("Cron: no hay notas de crédito candidatas")
            return True

        def _norm_price_for_vef(price, move):
            """Convierte price_unit a VEF si move está en USD usando move.tax_today.
               Si no aplica, devuelve price tal cual (float)."""
            try:
                cur = (move.currency_id.name or '').strip().upper()
            except Exception:
                cur = ''
            tax = float(getattr(move, 'tax_today', 1.0) or 1.0)
            price_f = float(price or 0.0)
            if cur == 'USD':
                return price_f * (tax or 1.0)
            return price_f

        updated_lines = 0
        for cn in credit_notes:
            orig = cn.reversed_entry_id
            if not orig:
                _logger.debug("Cron: NC %s sin reversed_entry_id, se omite", cn.name)
                continue

            # OMITIR si el motivo explícito indica que NO es devolución logística
            motivo = cn.x_studio_motivo_de_devolucin or ''
            motivo_sel = cn.x_studio_selection_field_Q69ft or ''
            # usar comprobación por substring para cubrir variaciones/extra texto
            if _is_no_inventory_motivo(motivo) or _is_no_inventory_motivo(motivo_sel) or motivo_sel.strip().lower() == 'diferencias de peso':
                _logger.info(
                    "Cron: NC %s marcada como motivo no logístico (motivo='%s', selection='%s'); se omite enlace a sale_lines",
                    cn.name, motivo, motivo_sel
                )
                continue

            orig_product_ids = set(orig.invoice_line_ids.mapped('product_id.id'))
            cn_product_ids = set(cn.invoice_line_ids.mapped('product_id.id'))

            # Si la factura original no contiene los productos de la NC, omitimos
            if not orig_product_ids.issuperset(cn_product_ids):
                _logger.debug("Cron: productos de la factura original %s no cubren NC %s, se omite",
                              orig.name, cn.name)
                continue

            # Detectar caso de corrección de precio:
            # - mismos productos en ambas
            # - las cantidades línea a línea coinciden
            # - y hay al menos una diferencia en price_unit (considerando conversión VEF/USD)
            price_correction = False
            if orig_product_ids == cn_product_ids:
                all_qty_equal = True
                any_price_diff = False

                # Determinar si debemos comparar en VEF (caso VEF/USD)
                try:
                    curr_orig = (orig.currency_id.name or '').strip().upper()
                    curr_cn = (cn.currency_id.name or '').strip().upper()
                except Exception:
                    curr_orig = curr_cn = ''

                compare_in_vef = {curr_orig, curr_cn} == {'USD', 'VEF'}

                for cn_line in cn.invoice_line_ids:
                    matched = orig.invoice_line_ids.filtered(lambda l: l.product_id.id == (cn_line.product_id.id or 0))
                    if not matched:
                        all_qty_equal = False
                        break
                    # Emparejar por cantidad si es posible
                    match_line = matched.filtered(lambda l: float_compare(l.quantity, cn_line.quantity, precision_digits=6) == 0)
                    if not match_line:
                        match_line = matched[:1]
                    orig_line = match_line[0]

                    if float_compare(orig_line.quantity, cn_line.quantity, precision_digits=6) != 0:
                        all_qty_equal = False

                    # Comparar price_unit con posible conversión
                    if compare_in_vef:
                        orig_price_cmp = _norm_price_for_vef(orig_line.price_unit, orig)
                        cn_price_cmp = _norm_price_for_vef(cn_line.price_unit, cn)
                    else:
                        orig_price_cmp = float(orig_line.price_unit or 0.0)
                        cn_price_cmp = float(cn_line.price_unit or 0.0)

                    if float_compare(orig_price_cmp, cn_price_cmp, precision_digits=6) != 0:
                        any_price_diff = True

                if all_qty_equal and any_price_diff:
                    price_correction = True

            if price_correction:
                _logger.info("Cron: NC %s parece corrección de precios respecto a %s; se omite enlace a sale_lines",
                             cn.name, orig.name)
                continue

            # Copiar sale_line_ids por línea cuando falten
            for cn_line in cn.invoice_line_ids:
                if cn_line.sale_line_ids:
                    continue
                matched = orig.invoice_line_ids.filtered(lambda l: l.product_id.id == (cn_line.product_id.id or 0))
                if not matched:
                    continue
                # Preferir líneas con cantidad suficiente, si existe
                match_line = matched.filtered(lambda l: l.quantity >= cn_line.quantity) or matched[:1]
                sale_ids = match_line.mapped('sale_line_ids.id')
                if sale_ids:
                    try:
                        cn_line.sudo().write({'sale_line_ids': [(6, 0, sale_ids)]})
                        _logger.info("Cron: asignadas sale_line_ids %s a invoice.line %s de NC %s",
                                     sale_ids, cn_line.id, cn.id)
                        updated_lines += 1
                    except Exception as e:
                        _logger.exception("Cron: error asignando sale_line_ids a linea %s de NC %s: %s",
                                          cn_line.id, cn.id, e)

        _logger.info("Cron finalizado. Líneas actualizadas: %s", updated_lines)
        return True

    def write(self, vals):
        """
        Después de escribir, para las notas de crédito vinculadas (reversed_entry_id)
        verificamos motivos financieros/configurados y diferencia de precio para
        eliminar sale_line_ids cuando corresponda. Además, si la nota NO está marcada
        como motivo no logístico y después de las comprobaciones hay líneas SIN
        sale_line_ids, intentamos volver a enlazarlas desde la factura original.
        """
        res = super().write(vals)

        try:
            refunds = self.filtered(lambda m: m.move_type in ('out_refund', 'in_refund') and m.reversed_entry_id)
            for rn in refunds:
                motivo = rn.x_studio_motivo_de_devolucin or ''
                motivo_sel = rn.x_studio_selection_field_Q69ft or ''

                # Si el motivo o la selección indican un motivo no-logístico, limpiamos enlaces
                if _is_no_inventory_motivo(motivo) or _is_no_inventory_motivo(motivo_sel):
                    for line in rn.invoice_line_ids.filtered(lambda l: l.sale_line_ids):
                        try:
                            line.sudo().write({'sale_line_ids': [(6, 0, [])]})
                            _logger.info(
                                "Se removieron sale_line_ids de la línea %s por motivo no logístico (motivo='%s', selection='%s') (NC %s)",
                                line.id, motivo, motivo_sel, rn.name
                            )
                        except Exception:
                            _logger.exception("Error removiendo sale_line_ids en línea %s de NC %s", line.id, rn.name)
                    # no intentamos relinkear cuando el motivo es no-logístico
                    continue

                # Helper local para comparar precios en VEF (convierte USD usando tax_today)
                def _norm_price_for_vef(price, move):
                    try:
                        cur = (move.currency_id.name or '').strip().upper()
                    except Exception:
                        cur = ''
                    tax = float(getattr(move, 'tax_today', 1.0) or 1.0)
                    price_f = float(price or 0.0)
                    if cur == 'USD':
                        return price_f * (tax or 1.0)
                    return price_f

                # Bandera: si detectamos diferencia de precio respetamos la eliminación y NO relinkamos
                price_difference_detected = False

                # Comprobar diferencia de precio línea a línea (como en el cron)
                try:
                    orig = rn.reversed_entry_id
                    if orig:
                        # comparar conjuntos de productos para determinar si aplicar lógica
                        orig_product_ids = set(orig.invoice_line_ids.mapped('product_id.id'))
                        cn_product_ids = set(rn.invoice_line_ids.mapped('product_id.id'))
                        if orig_product_ids == cn_product_ids:
                            # determinar si comparar en VEF (caso VEF/USD)
                            try:
                                curr_orig = (orig.currency_id.name or '').strip().upper()
                                curr_cn = (rn.currency_id.name or '').strip().upper()
                            except Exception:
                                curr_orig = curr_cn = ''
                            compare_in_vef = {curr_orig, curr_cn} == {'USD', 'VEF'}

                            all_qty_equal = True
                            any_price_diff = False
                            for cn_line in rn.invoice_line_ids:
                                matched = orig.invoice_line_ids.filtered(lambda l: l.product_id.id == (cn_line.product_id.id or 0))
                                if not matched:
                                    all_qty_equal = False
                                    break
                                match_line = matched.filtered(lambda l: float_compare(l.quantity, cn_line.quantity, precision_digits=6) == 0)
                                if not match_line:
                                    match_line = matched[:1]
                                orig_line = match_line[0]
                                if float_compare(orig_line.quantity, cn_line.quantity, precision_digits=6) != 0:
                                    all_qty_equal = False

                                if compare_in_vef:
                                    orig_price_cmp = _norm_price_for_vef(orig_line.price_unit, orig)
                                    cn_price_cmp = _norm_price_for_vef(cn_line.price_unit, rn)
                                else:
                                    orig_price_cmp = float(orig_line.price_unit or 0.0)
                                    cn_price_cmp = float(cn_line.price_unit or 0.0)

                                if float_compare(orig_price_cmp, cn_price_cmp, precision_digits=6) != 0:
                                    any_price_diff = True

                            if all_qty_equal and any_price_diff:
                                price_difference_detected = True
                                # eliminar enlaces por corrección de precio
                                for line in rn.invoice_line_ids.filtered(lambda l: l.sale_line_ids):
                                    try:
                                        line.sudo().write({'sale_line_ids': [(6, 0, [])]})
                                        _logger.info(
                                            "Se removieron sale_line_ids de la línea %s en NC %s por diferencia de precio",
                                            line.id, rn.name
                                        )
                                    except Exception:
                                        _logger.exception("Error removiendo sale_line_ids en línea %s de NC %s", line.id, rn.name)
                except Exception:
                    _logger.exception("Error comprobando diferencia de precio para NC %s", rn.name)

                # Si detectamos diferencia de precio no relinkear
                if price_difference_detected:
                    continue

                # A estas alturas: motivo NO es no-logístico y no hay diferencia de precio
                # Intentar relinkear líneas que quedaron sin sale_line_ids
                try:
                    orig = rn.reversed_entry_id
                    if not orig:
                        continue
                    for cn_line in rn.invoice_line_ids.filtered(lambda l: not l.sale_line_ids):
                        matched = orig.invoice_line_ids.filtered(lambda l: l.product_id.id == (cn_line.product_id.id or 0))
                        if not matched:
                            continue
                        # Preferir líneas con cantidad suficiente
                        match_line = matched.filtered(lambda l: l.quantity >= cn_line.quantity) or matched[:1]
                        sale_ids = match_line.mapped('sale_line_ids.id')
                        if sale_ids:
                            try:
                                cn_line.sudo().write({'sale_line_ids': [(6, 0, sale_ids)]})
                                _logger.info(
                                    "Se reasignaron sale_line_ids %s a invoice.line %s de NC %s tras escritura (rn=%s)",
                                    sale_ids, cn_line.id, rn.name, rn.id
                                )
                            except Exception:
                                _logger.exception("Error reasignando sale_line_ids en línea %s de NC %s", cn_line.id, rn.name)
                except Exception:
                    _logger.exception("Error intentando relinkear líneas para NC %s", rn.name)

        except Exception:
            _logger.exception("Error validando notas de crédito después de write")

        return res
