# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    def _set_currency_usd_id(self):
        usd = self.env.ref('base.USD')
        return usd

    list_price_usd = fields.Float('Sale Price USD', digits='Product Price', required=True, default=0.0)
    currency_usd_id = fields.Many2one('res.currency', 'USD', default=_set_currency_usd_id)

    @api.onchange('list_price_usd')
    def onchange_price_bs(self):
        new_price = 0.0
        rate = self.env['res.currency.rate'].search([
            ('name', '<=', date.today()), ('currency_id', '=', self.currency_usd_id.id)], limit=1).sell_rate
        if rate:
            new_price += self.list_price_usd * rate
        else:
            new_price += self.list_price_usd * 1
        self.list_price = new_price
        for item in self.product_variant_ids:
            item.list_price = new_price
    
    
class ProductTemplateAttributeValue(models.Model):
    _inherit = 'product.template.attribute.value'

    def _set_currency_usd_id(self):
        usd = self.env.ref('base.USD')
        return usd

    list_price_usd = fields.Float('Valor Precio Extra $', digits='Product Price', required=True, default=0.0)
    currency_usd_id = fields.Many2one('res.currency', 'USD', default=_set_currency_usd_id)


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    rate = fields.Float(
        string='Tasa', 
        default=lambda x: x.env['res.currency.rate'].search([
            ('name', '<=', fields.Date.today()), 
            ('currency_id', '=', 2)
        ], limit=1).sell_rate, 
        digits=(12, 2)
    )

    @api.onchange('rate')
    def _onchange_rate(self):
        """
        Actualiza el campo fixed_price en los items de la lista de precios 
        basándose en el valor de Precio $ y la tasa (rate).
        """
        for item in self.item_ids:
            if item.price_usd and self.rate:
                item.fixed_price = item.price_usd * self.rate
                
    def update_pricelist_items(self):
        """
        Actualiza automáticamente los precios de los ítems de la lista de precios
        según la tasa más reciente.
        """
        for pricelist in self.search([]):
            for item in pricelist.item_ids:
                if item.price_usd and pricelist.rate:
                    item.fixed_price = item.price_usd * pricelist.rate


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    price_usd = fields.Float(
        string='Precio $', 
        digits=(12, 3),
        help='Precio en dólares que se usará para calcular el precio fijo.'
    )    
