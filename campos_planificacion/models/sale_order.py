from odoo import models, fields, api
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    total_kg_qty = fields.Float(
        string='Cantidad Total de Kilos',
        compute='_compute_total_kg_qty',
        store=True,
        readonly=True
    )

    total_und_qty = fields.Float(
        string='Cantidad Total de Unidades',
        compute='_compute_totals',
        store=True,
        readonly=True
    )

    total_bultos_qty = fields.Float(
        string='Cantidad Total de Bultos',
        compute='_compute_totals',
        store=True,
        readonly=True
    )

    @api.depends('order_line.product_uom_qty', 'order_line.product_uom')
    def _compute_totals(self):
        for order in self:
            total_kg = 0.0
            total_und = 0.0
            total_bultos = 0.0

            for line in order.order_line:
                if not line.product_uom:
                    continue
                uom_name = line.product_uom.name.lower()
                product_name = (line.name or '').lower()

                # Suma kilos'
                if uom_name in ['kg', 'kilogramo', 'kilogramos']:
                    total_kg += line.product_uom_qty

                # Suma unidades
                elif uom_name in ['und', 'unidad', 'unidades']:
                    total_und += line.product_uom_qty

                # Suma bultos (contenga 'bulto')
                elif 'bulto' in uom_name:
                    total_bultos += line.product_uom_qty

                # Si el nombre contiene "bulto x 10", agrega 10 kg por cada bulto
                # if 'bulto x 10' in uom_name:
                #     total_kg += 10 * line.product_uom_qty

                # if 'bulto x 14' in uom_name:
                #     total_kg += 10 * line.product_uom_qty

                if 'caja' in uom_name:
                    total_kg += 20 * line.product_uom_qty

                # Si el nombre del producto contiene "cestas", suma 2.2 kg por unidad
                if 'cestas' in product_name:
                    total_kg += 2.2 * line.product_uom_qty

                if 'harina de trigo (saco de 45 kg)' in product_name:
                    total_kg += 45 * line.product_uom_qty


            order.total_kg_qty = total_kg
            order.total_und_qty = total_und
            order.total_bultos_qty = total_bultos

    # @api.constrains('order_line', 'order_line.product_uom_qty', 'order_line.product_uom', 'partner_id', 'date_order')
    # def _check_minimum_kg(self):
    #     for order in self:
    #         if not order.partner_id or not order.date_order:
    #             continue

    #         order_date = order.date_order.date()
    #         total_kg = 0.0

    #         # Calcular kg de este pedido manualmente (sin depender de total_kg_qty)
    #         for line in order.order_line:
    #             uom_name = line.product_uom.name.lower() if line.product_uom else ''
    #             product_name = (line.name or '').lower()

    #             if 'bulto x 10' in uom_name:
    #                 total_kg += 10 * line.product_uom_qty
    #             if 'bulto x 14' in uom_name:
    #                 total_kg += 10 * line.product_uom_qty
    #             elif 'caja' in uom_name:
    #                 total_kg += 20 * line.product_uom_qty
    #             elif uom_name in ['kg', 'kilogramo', 'kilogramos']:
    #                 total_kg += line.product_uom_qty

    #             # Si el nombre del producto contiene "cestas", suma 2.2 kg por unidad
    #             if 'cestas' in product_name:
    #                 total_kg += 2.2 * line.product_uom_qty
                    
    #             product_name = (line.product_id.name or '').lower()
    #             if 'harina de trigo (saco de 45 kg)' in product_name:
    #                 total_kg += 45 * line.product_uom_qty


    #         # Buscar otros pedidos del mismo cliente el mismo día (excluyendo cancelados)
    #         same_day_orders = self.search([
    #             ('partner_id', '=', order.partner_id.id),
    #             ('date_order', '>=', order_date.strftime('%Y-%m-%d 00:00:00')),
    #             ('date_order', '<=', order_date.strftime('%Y-%m-%d 23:59:59')),
    #             ('state', 'not in', ['cancel']),
    #             ('id', '!=', order.id),
    #         ])

    #         # También calcular manualmente los kg de los otros pedidos
    #         for other_order in same_day_orders:
    #             for line in other_order.order_line:
    #                 uom_name = line.product_uom.name.lower() if line.product_uom else ''
    #                 product_name = (line.name or '').lower()

    #                 if 'bulto x 10' in uom_name:
    #                     total_kg += 10 * line.product_uom_qty
    #                 elif 'caja' in uom_name:
    #                     total_kg += 20 * line.product_uom_qty
    #                 elif uom_name in ['kg', 'kilogramo', 'kilogramos']:
    #                     total_kg += line.product_uom_qty

    #                 # Si el nombre del producto contiene "cestas", suma 2.2 kg por unidad
    #                 if 'cestas' in product_name:
    #                     total_kg += 2.2 * line.product_uom_qty 

    #         if total_kg < 25:
    #             raise UserError(
    #                 f"No puedes confirmar este presupuesto. La cantidad total de kilos del cliente "
    #                 f"{order.partner_id.name} para el día {order_date.strftime('%d/%m/%Y')} es de {total_kg:.2f} kg, "
    #                 f"y debe ser al menos de 25 kg."
    #             )
