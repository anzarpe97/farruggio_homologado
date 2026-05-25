import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class StockQuantityHistoryInherited(models.TransientModel):
    _inherit = 'stock.quantity.history'

    location_ids = fields.Many2many('stock.location', string='Ubicaciones')
    group_by_warehouse = fields.Boolean(string='Agrupar por almacén', default=False)

    @api.model
    def default_get(self, fields_list):
        res = super(StockQuantityHistoryInherited, self).default_get(fields_list)
        ctx = self.env.context or {}
        if ctx.get('active_model') == 'stock.location':
            active_ids = ctx.get('active_ids') or ([ctx.get('active_id')] if ctx.get('active_id') else False)
            active_domain = ctx.get('active_domain')
            if active_ids:
                ids = active_ids if isinstance(active_ids, list) else [active_ids]
                res['location_ids'] = [(6, 0, ids)]
            elif active_domain:
                try:
                    locs = self.env['stock.location'].search(active_domain)
                    res['location_ids'] = [(6, 0, locs.ids)]
                except Exception:
                    _logger.exception('Failed to pre-fill location_ids from active_domain')
        if not res.get('location_ids'):
            try:
                locs = self.env['stock.location'].search([('usage', '=', 'internal')])
                res['location_ids'] = [(6, 0, locs.ids)]
            except Exception:
                _logger.exception('Failed to set default internal locations')
        return res

    def open_at_date(self):
        """Reemplazamos la acción nativa por líneas por Producto/Ubicación conservando
        campos de producto (costo estándar) y permitiendo agrupar en vista árbol/pivote.

        Si se desea volver al comportamiento nativo, quitar este override.
        """
        self.ensure_one()
        date_to = self.inventory_datetime or self.env.context.get('to_date')
        if not date_to:
            return super().open_at_date()
        lines = self._compute_location_lines(date_to)
        action = {
            'name': 'Inventario a la Fecha (Ubicaciones)',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quantity.history.location.line',
            'view_mode': 'tree,pivot',
            'domain': [('wizard_id', '=', self.id)],
            'context': {
                # Contexto inicial sin agrupaciones forzadas para que el usuario decida.
            },
            'target': 'current'
        }
        if self.group_by_warehouse:
            # Agrupación inicial por almacén; el usuario puede quitarla desde la vista.
            action['context']['group_by'] = 'warehouse_id'
        return action

    # ------------------- Cálculo líneas por ubicación -------------------
    def _compute_location_lines(self, date_to):
        self.ensure_one()
        Location = self.env['stock.location']
        MoveLine = self.env['stock.move.line']
        Product = self.env['product.product']
        target_locations = self.location_ids.filtered(lambda l: l.usage == 'internal') if self.location_ids else Location.search([('usage', '=', 'internal')])
        if not target_locations:
            return []
        domain = [
            ('state', '=', 'done'),
            ('date', '<=', date_to),
            '|', ('location_id', 'in', target_locations.ids), ('location_dest_id', 'in', target_locations.ids),
        ]
        mls = MoveLine.search(domain)
        from collections import defaultdict
        qty_map = defaultdict(float)
        uom_map = {}
        for ml in mls:
            product = ml.product_id
            if not product or product.type != 'product':
                continue
            qty = ml.product_uom_id._compute_quantity(ml.qty_done, product.uom_id)
            if ml.location_id.usage == 'internal' and ml.location_id in target_locations:
                qty_map[(product.id, ml.location_id.id)] -= qty
                uom_map[(product.id, ml.location_id.id)] = product.uom_id.id
            if ml.location_dest_id.usage == 'internal' and ml.location_dest_id in target_locations:
                qty_map[(product.id, ml.location_dest_id.id)] += qty
                uom_map[(product.id, ml.location_dest_id.id)] = product.uom_id.id

        # Limpiar líneas previas
        self.env['stock.quantity.history.location.line'].search([('wizard_id', '=', self.id)]).unlink()
        line_vals = []
        Warehouse = self.env['stock.warehouse']
        warehouses = Warehouse.search([])

        def find_wh(loc):
            """Devuelve el almacén cuyo lot_stock_id es ancestro (o igual) de la ubicación.
            Recorre hacia arriba la jerarquía usando location_id hasta la raíz interna.
            """
            if not loc:
                return False
            lot_map = {wh.lot_stock_id.id: wh.id for wh in warehouses if wh.lot_stock_id}
            current = loc
            visited = set()
            while current and current.id not in visited:
                visited.add(current.id)
                if current.id in lot_map:
                    return lot_map[current.id]
                current = current.location_id
            return False

        for (product_id, location_id), qty in qty_map.items():
            product = Product.browse(product_id)
            location = Location.browse(location_id)
            wh_id = find_wh(location)
            cost_unit = product.standard_price  # Simple: costo estándar; para promedio real se requiere valuation layers
            value_total = qty * cost_unit
            line_vals.append({
                'wizard_id': self.id,
                'product_id': product_id,
                'location_id': location_id,
                'warehouse_id': wh_id,
                'quantity': qty,
                'uom_id': uom_map.get((product_id, location_id)),
                'cost_unit': cost_unit,
                'value_total': value_total,
                'categ_id': product.categ_id.id,
                'default_code': product.default_code,
            })
        if line_vals:
            return self.env['stock.quantity.history.location.line'].create(line_vals)
        return []


