from odoo import models, fields, _, api
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    sale_order_id = fields.Many2one('sale.order', string="Pedido de Venta", readonly=True)


    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_("Esta factura no está vinculada a un pedido de venta."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pedido de Venta'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
        }

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if not move.sale_order_id and move.invoice_origin:
                # Buscar la orden por el nombre original
                sale_order = self.env['sale.order'].search([('name', '=', move.invoice_origin)], limit=1)
                if sale_order:
                    move.sale_order_id = sale_order.id
        return moves
    
    @api.onchange('invoice_origin')
    def _onchange_invoice_origin(self):
        if self.invoice_origin and not self.sale_order_id:
            sale_order = self.env['sale.order'].search([('name', '=', self.invoice_origin)], limit=1)
            if sale_order:
                self.sale_order_id = sale_order.id
