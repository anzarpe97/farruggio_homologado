from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, time
from collections import defaultdict
from io import BytesIO
import base64

# Requiere xlsxwriter instalado en el entorno de Python
import xlsxwriter

MATERIA_PRIMA_KEYWORDS = ['Bovino', 'Porcino', 'Pollo', 'huevo', 'embutido']


class SoldVsPurchasedWizard(models.TransientModel):
    def _get_full_category_name(self, categ):
        """Devuelve la ruta completa de la categoría, incluyendo padres"""
        names = []
        while categ:
            names.insert(0, categ.name)
            categ = categ.parent_id
        return ' / '.join(names)
    _name = 'sold.vs.purchased.wizard'
    _description = 'Productos Vendidos vs Comprados (XLSX sin controllers)'

    start_date = fields.Date(string='Fecha inicio', required=True, default=fields.Date.context_today)
    end_date = fields.Date(string='Fecha fin', required=True, default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='Comercial')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    include_purchase = fields.Boolean(string='Incluir Compras', default=True)
    filter_by_material = fields.Boolean(string='Filtrar por Materia Prima/Viveres', default=False, 
                                      help='Si está marcado, solo se incluirán productos con descripción "materia_prima" o "compra_viveres" en las compras')

    # ---------- Helpers ----------
    def _get_domain_dates(self, date_field):
        """Devuelve dominio inclusivo por fecha/datetime."""
        if not self.start_date or not self.end_date:
            raise UserError(_('Debe indicar el rango de fechas.'))
        if self.end_date < self.start_date:
            raise UserError(_('La fecha fin no puede ser menor que la fecha inicio.'))
        start_dt = datetime.combine(self.start_date, time.min)
        end_dt = datetime.combine(self.end_date, time.max)
        return [(date_field, '>=', start_dt), (date_field, '<=', end_dt)]

    def _fetch_sales(self):
        SaleOrder = self.env['sale.order']
        SaleLine = self.env['sale.order.line']
        domain = [('state', 'in', ['sale', 'done'])]
        domain += self._get_domain_dates('date_order')
        if self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        orders = SaleOrder.search(domain)
        lines = SaleLine.search([('order_id', 'in', orders.ids)])
        rows = []
        for l in lines:
            ref_val = float(getattr(l, 'ref', 0.0) or 0.0)
            unit_val = float(getattr(l, 'ref_unit', 0.0) or 0.0)
            qty_val = float(l.qty_delivered or 0.0)

            if qty_val == 0.0:
                continue

            subtotal = ref_val if ref_val != 0.0 else (unit_val * qty_val)

            # Guardar el id del template y del product
            product_template_id = l.product_template_id.id if l.product_template_id else (l.product_id.product_tmpl_id.id if l.product_id and l.product_id.product_tmpl_id else False)
            product_id = l.product_id.id if l.product_id else False

            rows.append({
                'order': l.order_id.name,
                'order_date': l.order_id.date_order,
                'customer': l.order_id.partner_id.display_name,
                'salesperson': l.order_id.user_id.name if l.order_id.user_id else '',
                'product_template': l.product_template_id.display_name if l.product_template_id else (l.product_id.product_tmpl_id.display_name if l.product_id and l.product_id.product_tmpl_id else ''),
                'product_template_id': product_template_id,
                'product_variant': l.product_id.display_name if l.product_id else '',
                'product_id': product_id,
                'qty': qty_val,
                'subtotal': subtotal,
                'currency': l.order_id.currency_id.name if l.order_id.currency_id else '',
            })
        return rows

    def _fetch_purchases(self):
        PurchaseOrder = self.env['purchase.order']
        PurchaseLine = self.env['purchase.order.line']
        
        # PO confirmadas
        domain = [('state', 'in', ['purchase', 'done'])]
        # Usar date_approve si existe
        date_field = 'date_approve' if 'date_approve' in PurchaseOrder._fields else 'date_order'
        domain += self._get_domain_dates(date_field)
        
        # Buscar todas las órdenes en el rango de fechas
        orders = PurchaseOrder.search(domain)
        
        # Aplicar filtro de materia prima si está activado
        if self.filter_by_material:
            # Buscar productos que contengan las palabras clave de materia prima
            Product = self.env['product.product']
            prod_domain = []
            for keyword in MATERIA_PRIMA_KEYWORDS:
                if prod_domain:
                    prod_domain.insert(0, '|')
                prod_domain.extend(['name', 'ilike', keyword])
            products = Product.search(prod_domain)
            if products:
                # Filtrar solo líneas que tengan estos productos
                lines_domain = [('order_id', 'in', orders.ids), ('product_id', 'in', products.ids)]
            else:
                lines_domain = [('order_id', 'in', orders.ids), ('product_id', '=', False)]
            lines = PurchaseLine.search(lines_domain)
        else:
            # Sin filtro, incluir todas las líneas
            lines = PurchaseLine.search([('order_id', 'in', orders.ids)])

        # Recalcular subtotal según regla:
        # - Si ref == 0 (o None), usar ref_unit * qty_received
        # - Si ref != 0, usar ref
        rows = []
        for l in lines:
            ref_val = float(getattr(l, 'ref', 0.0) or 0.0)
            unit_val = float(getattr(l, 'ref_unit', 0.0) or 0.0)
            qty_val = float(l.qty_received or 0.0)
            price_unit = float(getattr(l, 'price_unit', 0.0) or 0.0)
            tax_today = float(getattr(l.order_id, 'tax_today', 1.0) or 1.0)

            if qty_val == 0.0:
                continue

            if ref_val != 0.0:
                subtotal = ref_val
            else:
                if unit_val != 0.0:
                    subtotal = unit_val * qty_val
                else:
                    subtotal = (qty_val * price_unit) / tax_today if tax_today != 0 else 0.0

            # Guardar el id del template y del product
            product_template_id = l.product_id.product_tmpl_id.id if l.product_id and l.product_id.product_tmpl_id else False
            product_id = l.product_id.id if l.product_id else False

            rows.append({
                'order': l.order_id.name,
                'order_date': getattr(l.order_id, 'date_approve', False) or l.order_id.date_order,
                'vendor': l.order_id.partner_id.display_name,
                'product': l.product_id.display_name if l.product_id else '',
                'product_template_id': product_template_id,
                'product_id': product_id,
                'qty': qty_val,
                'subtotal': subtotal,
                'currency': l.order_id.currency_id.name if l.order_id.currency_id else '',
                'x_descripcion': getattr(l.order_id, 'x_descripcion', 'N/A') or 'N/A',
            })
        return rows

    # ---------- XLSX (sin controller): crear attachment y devolver act_url ----------
    def action_export_xlsx(self):
        self.ensure_one()

        sales_rows = self._fetch_sales()
        purchase_rows = self._fetch_purchases() if self.include_purchase else []

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        fmt_h = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        fmt_h.set_text_wrap()
        fmt_b = workbook.add_format({'align': 'left', 'valign': 'vcenter'})
        fmt_n = workbook.add_format({'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0.00'})
        fmt_t = workbook.add_format({'bold': True, 'align': 'left', 'valign': 'vcenter', 'font_size': 14})
        fmt_curr = workbook.add_format({'align': 'right', 'valign': 'vcenter', 'num_format': '#,##0.00'})
        fmt_dt = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm'})

        # --- Hoja: Vendidos ---
        sh = workbook.add_worksheet(_('Vendidos'))
        sh.freeze_panes(4, 0)
        # Estilo mejorado para el título principal
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'font_color': 'white',
            'bg_color': "#174188",
            'align': 'center',
            'valign': 'vcenter',
            'border': 2,
            'border_color': '#1F4E79',
            'text_wrap': True
        })
        sh.merge_range(0, 0, 0, 7, _('Productos Vendidos'), title_format)
        # Estilo mejorado para la información de rango de fechas
        date_info_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'font_color': '#404040',
            'bg_color': '#F2F2F2',
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#D9D9D9'
        })
        date_value_format = workbook.add_format({
            'font_size': 12,
            'font_color': '#404040',
            'bg_color': '#FFFFFF',
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#D9D9D9'
        })
        sh.write(1, 0, _('Rango de fechas:'), date_info_format)
        sh.write(1, 1, f"{self.start_date} a {self.end_date}", date_value_format)
        
        # Información adicional del reporte
        info_format = workbook.add_format({
            'font_size': 11,
            'font_color': '#404040',
            'align': 'left',
            'valign': 'vcenter'
        })
        
        if self.user_id:
            sh.write(2, 0, _('Comercial:'), date_info_format)
            sh.write(2, 1, self.user_id.name, date_value_format)
        else:
            sh.write(2, 0, _('Comercial:'), date_info_format)
            sh.write(2, 1, _('Todos'), date_value_format)
        headers = [_('Orden'), _('Fecha'), _('Cliente'), _('Comercial'), _('Producto (Plantilla)'), _('Variante'), _('Cant. Vendida'), _('Subtotal')]
        
        # Estilos mejorados para encabezado
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'bg_color': '#5B9BD5',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#FFFFFF'
        })
        
        # Estilos para datos
        data_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10
        })
        
        number_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': '#,##0.00'
        })
        
        date_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': 'yyyy-mm-dd'
        })
        
        currency_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': '$#,##0.00'
        })
        
        # Estilo para totales
        total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#F2F2F2',
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': '#,##0.00'
        })
        
        for c, h in enumerate(headers):
            sh.write(3, c, h, header_format)

        row = 4
        tot_qty = tot_sub = 0.0
        for r in sales_rows:
            sh.write(row, 0, r['order'], data_format)
            if r['order_date']:
                try:
                    sh.write_datetime(row, 1, r['order_date'], date_format)
                except Exception:
                    sh.write(row, 1, str(r['order_date']), data_format)
            else:
                sh.write(row, 1, '', data_format)
            sh.write(row, 2, r['customer'], data_format)
            sh.write(row, 3, r['salesperson'], data_format)
            sh.write(row, 4, r['product_template'], data_format)
            sh.write(row, 5, r['product_variant'], data_format)
            sh.write_number(row, 6, r['qty'] or 0.0, number_format)
            sh.write_number(row, 7, r['subtotal'] or 0.0, currency_format)
            tot_qty += r['qty'] or 0.0
            tot_sub += r['subtotal'] or 0.0
            row += 1

        sh.write(row, 5, _('Totales:'), total_format)
        sh.write_formula(row, 6, f'SUBTOTAL(9,G5:G{row})', total_format)
        sh.write_formula(row, 7, f'SUBTOTAL(9,H5:H{row})', total_format)
        sh.autofilter(3, 0, row-1, len(headers)-1)
        widths = [15, 18, 28, 18, 30, 28, 15, 18]
        for i, w in enumerate(widths):
            sh.set_column(i, i, w)

        # --- Hoja: Comprados ---
        sh2 = workbook.add_worksheet(_('Comprados'))
        sh2.freeze_panes(4, 0)
        # Estilo mejorado para el título principal de compras
        title_format_purchase = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'font_color': 'white',
            'bg_color': '#174188',
            'align': 'center',
            'valign': 'vcenter',
            'border': 2,
            'border_color': '#1F4E79',
            'text_wrap': True
        })
        sh2.merge_range(0, 0, 0, 6, _('Productos Comprados'), title_format_purchase)
        sh2.write(1, 0, _('Rango de fechas:'), date_info_format)
        sh2.write(1, 1, f"{self.start_date} a {self.end_date}", date_value_format)
        
        # Información adicional del reporte
        if self.filter_by_material:
            sh2.write(2, 0, _('Filtro aplicado:'), date_info_format)
            sh2.write(2, 1, _('Materia Prima y Compra de Viveres'), date_value_format)
        else:
            sh2.write(2, 0, _('Filtro aplicado:'), date_info_format)
            sh2.write(2, 1, _('Todos los productos'), date_value_format)
        headers2 = [_('Orden'), _('Fecha'), _('Proveedor'), _('Producto'), _('Cant. Comprada'), _('Subtotal'), _('Descripción')]
        
        # Estilos mejorados para encabezado
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'bg_color': '#5B9BD5',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#FFFFFF'
        })
        
        # Estilos para datos
        data_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10
        })
        
        number_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': '#,##0.00'
        })
        
        date_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': 'yyyy-mm-dd'
        })
        
        currency_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': '$#,##0.00'
        })
        
        for c, h in enumerate(headers2):
            sh2.write(3, c, h, header_format)

        # Filtrar compras con x_description = 'materia_prima' o 'compra_viveres'
        filtered_purchase_rows = [r for r in purchase_rows if r.get('x_descripcion', '').lower() in ['materia_prima', 'compra_viveres']]
        
        row = 4
        tot_qty = tot_sub = 0.0
        for r in filtered_purchase_rows:
            sh2.write(row, 0, r['order'], data_format)
            if r['order_date']:
                try:
                    sh2.write_datetime(row, 1, r['order_date'], date_format)
                except Exception:
                    sh2.write(row, 1, str(r['order_date']), data_format)
            else:
                sh2.write(row, 1, '', data_format)
            sh2.write(row, 2, r['vendor'], data_format)
            sh2.write(row, 3, r['product'], data_format)
            sh2.write_number(row, 4, r['qty'] or 0.0, number_format)
            sh2.write_number(row, 5, r['subtotal'] or 0.0, currency_format)
            sh2.write(row, 6, r['x_descripcion'], data_format)
            tot_qty += r['qty'] or 0.0
            tot_sub += r['subtotal'] or 0.0
            row += 1

        sh2.write(row, 3, _('Totales:'), fmt_h)
        sh2.write_formula(row, 4, f'SUBTOTAL(9,E5:E{row})', fmt_n)
        sh2.write_formula(row, 5, f'SUBTOTAL(9,F5:F{row})', fmt_curr)
        sh2.autofilter(3, 0, row-1, len(headers2)-1)
        widths2 = [15, 18, 28, 30, 15, 18, 22]
        for i, w in enumerate(widths2):
            sh2.set_column(i, i, w)

        # --- Hoja: Vendido vs Comprado (comparativo) ---
        sh3 = workbook.add_worksheet(_('Vendido vs Comprado'))
        sh3.freeze_panes(4, 0)
        # Estilo mejorado para el título principal del comparativo
        title_format_compare = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'font_color': 'white',
            'bg_color': '#C55A11',
            'align': 'center',
            'valign': 'vcenter',
            'border': 2,
            'border_color': '#974706',
            'text_wrap': True
        })
        sh3.merge_range(0, 0, 0, 6, _('Comparativo: Vendido vs Comprado'), title_format_compare)
        sh3.write(1, 0, _('Rango de fechas:'), date_info_format)
        sh3.write(1, 1, f"{self.start_date} a {self.end_date}", date_value_format)
        
        # Información adicional del reporte
        if self.user_id:
            sh3.write(2, 0, _('Comercial:'), date_info_format)
            sh3.write(2, 1, self.user_id.name, date_value_format)
        else:
            sh3.write(2, 0, _('Comercial:'), date_info_format)
            sh3.write(2, 1, _('Todos'), date_value_format)
        headers3 = [
            _('Categoría'), _('Producto (Plantilla/Nombre)'), _('Cant. Vendida'), _('Subtotal Venta'),
            _('Cant. Comprada'), _('Subtotal Compra'),
            _('∆ Cantidad (V-C)'), _('∆ Subtotal (V-C)')
        ]
        
        # Estilos mejorados para encabezado
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'bg_color': '#70AD47',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#FFFFFF'
        })
        
        # Estilos para datos
        data_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10
        })
        
        number_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': '#,##0.00'
        })
        
        currency_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': '$#,##0.00'
        })
        
        # Estilo para diferencias (con colores según signo)
        positive_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': '#,##0.00',
            'font_color': '#006100',
            'bg_color': '#C6EFCE'
        })
        
        negative_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#E7E6E6',
            'font_size': 10,
            'num_format': '#,##0.00',
            'font_color': '#9C0006',
            'bg_color': '#FFC7CE'
        })
        
        for c, h in enumerate(headers3):
            sh3.write(3, c, h, header_format)

        # Filtrar compras para el comparativo (materia prima o compra de viveres)
        filtered_purchase_rows = [r for r in purchase_rows if r.get('x_descripcion', '').lower() in ['materia_prima', 'compra_viveres']]

        # --- Agrupar por categoría ---
        # Para ventas, obtener categ_id de product_template
        sales_agg = defaultdict(lambda: {'qty': 0.0, 'subtotal': 0.0, 'category': _('Sin categoría')})
        for r in sales_rows:
            category_name = _('Sin categoría')
            pt = None
            prod = None
            # Buscar por id de product_template
            if r.get('product_template_id'):
                pt = self.env['product.template'].browse(r['product_template_id'])
            # Si no se encontró, buscar por id de product.product
            if not pt or not pt.exists():
                if r.get('product_id'):
                    prod = self.env['product.product'].browse(r['product_id'])
                    if prod.exists() and prod.categ_id:
                        category_name = self._get_full_category_name(prod.categ_id)
            if pt and pt.exists() and pt.categ_id:
                category_name = self._get_full_category_name(pt.categ_id)
            key = (category_name, r['product_template'] or r['product_variant'] or 'N/A')
            sales_agg[key]['qty'] += r['qty'] or 0.0
            sales_agg[key]['subtotal'] += r['subtotal'] or 0.0
            sales_agg[key]['category'] = category_name

        # Para compras, buscar por id de product_template/product y obtener la categoría completa
        purch_agg = defaultdict(lambda: {'qty': 0.0, 'subtotal': 0.0, 'category': _('Sin categoría')})
        for r in filtered_purchase_rows:
            category_name = _('Sin categoría')
            pt = None
            prod = None
            if r.get('product_template_id'):
                pt = self.env['product.template'].browse(r['product_template_id'])
            if not pt or not pt.exists():
                if r.get('product_id'):
                    prod = self.env['product.product'].browse(r['product_id'])
                    if prod.exists() and prod.categ_id:
                        category_name = self._get_full_category_name(prod.categ_id)
            if pt and pt.exists() and pt.categ_id:
                category_name = self._get_full_category_name(pt.categ_id)
            key = (category_name, r['product'] or 'N/A')
            purch_agg[key]['qty'] += r['qty'] or 0.0
            purch_agg[key]['subtotal'] += r['subtotal'] or 0.0
            purch_agg[key]['category'] = category_name

        all_keys = set(sales_agg.keys()) | set(purch_agg.keys())
        row = 4
        for k in sorted(all_keys):
            category, product_name = k
            s_qty = sales_agg.get(k, {}).get('qty', 0.0)
            s_sub = sales_agg.get(k, {}).get('subtotal', 0.0)
            p_qty = purch_agg.get(k, {}).get('qty', 0.0)
            p_sub = purch_agg.get(k, {}).get('subtotal', 0.0)

            delta_qty = s_qty - p_qty
            delta_sub = s_sub - p_sub

            sh3.write(row, 0, category, data_format)
            sh3.write(row, 1, product_name, data_format)
            sh3.write_number(row, 2, s_qty, number_format)
            sh3.write_number(row, 3, s_sub, currency_format)
            sh3.write_number(row, 4, p_qty, number_format)
            sh3.write_number(row, 5, p_sub, currency_format)

            # Aplicar colores según el signo de la diferencia
            if delta_qty >= 0:
                sh3.write_number(row, 6, delta_qty, positive_format)
            else:
                sh3.write_number(row, 6, delta_qty, negative_format)

            if delta_sub >= 0:
                sh3.write_number(row, 7, delta_sub, positive_format)
            else:
                sh3.write_number(row, 7, delta_sub, negative_format)

            row += 1

        sh3.autofilter(3, 0, row, len(headers3)-1)
        widths3 = [22, 40, 16, 18, 16, 18, 16, 18]
        for i, w in enumerate(widths3):
            sh3.set_column(i, i, w)

        # Cerrar libro y crear attachment
        workbook.close()
        output.seek(0)
        filename = f"Vendido_vs_Comprado_{self.start_date}_{self.end_date}.xlsx"

        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        # Devolver descarga directa del attachment
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_export_xlsx_and_reload(self):
        """
        Método alternativo que descarga y luego recarga el wizard
        para permitir cambios inmediatos sin salir
        """
        self.ensure_one()
        
        # Primero descargar
        download_action = self.action_export_xlsx()
        
        # Luego crear un nuevo wizard con los mismos valores pero nuevo ID
        new_wizard = self.create({
            'start_date': self.start_date,
            'end_date': self.end_date,
            'user_id': self.user_id.id if self.user_id else False,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'include_purchase': self.include_purchase,
            'filter_by_material': self.filter_by_material,
        })
        
        # Devolver acción para abrir el nuevo wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Productos Vendidos vs Comprados'),
            'res_model': 'sold.vs.purchased.wizard',
            'view_mode': 'form',
            'res_id': new_wizard.id,
            'target': 'new',
            'context': dict(self.env.context),
        }
