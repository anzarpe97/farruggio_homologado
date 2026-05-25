from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    notas = fields.Text(string='Notas')

class StockMove(models.Model):
    _inherit = 'stock.move'

    notas = fields.Text(string='Notas', compute='_compute_notas', store=True)

    @api.depends('sale_line_id', 'sale_line_id.notas')
    def _compute_notas(self):
        for move in self:
            move.notas = move.sale_line_id.notas if move.sale_line_id else ''

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def get_sale_line_description(self, move):
        # Busca la descripción de la venta relacionada, si existe
        sale_line = move.sale_line_id
        if sale_line:
            return sale_line.name
        return move.name or move.product_id.display_name

    def get_nro_pqts(self, move):
        return getattr(move, 'nro_pqts', '')

    def get_nro_cestas(self, move):
        return getattr(move, 'nro_cestas', '') 