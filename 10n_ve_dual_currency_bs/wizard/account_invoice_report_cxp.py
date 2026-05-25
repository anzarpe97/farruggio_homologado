import base64 
from io import BytesIO
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

class DueRangeCXP(models.Model):
    _name = 'due.range.cxp'
    _description = 'Rango de Vencimiento CXP'

    name = fields.Char(string='Nombre')
    code = fields.Char(string='Código')
    days_from = fields.Integer(string='Desde (días)')
    days_to = fields.Integer(string='Hasta (días)')


class AccountReportCXP(models.TransientModel):
    _name = 'account.invoice.report.cxp'
    _description = 'Reporte de Cuentas por Pagar'

    start_date = fields.Date(string='Fecha Inicio')
    end_date = fields.Date(string='Fecha Fin')
    partner_id = fields.Many2one('res.partner', string="Proveedor")

    due_range_ids = fields.Many2many('due.range.cxp', string="Filtrar por Vencimiento")

    report_format = fields.Selection([
        ('pdf', 'PDF')
    ], string="Formato del Reporte", required=True, default='pdf')

    invoice_data = fields.Char(string='Nombre del Archivo')
    file_name_pdf = fields.Binary('Descargar PDF', readonly=True)
    state = fields.Selection([('choose', 'choose'), ('get', 'get')], default='choose')

    def action_generate_report(self):
        if self.report_format == "pdf":
            return self._generate_pdf_report()
        else:
            raise ValidationError("Formato de reporte no válido. Elija PDF.")

    def _get_due_ranges(self):
        """
        Devuelve una lista de tuplas (days_from, days_to) para los rangos seleccionados.
        """
        ranges = []
        for r in self.due_range_ids:
            ranges.append((r.days_from, r.days_to))
        return ranges

    def _get_current_exchange_rate(self):
        currency_usd = self.env.ref('base.USD')
        currency_company = self.env.company.currency_id
        if currency_usd == currency_company:
            return 1.0

        today = fields.Date.context_today(self)
        rate = self.env['res.currency.rate'].search([
            ('currency_id', '=', currency_usd.id),
            ('name', '<=', today)
        ], order='name desc', limit=1)
        return rate.inverse_company_rate if rate else 1.0

    def _get_report_data(self):
        company_id = self.env.company
        current_rate = self._get_current_exchange_rate()

        query = """
            SELECT 
                m.id, 
                m.supplier_invoice_number AS name, 
                m.date,
                m.invoice_date_due, 
                m.currency_id, 
                c.name as currency_name,
                m.amount_total_usd,
                m.amount_total,
                m.amount_residual,
                m.amount_residual_usd,
                m.tax_today AS invoice_tax_rate,
                p.name as partner_name,
                EXTRACT(DAY FROM NOW() - m.invoice_date_due) AS days_due
            FROM 
                account_move m
            JOIN 
                res_partner p ON m.partner_id = p.id
            JOIN 
                res_currency c ON m.currency_id = c.id
            WHERE 
                m.move_type = 'in_invoice'
                AND m.amount_residual > 0
                AND m.state = 'posted'
                AND m.company_id = %s
        """
        params = [company_id.id]

        if self.start_date:
            query += " AND m.date >= %s"
            params.append(self.start_date)
        
        if self.end_date:
            query += " AND m.date <= %s"
            params.append(self.end_date)

        if self.partner_id:
            query += " AND m.partner_id = %s"
            params.append(self.partner_id.id)
        # Aseguramos ordenar por nombre del proveedor para que el reporte salga alfabéticamente
        query += " ORDER BY p.name"

        self.env.cr.execute(query, tuple(params))
        result = self.env.cr.dictfetchall()

        if not result:
            raise ValidationError("No hay facturas por pagar en el rango o filtros especificados.")

        # Filtrar por los rangos seleccionados
        filtered_result = []
        due_ranges = self._get_due_ranges() if self.due_range_ids else []
        for inv in result:
            days_due = inv.get('days_due')
            if days_due is None:
                continue
            if due_ranges:
                for dr_from, dr_to in due_ranges:
                    if dr_from <= days_due <= dr_to:
                        filtered_result.append(inv)
                        break
            else:
                filtered_result.append(inv)

        grouped_result = defaultdict(list)
        for inv in filtered_result:
            amount_total_usd = inv['amount_total_usd']
            amount_total_bs = amount_total_usd * current_rate
            amount_residual = inv['amount_residual']

            if inv['currency_name'] == 'VEF':
                deuda_usd = inv.get('amount_residual_usd', amount_residual / current_rate)
            else:
                deuda_usd = amount_residual

            # Deuda (Bs.) siempre debe ser: Deuda (USD) * Tasa del día
            amount_residual_bs = deuda_usd * current_rate

            inv.update({
                'amount_total_usd': amount_total_usd,
                'amount_residual': deuda_usd,  
                'amount_total_bs': amount_total_bs,
                'amount_residual_bs': amount_residual_bs,
                'tax_today': inv.get('invoice_tax_rate', 0.0),
            })

            grouped_result[inv['partner_name']].append(inv)

        return grouped_result

    def _generate_pdf_report(self):
        grouped_result = self._get_report_data()
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=landscape(letter))

        def draw_header():
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(250, 550, "REPORTE DE CUENTAS POR PAGAR")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(100, 520, f"Empresa: {self.env.company.name}")
            pdf.drawString(100, 500, f"R.I.F.: {self.env.company.vat or 'No posee RIF asociado'}")
            pdf.drawString(400, 520, f"Tasa del día: {self._get_current_exchange_rate()}")
            pdf.drawString(100, 480, f"Fecha desde: {self.start_date.strftime('%d/%m/%Y') if self.start_date else 'Automático'}")
            pdf.drawString(250, 480, f"Fecha hasta: {self.end_date.strftime('%d/%m/%Y') if self.end_date else 'Automático'}")
            if self.partner_id:
                pdf.drawString(100, 465, f"Proveedor: {self.partner_id.name}")
            if self.due_range_ids:
                due_names = ', '.join(self.due_range_ids.mapped('name'))
                pdf.drawString(550, 465, f"Filtro de Vencimiento: {due_names}")

            y_position = 450
            pdf.setFont("Helvetica", 8)
            headers = ["Fecha", "Proveedor", "N° Doc.", "Moneda", "Monto (Bs.)", "Deuda (Bs.)", "Monto (USD)", "Deuda (USD)", "Tasa BCV", "Días Venc."]
            x_positions = [30, 80, 220, 310, 365, 435, 510, 580, 660, 720]
            for i, header in enumerate(headers):
                pdf.drawString(x_positions[i], y_position, header)
            return y_position - 20

        total_monto_bs = 0
        total_deuda_bs = 0
        total_monto_usd = 0
        total_deuda_usd = 0

        y_position = draw_header()

        # Iteramos proveedores en orden alfabético independiente del orden del dict
        for partner_name in sorted(grouped_result.keys(), key=lambda x: (x or '').lower()):
            # Ordenar facturas por días vencidos ascendente
            invoices = sorted(grouped_result[partner_name], key=lambda inv: inv.get('days_due') if inv.get('days_due') is not None else -9999)
            client_total_monto_bs = 0
            client_total_deuda_bs = 0
            client_total_monto_usd = 0
            client_total_deuda_usd = 0

            if y_position < 50:
                pdf.showPage()
                y_position = draw_header()

            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(30, y_position, f"Proveedor: {partner_name}")
            y_position -= 10
            pdf.setFont("Helvetica", 8)

            for inv in invoices:
                if y_position < 50:
                    pdf.showPage()
                    y_position = draw_header()

                pdf.drawString(30, y_position, inv.get('date').strftime('%d/%m/%Y') if inv.get('date') else '-')
                pdf.drawString(220, y_position, inv.get('name', '-'))
                pdf.drawString(310, y_position, inv.get('currency_name', 'N/A'))
                pdf.drawString(365, y_position, f"{inv.get('amount_total_bs', 0):,.2f}")
                pdf.drawString(435, y_position, f"{inv.get('amount_residual_bs', 0):,.2f}")
                pdf.drawString(510, y_position, f"{inv.get('amount_total_usd', 0):,.2f}")
                pdf.drawString(580, y_position, f"{inv.get('amount_residual', 0):,.2f}")  # Aquí se muestra el valor condicional
                pdf.drawString(660, y_position, f"{inv.get('tax_today', 0):,.2f}")
                pdf.drawString(720, y_position, str(inv.get('days_due') or "VIGENTE"))

                client_total_monto_bs += inv.get('amount_total_bs', 0)
                client_total_deuda_bs += inv.get('amount_residual_bs', 0)
                client_total_monto_usd += inv.get('amount_total_usd', 0)
                client_total_deuda_usd += inv.get('amount_residual', 0)

                y_position -= 15

            pdf.drawString(30, y_position, "Total Proveedor:")
            pdf.drawString(365, y_position, f"{client_total_monto_bs:,.2f}")
            pdf.drawString(435, y_position, f"{client_total_deuda_bs:,.2f}")
            pdf.drawString(510, y_position, f"{client_total_monto_usd:,.2f}")
            pdf.drawString(580, y_position, f"{client_total_deuda_usd:,.2f}")
            pdf.line(30, y_position - 2, 740, y_position - 2)

            total_monto_bs += client_total_monto_bs
            total_deuda_bs += client_total_deuda_bs
            total_monto_usd += client_total_monto_usd
            total_deuda_usd += client_total_deuda_usd

            y_position -= 35

        if y_position < 80:
            pdf.showPage()
            y_position = draw_header()

        current_rate = self._get_current_exchange_rate()
        total_deuda_bs = total_deuda_usd * current_rate

        y_position -= 30
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(30, y_position, "TOTALES GENERALES:")

        pdf.setFont("Helvetica", 9)
        y_position -= 15
        pdf.drawString(50, y_position, f"Monto (Bs.): {total_monto_bs:,.2f}")
        y_position -= 15
        pdf.drawString(50, y_position, f"Deuda (Bs.): {total_deuda_bs:,.2f}")
        y_position -= 15
        pdf.drawString(50, y_position, f"Monto (USD): {total_monto_usd:,.2f}")
        y_position -= 15
        pdf.drawString(50, y_position, f"Deuda (USD): {total_deuda_usd:,.2f}")

        pdf.showPage()
        pdf.save()

        buffer.seek(0)
        file_data = buffer.getvalue()
        encoded_file = base64.b64encode(file_data)

        self.write({
            'file_name_pdf': encoded_file,
            'invoice_data': 'reporte_cxp.pdf',
            'state': 'get',
        })

        buffer.close()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice.report.cxp',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }