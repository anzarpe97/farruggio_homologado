# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_recalculate_residual_usd(self):
        """
        Método para forzar el recálculo del amount_residual_usd en facturas.
        Aplica procesamiento por lotes para evitar bloqueos de DB.
        """
        
        # Tipos de movimiento: Solo facturas de cliente/proveedor
        INVOICE_MOVE_TYPES = ['out_invoice', 'in_invoice']
        
        # Dominio Optimizado: Busca inconsistencias (partial O paid y residual > 0)
        domain = [
            ('move_type', 'in', INVOICE_MOVE_TYPES),
            ('state', '=', 'posted'),
            '|',
                ('payment_state', '=', 'partial'), 
                '&',
                    ('payment_state', '=', 'paid'),
                    ('amount_residual_usd', '>', 0.0),
        ]
        
        # 1. Determinar el conjunto de registros a procesar y obtener solo IDs
        # Esto nos permite ejecutar la acción con el usuario de sistema para asegurar permisos (necesario en CRON).
        current_self = self.sudo() if self.env.uid != SUPERUSER_ID else self

        if current_self and not self._context.get('cron_mode'):
            # Si se ejecuta desde la vista (list/form), filtramos en memoria y obtenemos los IDs
            moves_to_recalculate_ids = current_self.filtered(
                lambda m: m.move_type in INVOICE_MOVE_TYPES
                and m.state == 'posted'
                and (m.payment_state == 'partial' or (m.payment_state == 'paid' and m.amount_residual_usd > 0.0))
            ).ids
        else:
            # Si se ejecuta globalmente (CRON), usamos el dominio de búsqueda optimizado en la DB.
            moves_to_recalculate_ids = current_self.search(domain).ids

        total_count = len(moves_to_recalculate_ids)
        processed_count = 0
        BATCH_SIZE = 1000

        if total_count > 0:
            _logger.info("[DUAL FIX] Iniciando recálculo en %s documentos. Lote de %s.", total_count, BATCH_SIZE)

            # 2. Procesamiento por Lotes
            for i in range(0, total_count, BATCH_SIZE):
                batch_ids = moves_to_recalculate_ids[i:i + BATCH_SIZE]
                moves_batch = self.env['account.move'].sudo().browse(batch_ids) # Usar self.env para asegurar el modelo
                
                # Forzar el recálculo
                moves_batch.with_context(skip_tax_today_update=True)._compute_amount_residual_usd()
                
                # Invalida la caché del lote y confirma (commit)
                # La confirmación es lo que previene el bloqueo de la DB.
                self.env.cr.commit()
                processed_count += len(moves_batch)
                _logger.info("[DUAL FIX] Lote procesado: %s/%s", processed_count, total_count)
            
            # 3. Limpieza final de caché CORRECTA
            # Invalida el caché de la capa ORM después de terminar todos los commits
            self.env.invalidate_all() # <=== ¡CORRECCIÓN APLICADA AQUÍ!

        # Retorno para el CRON
        if self._context.get('cron_mode'):
            return f"Finalizado. {processed_count} facturas actualizadas en lotes de {BATCH_SIZE}."
        
        # Retorno para la Acción de Servidor (UI)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recálculo de Adeudado USD (Fix Cache)'),
                'message': _('Proceso finalizado. %s facturas actualizadas en lotes.') % processed_count,
                'type': 'success',
                'sticky': False,
            }
        }