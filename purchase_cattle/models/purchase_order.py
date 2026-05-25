from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    cattle_line_ids = fields.One2many(
        'purchase.cattle.line', 'purchase_id', 
        string="Reses en Canal"
    )

    @api.onchange('cattle_line_ids')
    def _onchange_cattle_products(self):
        """
        Llena automáticamente las líneas de productos en la orden de compra 
        cuando se agregan reses en canal.
        """
        self.order_line = [(5, 0, 0)]  # Elimina todas las líneas actuales

        lines = []
        for cattle in self.cattle_line_ids:
            if cattle.product_id and hasattr(cattle.product_id, 'cattle_products_ids'):
                for product in cattle.product_id.cattle_products_ids:
                    lines.append((0, 0, {
                        'product_id': product.id,
                        'product_qty': 1.00,
                        'name': product.name,
                        'product_uom': product.uom_id.id,
                        'price_unit': 0.0  
                    }))

        if lines:
            self.order_line = lines  # Asigna las nuevas líneas de productos
