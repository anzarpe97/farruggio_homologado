from odoo import models, fields, api
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()
        for picking in self:
            if picking.picking_type_id.code == 'incoming':
                for move in picking.move_ids_without_package:
                    if move.custom_cost_usd:
                        product = move.product_id.product_tmpl_id
                        old_cost = product.standard_price_usd
                        new_cost = move.custom_cost_usd

                        if old_cost != new_cost:
                            # Actualizar costo
                            product.standard_price_usd = new_cost
                            # Registrar en chatter
                            product.message_post(
                                body=f"<b>Costo actualizado desde la recepción <a href='/web#id={picking.id}&model=stock.picking'>{picking.name}</a></b><br/>"
                                     f"Producto: <b>{product.name}</b><br/>"
                                     f"Costo anterior: <b>{old_cost:.2f} USD</b><br/>"
                                     f"Nuevo costo: <b>{new_cost:.2f} USD</b>",
                                subtype_xmlid="mail.mt_note"
                            )
        return res