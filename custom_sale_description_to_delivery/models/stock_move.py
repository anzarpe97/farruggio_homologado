from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = "stock.move"

    sale_line_description = fields.Text(
        string="Descripción de venta"
    )

    @api.model
    def create(self, vals):
        if not vals.get('sale_line_description') and vals.get('sale_line_id'):
            sale_line = self.env['sale.order.line'].browse(vals['sale_line_id'])
            vals['sale_line_description'] = sale_line.name or ''
        return super().create(vals)

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    sale_line_description = fields.Text(
        related="move_id.sale_line_description",
        store=True,
        readonly=True
    )
