from odoo import models, api, fields
from datetime import datetime
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _check_period_closed(self):
        """Verifica si el periodo anterior está cerrado"""
        if not self.date:
            return False
            
        move_date = fields.Date.to_date(self.date)
        company = self.company_id or self.env.company
        
        return (company.period_lock_date and move_date > company.period_lock_date) or \
               (company.fiscalyear_lock_date and move_date > company.fiscalyear_lock_date)

    def _get_period_warning_message(self):
        """Genera el mensaje de advertencia"""
        move_date = fields.Date.to_date(self.date)
        company = self.company_id or self.env.company
        
        return """
        🔔 ADVERTENCIA: PERIODO ANTERIOR SIN CERRAR
        Fecha del movimiento: {date}
        Último periodo cerrado: {period_lock}
        Último cierre fiscal: {fiscal_lock}
        
        Antes de iniciar un nuevo periodo, debe cerrarse correctamente el periodo anterior.
        Por favor, revise y complete el cierre correspondiente.
        
        ⚠️ Registrar movimientos en periodos no cerrados puede constituir un ilícito fiscal.
        """.format(
            date=move_date,
            period_lock=company.period_lock_date or "No definido",
            fiscal_lock=company.fiscalyear_lock_date or "No definido"
        )

    def action_post(self):
        """Mostrar ventana emergente al validar factura si aplica"""
        if self._check_period_closed():
            return {
                'type': 'ir.actions.act_window',
                'name': 'Alerta de Periodo no Cerrado',
                'res_model': 'account.move',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'views': [(False, 'form')],
                'context': {
                    'default_warning_message': self._get_period_warning_message(),
                    'show_warning': True
                }
            }
        return super().action_post()

    @api.model
    def create(self, vals):
        """Mostrar advertencia al crear factura"""
        record = super().create(vals)
        if record._check_period_closed():
            return {
                'type': 'ir.actions.act_window',
                'name': 'Alerta de Periodo no Cerrado',
                'res_model': 'account.move',
                'res_id': record.id,
                'view_mode': 'form',
                'target': 'new',
                'views': [(False, 'form')],
                'context': {
                    'default_warning_message': record._get_period_warning_message(),
                    'show_warning': True
                }
            }
        return record
    
    def action_post_force(self):
     """Permite continuar con la validación a pesar de la advertencia"""
     return super().action_post()