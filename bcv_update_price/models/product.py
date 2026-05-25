from odoo import models, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def actualizar_precios_bs(self):
        """ Actualiza lst_price en Bs basado en list_price_usd_variant y la tasa de cambio de USD. """
        
        # Buscar la moneda USD
        usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)

        if not usd_currency or usd_currency.rate == 0:
            return False  # Evitar divisiones por 0 y problemas si no hay tasa

        productos = self.search([('list_price_usd_variant', '>', 0)])

        for producto in productos:
            producto.lst_price = producto.list_price_usd_variant * usd_currency.rate  # Multiplicación correcta

        return True
