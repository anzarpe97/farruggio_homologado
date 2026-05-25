from odoo import models, fields, api

class StockMoveLine(models.Model):
    _inherit = 'stock.move'

    und = fields.Integer(
        string='Und',
        help='Unidad de medida adicional',
        store=True,
    )
    
    nro_paqts = fields.Integer(
        string='Nro Paqts',
        help='Número de paquetes',
        store=True,
    )
    
    nro_cestas = fields.Integer(
        string='Nro Cestas',
        help='Número de cestas',
        store=True,
    )