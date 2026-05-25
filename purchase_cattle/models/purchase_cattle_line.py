from odoo import models, fields, api

class PurchaseCattleLine(models.Model):
    _name = 'purchase.cattle.line'
    _description = "Líneas de Reses en Canal"

    purchase_id = fields.Many2one('purchase.order', string="Orden de Compra", required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Producto", required=True, domain=[('is_cattle_product', '=', True)])
    quantity = fields.Float(string="Cantidad", default=1.0, required=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """ Si se selecciona un producto, actualiza las líneas de la orden de compra """
        if self.purchase_id and hasattr(self.purchase_id, '_update_cattle_products'):
            self.purchase_id._update_cattle_products()
