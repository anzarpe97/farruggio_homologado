from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_cattle_product = fields.Boolean('¿Es Res en Canal?', help="Indica si el producto es una res en canal")
    cattle_products_ids = fields.Many2many(
        'product.product',
        'cattle_product_rel',
        'template_id',
        'product_id',
        string="Productos asociados a la compra de res en canal",
        domain=[('is_cattle_product', '=', True)]
    )