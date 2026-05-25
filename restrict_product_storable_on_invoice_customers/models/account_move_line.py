from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('product_id')
    def _onchange_product_id_invoice_origin(self):
        if self.move_id and not self.move_id.invoice_origin:
            return {
                'domain': {
                    'product_id': [('type', '=', 'service')]
                }
            }
        else:
            return {
                'domain': {
                    'product_id': []
                }
            }
