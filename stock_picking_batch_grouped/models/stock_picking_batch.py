from odoo import models, api

import logging

_logger = logging.getLogger(__name__)

class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    def get_grouped_move_lines(self):
        self.ensure_one()
        grouped = {}
        for move in self.picking_ids.mapped('move_ids'):
            key = move.product_id.id
            if key not in grouped:
                grouped[key] = {
                    'product': move.product_id,
                    'qty_done': move.quantity_done or 0.0,
                    'reserved_uom_qty': move.product_uom_qty or 0.0,
                    'uom': move.product_uom, # Changed from product_uom_id
                    'picking': move.picking_id,
                    'lot_ids': [],
                    'barcode': move.product_id.barcode,
                    'packages': [],
                }
            else:
                grouped[key]['qty_done'] += move.quantity_done or 0.0
                grouped[key]['reserved_uom_qty'] += move.product_uom_qty or 0.0
        return list(grouped.values())
