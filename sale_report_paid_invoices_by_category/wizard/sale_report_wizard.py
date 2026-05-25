from odoo import models, fields
import io
import base64
import xlsxwriter

class SaleReportWizard(models.TransientModel):
    _name = 'sale.report.wizard'
    _description = 'Reporte de Facturas Pagadas por Categoría'

    date_from = fields.Date("Desde", required=True)
    date_to = fields.Date("Hasta", required=True)
    user_id = fields.Many2one('res.users', string="Comercial", required=False)

    def generate_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Facturas por días")

        # FORMATOS
        header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#D9D9D9', 'border': 1, 'font_size': 12
        })
        bold_center = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        normal_center = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
        number_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1, 'align': 'right'})

        worksheet.set_column("A:A", 20)
        worksheet.set_column("B:B", 15)
        worksheet.set_column("C:C", 30)
        worksheet.set_column("D:G", 14)

        def write_commercial_block(invoices, user, start_row):
            comercial = user.name if user else 'Todos los comerciales'
            equipo = user.sale_team_id.name if user and user.sale_team_id else 'Todos los equipos'
            titulo = f"{equipo.upper()} - {comercial.upper()}"
            worksheet.merge_range(start_row, 0, start_row, 6, titulo, header_format)
            start_row += 1

            worksheet.merge_range(start_row, 0, start_row + 1, 0, "Zona", bold_center)
            worksheet.merge_range(start_row, 1, start_row + 1, 1, "Indicador", bold_center)
            worksheet.merge_range(start_row, 2, start_row + 1, 2, "Rubro", bold_center)
            worksheet.write(start_row, 3, "1-10 días", bold_center)
            worksheet.write(start_row, 4, "11-20 días", bold_center)
            worksheet.write(start_row, 5, "21-30 días", bold_center)
            worksheet.write(start_row, 6, "Más de 31 días", bold_center)
            for col in range(3, 7):
                worksheet.write(start_row + 1, col, "", bold_center)

            row = start_row + 2
            data = {}

            nc_map = {}
            refunds = self.env['account.move'].search([
                ('move_type', '=', 'out_refund'),
                ('reversed_entry_id', 'in', invoices.ids),
                ('state', '=', 'posted'),
            ])
            for refund in refunds:
                origin = refund.reversed_entry_id.id
                nc_map.setdefault(origin, []).append(refund)

            for invoice in invoices:
                related_refunds = nc_map.get(invoice.id, [])
                invoice_total_subtotal = 0.0
                for line in invoice.invoice_line_ids:
                    line_subtotal = line.price_subtotal
                    if invoice.currency_id.name == 'VEF' and invoice.tax_today:
                        line_subtotal = line_subtotal / invoice.tax_today
                    invoice_total_subtotal += line_subtotal

                has_pronto_pago = False
                has_negociacion = False
                for refund in related_refunds:
                    for refund_line in refund.line_ids:
                        acc_name = (refund_line.account_id.name or '').upper()
                        if 'DESCUENTO PRONTO PAGO' in acc_name:
                            has_pronto_pago = True
                        elif 'DESCUENTOS EN VENTAS' in acc_name:
                            has_negociacion = True

                for line in invoice.invoice_line_ids:
                    if not invoice.invoice_date or not invoice.last_payment_date:
                        continue

                    delta_days = (invoice.last_payment_date - invoice.invoice_date).days
                    category = line.product_id.categ_id.name or 'Sin categoría'
                    subtotal = line.price_subtotal
                    if invoice.currency_id.name == 'VEF' and invoice.tax_today:
                        subtotal = subtotal / invoice.tax_today

                    amount = subtotal

                    # 1️⃣ Devolución
                    devolucion_total = 0.0
                    for refund in related_refunds:
                        for refund_line in refund.invoice_line_ids:
                            if refund_line.product_id == line.product_id:
                                refund_subtotal = refund_line.price_subtotal
                                if refund.currency_id.name == 'VEF' and refund.tax_today:
                                    refund_subtotal = refund_subtotal / refund.tax_today
                                devolucion_total += abs(refund_subtotal)
                    amount -= devolucion_total

                    # 2️⃣ Descuento por pronto pago
                    if has_pronto_pago:
                        amount -= amount * 0.03

                    # 3️⃣ Descuento por negociación
                    if has_negociacion:
                        amount -= amount * 0.25

                    if category not in data:
                        data[category] = [0, 0, 0, 0]

                    if 0 <= delta_days <= 10:
                        data[category][0] += amount
                    elif 11 <= delta_days <= 20:
                        data[category][1] += amount
                    elif 21 <= delta_days <= 30:
                        data[category][2] += amount
                    elif delta_days > 30:
                        data[category][3] += amount

            # Obtener el equipo de ventas del comercial usando sale.order.team_id
            team_name = None
            if user:
                sale_order = self.env['sale.order'].search([('user_id', '=', user.id)], limit=1)
                team_name = sale_order.team_id.name if sale_order and sale_order.team_id else 'Sin equipo'
            else:
                team_name = 'Todos los equipos'

            for category, values in sorted(data.items()):
                worksheet.write(row, 0, team_name, normal_center)
                worksheet.write(row, 1, "ICO", normal_center)
                worksheet.write(row, 2, category, normal_center)
                for col, val in enumerate(values, start=3):
                    worksheet.write_number(row, col, val, number_format)
                row += 1

            total_1_10 = sum([v[0] for v in data.values()])
            total_11_20 = sum([v[1] for v in data.values()])
            total_21_30 = sum([v[2] for v in data.values()])
            total_31_plus = sum([v[3] for v in data.values()])
            worksheet.merge_range(row, 0, row, 2, "TOTAL", bold_center)
            worksheet.write_number(row, 3, total_1_10, number_format)
            worksheet.write_number(row, 4, total_11_20, number_format)
            worksheet.write_number(row, 5, total_21_30, number_format)
            worksheet.write_number(row, 6, total_31_plus, number_format)

            return row + 2

        # Filtrar por fecha del pago en vez de fecha de factura
        base_domain = [
            ('move_type', '=', 'out_invoice'),
            ('payment_state', '=', 'paid'),
            ('last_payment_date', '>=', self.date_from),
            ('last_payment_date', '<=', self.date_to),
        ]

        if self.user_id:
            invoices = self.env['account.move'].search(base_domain + [('invoice_user_id', '=', self.user_id.id)])
            write_commercial_block(invoices, self.user_id, start_row=0)
        else:
            all_invoices = self.env['account.move'].search(base_domain)
            user_ids = all_invoices.mapped('invoice_user_id')
            current_row = 0
            for user in user_ids:
                user_invoices = all_invoices.filtered(lambda inv: inv.invoice_user_id == user)
                current_row = write_commercial_block(user_invoices, user, current_row)

        workbook.close()
        output.seek(0)
        report_file = self.env['ir.attachment'].create({
            'name': 'reporte_facturas_ajustado.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'sale.report.wizard',
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{report_file.id}?download=true",
            'target': 'self',
        }
