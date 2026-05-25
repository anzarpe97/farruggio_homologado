# -*- coding: utf-8 -*-

from odoo import models, fields, api
from bs4 import BeautifulSoup
from datetime import date, datetime
from pytz import timezone
import requests
import urllib3
urllib3.disable_warnings()


class ResCurrencyRateServer(models.Model):
    _name = "res.currency.rate.server"
    _description = "Tasa de Cambio"

    name = fields.Many2one(comodel_name='res.currency', string='Moneda')
    server = fields.Selection([
        ('BCV', 'Banco Central de Venezuela'),
        ('dolar-today', 'DolarToday'), ('sunacrip', 'SUNACRIP')
    ], string='Plataforma')

    res_currency = fields.Many2many('res.currency.rate', string='Rate', compute='_compute_res_currency')
    tasa_euro = fields.Float('Tasa Euro')

    def _compute_res_currency(self):
        temp = self.env['res.currency.rate'].search([('currency_id', '=', self.name.id)])
        self.res_currency = temp.ids

    def sunacrip(self):
        headers = {'Content-type': 'application/json'}
        data = '{"coins":["' + self.name.name + '"], "fiats":["USD"]}'
        response = requests.post('https://petroapp-price.petro.gob.ve/price/', headers=headers, data=data)
        var = response.json()

        if var['status'] == 200 and var['success'] == True:
            var = float(var['data']['' + self.name.name + '']['USD'])
            return var
        else:
            return False

    def central_bank(self):
        url = "https://www.bcv.org.ve/"
        req = requests.get(url, verify=False)

        status_code = req.status_code
        if status_code == 200:

            html = BeautifulSoup(req.text, "html.parser")
            # Dolar
            dolar = html.find('div', {'id': 'dolar'})
            dolar = str(dolar.find('strong')).split()
            dolar = str.replace(dolar[1], '.', '')
            dolar = float(str.replace(dolar, ',', '.'))
            # Euro
            euro = html.find('div', {'id': 'euro'})
            euro = str(euro.find('strong')).split()
            euro = str.replace(euro[1], '.', '')
            euro = float(str.replace(euro, ',', '.'))

            if self.name.name == 'USD':
                bcv = dolar
            elif self.name.name == 'EUR':
                bcv = euro
            else:
                bcv = False

            return bcv
        else:
            return False

    def dtoday(self):
        url = "https://s3.amazonaws.com/dolartoday/data.json"
        response = requests.get(url)
        status_code = response.status_code

        if status_code == 200:
            response = response.json()
            usd = float(response['USD']['transferencia'])
            eur = float(response['EUR']['transferencia'])

            if self.name.name == 'USD':
                data = usd
            elif self.name.name == 'EUR':
                data = eur
            else:
                data = False

            return data
        else:
            return False

    def set_rate(self):
        """Este método actualiza la tasa y los precios de los productos si la tasa ha cambiado."""
        if self.server == 'BCV':
            currency = self.central_bank()
        elif self.server == 'dolar-today':
            currency = self.dtoday()
        elif self.server == 'sunacrip':
            currency = self.sunacrip()
        else:
            return False
        
        rate = self.env['res.currency.rate'].search([('name', '=', datetime.now().date()), ('currency_id', '=', self.name.id)], limit=1)
        
        if len(rate) == 0:
            new_rate = 1 / round(currency, 2)
            self.env['res.currency.rate'].create({
                'currency_id': self.name.id,
                'name': datetime.now(),
                'sell_rate': round(currency, 2),
                'rate': new_rate
            })
            if self.tasa_euro > 1:
                self.env['res.currency.rate'].create({
                    'currency_id': 1,
                    'name': datetime.now(),
                    'sell_rate': round(currency, 2) * self.tasa_euro,
                    'rate': 1 / (round(currency, 2) * self.tasa_euro)
                })
        else:
            last_rate = rate.sell_rate
            new_rate = 1 / round(currency, 2)
            if round(last_rate, 2) != round(currency, 2):
                rate.rate = new_rate
                rate.sell_rate = round(currency, 2)
                if self.name.id == 2:  # Solo si la moneda es USD
                    self.update_product(new_rate)
                    self.update_pricelist(new_rate)
            else:
                # Si la tasa no cambió, no hacemos nada
                pass                    
    
    def update_product(self, new_rate):
        """Este método actualiza los precios de los productos, solo si list_price está en 0."""
        products = self.env['product.product'].search([('currency_id', '=', self.name.id)])
        
        for product in products:
            # Si list_price es 0 y list_price_usd tiene valor, se actualiza el list_price
            if product.list_price == 0 and product.list_price_usd:
                # Convertir list_price_usd a list_price usando la tasa
                product.write({'list_price': product.list_price_usd * new_rate})
            elif product.list_price != 0:
                # Si el producto ya tiene un valor en list_price, no se actualiza
                pass


    def update_pricelist(self, currency):
        product = self.env['product.pricelist'].search([('currency_id', '=', self.env.user.company_id.currency_id.id)])
        for item in product:
            item.rate = currency
    

    def _cron_update_product(self):
        products = self.env['product.template'].search([])
        for product in products:
            product.write({'list_price': product.list_price * 1.05})  # Aumento del 5% como ejemplo
    
    @api.model
    def _cron_update_rate(self):
        """Acción planificada para actualizar la tasa de cambio"""
        servers = self.search([])  # Buscar todos los registros de tasas de moneda
        for server in servers:
            server.set_rate()  # Llamar al método set_rate de cada registro

            
