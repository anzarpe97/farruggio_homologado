from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        copy=True,  # Nos aseguramos de que se copie al duplicar
        readonly=True,  # Hacemos que sea de solo lectura para evitar cambios manuales
    )
