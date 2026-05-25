# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    has_invoice = fields.Boolean(
        string='Con Factura',
        compute='_compute_has_invoice',
        store=True,
        index=True,
        help='Indica si el pago está vinculado a una o más facturas.'
    )

    # Compatibilidad: si existe invoice_ids (custom/local), úsalo; sino usa reconciled_invoice_ids (estándar Odoo 16);
    # como respaldo, detecta relación vía conciliaciones de líneas del apunte contable.
    @api.depends(
        'invoice_ids',
        'reconciled_invoice_ids',
        'move_id.line_ids.matched_debit_ids',
        'move_id.line_ids.matched_credit_ids',
    )
    def _compute_has_invoice(self):
        invoice_move_types = ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
        for rec in self:
            invoices_bool = False

            # 1) Campo local/custom ampliamente usado en este repositorio
            if hasattr(rec, 'invoice_ids'):
                invoices_bool = bool(rec.invoice_ids)

            # 2) Campo estándar en Odoo 16
            elif hasattr(rec, 'reconciled_invoice_ids'):
                invoices_bool = bool(rec.reconciled_invoice_ids)

            # 3) Respaldo: buscar conciliaciones contra facturas
            else:
                move = rec.move_id
                if move:
                    # líneas en cuentas por cobrar/pagar
                    rp_lines = move.line_ids.filtered(
                        lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
                    )
                    # líneas contrapartes conciliadas (parciales o totales)
                    matched = rp_lines.mapped('matched_debit_ids.debit_move_id') | rp_lines.mapped('matched_credit_ids.credit_move_id')
                    invoices_bool = any(ml.move_id.move_type in invoice_move_types for ml in matched)

            rec.has_invoice = invoices_bool
