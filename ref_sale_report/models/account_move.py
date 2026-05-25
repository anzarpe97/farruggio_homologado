from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Puedes agregar campos calculados a nivel de factura si lo necesitas
    # Por ejemplo, el costo total de todos los productos
    total_cost = fields.Monetary(
        string="Costo Total",
        compute="_compute_total_cost",
        currency_field='currency_id',
        store=True,
        help="Suma de los costos de todas las líneas de la factura"
    )

    total_cost_usd = fields.Float(
        string="Costo Total (USD)",
        compute="_compute_total_cost_usd",
        store=True,
        digits=(16, 2),
        help="Suma de los costos en USD de todas las líneas de la factura"
    )

    @api.depends('invoice_line_ids.sale_line_cost')
    def _compute_total_cost(self):
        """Calcula el costo total sumando los costos de todas las líneas"""
        for move in self:
            move.total_cost = sum(move.invoice_line_ids.mapped('sale_line_cost'))

    @api.depends('invoice_line_ids.total_cost_usd')
    def _compute_total_cost_usd(self):
        """Calcula el costo total en USD sumando los costos en USD de todas las líneas"""
        for move in self:
            move.total_cost_usd = sum(move.invoice_line_ids.mapped('total_cost_usd'))

    def action_recalculate_costs(self):
        """
        Método manual para recalcular los costos de las facturas seleccionadas.
        Útil para actualizar facturas existentes.
        """
        for move in self:
            # Forzar recálculo de las líneas de factura
            move.invoice_line_ids._compute_sale_line_cost()
            move.invoice_line_ids._compute_sale_line_cost_usd()
            move.invoice_line_ids._compute_price_unit_ref()
            move.invoice_line_ids._compute_total_cost()
            move.invoice_line_ids._compute_total_cost_usd()
            move.invoice_line_ids._compute_margin()
            
            # Recalcular totales de la factura
            move._compute_total_cost()
            move._compute_total_cost_usd()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Recálculo completado',
                'message': f'Se han recalculado los costos de {len(self)} factura(s)',
                'type': 'success',
                'sticky': False,
            }
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    sale_line_cost = fields.Monetary(
        string="Costo del Pedido",
        currency_field='currency_id',
        compute="_compute_sale_line_cost",
        store=True,
        help="Costo unitario del producto tomado del pedido de venta"
    )

    sale_line_cost_usd = fields.Float(
        string="Costo del Pedido (USD)",
        compute="_compute_sale_line_cost_usd",
        store=True,
        digits=(16, 2),
        help="Costo unitario del producto en USD según la tasa del pedido de venta"
    )

    total_cost = fields.Monetary(
        string="Costo Total Línea",
        currency_field='currency_id',
        compute="_compute_total_cost",
        store=True,
        help="Costo total de la línea (costo unitario x cantidad)"
    )

    total_cost_usd = fields.Float(
        string="Costo Total Línea (USD)",
        compute="_compute_total_cost_usd",
        store=True,
        digits=(16, 2),
        help="Costo total de la línea en USD según la tasa del pedido de venta"
    )

    price_unit_ref = fields.Float(
        string="Precio Unitario (USD)",
        compute="_compute_price_unit_ref",
        store=True,
        digits=(16, 2),
        help="Precio unitario en USD según la tasa del pedido de venta"
    )

    margin = fields.Float(
        string="Margen (USD)",
        compute="_compute_margin",
        store=True,
        digits=(16, 2),
        help="Diferencia entre el precio unitario USD y el costo USD (price_unit_ref - sale_line_cost_usd)"
    )

    margin_percent = fields.Float(
        string="Margen %",
        compute="_compute_margin",
        store=True,
        help="Porcentaje de margen sobre el precio de venta"
    )

    @api.depends('sale_line_ids', 'sale_line_ids.purchase_price', 'product_id', 'product_id.standard_price', 
                 'move_id.partner_id', 'move_id.invoice_origin')
    def _compute_sale_line_cost(self):
        """
        Obtiene el costo del producto desde la línea del pedido de venta.
        
        CASO ESPECIAL PDVSA:
        - Si el cliente es PDVSA Petroleos y la factura tiene invoice_origin con múltiples pedidos
        - Lee todos los pedidos separados por coma en invoice_origin
        - Suma el costo total de todas las líneas de todos esos pedidos
        - Asigna ese costo total a la línea de servicio
        
        CASO NORMAL:
        1. Campo purchase_price de la línea de pedido de venta (costo al momento de la venta)
        2. Costo estándar del producto actual (standard_price)
        """
        for line in self:
            cost = 0.0
            
            # Solo calcular para líneas de producto (no secciones ni notas)
            if line.display_type in ('line_section', 'line_note'):
                line.sale_line_cost = 0.0
                continue
            
            # CASO ESPECIAL: Verificar si es factura de PDVSA Petroleos
            is_pdvsa = False
            if line.move_id and line.move_id.partner_id:
                partner_name = line.move_id.partner_id.name or ''
                if 'PDVSA' in partner_name.upper() and 'PETROLEO' in partner_name.upper():
                    is_pdvsa = True
            
            # Si es PDVSA y tiene invoice_origin con pedidos múltiples
            if is_pdvsa and line.move_id and line.move_id.invoice_origin:
                try:
                    # Obtener los nombres de los pedidos desde invoice_origin (separados por coma)
                    order_names = [name.strip() for name in line.move_id.invoice_origin.split(',')]
                    
                    # Buscar todos los pedidos de venta por sus nombres
                    sale_orders = self.env['sale.order'].search([('name', 'in', order_names)])
                    
                    if sale_orders:
                        # Sumar el costo total en moneda local de todas las líneas de todos los pedidos
                        total_cost_all_orders = 0.0
                        for order in sale_orders:
                            for order_line in order.order_line:
                                # Solo líneas de producto
                                if order_line.display_type not in ('line_section', 'line_note'):
                                    line_cost = 0.0
                                    if hasattr(order_line, 'purchase_price') and order_line.purchase_price:
                                        line_cost = order_line.purchase_price
                                    elif order_line.product_id:
                                        line_cost = order_line.product_id.standard_price
                                    # Multiplicar por la cantidad
                                    total_cost_all_orders += line_cost * order_line.product_uom_qty
                        
                        # Asignar el costo total como costo unitario (se multiplicará por cantidad después)
                        # Dividir entre la cantidad de la línea de factura para obtener costo unitario
                        if line.quantity and line.quantity != 0:
                            cost = total_cost_all_orders / line.quantity
                        else:
                            cost = total_cost_all_orders
                        
                        line.sale_line_cost = cost
                        continue
                except Exception as e:
                    # Si hay error, continuar con el método normal
                    pass
            
            # CASO NORMAL: Obtener el costo desde el campo purchase_price de las líneas de pedido de venta
            try:
                if line.sale_line_ids:
                    # Obtener el costo de la primera línea de venta relacionada
                    sale_line = line.sale_line_ids[0]
                    purchase_price = sale_line.purchase_price
                    if purchase_price:
                        cost = purchase_price
            except Exception:
                # Si hay cualquier error durante el acceso al campo, continuar con el fallback
                pass
            
            # Si no hay línea de venta o no tiene purchase_price, usar el costo estándar del producto
            if not cost and line.product_id:
                try:
                    cost = line.product_id.standard_price
                except Exception:
                    cost = 0.0
            
            line.sale_line_cost = cost

    @api.depends('price_unit', 'sale_line_ids', 'sale_line_ids.order_id', 'sale_line_ids.order_id.tax_today',
                 'move_id.partner_id', 'move_id.invoice_origin')
    def _compute_price_unit_ref(self):
        """
        Calcula el precio unitario en USD dividiendo el precio entre la tasa del pedido de venta.
        Si no hay tasa o es 0, usa 1 como tasa por defecto.
        
        Para PDVSA: usa la tasa del primer pedido encontrado en invoice_origin.
        """
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                line.price_unit_ref = 0.0
                continue
            
            # Obtener la tasa del pedido de venta
            tax_rate = 1.0
            
            # CASO ESPECIAL PDVSA: Verificar si es factura de PDVSA Petroleos
            is_pdvsa = False
            if line.move_id and line.move_id.partner_id:
                partner_name = line.move_id.partner_id.name or ''
                if 'PDVSA' in partner_name.upper() and 'PETROLEO' in partner_name.upper():
                    is_pdvsa = True
            
            # Si es PDVSA, obtener la tasa del primer pedido en invoice_origin
            if is_pdvsa and line.move_id and line.move_id.invoice_origin:
                try:
                    order_names = [name.strip() for name in line.move_id.invoice_origin.split(',')]
                    if order_names:
                        # Buscar el primer pedido
                        first_order = self.env['sale.order'].search([('name', '=', order_names[0])], limit=1)
                        if first_order and first_order.tax_today:
                            tax_rate = first_order.tax_today
                except Exception:
                    pass
            
            # Caso normal: obtener tasa del pedido relacionado
            if tax_rate == 1.0 and line.sale_line_ids:
                # Tomar la tasa del primer pedido de venta relacionado
                sale_order = line.sale_line_ids[0].order_id
                if sale_order and sale_order.tax_today:
                    tax_rate = sale_order.tax_today
            
            # Calcular el precio unitario en USD
            if tax_rate and tax_rate != 0:
                line.price_unit_ref = line.price_unit / tax_rate
            else:
                line.price_unit_ref = line.price_unit

    @api.depends('sale_line_cost', 'sale_line_ids', 'sale_line_ids.order_id', 'sale_line_ids.order_id.tax_today',
                 'move_id.partner_id', 'move_id.invoice_origin')
    def _compute_sale_line_cost_usd(self):
        """
        Calcula el costo unitario en USD dividiendo el costo entre la tasa del pedido de venta.
        Si no hay tasa o es 0, usa 1 como tasa por defecto.
        
        Para PDVSA: Calcula directamente sumando (costo * cantidad / tasa) de cada línea de todos los pedidos.
        """
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                line.sale_line_cost_usd = 0.0
                continue
            
            # CASO ESPECIAL PDVSA: Verificar si es factura de PDVSA Petroleos
            is_pdvsa = False
            if line.move_id and line.move_id.partner_id:
                partner_name = line.move_id.partner_id.name or ''
                if 'PDVSA' in partner_name.upper() and 'PETROLEO' in partner_name.upper():
                    is_pdvsa = True
            
            # Si es PDVSA, calcular el costo total en USD de todos los pedidos
            if is_pdvsa and line.move_id and line.move_id.invoice_origin:
                try:
                    order_names = [name.strip() for name in line.move_id.invoice_origin.split(',')]
                    sale_orders = self.env['sale.order'].search([('name', 'in', order_names)])
                    
                    if sale_orders:
                        # Sumar: (costo * cantidad / tasa) de cada línea
                        total_cost_usd = 0.0
                        for order in sale_orders:
                            tax_rate = order.tax_today if order.tax_today else 1.0
                            for order_line in order.order_line:
                                if order_line.display_type not in ('line_section', 'line_note'):
                                    # Obtener el costo de la línea
                                    line_cost = 0.0
                                    if hasattr(order_line, 'purchase_price') and order_line.purchase_price:
                                        line_cost = order_line.purchase_price
                                    elif order_line.product_id:
                                        line_cost = order_line.product_id.standard_price
                                    
                                    # Calcular: costo * cantidad / tasa
                                    if tax_rate and tax_rate != 0:
                                        total_cost_usd += (line_cost * order_line.product_uom_qty) / tax_rate
                                    else:
                                        total_cost_usd += line_cost * order_line.product_uom_qty
                        
                        # Dividir entre la cantidad de la línea de factura para obtener costo unitario USD
                        if line.quantity and line.quantity != 0:
                            line.sale_line_cost_usd = total_cost_usd / line.quantity
                        else:
                            line.sale_line_cost_usd = total_cost_usd
                        
                        continue
                except Exception as e:
                    # Si hay error, continuar con el método normal
                    pass
            
            # CASO NORMAL: Calcular usando la tasa del pedido relacionado
            tax_rate = 1.0
            if line.sale_line_ids:
                sale_order = line.sale_line_ids[0].order_id
                if sale_order and sale_order.tax_today:
                    tax_rate = sale_order.tax_today
            
            # Calcular el costo en USD
            if tax_rate and tax_rate != 0:
                line.sale_line_cost_usd = line.sale_line_cost / tax_rate
            else:
                line.sale_line_cost_usd = line.sale_line_cost

    @api.depends('sale_line_cost', 'quantity')
    def _compute_total_cost(self):
        """Calcula el costo total multiplicando el costo unitario por la cantidad"""
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                line.total_cost = 0.0
            else:
                line.total_cost = line.sale_line_cost * line.quantity

    @api.depends('sale_line_cost_usd', 'quantity')
    def _compute_total_cost_usd(self):
        """Calcula el costo total en USD multiplicando el costo unitario USD por la cantidad"""
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                line.total_cost_usd = 0.0
            else:
                line.total_cost_usd = line.sale_line_cost_usd * line.quantity

    @api.depends('price_unit_ref', 'sale_line_cost_usd')
    def _compute_margin(self):
        """
        Calcula el margen en USD y el porcentaje de margen.
        Margen USD = price_unit_ref - sale_line_cost_usd
        Margen % = ((price_unit_ref - sale_line_cost_usd) / sale_line_cost_usd) * 100
        """
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                line.margin = 0.0
                line.margin_percent = 0.0
            else:
                # Calcular margen en USD
                line.margin = (line.price_unit_ref - line.sale_line_cost_usd) * line.quantity
                
                # Calcular porcentaje de margen
                if line.sale_line_cost_usd and line.sale_line_cost_usd != 0:
                    line.margin_percent = ((line.price_unit_ref - line.sale_line_cost_usd) / line.sale_line_cost_usd)
                else:
                    line.margin_percent = 0.0
