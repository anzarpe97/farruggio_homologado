from odoo import models, fields

class IntercompanyTransferLine(models.Model):
    _name = 'intercompany.transfer.line'
    _description = 'Línea de productos para transferencia entre compañías'

    transfer_id = fields.Many2one('intercompany.transfer', string='Transferencia')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    quantity = fields.Float(string='Cantidad', required=True, default=1.0)