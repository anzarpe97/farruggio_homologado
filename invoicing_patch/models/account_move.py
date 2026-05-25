from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def unlink(self):
        # Guardar relación con pedidos antes de eliminar
        sale_orders = self._get_related_sale_orders()
        res = super().unlink()
        if sale_orders:
            sale_orders._compute_invoice_status()
        return res

    def write(self, vals):
        # Si se cancela la factura (state -> cancel) necesitamos recomputar
        recompute = False
        if 'state' in vals and vals['state'] == 'cancel':
            recompute = True
        res = super().write(vals)
        if recompute:
            sale_orders = self._get_related_sale_orders()
            if sale_orders:
                sale_orders._compute_invoice_status()
        return res

    def _get_related_sale_orders(self):
        # Obtener pedidos de venta ligados a los invoice lines (sale_line_ids) o a través de invoice_origin
        sale_orders = self.env['sale.order']
        # Vía líneas
        lines = self.mapped('invoice_line_ids.sale_line_ids.order_id')
        if lines:
            sale_orders |= lines
        # Fallback: origen por nombre (menos preciso, pero útil si no hay relación directa)
        origins = self.mapped('invoice_origin')
        if origins:
            sale_orders |= self.env['sale.order'].search([('name', 'in', origins)])
        return sale_orders