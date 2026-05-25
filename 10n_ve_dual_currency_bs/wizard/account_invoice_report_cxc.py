import base64
import calendar
from io import BytesIO
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from collections import defaultdict
import logging
import requests

_logger = logging.getLogger(__name__)

class AccountInvoiceReportDueRange(models.Model):
    _name = 'account.invoice.report.due.range'
    _description = 'Rango de Vencimiento'

    name = fields.Char(string='Nombre')
    min_days = fields.Integer(string='Días desde')
    max_days = fields.Integer(string='Días hasta')

    @api.model
    def name_get(self):
        """Mostrar "+90" en el selector cuando el rango inicia en 90 días o más.
        No altera el valor real del campo 'name'; solo la etiqueta mostrada.
        """
        result = []
        for rec in self:
            display = "+90" if rec.min_days is not None and rec.min_days >= 90 else (rec.name or "")
            result.append((rec.id, display))
        return result


class AccountReportCXC(models.TransientModel):
    _name = 'account.invoice.report.cxc'
    _description = 'Reporte de Cuentas por Cobrar'

    start_date = fields.Date(string='Fecha Inicio')
    end_date = fields.Date(string='Fecha Fin')
    partner_id = fields.Many2one('res.partner', string="Cliente")
    user_id = fields.Many2one('res.users', string="Comercial")  # <--- Aquí se añade

    # due_range = fields.Selection([ 
    #     ('1-7', '1-7 días'),
    #     ('7-15', '7-15 días'),
    #     ('1-30', '1-30 días'),
    #     ('15-30', '15-30 días'),
    #     ('30-60', '30-60 días'),
    #     ('60-90', '60-90 días'),
    #     ('90-120', '90-120 días'),
    # ], string="Filtrar por Vencimiento")

    due_range_ids = fields.Many2many(
        'account.invoice.report.due.range', 
        string="Filtrar por Vencimiento"
    )


    report_format = fields.Selection([ 
        ('pdf', 'PDF'),
        ('excel', 'Excel')
    ], string="Formato del Reporte", required=True, default='pdf')

    invoice_data = fields.Char(string='Nombre del Archivo')
    file_name_pdf = fields.Binary('Descargar PDF', readonly=True)
    file_name_excel = fields.Binary('Descargar Excel', readonly=True)
    state = fields.Selection([('choose', 'choose'), ('get', 'get')], default='choose')

    def _get_exchange_rate(self):
        """Obtiene la tasa de cambio más reciente en Bs. por USD desde Odoo."""
        company_currency = self.env.company.currency_id
        usd_currency = self.env.ref('base.USD')  # Dólar americano
        
        if company_currency == usd_currency:
            return 1  # Si la moneda de la empresa es USD, la tasa es 1
        
        # Obtener la tasa más reciente registrada en Odoo
        currency_rate = self.env['res.currency.rate'].search([ 
            ('currency_id', '=', usd_currency.id),
            ('company_id', '=', self.env.company.id) 
        ], order='name desc', limit=1)
        
        return round(1 / currency_rate.rate, 2) if currency_rate else "No disponible"

    def action_generate_report(self):
        """Genera el reporte según el formato seleccionado"""
        # if not self.due_range and not (self.start_date and self.end_date):
        #     raise ValidationError("Debe seleccionar un rango de vencimiento o indicar fechas manualmente.")
        if self.report_format == "pdf":
            return self._generate_pdf_report()
        elif self.report_format == "excel":
            return self._generate_excel_report()
        else:
            raise ValidationError("Formato de reporte no válido. Elija PDF o Excel.")

    def _generate_excel_report(self):
        """Genera el reporte en formato Excel mostrando primero CLIENTE y dentro sus rangos y facturas, con ajuste de celdas, fechas y resumen por rango."""
        import xlsxwriter
        import base64
        grouped_result = self._get_report_data()
        if not grouped_result:
            raise ValidationError("No hay facturas en el rango de fecha especificado")

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('CXC')

        # Formatos
        bold = workbook.add_format({'bold': True})
        center_bold = workbook.add_format({'bold': True, 'align': 'center'})
        money = workbook.add_format({'num_format': '#,##0.00'})
        header_bg = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'align': 'center'})
        total_bg = workbook.add_format({'bold': True, 'bg_color': '#B7B7B7'})
        # Colores para resumen por rango
        color_vigente = workbook.add_format({'bg_color': '#90ee90', 'num_format': '#,##0.00', 'align': 'right'}) # lightgreen
        color_amarillo = workbook.add_format({'bg_color': '#ffff99', 'num_format': '#,##0.00', 'align': 'right'}) # lightyellow
        color_salmon = workbook.add_format({'bg_color': '#fa8072', 'num_format': '#,##0.00', 'align': 'right'}) # salmon
        color_total = workbook.add_format({'bold': True, 'bg_color': '#808080', 'font_color': '#FFFFFF', 'align': 'center'}) # grey

        # Ajuste de columnas
        col_widths = [15, 20, 18, 15, 12, 12, 10, 14, 14, 14, 14, 10, 12]
        for i, w in enumerate(col_widths):
            worksheet.set_column(i, i, w)

        # Encabezados principales
        worksheet.merge_range('A1:L1', 'REPORTE DE CUENTAS POR COBRAR', center_bold)
        worksheet.write('A2', f"Empresa: {self.env.company.name}")
        worksheet.write('A3', f"Tasa del día: {self._get_exchange_rate()}")
        worksheet.write('A4', f"R.I.F.: {self.env.company.vat or 'No posee RIF asociado'}")
        worksheet.write('A5', f"Fecha desde: {self.start_date.strftime('%d/%m/%Y') if self.start_date else 'Automático'}")
        worksheet.write('C5', f"Fecha hasta: {self.end_date.strftime('%d/%m/%Y') if self.end_date else 'Automático'}")
        if self.partner_id:
            worksheet.write('E5', f"Cliente: {self.partner_id.name}")
        if self.user_id:
            worksheet.write('G5', f"Comercial: {self.user_id.name}")
        if self.due_range_ids:
            # Mostrar "+90 días" en lugar de "90-120" para rangos con min_days >= 90
            rangos = ", ".join("+90 días" if r.min_days >= 90 else r.name for r in self.due_range_ids)
            worksheet.write('I5', f"Rangos de Vencimiento: {rangos}")

        # Encabezados de tabla principal
        row = 7
        headers = [
            'Zona', 'Cliente', 'Rango', 'Factura', 'Fecha', 'Fecha Venc.', 'Moneda',
            'Monto Bs.', 'Deuda Bs.', 'Monto USD', 'Deuda USD', 'Tasa BCV', 'Días Venc.'
        ]
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, header_bg)
        row += 1

        # Totales generales
        total_monto_bs = 0.0
        total_deuda_bs = 0.0
        total_monto_usd = 0.0
        total_deuda_usd = 0.0

        prev_partner = None
        client_total_monto_bs = client_total_deuda_bs = client_total_monto_usd = client_total_deuda_usd = 0.0
        for (partner_name, rango_min, rango_label), invoices in grouped_result:
            # Si cambia el cliente, dibuja una línea divisoria y muestra total por cliente
            if prev_partner is not None and prev_partner != partner_name:
                # Fila total por cliente
                worksheet.write(row, 0, 'Total Cliente:', total_bg)
                worksheet.write(row, 6, client_total_monto_bs, money)
                worksheet.write(row, 7, client_total_deuda_bs, money)
                worksheet.write(row, 8, client_total_monto_usd, money)
                worksheet.write(row, 9, client_total_deuda_usd, money)
                row += 1
                # Línea divisoria
                worksheet.merge_range(row, 0, row, 11, '', workbook.add_format({'bottom': 2, 'border_color': '#000000'}))
                row += 1
                client_total_monto_bs = client_total_deuda_bs = client_total_monto_usd = client_total_deuda_usd = 0.0
            prev_partner = partner_name
            for inv in invoices:
                worksheet.write(row, 0, inv.get('team_name') or '')
                worksheet.write(row, 1, partner_name)
                worksheet.write(row, 2, rango_label)
                worksheet.write(row, 3, inv.get('name'))
                worksheet.write(row, 4, inv.get('date').strftime('%d/%m/%Y') if inv.get('date') else '')
                worksheet.write(row, 5, inv.get('invoice_date_due').strftime('%d/%m/%Y') if inv.get('invoice_date_due') else '')
                worksheet.write(row, 6, inv.get('currency_name'))
                worksheet.write_number(row, 7, inv.get('monto_bs', 0.0), money)
                worksheet.write_number(row, 8, inv.get('deuda_bs', 0.0), money)
                worksheet.write_number(row, 9, inv.get('monto_usd', 0.0), money)
                worksheet.write_number(row, 10, inv.get('deuda_usd', 0.0), money)
                worksheet.write(row, 11, inv.get('tasa_bcv'))
                worksheet.write(row, 12, inv.get('days_due'))
                client_total_monto_bs += inv.get('monto_bs', 0.0)
                client_total_deuda_bs += inv.get('deuda_bs', 0.0)
                client_total_monto_usd += inv.get('monto_usd', 0.0)
                client_total_deuda_usd += inv.get('deuda_usd', 0.0)
                total_monto_bs += inv.get('monto_bs', 0.0)
                total_deuda_bs += inv.get('deuda_bs', 0.0)
                total_monto_usd += inv.get('monto_usd', 0.0)
                total_deuda_usd += inv.get('deuda_usd', 0.0)
                row += 1
        # Fila total del último cliente
        worksheet.write(row, 0, 'Total Cliente:', total_bg)
        worksheet.write(row, 6, client_total_monto_bs, money)
        worksheet.write(row, 7, client_total_deuda_bs, money)
        worksheet.write(row, 8, client_total_monto_usd, money)
        worksheet.write(row, 9, client_total_deuda_usd, money)
        row += 1

        # Totales generales al final
        row += 1
        worksheet.write(row, 0, 'TOTALES GENERALES', total_bg)
        worksheet.write(row + 1, 1, 'Monto (Bs.):', bold)
        worksheet.write_number(row + 1, 2, total_monto_bs, money)
        worksheet.write(row + 2, 1, 'Deuda (Bs.):', bold)
        worksheet.write_number(row + 2, 2, total_deuda_bs, money)
        worksheet.write(row + 3, 1, 'Monto (USD):', bold)
        worksheet.write_number(row + 3, 2, total_monto_usd, money)
        worksheet.write(row + 4, 1, 'Deuda (USD):', bold)
        worksheet.write_number(row + 4, 2, total_deuda_usd, money)

        # === TABLA RESUMEN POR RANGO DE VENCIMIENTO ===
        # Calcular resumen igual que en PDF
        resumen = {}
        if self.user_id:
            resumen = {
                'Facturas vigentes': 0.0,
                '1-10 días': 0.0,
                '11-20 días': 0.0,
                '21-30 días': 0.0,
                '+31 días': 0.0,
            }
            for (partner_name, rango_min, rango_label), invoices in grouped_result:
                for inv in invoices:
                    days_due = inv.get('days_due') or 0
                    val = inv.get('deuda_usd', 0.0) or 0.0
                    if days_due <= 0:
                        resumen['Facturas vigentes'] += val
                    elif 1 <= days_due <= 10:
                        resumen['1-10 días'] += val
                    elif 11 <= days_due <= 20:
                        resumen['11-20 días'] += val
                    elif 21 <= days_due <= 30:
                        resumen['21-30 días'] += val
                    elif days_due > 30:
                        resumen['+31 días'] += val
        else:
            usuarios = {}
            for (partner_name, rango_min, rango_label), invoices in grouped_result:
                for inv in invoices:
                    ejecutivo = inv.get('ejecutivo_name') or 'Sin Ejecutivo'
                    if ejecutivo not in usuarios:
                        usuarios[ejecutivo] = {
                            'Facturas vigentes': 0.0,
                            '1-10 días': 0.0,
                            '11-20 días': 0.0,
                            '21-30 días': 0.0,
                            '+31 días': 0.0,
                        }
                    days_due = inv.get('days_due') or 0
                    val = inv.get('deuda_usd', 0.0) or 0.0
                    if days_due <= 0:
                        usuarios[ejecutivo]['Facturas vigentes'] += val
                    elif 1 <= days_due <= 10:
                        usuarios[ejecutivo]['1-10 días'] += val
                    elif 11 <= days_due <= 20:
                        usuarios[ejecutivo]['11-20 días'] += val
                    elif 21 <= days_due <= 30:
                        usuarios[ejecutivo]['21-30 días'] += val
                    elif days_due > 30:
                        usuarios[ejecutivo]['+31 días'] += val
            resumen = usuarios

        # Insertar tabla resumen en hoja nueva
        resumen_ws = workbook.add_worksheet('Resumen Vencimiento')
        resumen_ws.set_column(0, 0, 22)
        resumen_ws.set_column(1, 5, 18)
        resumen_ws.merge_range('A1:F1', 'RESUMEN POR RANGO DE VENCIMIENTO', center_bold)

        if self.user_id:
            headers = ["Facturas vigentes", "1-10 días", "11-20 días", "21-30 días", "+31 días"]
            for col, h in enumerate(headers):
                resumen_ws.write(2, col, h, header_bg)
            row = 3
            # Colores por rango
            resumen_ws.write_number(row, 0, resumen[headers[0]], color_vigente)
            resumen_ws.write_number(row, 1, resumen[headers[1]], color_amarillo)
            resumen_ws.write_number(row, 2, resumen[headers[2]], color_amarillo)
            resumen_ws.write_number(row, 3, resumen[headers[3]], color_salmon)
            resumen_ws.write_number(row, 4, resumen[headers[4]], color_salmon)
        else:
            headers = ["Ejecutivo", "Facturas vigentes", "1-10 días", "11-20 días", "21-30 días", "+31 días"]
            for col, h in enumerate(headers):
                resumen_ws.write(2, col, h, header_bg)
            row = 3
            for ejecutivo, totales in resumen.items():
                resumen_ws.write(row, 0, ejecutivo)
                resumen_ws.write_number(row, 1, totales[headers[1]], color_vigente)
                resumen_ws.write_number(row, 2, totales[headers[2]], color_amarillo)
                resumen_ws.write_number(row, 3, totales[headers[3]], color_amarillo)
                resumen_ws.write_number(row, 4, totales[headers[4]], color_salmon)
                resumen_ws.write_number(row, 5, totales[headers[5]], color_salmon)
                row += 1
            # Fila TOTAL (toda la fila en gris)
            for col in range(len(headers)):
                if col == 0:
                    resumen_ws.write(row, col, 'TOTAL', color_total)
                else:
                    resumen_ws.write_number(row, col, sum(resumen[ej][headers[col]] for ej in resumen), color_total)

        workbook.close()
        output.seek(0)
        excel_data = base64.b64encode(output.read())
        self.write({
            'state': 'get',
            'file_name_excel': excel_data,
            'invoice_data': 'cuentas_por_cobrar.xlsx'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice.report.cxc',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'target': 'new',
        }
    
    def _get_due_days_range(self):
        # Mapea cada selección al rango real de días vencidos
        ranges = {
            '1-7': (1, 7),
            '7-15': (7, 15),
            '1-30': (1, 30),
            '15-30': (15, 30),
            '30-60': (30, 60),
            '60-90': (60, 90),
            '90-120': (90, 120),
        }
        return ranges.get(self.due_range, (None, None))
        
    def _calculate_dates_from_due_range(self):
        """Calcula las fechas de inicio y fin según el filtro de vencimiento"""
        today = datetime.today()
        first_day_of_month = today.replace(day=1)

        ranges = {
            '1-7': (today - timedelta(days=7), today),
            '7-15': (today - timedelta(days=15), today),
            '1-30': (first_day_of_month, today),
            '15-30': (today - timedelta(days=30), today),
            '30-60': (first_day_of_month - timedelta(days=30), today),
            '60-90': (first_day_of_month - timedelta(days=60), today),
            '90-120': (first_day_of_month - timedelta(days=90), today),
        }

        return ranges.get(self.due_range, (self.start_date, self.end_date))
    
    def _get_due_range_label(self, days_due):
        """Devuelve el nombre del rango de vencimiento según el número de días"""
        # Para 90 días o más, siempre mostrar "+90 días"
        if days_due >= 90:
            return "+90 días"
        for rango in self.due_range_ids:
            if rango.min_days <= days_due <= rango.max_days:
                return rango.name
        return "COBRO VIGENTE" if days_due <= 0 else f"{int(days_due)} días"


    def _get_report_data(self):
        """Obtiene y prepara los datos del reporte, ordenados por CLIENTE."""
        current_company_id = self.env.company
        start_date = self.start_date
        end_date = self.end_date
        tasa_bcv = self._get_exchange_rate()  # Tasa en Bs/USD

        query = """
            SELECT 
                m.id, 
                m.name, 
                m.date,
                m.invoice_date_due, 
                m.currency_id, 
                c.name AS currency_name,
                m.amount_total,
                m.amount_residual,
                m.amount_total_usd,
                m.amount_residual_usd,
                m.tax_today,
                p.name AS partner_name,
                up.name AS ejecutivo_name,
                COALESCE(pt.name->>'es_VE', pt.name::text, '') AS team_name,
                (CURRENT_DATE - m.invoice_date_due) AS days_due
            FROM 
                account_move m
            JOIN 
                res_partner p ON m.partner_id = p.id
            LEFT JOIN crm_team pt ON p.team_id = pt.id
            JOIN
                res_currency c ON m.currency_id = c.id
            LEFT JOIN res_users u ON m.invoice_user_id = u.id
            LEFT JOIN res_partner up ON u.partner_id = up.id
            WHERE 
                m.move_type = 'out_invoice'
                AND m.state = 'posted'
                -- Mantener tu condición de adeudado por moneda:
                AND (
                    (c.name = 'VEF' AND COALESCE(m.amount_residual_usd, 0) <> 0)
                    OR
                    (c.name != 'VEF' AND COALESCE(m.amount_residual, 0) <> 0)
                )
        """
        params = []

        # Prioridad: si hay due_range_ids, ignora fechas
        if self.due_range_ids:
            # Si el rango inicia en 90 días, se considera abierto (>= 90 días)
            conditions = []
            for rango in self.due_range_ids:
                if rango.min_days >= 90:
                    conditions.append("((CURRENT_DATE - m.invoice_date_due) >= %s)")
                    params.append(rango.min_days)
                else:
                    conditions.append("((CURRENT_DATE - m.invoice_date_due) >= %s AND (CURRENT_DATE - m.invoice_date_due) <= %s)")
                    params.extend([rango.min_days, rango.max_days])
            query += " AND (" + " OR ".join(conditions) + ")"
        else:
            # Fechas por vencimiento (invoice_date_due)
            if self.start_date and self.end_date:
                query += " AND m.invoice_date_due BETWEEN %s AND %s"
                params.extend([self.start_date, self.end_date])
            elif self.start_date and not self.end_date:
                query += " AND m.invoice_date_due >= %s"
                params.append(self.start_date)
            elif self.end_date and not self.start_date:
                query += " AND m.invoice_date_due <= %s"
                params.append(self.end_date)

        # Filtros adicionales
        query += " AND m.company_id = %s"
        params.append(self.env.company.id)

        if self.partner_id:
            query += " AND m.partner_id = %s"
            params.append(self.partner_id.id)

        if self.user_id:
            query += " AND m.invoice_user_id = %s"
            params.append(self.user_id.id)

        # Orden lógico para CxC: Cliente → Vencimiento → Número
        query += " ORDER BY p.name ASC, m.invoice_date_due ASC, m.name ASC"
        self.env.cr.execute(query, tuple(params))
        result = self.env.cr.dictfetchall()

        if not result:
            raise ValidationError("No hay facturas por cobrar en el rango o filtros especificados.")

        # Preparación de rangos definidos (ordenados por min_days)
        rangos_definidos = self.due_range_ids.sorted(key=lambda r: r.min_days)

        all_invoices = []
        for inv in result:
            # Normalizamos montos en USD según moneda del documento
            if inv['currency_name'] == 'USD':
                monto_usd = inv['amount_total'] or 0
                deuda_usd = inv['amount_residual'] or 0
            else:
                monto_usd = inv['amount_total_usd'] or 0
                deuda_usd = inv['amount_residual_usd'] or 0

            monto_bs = monto_usd * tasa_bcv
            deuda_bs = deuda_usd * tasa_bcv

            days_due = inv.get('days_due') or 0

            # Calcular etiqueta y prioridad del rango
            def get_due_range_info(days, ranges):
                if days <= 0:
                    return "COBRO VIGENTE", -1
                # Para 90 días o más, agrupar como "+90 días"
                if days >= 90:
                    return "+90 días", 90
                for r in ranges:
                    if r.min_days <= days <= r.max_days:
                        return r.name, r.min_days
                return f"{int(days)} días", days

            rango_nombre, rango_min = get_due_range_info(days_due, rangos_definidos)

            inv.update({
                'monto_usd': monto_usd,
                'deuda_usd': deuda_usd,
                'monto_bs': monto_bs,
                'deuda_bs': deuda_bs,
                'tasa_bcv': tasa_bcv,
                'range_label': rango_nombre,
                'due_range_min': rango_min,
            })

            all_invoices.append(inv)

        # === Cambio clave: ordenar por CLIENTE, luego por rango, luego por fecha ===
        all_invoices.sort(key=lambda i: (i['partner_name'] or '', i['due_range_min'], i['date']))

        # Agrupar por (cliente, rango)
        from collections import defaultdict
        grouped_result = defaultdict(list)
        for inv in all_invoices:
            key = (inv['partner_name'], inv['due_range_min'], inv['range_label'])
            grouped_result[key].append(inv)

        # Lista ordenada: primero cliente, luego rango
        ordered_grouped_result = sorted(grouped_result.items(), key=lambda k: (k[0][0], k[0][1]))
        return ordered_grouped_result


    def _generate_pdf_report(self):
        """Genera el PDF mostrando primero CLIENTE y dentro sus rangos y facturas."""
        grouped_result = self._get_report_data()
        if not grouped_result:
            raise ValidationError("No hay facturas en el rango de fecha especificado")

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=landscape(letter))

        def draw_header():
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(250, 550, "REPORTE DE CUENTAS POR COBRAR")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(100, 520, f"Empresa: {self.env.company.name}")
            pdf.drawString(400, 520, f"Tasa del día: {self._get_exchange_rate()}")
            pdf.drawString(100, 500, f"R.I.F.: {self.env.company.vat or 'No posee RIF asociado'}")
            pdf.drawString(100, 480, f"Fecha desde: {self.start_date.strftime('%d/%m/%Y') if self.start_date else 'Automático'}")
            pdf.drawString(250, 480, f"Fecha hasta: {self.end_date.strftime('%d/%m/%Y') if self.end_date else 'Automático'}")

            if self.partner_id:
                pdf.drawString(100, 465, f"Cliente: {self.partner_id.name}")
            if self.user_id:
                pdf.drawString(450, 480, f"Comercial: {self.user_id.name}")
            if self.due_range_ids:
                # Mostrar "+90 días" en lugar de "90-120" para rangos con min_days >= 90
                rangos = ", ".join("+90 días" if r.min_days >= 90 else r.name for r in self.due_range_ids)
                pdf.drawString(550, 465, f"Rangos de Vencimiento: {rangos}")

            y = 450
            pdf.setFont("Helvetica", 8)
            headers = ["Fecha", "Cliente", "N° Doc.", "Moneda", "Monto (Bs.)", "Deuda (Bs.)", "Monto (USD)", "Deuda (USD)", "Tasa BCV", "Días Venc."]
            x_positions = [30, 80, 370, 400, 440, 495, 555, 620, 680, 720]
            for i, header in enumerate(headers):
                pdf.drawString(x_positions[i], y, header)
            return y - 20

        # Totales generales
        total_monto_bs = 0.0
        total_deuda_bs = 0.0
        total_monto_usd = 0.0
        total_deuda_usd = 0.0

        y_position = draw_header()

        # Variables para controlar cambio de cliente
        current_partner = None
        client_total_monto_bs = client_total_deuda_bs = client_total_monto_usd = client_total_deuda_usd = 0.0

        def flush_client_totals(y):
            """Imprime totales del cliente actual y devuelve la nueva y."""
            nonlocal client_total_monto_bs, client_total_deuda_bs, client_total_monto_usd, client_total_deuda_usd
            if current_partner is None:
                return y
            if y < 60:
                pdf.showPage()
                y = draw_header()
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(30, y, "Total Cliente:")
            pdf.drawString(440, y, f"{client_total_monto_bs:,.2f}")
            pdf.drawString(495, y, f"{client_total_deuda_bs:,.2f}")
            pdf.drawString(555, y, f"{client_total_monto_usd:,.2f}")
            pdf.drawString(620, y, f"{client_total_deuda_usd:,.2f}")
            y -= 15
            pdf.line(30, y, 740, y)
            y -= 10
            return y

        for (partner_name, rango_min, rango_label), invoices in grouped_result:
            # Cambio de cliente: imprime totales del anterior y reinicia acumuladores de cliente
            if current_partner != partner_name:
                if current_partner is not None:
                    y_position = flush_client_totals(y_position)
                current_partner = partner_name
                client_total_monto_bs = client_total_deuda_bs = client_total_monto_usd = client_total_deuda_usd = 0.0

                if y_position < 60:
                    pdf.showPage()
                    y_position = draw_header()

                pdf.setFont("Helvetica-Bold", 10)
                pdf.drawString(30, y_position, f"Cliente: {partner_name}")
                y_position -= 12

            # Título de subgrupo por rango
            if y_position < 60:
                pdf.showPage()
                y_position = draw_header()
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(30, y_position, f"Rango: {rango_label}")
            y_position -= 10
            pdf.setFont("Helvetica", 8)

            # Filas de facturas
            for inv in invoices:
                if y_position < 60:
                    pdf.showPage()
                    y_position = draw_header()

                pdf.drawString(30, y_position, inv.get('date').strftime('%d/%m/%Y') if inv.get('date') else '-')
                pdf.drawString(80, y_position, partner_name or '-')
                pdf.drawString(380, y_position, f"{inv.get('name', '-')}")
                pdf.drawString(415, y_position, f"{inv.get('currency_name', 'N/A')}")
                pdf.drawString(440, y_position, f"{inv.get('monto_bs', 0):,.2f}")
                pdf.drawString(495, y_position, f"{inv.get('deuda_bs', 0):,.2f}")
                pdf.drawString(555, y_position, f"{inv.get('monto_usd', 0):,.2f}")
                pdf.drawString(620, y_position, f"{inv.get('deuda_usd', 0):,.2f}")
                pdf.drawString(680, y_position, f"{inv.get('tax_today', 0):,.2f}")
                days_due = inv.get('days_due') or 0
                pdf.drawString(720, y_position, self._get_due_range_label(days_due))

                # Acumulados por cliente
                client_total_monto_bs += inv.get('monto_bs', 0) or 0.0
                client_total_deuda_bs += inv.get('deuda_bs', 0) or 0.0
                client_total_monto_usd += inv.get('monto_usd', 0) or 0.0
                client_total_deuda_usd += inv.get('deuda_usd', 0) or 0.0

                # Totales generales
                total_monto_bs += inv.get('monto_bs', 0) or 0.0
                total_deuda_bs += inv.get('deuda_bs', 0) or 0.0
                total_monto_usd += inv.get('monto_usd', 0) or 0.0
                total_deuda_usd += inv.get('deuda_usd', 0) or 0.0

                y_position -= 15

        # Totales del último cliente
        y_position = flush_client_totals(y_position)

        # --- Totales generales ---
        if y_position < 100:
            pdf.showPage()
            y_position = draw_header()
        y_position -= 5
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

        # === TABLA RESUMEN POR RANGO DE VENCIMIENTO ===
        from reportlab.platypus import Table, TableStyle, Paragraph
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet

        styles = getSampleStyleSheet()
        normal_style = styles["Normal"]
        normal_style.fontSize = 7
        normal_style.leading = 8

        # 1) Calcular 'resumen' (antes de construir la tabla)
        resumen = {}
        if self.user_id:
            # Reporte por ejecutivo: solo totales por rango
            resumen = {
                'Facturas vigentes': 0.0,
                '1-10 días': 0.0,
                '11-20 días': 0.0,
                '21-30 días': 0.0,
                '+31 días': 0.0,
            }
            for (partner_name, rango_min, rango_label), invoices in grouped_result:
                for inv in invoices:
                    days_due = inv.get('days_due') or 0
                    val = inv.get('deuda_usd', 0.0) or 0.0
                    if days_due <= 0:
                        resumen['Facturas vigentes'] += val
                    elif 1 <= days_due <= 10:
                        resumen['1-10 días'] += val
                    elif 11 <= days_due <= 20:
                        resumen['11-20 días'] += val
                    elif 21 <= days_due <= 30:
                        resumen['21-30 días'] += val
                    elif days_due > 30:
                        resumen['+31 días'] += val
        else:
            # Reporte general: por ejecutivo y rango
            usuarios = {}
            for (partner_name, rango_min, rango_label), invoices in grouped_result:
                for inv in invoices:
                    ejecutivo = inv.get('ejecutivo_name') or 'Sin Ejecutivo'
                    if ejecutivo not in usuarios:
                        usuarios[ejecutivo] = {
                            'Facturas vigentes': 0.0,
                            '1-10 días': 0.0,
                            '11-20 días': 0.0,
                            '21-30 días': 0.0,
                            '+31 días': 0.0,
                        }
                    days_due = inv.get('days_due') or 0
                    val = inv.get('deuda_usd', 0.0) or 0.0
                    if days_due <= 0:
                        usuarios[ejecutivo]['Facturas vigentes'] += val
                    elif 1 <= days_due <= 10:
                        usuarios[ejecutivo]['1-10 días'] += val
                    elif 11 <= days_due <= 20:
                        usuarios[ejecutivo]['11-20 días'] += val
                    elif 21 <= days_due <= 30:
                        usuarios[ejecutivo]['21-30 días'] += val
                    elif days_due > 30:
                        usuarios[ejecutivo]['+31 días'] += val
            resumen = usuarios

        # 2) Construir la tabla (nueva hoja)
        pdf.showPage()
        pdf.setFont("Helvetica-Bold", 14)

        # Título centrado con margen superior
        title = "RESUMEN POR RANGO DE VENCIMIENTO"
        page_width, page_height = pdf._pagesize
        pdf.drawCentredString(page_width/2, page_height - 50, title)

        data = []
        if self.user_id:
            # Reporte filtrado por comercial: solo fila de datos, sin TOTAL
            headers = ["Facturas vigentes", "1-10 días", "11-20 días", "21-30 días", "+31 días"]
            data.append(headers)
            row = [f"{resumen[h]:,.2f}" for h in headers]
            data.append(row)
            col_widths = [120, 120, 120, 120, 120]
            first_data_col = 0

        else:
            headers = ["Ejecutivo", "Facturas vigentes", "1-10 días", "11-20 días", "21-30 días", "+31 días"]
            data.append(headers)
            for ejecutivo, totales in resumen.items():
                ejecutivo_cell = Paragraph(ejecutivo, normal_style)
                row = [ejecutivo_cell] + [f"{totales[h]:,.2f}" for h in headers[1:]]
                data.append(row)
            col_widths = [200, 100, 100, 100, 100, 100]
            first_data_col = 1

            # Fila TOTAL
            totals = ["TOTAL"]
            for i in range(1, len(headers)):
                col_sum = sum(resumen[ej][headers[i]] for ej in resumen)
                totals.append(f"{col_sum:,.2f}")
            data.append(totals)

        table = Table(data, colWidths=col_widths)

        # --- Después de calcular 'data' y 'col_widths' ---
        table = Table(data, colWidths=col_widths)

        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),      # Header más pequeño

            ('FONTSIZE', (0, 1), (-1, -1), 7),     # Cuerpo más pequeño

            ('ALIGN', (first_data_col, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),

            # Padding más compacto para que rinda el espacio
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),

            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ])

        # Colores por rango (igual que tenías)
        style.add('BACKGROUND', (first_data_col + 0, 1), (first_data_col + 1, -2), colors.lightgreen)
        style.add('BACKGROUND', (first_data_col + 2, 1), (first_data_col + 2, -2), colors.lightyellow)
        style.add('BACKGROUND', (first_data_col + 3, 1), (first_data_col + 4, -2), colors.salmon)

        # Fila TOTAL (si aplica)
        if not self.user_id:
            style.add('BACKGROUND', (0, -1), (-1, -1), colors.grey)
            style.add('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke)
            style.add('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')

        table.setStyle(style)

        # Posición: debajo del título
        x_margin = 30
        top_margin = 50   # espacio extra entre el título y la tabla
        y_start = page_height - 80  # 50px del título + 30px de separación
        table.wrapOn(pdf, x_margin, y_start)
        table.drawOn(pdf, x_margin, y_start - table._height)

        # Cerrar PDF
        pdf.save()
        buffer.seek(0)

        pdf_data = base64.b64encode(buffer.getvalue())
        self.write({
            'state': 'get',
            'file_name_pdf': pdf_data,
            'invoice_data': 'cuentas_por_cobrar.pdf'
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice.report.cxc',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'target': 'new',
        }