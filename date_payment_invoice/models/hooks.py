from odoo import SUPERUSER_ID, api
from odoo.api import Environment

def post_init_recalcular_fechas_pago(cr, registry):
    env = Environment(cr, SUPERUSER_ID, {})
    env['account.move'].recalcular_last_payment_date()

@api.model
def recalcular_last_payment_date(self):
    facturas = self.search([
        ('move_type', '=', 'out_invoice'),
        ('payment_state', '=', 'paid')
    ])
    facturas._compute_last_payment_date()
    # Forzar guardar y que se aplique store=True
    facturas.write({})
