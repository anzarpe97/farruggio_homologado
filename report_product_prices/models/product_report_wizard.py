from odoo import models, fields, api
from io import BytesIO
import base64
import xlsxwriter
from datetime import datetime, time
from collections import defaultdict
import pytz
from datetime import datetime as dt, time as dtime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

class ProductReportWizard(models.TransientModel):
    _name = 'product.report.wizard'
    _description = 'Reporte de Productos Vendidos'

    date_start = fields.Date(string="Fecha Inicio", required=True)
    date_end = fields.Date(string="Fecha Fin", required=True)
    user_id = fields.Many2one('res.users', string="Comercial")
    partner_id = fields.Many2one('res.partner', string="Cliente")

    # ====  Helper: líneas agrupadas por producto con categoría ====
    def _get_grouped_rows(self):
        """
        Agrupa por producto y agrega la categoría del producto.
        Ahora:
        - Filtra por fecha de factura (account.move.invoice_date) dentro del rango del wizard.
        - Toma precio unitario desde las líneas de factura relacionadas:
            * Si la factura está en VEF -> price_unit_usd = invoice_line.price_unit / move.tax_today
            * Si la factura está en USD -> price_unit_usd = invoice_line.price_unit
        - Hace agregados ponderados por cantidad (price_value_sum = sum(price_unit_usd * qty))
        - Usa SVL asociados a los stock.moves vinculados a las sale.order.line dentro del mismo rango (create_date filtrado por el rango)
        - Devuelve filas por producto con su categoría
        """
        self.ensure_one()

        tz = pytz.timezone('America/Caracas')

        # --- Domain: buscamos sale.order.line que tengan invoice_lines con facturas en el rango ---
        invoice_domain = [
            ('invoice_lines.move_id.invoice_date', '>=', self.date_start),
            ('invoice_lines.move_id.invoice_date', '<=', self.date_end),
            ('invoice_lines.move_id.state', '=', 'posted'),
            ('invoice_lines.move_id.payment_state', '!=', 'reversed'),
            ('invoice_lines.move_id.move_type', 'in', ('out_invoice', 'out_refund')),
        ]
        if self.partner_id:
            invoice_domain.append(('order_id.partner_id', '=', self.partner_id.id))

        lines = self.env['sale.order.line'].search(invoice_domain)
        if not lines:
            return []

        # --- Filtrar stock.moves DONE relacionados ---
        moves = self.env['stock.move'].search([
            ('sale_line_id', 'in', lines.ids),
            ('state', '=', 'done'),
            ('product_id', '!=', False),
        ])
        if not moves:
            return []

        # Solo considerar líneas que tengan al menos un move DONE
        line_ids_with_done_move = {m.sale_line_id.id for m in moves if m.sale_line_id}
        lines = lines.filtered(lambda l: l.id in line_ids_with_done_move)

        # --- Cargar costo por línea de pedido (sale.order.line) ---
        cost_by_line = defaultdict(float)
        for line in lines:
            line_moves = moves.filtered(lambda m: m.sale_line_id.id == line.id)
            for move in line_moves:
                for svl in move.stock_valuation_layer_ids:
                    acc_move = svl.account_move_id
                    if acc_move and acc_move.state == 'posted':
                        cost_lines = acc_move.line_ids.filtered(
                            lambda l: l.product_id == move.product_id and l.debit_usd > 0
                        )
                        for cl in cost_lines:
                            cost_by_line[line.id] += cl.debit_usd or 0.0

        # ==== Agrupado por producto (con categoría incluida) ====
        grouped = defaultdict(lambda: {
            'product_id': 0,
            'product_name': '',
            'categ_name': '',
            'price_value_sum': 0.0,
            'price_unit_avg': 0.0,
            'cost_sum': 0.0,
            'invoiced_sum': 0.0,
            'uom_name': '',
        })

        # Recorrer cada sale.order.line y sus invoice_lines dentro del rango
        for line in lines:
            inv_lines = line.invoice_lines.filtered(
                lambda il: il.move_id and il.move_id.state == 'posted'
                and il.move_id.invoice_date >= self.date_start
                and il.move_id.invoice_date <= self.date_end
            )
            if not inv_lines:
                continue

            total_qty_for_line = 0.0
            total_value_for_line_usd = 0.0

            # Sumar cantidad y valor de cada línea de factura
            for inv_l in inv_lines:
                move = inv_l.move_id
                if not move:
                    continue
                inv_currency = getattr(move, 'currency_id', False)
                cur_name = (inv_currency.name or '').upper() if inv_currency else ''
                inv_price_unit = inv_l.price_unit or 0.0
                qty = inv_l.quantity or 0.0

                # Convertir a USD si factura en VEF usando move.tax_today
                if 'VEF' in cur_name:
                    tax_today = getattr(move, 'tax_today', 1.0)
                    price_unit_usd = inv_price_unit / tax_today if tax_today else inv_price_unit
                else:
                    price_unit_usd = inv_price_unit

                total_qty_for_line += qty
                total_value_for_line_usd += price_unit_usd * qty

            if total_qty_for_line == 0:
                continue

            # Agrupar por producto
            key = line.product_id.id
            g = grouped[key]
            g['product_id'] = line.product_id.id
            g['product_name'] = line.product_id.display_name or line.product_id.name or ''
            g['categ_name'] = line.product_id.categ_id.name or 'Sin categoría'
            g['price_value_sum'] += total_value_for_line_usd
            g['invoiced_sum'] += total_qty_for_line
            g['cost_sum'] += cost_by_line.get(line.id, 0.0)
            g['uom_name'] = line.product_uom.name or ''

        # Calcular precio unitario promedio por producto
        rows = []
        for v in grouped.values():
            invoiced = v.get('invoiced_sum', 0.0)
            price_unit_avg = (v.get('price_value_sum', 0.0) / invoiced) if invoiced else 0.0
            v['price_unit_avg'] = price_unit_avg
            v['price_sum'] = price_unit_avg   # usado como unitario en el Excel
            rows.append(dict(v))

        # Ordenar por categoría y luego por nombre de producto
        rows.sort(key=lambda r: (r['categ_name'] or '', r['product_name'] or ''))
        return rows

    # ==== Excel ====
    def action_export_excel(self):
        self.ensure_one()
        rows = self._get_grouped_rows()

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Productos")

        # Formats
        header_fmt = workbook.add_format({
            'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#34495e',
            'align': 'center', 'valign': 'vcenter', 'border': 1
        })
        data_fmt = workbook.add_format({'border': 1})
        money_fmt = workbook.add_format({'num_format': '$#,##0.00', 'border': 1})
        bold_fmt = workbook.add_format({'bold': True})
        total_fmt = workbook.add_format({'bold': True, 'border': 1})

        # ==== Título principal ====
        title_fmt = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
            'font_color': '#2c3e50'
        })
        sheet.merge_range('A1:H1', 'Reporte de Productos Vendidos', title_fmt)

        # ==== Info de filtros (desplazada) ====
        sheet.write('A3', 'Período:', bold_fmt)
        sheet.write('B3', f"{self.date_start} hasta {self.date_end}")
        sheet.write('A4', 'Generado:', bold_fmt)
        tz = pytz.timezone('America/Caracas')
        now_ve = datetime.now(pytz.UTC).astimezone(tz)
        sheet.write('B4', now_ve.strftime('%d/%m/%Y %H:%M'))
        if self.partner_id:
            sheet.write('A5', 'Cliente:', bold_fmt)
            sheet.write('B5', self.partner_id.name)

        # --- Encabezados ---
        headers = [
            "Categoría",
            "Producto",
            "Precio Unitario (USD)",
            "Costo Unitario (USD)",
            "Entregado",
            "Total de Ventas (USD)",
            "Costo (USD)",
            "Ganancia (USD)",
        ]

        header_row = 6
        for col, title in enumerate(headers):
            sheet.write(header_row, col, title, header_fmt)

        # Column widths
        sheet.set_column(0, 0, 24)  # Categoría
        sheet.set_column(1, 1, 58)  # Producto
        sheet.set_column(2, 3, 20)  # Precio, Costo unitario
        sheet.set_column(4, 4, 12)  # Entregado
        sheet.set_column(5, 7, 20)  # Totales

        sheet.freeze_panes(header_row + 1, 0)

        # Acumuladores de totales
        row = header_row + 1
        total_cost_usd = 0.0
        total_invoiced = 0.0
        total_sales_sum = 0.0
        total_profit_sum = 0.0

        # Filas
        for r in rows:
            price_unit = r.get('price_sum', 0.0)
            qty_invoiced = r.get('invoiced_sum', 0.0)
            cost_total = r.get('cost_sum', 0.0)
            cost_unit = (cost_total / qty_invoiced) if qty_invoiced else 0.0

            total_sales = price_unit * qty_invoiced
            profit = total_sales - cost_total

            sheet.write(row, 0, r.get('categ_name', 'Sin categoría'), data_fmt)
            sheet.write(row, 1, r.get('product_name', ''), data_fmt)
            sheet.write_number(row, 2, price_unit, money_fmt)
            sheet.write_number(row, 3, cost_unit, money_fmt)
            sheet.write_number(row, 4, qty_invoiced, data_fmt)
            sheet.write_number(row, 5, total_sales, money_fmt)
            sheet.write_number(row, 6, cost_total, money_fmt)
            sheet.write_number(row, 7, profit, money_fmt)

            total_cost_usd += cost_total
            total_invoiced += qty_invoiced
            total_sales_sum += total_sales
            total_profit_sum += profit
            row += 1

        # Totales
        sheet.write(row, 0, "TOTAL", total_fmt)

        # Promedios ponderados globales
        avg_price_unit_total = (total_sales_sum / total_invoiced) if total_invoiced else 0.0
        avg_cost_unit_total  = (total_cost_usd / total_invoiced) if total_invoiced else 0.0

        sheet.write_number(row, 2, avg_price_unit_total, money_fmt)
        sheet.write_number(row, 3, avg_cost_unit_total, money_fmt)
        sheet.write_number(row, 4, total_invoiced, data_fmt)
        sheet.write_number(row, 5, total_sales_sum, money_fmt)
        sheet.write_number(row, 6, total_cost_usd, money_fmt)
        sheet.write_number(row, 7, total_profit_sum, money_fmt)

        workbook.close()
        output.seek(0)

        report_name = 'reporte_productos.xlsx'
        export_id = self.env['ir.attachment'].sudo().create({
            'name': report_name,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'product.report.wizard',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{export_id.id}?download=true',
            'target': 'self',
        }

    def action_export_pdf(self):
        # El template QWeb debe llamar a doc._get_grouped_rows() para usar esta misma lógica
        return self.env.ref('report_product_prices.action_product_report_pdf').report_action(self)
