from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    last_sale_order_date = fields.Date(
        string='Última fecha de pedido de venta',
        compute='_compute_last_sale_order_date',
        store=True
    )

    @api.depends('sale_order_ids.date_order')
    def _compute_last_sale_order_date(self):
        for partner in self:
            orders = partner.sale_order_ids.filtered(lambda o: o.state not in ['cancel'])
            if orders:
                partner.last_sale_order_date = max(orders.mapped('date_order')).date()
            else:
                partner.last_sale_order_date = False
