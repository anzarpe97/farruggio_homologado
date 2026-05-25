from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    show_contract_fields = fields.Boolean(string="Mostrar campos de contrato en factura fiscal dual")
