from odoo import models, api, fields
from datetime import datetime

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _get_custom_warning(self):
        """Método para mensaje condicional basado en periodos"""
        # Solo verificar si hay fecha en el movimiento
        if not self.date:
            return False
            
        move_date = fields.Date.to_date(self.date)
        company = self.company_id or self.env.company
        
        # Verificar condición de periodo no cerrado
        if (company.period_lock_date and move_date > company.period_lock_date) or \
           (company.fiscalyear_lock_date and move_date > company.fiscalyear_lock_date):
            
            message = """
            🔔 ADVERTENCIA: PERIODO ANTERIOR SIN CERRAR
            Fecha del movimiento: {date}
            Último periodo cerrado: {period_lock}
            Último cierre fiscal: {fiscal_lock}
            
            Antes de iniciar un nuevo periodo, debe cerrarse correctamente el periodo anterior.
            Por favor, revise y complete el cierre correspondiente.
            """.format(
                date=move_date,
                period_lock=company.period_lock_date or "No definido",
                fiscal_lock=company.fiscalyear_lock_date or "No definido"
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '¡Alerta de Periodo!',
                    'message': message,
                    'sticky': True,
                    'type': 'danger'
                }
            }
        return False

    def action_post(self):
        """Mostrar advertencia al validar factura si aplica"""
        res = super().action_post()
        warning = self._get_custom_warning()
        return warning or res
    
    @api.model
    def create(self, vals):
      record = super().create(vals)
      if record._get_custom_warning():
        # Mostrar como notificación no sticky al crear
        warning = record._get_custom_warning()
        warning['params']['sticky'] = False
        return warning
      return record