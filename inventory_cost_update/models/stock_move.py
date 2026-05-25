from odoo import models, fields, api
from odoo.exceptions import UserError

class StockMove(models.Model):
    _inherit = 'stock.move'

    custom_cost_usd = fields.Float(
        string="Costo USD",
        groups="inventory_cost_update.group_inventory_cost_manager"
    )

    picking_type_code = fields.Selection(
        related='picking_id.picking_type_id.code',
        store=True,
        readonly=True
    )
