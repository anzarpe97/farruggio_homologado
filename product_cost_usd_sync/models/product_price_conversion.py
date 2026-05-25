from odoo import models, fields, api
from odoo.exceptions import UserError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _update_standard_price_usd(self):
        products = self.env['product.template'].search([('standard_price', '>', 0)])
        usd_currency = self.env.ref('base.USD')  # Obtenemos la moneda USD
        if usd_currency:
            inverse_rate = usd_currency.rate
            for product in products:
                product.standard_price_usd = product.standard_price / (1/inverse_rate)


    @api.onchange('standard_price')
    def _onchange_standard_price(self):
        if self.standard_price:
            usd_currency = self.env.ref('base.USD')  # Moneda USD
            inverse_rate = usd_currency.rate if usd_currency else 1
            self.standard_price_usd = self.standard_price / (1/inverse_rate)

    @api.onchange('standard_price_usd')
    def _onchange_standard_price_usd(self):
        if self.standard_price_usd:
            usd_currency = self.env.ref('base.USD')  # Moneda USD
            inverse_rate = usd_currency.rate if usd_currency else 1
            self.standard_price = self.standard_price_usd * (1/inverse_rate)

    def write(self, vals):
        # Detectamos si se está escribiendo en el campo standard_price
        if 'standard_price' in vals:
            usd_currency = self.env.ref('base.USD')  # Moneda USD
            inverse_rate = usd_currency.rate if usd_currency else 1
            if 'standard_price_usd' not in vals:
                # Si no hay valor para standard_price_usd, lo calculamos
                vals['standard_price_usd'] = vals['standard_price'] / (1/inverse_rate)
        return super(ProductTemplate, self).write(vals)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _update_standard_price_usd(self):
        products = self.env['product.product'].search([('standard_price', '>', 0)])
        usd_currency = self.env.ref('base.USD')  # Obtenemos la moneda USD
        if usd_currency:
            inverse_rate = usd_currency.rate
            for product in products:
                product.standard_price_usd = product.standard_price / (1/inverse_rate)

    @api.onchange('standard_price')
    def _onchange_standard_price(self):
        if self.standard_price:
            usd_currency = self.env.ref('base.USD')  # Moneda USD
            inverse_rate = usd_currency.rate if usd_currency else 1
            self.standard_price_usd = self.standard_price / (1/inverse_rate)

    @api.onchange('standard_price_usd')
    def _onchange_standard_price_usd(self):
        if self.standard_price_usd:
            usd_currency = self.env.ref('base.USD')  # Moneda USD
            inverse_rate = usd_currency.rate if usd_currency else 1
            self.standard_price = self.standard_price_usd * (1/inverse_rate)

    def write(self, vals):
        # Detectamos si se está escribiendo en el campo standard_price
        if 'standard_price' in vals:
            usd_currency = self.env.ref('base.USD')  # Moneda USD
            inverse_rate = usd_currency.rate if usd_currency else 1
            if 'standard_price_usd' not in vals:
                # Si no hay valor para standard_price_usd, lo calculamos
                vals['standard_price_usd'] = vals['standard_price'] / (1/inverse_rate)
        return super(ProductProduct, self).write(vals)
