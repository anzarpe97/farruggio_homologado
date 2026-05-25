from . import models

import logging
_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """
    Hook que se ejecuta después de instalar o actualizar el módulo.
    Recalcula los campos computados en las facturas existentes.
    """
    from odoo import api, SUPERUSER_ID
    
    _logger.info('=== Iniciando recálculo de campos en facturas existentes ===')
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    try:
        # Buscar todas las líneas de factura de cliente
        invoice_lines = env['account.move.line'].search([
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('display_type', 'not in', ['line_section', 'line_note'])
        ])
        
        _logger.info(f'Encontradas {len(invoice_lines)} líneas de factura para recalcular')
        
        if invoice_lines:
            # Invalidar caché para forzar recálculo
            invoice_lines.invalidate_cache()
            
            # Forzar recálculo usando recompute
            fields_to_recompute = [
                'sale_line_cost',
                'sale_line_cost_usd',
                'price_unit_ref',
                'total_cost',
                'total_cost_usd',
                'margin',
                'margin_percent'
            ]
            
            for field_name in fields_to_recompute:
                field = env['account.move.line']._fields[field_name]
                env.add_to_compute(field, invoice_lines)
            
            # Ejecutar el cálculo
            invoice_lines.recompute()
            
            _logger.info('Recálculo de líneas completado')
        
        # Recalcular totales en las facturas
        invoices = env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund'])
        ])
        
        _logger.info(f'Encontradas {len(invoices)} facturas para recalcular totales')
        
        if invoices:
            invoices.invalidate_cache()
            
            for field_name in ['total_cost', 'total_cost_usd']:
                field = env['account.move']._fields[field_name]
                env.add_to_compute(field, invoices)
            
            invoices.recompute()
            
            _logger.info('Recálculo de totales de facturas completado')
        
        _logger.info('=== Recálculo completado exitosamente ===')
        
    except Exception as e:
        _logger.error(f'Error durante el recálculo: {str(e)}', exc_info=True)
