# -*- coding: utf-8 -*-
from odoo import models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _compute_invoice_status(self):
        """Override para forzar invoice_status.

        Reglas:
          * Si existe cualquier factura (out_invoice u out_refund) no cancelada => 'invoiced'.
          * Si ya no hay facturas vigentes y existen líneas facturables => 'to invoice'.
          * Si no hay facturas ni líneas facturables => 'no' (o lo que deje el super si cambia en el futuro).
        """
        super(SaleOrder, self)._compute_invoice_status()
        for order in self:
            if order.state not in ('sale', 'done'):
                continue
            invoices = order.invoice_ids.filtered(lambda m: m.move_type in ('out_invoice','out_refund') and m.state != 'cancel')
            # Dependemos únicamente del campo delivery_status (sale_stock) para determinar entrega completa.
            # No se realiza cálculo manual.
            fully_delivered = (getattr(order, 'delivery_status', False) == 'full')

            has_to_invoice = any(line.invoice_status == 'to invoice' for line in order.order_line if line.state != 'cancel')

            # Solo marcamos totalmente facturado si:
            #  - Hay al menos una factura vigente
            #  - El pedido está totalmente entregado
            #  - NO quedan líneas con invoice_status == 'to invoice'
            if invoices and fully_delivered and not has_to_invoice:
                order.invoice_status = 'invoiced'
                continue

            if has_to_invoice:
                order.invoice_status = 'to invoice'
            else:
                if order.invoice_status == 'invoiced':
                    order.invoice_status = 'no'
