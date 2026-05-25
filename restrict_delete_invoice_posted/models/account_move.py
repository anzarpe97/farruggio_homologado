from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    was_posted_once = fields.Boolean(string="Fue publicada alguna vez", default=False)

    def action_delete_invoice(self):
        invoice_types = ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']
        for move in self:
            if move.move_type in invoice_types and move.was_posted_once:
                raise UserError("Este documento contable ya fue publicado anteriormente y no puede eliminarse. Debe cancelarlo si desea anularlo.")
            move.unlink()

    def unlink(self):
        # Validacion desactivada para permitir eliminar documentos publicados.
        return super().unlink()

    def action_post(self):
        res = super().action_post()
        self.filtered(lambda m: not m.was_posted_once).write({'was_posted_once': True})
        return res