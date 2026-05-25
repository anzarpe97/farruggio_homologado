# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from odoo.tools import (
    date_utils,
    email_re,
    email_split,
    float_compare,
    float_is_zero,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    is_html_empty,
    sql
)
import json

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    journal_id = fields.Many2one('account.journal', string='Diario', required=False, readonly=True)
        
    @api.model
    def create(self, vals):
        # Eliminar la generación de número de control aquí.
        # Permitir que Odoo asigne el valor por defecto si no se proporciona.
        return super(AccountMove, self).create(vals)
    
    

    def action_post(self):
        res = super(AccountMove, self).action_post()  # Llama al action_post original.
        for rec in self:  # Itera por los registros si es necesario.
            if not rec.nro_ctrl:  # Verifica si nro_ctrl está vacío.
                nro_interno_control = self._generar_numero_control()
                if nro_interno_control:
                    rec.nro_ctrl = nro_interno_control
                else:
                    # Manejo de error si no se encuentra la secuencia.
                    raise UserError("No se pudo generar el número de control.")
        return res


    def _generar_numero_control(self):
        sequence = self.env['ir.sequence'].search([('name', '=', 'Secuencia Numero de Control')])
        if sequence:
            nro_interno_control = str(sequence.number_next).zfill(8)
            sequence.number_next_actual = sequence.number_next_actual + sequence.number_increment
            return nro_interno_control
        else:
            return False  # Indica que no se pudo generar el número de control.
    
    class StockPicking(models.Model):
        _inherit = 'stock.picking'

        def action_cancel(self):
            raise UserError(_('No se puede cancelar esta orden de entrega.'))

