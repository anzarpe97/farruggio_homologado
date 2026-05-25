from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = 'product.category'

    margin_percent = fields.Float(
        string='Margen de utilidad (%)',
        tracking=True
    )

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    margin_percent = fields.Float(string="Margen de utilidad (%)", tracking=True)

    # Este ya existe, pero si quieres asegurarte de tracking:
    list_price_usd = fields.Float(string="Precio de venta $", tracking=True)

    computed_margin_percent = fields.Float(
        string='Margen efectivo (%)',
        compute='_compute_margin_effective',
        store=False
    )

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec.with_context(margin_price_computing=True)._compute_lst_price_margin()
        return rec

    def write(self, vals):
        # No ejecutar si ya venimos de una operación de recálculo
        if self.env.context.get('margin_price_computing'):
            return super().write(vals)

        res = super().write(vals)
        self.with_context(margin_price_computing=True)._compute_lst_price_margin()
        return res

    def _compute_lst_price_margin(self):
        for product in self:
            old_price = product.list_price_usd
            margin = product.margin_percent if product.margin_percent not in (None, 0.0) else product.categ_id.margin_percent
            if margin not in (None, 0.0) and product.standard_price:
                new_price = product.standard_price_usd / ((100 - margin) / 100.0)
                if product.list_price_usd != new_price:
                    product.message_post(
                        body=f"💸 Precio recalculado automáticamente desde costo ({product.standard_price_usd}) y margen ({margin}%). Nuevo precio: {new_price:.2f}"
                    )
                    product.list_price_usd = new_price

    @api.depends('margin_percent', 'categ_id.margin_percent')
    def _compute_margin_effective(self):
        for rec in self:
            rec.computed_margin_percent = rec.margin_percent if rec.margin_percent else rec.categ_id.margin_percent

class ProductProduct(models.Model):
    _inherit = 'product.product'

    margin_percent = fields.Float(
        related='product_tmpl_id.margin_percent',
        store=True,
        readonly=True
    )

    def write(self, vals):
        res = super().write(vals)
        if 'standard_price' in vals:
            # Recalcular en la plantilla asociada
            templates = self.mapped('product_tmpl_id')
            templates._compute_lst_price_margin()
        return res