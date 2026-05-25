from odoo import models, api
from odoo.exceptions import ValidationError

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.constrains('price_unit', 'product_uom_qty')
    def _check_negative_values(self):
        for line in self:
            if line.display_type:  # Es una nota o sección, omitir validación
                continue
            if line.price_unit < 0:
                raise ValidationError("No se permiten precios unitarios negativos en las órdenes de venta.")
            if line.product_uom_qty < 0:
                raise ValidationError("No se permiten cantidades negativas en las órdenes de venta.")
            if line.price_unit == 0:
                raise ValidationError("No se permiten precios unitarios en 0 en las órdenes de venta.")
            if line.product_uom_qty == 0:
                raise ValidationError("No se permiten cantidades en 0 en las órdenes de venta.")
