# from odoo import models, fields, api

# class CattleProductWizard(models.TransientModel):
#     _name = 'cattle.product.wizard'
#     _description = "Seleccionar Reses a Recibir"

#     picking_id = fields.Many2one('stock.picking', string="Recepción", required=True)
#     cattle_product_ids = fields.Many2many(
#         'product.product', 
#         string="Productos a Recibir",
#         domain=[('is_cattle_product', '=', True)]
#     )

#     def action_confirm(self):
#         """ Reemplaza los productos en la recepción sin eliminar la recepción ni perder la relación con la compra """
#         self.ensure_one()
#         picking = self.picking_id
#         purchase_order = self.env['purchase.order'].search([('name', '=', picking.origin)], limit=1)

#         if not purchase_order:
#             return

#         # ✅ Eliminamos los productos actuales sin perder la relación con la compra
#         picking.move_ids.unlink()

#         # ✅ Agregamos los productos seleccionados
#         for product in self.cattle_product_ids:
#             purchase_line = purchase_order.order_line.filtered(lambda l: l.product_id == product)[:1]
#             self.env['stock.move'].create({
#                 'picking_id': picking.id,
#                 'product_id': product.id,
#                 'name': product.name,
#                 'product_uom': product.uom_id.id,
#                 'product_uom_qty': 1.0,  # Modificable según necesidad
#                 'location_id': picking.location_id.id,  # ✅ Ubicación de origen
#                 'location_dest_id': picking.location_dest_id.id,  # ✅ Ubicación destino
#                 'purchase_line_id': purchase_line.id if purchase_line else False,  # ✅ Mantiene la relación con la compra
#             })

#         return {'type': 'ir.actions.act_window_close'}
