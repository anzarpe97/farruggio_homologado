# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_cruce = fields.Boolean(
        string='Cruce',
        help='Marque este documento si corresponde a un cruce de cuentas.\n'
             'Al estar activo, los reportes mostrarán el total del campo "debit_usd" '
             'de las líneas contables como "Instrumento de Pago".',
        default=False,
    )

    amount_total_div_rate = fields.Float(
        string='Total REF.',
        compute='_compute_amount_total_div_rate',
        store=False,
        digits=(16, 2),
        help='Para facturas: amount_total_signed / tax_today. Para asientos (pagos/cruces): suma de débitos USD (o créditos USD) de las líneas.'
    )

    has_correlative = fields.Boolean(
        string='Tiene correlativo',
        compute='_compute_has_correlative',
        store=False,
        help='Indicador auxiliar para vistas: Verdadero cuando el campo correlative tiene un valor real (distinto de vacío o "/").'
    )

    @api.depends('amount_total_signed', 'tax_today', 'line_ids.debit_usd', 'line_ids.credit_usd')
    def _compute_amount_total_div_rate(self):
        MoveLine = self.env['account.move.line']
        has_usd_fields = 'debit_usd' in MoveLine._fields and 'credit_usd' in MoveLine._fields
        for move in self:
            # Si es factura/recibo: usar amount_total_signed / tax_today (si disponible)
            if hasattr(move, 'is_invoice') and move.is_invoice(include_receipts=True):
                tasa = float(getattr(move, 'tax_today', 1.0) or 1.0)
                move.amount_total_div_rate = (move.amount_total_signed / tasa) if tasa else 0.0
                continue

            # Para asientos tipo 'entry' (pagos/cruces): tomar USD de líneas si existen
            if has_usd_fields:
                debit_sum = sum((l.debit_usd or 0.0) for l in move.line_ids)
                if debit_sum:
                    move.amount_total_div_rate = debit_sum
                    continue
                credit_sum = sum((l.credit_usd or 0.0) for l in move.line_ids)
                move.amount_total_div_rate = credit_sum or 0.0
            else:
                # Último recurso: dividir el total en moneda compañía por tax_today
                tasa = float(getattr(move, 'tax_today', 1.0) or 1.0)
                amt = float(getattr(move, 'amount_total', 0.0) or 0.0)
                move.amount_total_div_rate = (amt / tasa) if tasa else 0.0

    def _compute_has_correlative(self):
        for move in self:
            # No referenciamos el campo en @api.depends para evitar errores cuando no exista en el modelo.
            val = getattr(move, 'correlative', False)
            move.has_correlative = bool(val and val != '/')
