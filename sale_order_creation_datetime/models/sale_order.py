from odoo import models, fields, api
from datetime import datetime, time
import pytz

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _domain_created_before_2pm(self):
        """Devuelve un dominio para pedidos creados hoy antes de las 2PM Caracas."""
        user_tz = self.env.user.tz or 'America/Caracas'
        tz = pytz.timezone(user_tz)

        today_local = fields.Datetime.context_timestamp(self, fields.Datetime.now()).date()
        local_start = tz.localize(datetime.combine(today_local, time.min))
        local_end = tz.localize(datetime.combine(today_local, time(14, 1)))

        utc_start = local_start.astimezone(pytz.utc)
        utc_end = local_end.astimezone(pytz.utc)

        return [('create_date', '>=', utc_start.strftime('%Y-%m-%d %H:%M:%S')),
                ('create_date', '<=', utc_end.strftime('%Y-%m-%d %H:%M:%S'))]
    creation_datetime = fields.Datetime(
        string='Fecha de Creación',
        readonly=True,
        compute='_compute_creation_datetime',
        store=False,
    )
    def _compute_creation_datetime(self):
        for order in self:
            order.creation_datetime = order.create_date