class ProductProductInventoryBreakdown(models.Model):
    _inherit = 'product.product'

    ubicaciones_detalle = fields.Text(string='Ubicaciones (cantidades)', compute='_compute_ubicaciones_detalle')

    def _compute_ubicaciones_detalle(self):
        """Construye un string con las cantidades por ubicación a la fecha del contexto.
        Requiere contexto 'to_date' y opcionalmente 'inventory_location_ids'."""
        products = self
        ctx = self.env.context
        date_to = ctx.get('to_date')
        show = ctx.get('show_location_breakdown')
        if not date_to or not show or not products:
            for p in products:
                p.ubicaciones_detalle = ''
            return

        # Determinar ubicaciones objetivo
        Location = self.env['stock.location']
        if ctx.get('inventory_location_ids'):
            target_locations = Location.browse(ctx['inventory_location_ids']).filtered(lambda l: l.usage == 'internal')
        else:
            target_locations = Location.search([('usage', '=', 'internal')])
        if not target_locations:
            for p in products:
                p.ubicaciones_detalle = ''
            return

        # Obtener líneas de movimiento relevantes
        MoveLine = self.env['stock.move.line']
        domain = [
            ('state', '=', 'done'),
            ('product_id', 'in', products.ids),
            ('date', '<=', date_to),
            '|', ('location_id', 'in', target_locations.ids), ('location_dest_id', 'in', target_locations.ids),
        ]
        mls = MoveLine.search(domain)

        # Acumular cantidades netas por (producto, ubicación)
        from collections import defaultdict
        qty_map = defaultdict(float)
        for ml in mls:
            prod = ml.product_id
            # Convertir a UdM base producto
            qty = ml.product_uom_id._compute_quantity(ml.qty_done, prod.uom_id)
            # Restar de origen interno
            if ml.location_id.usage == 'internal' and ml.location_id in target_locations:
                qty_map[(prod.id, ml.location_id.id)] -= qty
            # Sumar a destino interno
            if ml.location_dest_id.usage == 'internal' and ml.location_dest_id in target_locations:
                qty_map[(prod.id, ml.location_dest_id.id)] += qty

        # Preparar nombres de ubicación y construir string
        by_product = {}
        for (prod_id, loc_id), q in qty_map.items():
            if abs(q) < 1e-9:
                continue
            by_product.setdefault(prod_id, []).append((loc_id, q))

        # Cache de nombres
        name_cache = {}
        def loc_name(lid):
            if lid not in name_cache:
                name_cache[lid] = Location.browse(lid).display_name
            return name_cache[lid]

        for p in products:
            lines = []
            for loc_id, qty in sorted(by_product.get(p.id, []), key=lambda t: loc_name(t[0]).lower()):
                lines.append(f"{loc_name(loc_id)}: {round(qty, 2)}")
            p.ubicaciones_detalle = ' | '.join(lines) if lines else ''


class StockQuantityHistoryLocationLine(models.TransientModel):
    _name = 'stock.quantity.history.location.line'
    _description = 'Inventario a la fecha por ubicación'
    _order = 'product_id, location_id'

    wizard_id = fields.Many2one('stock.quantity.history', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string='Producto', required=True, index=True)
    default_code = fields.Char(string='Referencia interna')
    categ_id = fields.Many2one('product.category', string='Categoría')
    location_id = fields.Many2one('stock.location', string='Ubicación', required=True, index=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén', index=True)
    quantity = fields.Float(string='Cantidad', digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', string='UdM')
    cost_unit = fields.Float(string='Costo Unit.')
    value_total = fields.Float(string='Valor Total')

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f"{rec.product_id.display_name} / {rec.location_id.display_name}"))
        return res



