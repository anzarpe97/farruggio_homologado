# -*- coding: utf-8 -*-
from odoo import http, fields as odoo_fields
from odoo.http import request
from datetime import date
from html import escape


class CollectionCustomListController(http.Controller):

    @http.route(['/collection_dashboard/list'], type='http', auth='user', website=False)
    def collection_custom_list(self, **kwargs):
        env = request.env
        # Seguridad: limitar a usuarios con permiso de facturación
        try:
            if not env.user.has_group('account.group_account_invoice'):
                return request.make_response('Acceso denegado', status=403)
        except Exception:
            # Si el grupo no existe, continuar para no romper en instalaciones sin account
            pass
        Move = env['account.move']
        today = date.today()

        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial', 'in_payment')),
            ('amount_residual', '>', 0),
        ]
        # Fetch minimal fields to reduce overhead
        fields = [
            'name', 'partner_id', 'invoice_date', 'invoice_date_due', 'amount_total',
            'amount_residual', 'currency_id', 'invoice_user_id'
        ]
        # Optionally include team_id if exists to avoid attribute error
        if 'team_id' in Move._fields:
            fields.append('team_id')

        records = Move.search_read(domain, fields, order='invoice_date desc', limit=1000)

        # Prepare USD currency
        usd = env.ref('base.USD', raise_if_not_found=False) or env['res.currency'].search([('name', '=', 'USD')], limit=1)
        company = env.company

        rows_html = []
        for rec in records:
            name = rec.get('name') or ''
            partner = rec.get('partner_id') and rec['partner_id'][1] or ''
            inv_date = rec.get('invoice_date') or ''
            amount_total = rec.get('amount_total') or 0.0
            amount_residual = rec.get('amount_residual') or 0.0
            currency_id = rec.get('currency_id') and rec['currency_id'][0]
            currency = env['res.currency'].browse(currency_id) if currency_id else env.company.currency_id

            # Compute days overdue
            inv_due = rec.get('invoice_date_due')
            if inv_due:
                try:
                    inv_due_dt = odoo_fields.Date.from_string(inv_due)
                except Exception:
                    inv_due_dt = today
            else:
                inv_due_dt = today
            days_overdue = max((today - inv_due_dt).days, 0)

            # Status bucket
            if days_overdue >= 31:
                status = 'MOROSO'
            elif days_overdue >= 20:
                status = 'CRÍTICO'
            elif days_overdue >= 1:
                status = 'VENCIDO'
            else:
                status = 'A VENCER'

            # Zone / Sales Team name
            zone = 'Sin equipo'
            # Prefer invoice team if available, otherwise user's team
            if 'team_id' in rec and rec['team_id']:
                zone = rec['team_id'][1]
            else:
                user_id = rec.get('invoice_user_id') and rec['invoice_user_id'][0]
                if user_id:
                    user = env['res.users'].browse(user_id)
                    if 'sale_team_id' in user._fields and user.sale_team_id:
                        zone = user.sale_team_id.name

            # Convert residual amount to USD if possible
            if usd:
                try:
                    residual_usd = currency._convert(amount_residual, usd, company, today)
                except Exception:
                    residual_usd = amount_residual
            else:
                residual_usd = amount_residual

            rows_html.append(
                f"<tr>"
                f"<td>{escape(zone)}</td>"
                f"<td>{escape(name)}</td>"
                f"<td>{escape(partner)}</td>"
                f"<td>{escape(str(inv_date or ''))}</td>"
                f"<td style='text-align:right'>{amount_total:,.2f}</td>"
                f"<td style='text-align:right'>{residual_usd:,.2f}</td>"
                f"<td style='text-align:center'>{days_overdue}</td>"
                f"<td>{escape(status)}</td>"
                f"</tr>"
            )

        # Basic minimal HTML without Odoo layout
        html = f"""
<!DOCTYPE html>
<html lang=\"es\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Lista Personalizada de Cobranzas</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'Liberation Sans', sans-serif; margin: 16px; color: #111827; }}
    h1   {{ font-size: 20px; margin: 0 0 12px 0; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; }}
    thead th {{ text-align: left; background: #f3f4f6; font-weight: 600; border-bottom: 1px solid #e5e7eb; padding: 8px; font-size: 13px; }}
    tbody td {{ border-top: 1px solid #f1f5f9; padding: 8px; font-size: 13px; }}
    .meta {{ color: #6b7280; font-size: 12px; margin-bottom: 8px; }}
  </style>
</head>
<body>
  <h1>Lista Personalizada de Cobranzas</h1>
  <div class=\"meta\">Fecha de corte: {today.isoformat()}</div>
  <table>
    <thead>
      <tr>
        <th>Zona (Equipo de Venta)</th>
        <th>Factura</th>
        <th>Cliente</th>
        <th>Fecha Factura</th>
        <th style=\"text-align:right\">Monto Factura</th>
        <th style=\"text-align:right\">Deuda USD</th>
        <th style=\"text-align:center\">Días</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</body>
</html>
        """
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])