class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    sell_rate = fields.Float(string='Tasa de Cambio', digits=(12, 4))

    @api.model
    def update_sell_rate_cron(self):
        """Actualizar el campo sell_rate con el valor de rate o inverse_company_rate"""
        today = datetime.now().date()
        rates = self.search([('name', '=', today)])
        for rate in rates:
            if rate.rate:
                rate.sell_rate = 1 / rate.rate
            elif hasattr(rate, 'inverse_company_rate') and rate.inverse_company_rate:
                rate.sell_rate = rate.inverse_company_rate

    @api.constrains("sell_rate")
    def set_sell_rate(self):
        self.rate = 1 / self.sell_rate
        
    def get_systray_dict(self, date):
        tz_name = "America/Lima"
        today_utc = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')
        context_today = today_utc.astimezone(timezone(tz_name))
        date = context_today.strftime("%Y-%m-%d")
        
        rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', 2), ('name', '=', date)], limit=1).sorted(lambda x: x.name)
        rate_euro = self.env['res.currency.rate'].search([
            ('currency_id', '=', 1), ('name', '=', date)], limit=1).sorted(lambda x: x.name)

        if rate:
            exchange_rate = 1 / rate.rate
            exchange_rate_euro = 1 / rate_euro.rate if rate_euro.rate > 0 else 1 
            return {
                'date': ('Fecha: ') + rate.name.strftime("%d/%m/%Y"),
                'rate': "USD: " + str("{:,.2f}".format(exchange_rate)),
                'rate_euro': " EUR: " + str("{:,.2f}".format(exchange_rate_euro))
            }
        else:
            return {'date': ('No hay tipo de cambio para ') + context_today.strftime("%d/%m/%Y"), 'rate': 'N/R'}


class Currency(models.Model):
    _inherit = "res.currency"

    sell_rate = fields.Float(compute='_compute_tasa_real', digits=(12, 2), help='se introduce la tasa real del mercado')
    rate = fields.Float(compute='_compute_current_rate', string='Current Rate', digits=(12, 20),
                        help='The rate of the currency to the currency of rate 1.')
    rate_rounding = fields.Float(digits=(12, 9), help='la tasa inversa del mercado')

    def _compute_tasa_real(self):
        tasa_actual = 0.0
        tasa_actual_inv = 0.0
        lista_tasa = self.env['res.currency.rate'].search(
            [('currency_id', '=', self.id)], order='id desc', limit=1)
        if lista_tasa:
            for tasa in lista_tasa:
                tasa_actual += tasa.sell_rate
                tasa_actual_inv += tasa.rate
        else:
            tasa_actual += 1
            tasa_actual_inv += 1
        self.sell_rate = tasa_actual
        self.rate = tasa_actual_inv