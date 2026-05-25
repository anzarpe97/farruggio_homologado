# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.
from odoo import models, fields, api


class WarningWizard(models.TransientModel):
    _name = "warning.wizard"
    _description = "Warning Wizard"

    @api.model
    def get_default(self):
        return self.env.context.get("message", False)

    name = fields.Text(string="Mensaje", readonly=True, default=get_default)
    sale_id = fields.Many2one('sale.order', string="Pedido de Venta")

    def action_confirm(self):
        self.ensure_one()
        return self.sale_id.with_context(warning=True).action_confirm()
