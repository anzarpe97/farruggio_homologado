from odoo import models, fields, api
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    x_aprobada = fields.Boolean("Aprobada")

    x_aprobada_text = fields.Char(
        string="Aprobada?",
        compute="_compute_x_aprobada_text",
        store=False
    )

    @api.depends('x_aprobada')
    def _compute_x_aprobada_text(self):
        for record in self:
            record.x_aprobada_text = "Sí" if record.x_aprobada else "No"

    def action_approve_invoice(self):
        """Aprobar factura desde el botón en el formulario solo si es de proveedor."""
        if self.move_type != 'in_invoice':
            raise UserError("Solo puedes aprobar facturas de proveedor.")
        if self.state != 'posted':
            raise UserError("La factura debe estar publicada para ser aprobada.")
        if self.payment_state in ('paid', 'in_payment'):
            raise UserError("No puedes aprobar una factura ya pagada.")
        
        self.x_aprobada = True
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Factura aprobada',
                'message': f'La factura {self.name} ha sido aprobada.',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def action_approve_selected_invoices(self):
        """Aprobar múltiples facturas proveedor desde la vista lista."""
        invoices = self.browse(self.env.context.get('active_ids', []))
        for invoice in invoices.filtered(lambda m: m.move_type == 'in_invoice'):
            if invoice.state == 'posted' and invoice.payment_state not in ('paid', 'in_payment'):
                invoice.x_aprobada = True

        return {
            'type': 'ir.actions.act_window',
            'name': 'Facturas Aprobadas',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('x_aprobada', '=', True), ('move_type', '=', 'in_invoice')],
        }

    def action_register_payment(self):
        for move in self:
            if move.move_type == 'in_invoice' and not move.x_aprobada:
                raise UserError("No puedes registrar el pago porque la factura de proveedor no está aprobada.")
        return super().action_register_payment()
