from odoo import models, fields, api, _
from datetime import date, timedelta
import calendar

class CollectionDashboardInvoice(models.Model):
    _name = 'collection.dashboard.invoice'
    _description = 'Dashboard de Cobranzas (Vista Agregada)'
    _order = 'invoice_date desc, id desc'
    _table = 'collection_dashboard_invoice_m'
    _rec_name = 'name'

    currency_id = fields.Many2one('res.currency', string='Moneda',
                                  default=lambda self: self.env.company.currency_id.id,
                                  required=True)

    zone_name = fields.Char(string='Zona')
    name = fields.Char(string='Factura')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    invoice_date = fields.Date(string='Fecha')

    # Mes de la factura (YYYY-MM) para búsquedas y agrupaciones rápidas
    invoice_month = fields.Char(
        string='Mes',
        compute='_compute_invoice_month',
        store=False,
        search='_search_invoice_month'
    )
    days_since_issue = fields.Integer(string='Días', compute='_compute_days_since_issue', store=False, search='_search_days_since_issue')
    amount_total = fields.Monetary(string='Total', currency_field='currency_id')
    amount_residual_usd = fields.Monetary(string='Deuda USD', currency_field='currency_id')

    status_bucket = fields.Selection([
        ('al_dia', 'AL DÍA'),
        ('vencido', 'VENCIDO'),
        ('critico', 'CRÍTICO'),
        ('moroso', 'MOROSO'),
    ], string='Estado', compute='_compute_status_bucket', store=False, search='_search_status_bucket')

    # Campo fantasma para satisfacer el widget usado en la vista
    search_dashboard = fields.Boolean(string='Panel de búsqueda', default=True)

    @api.depends('invoice_date')
    def _compute_days_since_issue(self):
        today = date.today()
        for rec in self:
            if rec.invoice_date:
                rec.days_since_issue = (today - rec.invoice_date).days
            else:
                rec.days_since_issue = 0

    @api.depends('invoice_date')
    def _compute_invoice_month(self):
        for rec in self:
            if rec.invoice_date:
                rec.invoice_month = f"{rec.invoice_date.year:04d}-{rec.invoice_date.month:02d}"
            else:
                rec.invoice_month = False

    @api.depends('days_since_issue')
    def _compute_status_bucket(self):
        for rec in self:
            d = rec.days_since_issue or 0
            if d >= 31:
                rec.status_bucket = 'moroso'
            elif d >= 20:
                rec.status_bucket = 'critico'
            elif d >= 1:
                rec.status_bucket = 'vencido'
            else:
                rec.status_bucket = 'al_dia'

    # Traduce dominios sobre days_since_issue a dominios sobre invoice_date
    def _search_days_since_issue(self, operator, value):
        # Normalizamos operador/valor y construimos fecha de corte
        today = fields.Date.context_today(self)
        if not isinstance(value, (int, float)):
            try:
                value = int(value)
            except Exception:
                value = 0
        delta = timedelta(days=int(value))
        cutoff = today - delta

        # Mapear operador: dsi = hoy - invoice_date
        # dsi > N  => invoice_date <  today - N
        # dsi >= N => invoice_date <= today - N
        # dsi < N  => invoice_date >  today - N
        # dsi <= N => invoice_date >= today - N
        # dsi = N  => invoice_date =  today - N
        # dsi != N => invoice_date != today - N
        mapping = {
            '>':  ('<', cutoff),
            '>=': ('<=', cutoff),
            '<':  ('>', cutoff),
            '<=': ('>=', cutoff),
            '=':  ('=', cutoff),
            '!=': ('!=', cutoff),
        }
        op = mapping.get(operator)
        if not op:
            # fallback seguro: sin filtro
            return []
        inv_op, inv_val = op
        return [('invoice_date', inv_op, inv_val)]

    # Permite buscar por estado traduciendo a rangos de days_since_issue => rangos de invoice_date
    def _search_status_bucket(self, operator, value):
        today = fields.Date.context_today(self)
        def date_minus(days):
            return today - timedelta(days=days)

        # Mapeos por estado
        ranges = {
            'moroso':  [('invoice_date', '<=', date_minus(31))],
            'critico': ['&', ('invoice_date', '<=', date_minus(20)), ('invoice_date', '>', date_minus(31))],
            'vencido': ['&', ('invoice_date', '<=', date_minus(1)),  ('invoice_date', '>', date_minus(20))],
            'al_dia':  [('invoice_date', '>', date_minus(1))],
        }

        # Soporte para '=' e 'in' básicos; otros operadores se devuelven sin filtro
        if operator in ('=', '==') and isinstance(value, str):
            return ranges.get(value, [])
        if operator == 'in' and isinstance(value, (list, tuple)):
            domain = []
            first = True
            for v in value:
                r = ranges.get(v)
                if not r:
                    continue
                if first:
                    domain += r
                    first = False
                else:
                    domain = ['|'] + domain + r
            return domain
        if operator in ('!=', 'not in'):
            # Negación: devolvemos dominios OR de los restantes
            values = ['al_dia', 'vencido', 'critico', 'moroso']
            if operator == '!=' and isinstance(value, str):
                values = [v for v in values if v != value]
            elif operator == 'not in' and isinstance(value, (list, tuple)):
                values = [v for v in values if v not in value]
            domain = []
            first = True
            for v in values:
                r = ranges.get(v)
                if not r:
                    continue
                if first:
                    domain += r
                    first = False
                else:
                    domain = ['|'] + domain + r
            return domain
        return []

    # Búsqueda por mes (YYYY-MM) con soporte para 'mes_actual'/'current'
    def _search_invoice_month(self, operator, value):
        today = fields.Date.context_today(self)

        def month_range(y, m):
            last_day = calendar.monthrange(y, m)[1]
            first = date(y, m, 1)
            last = date(y, m, last_day)
            return first, last

        def parse_value(v):
            if not v or v in ('mes_actual', 'current', 'this_month', 'actual'):
                return today.year, today.month
            try:
                parts = str(v).split('-')
                if len(parts) == 2:
                    y = int(parts[0])
                    m = int(parts[1])
                    if 1 <= m <= 12:
                        return y, m
            except Exception:
                pass
            # fallback: mes actual
            return today.year, today.month

        if operator in ('=', '=='):
            y, m = parse_value(value)
            first, last = month_range(y, m)
            return ['&', ('invoice_date', '>=', first), ('invoice_date', '<=', last)]

        if operator == 'in' and isinstance(value, (list, tuple)):
            domain = []
            first_cond = True
            for v in value:
                y, m = parse_value(v)
                first_m, last_m = month_range(y, m)
                cond = ['&', ('invoice_date', '>=', first_m), ('invoice_date', '<=', last_m)]
                if first_cond:
                    domain += cond
                    first_cond = False
                else:
                    domain = ['|'] + domain + cond
            return domain

        if operator in ('!=', 'not in'):
            # Negación: OR de los meses restantes no tiene una forma sencilla; devolvemos NOT entre rangos
            # Construimos un dominio que excluya los rangos seleccionados con ANDs anidados.
            months = []
            if operator == '!=':
                months = [value]
            elif operator == 'not in' and isinstance(value, (list, tuple)):
                months = list(value)

            # Si no hay meses definidos, no filtramos
            if not months:
                return []

            # Dominio: invoice_date < first_m OR invoice_date > last_m para cada mes (combinado con AND)
            # Aquí simplificamos: devolvemos un NOT sobre el OR de los meses incluidos
            include_domain = []
            first_inc = True
            for v in months:
                y, m = parse_value(v)
                first_m, last_m = month_range(y, m)
                cond = ['&', ('invoice_date', '>=', first_m), ('invoice_date', '<=', last_m)]
                if first_inc:
                    include_domain += cond
                    first_inc = False
                else:
                    include_domain = ['|'] + include_domain + cond
            return ['!'] + include_domain

        # Otros operadores no soportados específicamente: sin filtro
        return []

    # Botones del header en la vista tree (stubs seguros)
    def action_refresh(self):
        # Aquí podrías recalcular/actualizar registros desde facturas reales
        return True

    def action_export(self):
        # Aquí podrías retornar una acción de exportación personalizada
        return True
