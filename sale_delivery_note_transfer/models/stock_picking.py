from odoo import models, fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    sale_note_lines = fields.Text(string="Notas del Pedido de Venta")
