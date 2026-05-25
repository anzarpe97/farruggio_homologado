from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    editable_date = fields.Date(
        string="Fecha Contable Editable",
        compute='_compute_editable_date',
        inverse='_inverse_editable_date',
        store=False,
        readonly=False,
    )

    @api.depends('date')
    def _compute_editable_date(self):
        for move in self:
            move.editable_date = move.date

    def _inverse_editable_date(self):
        for move in self:
            if move.state == 'posted' and move.move_type == 'in_invoice':
                move.with_context(check_move_validity=False).write({'date': move.editable_date})
