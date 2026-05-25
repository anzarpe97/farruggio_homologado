# ©  2015-2022 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    trade_markup = fields.Float(string="Margen de Utilidad", tracking=True)

    def set_inverse_trade_markup(self):
        pass


class ProductProduct(models.Model):
    _inherit = "product.product"

    def set_inverse_trade_markup(self):
        pass
