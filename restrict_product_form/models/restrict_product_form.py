from odoo import models, api
from odoo.exceptions import AccessError

class ProductTemplateRestrict(models.Model):
    _inherit = 'product.template'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        user = self.env.user
        restrict_group = self.env.ref('restrict_product_form.group_restrict_product_form')
        if view_type == 'form' and restrict_group in user.groups_id:
            raise AccessError('No tienes permiso para acceder a la ficha del producto.')
        return super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
