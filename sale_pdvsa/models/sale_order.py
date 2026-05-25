from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_pdvsa = fields.Boolean(
        string="Es PDVSA",
        compute='_compute_is_pdvsa',
        store=True
    )

    pdvsa_invoice_count = fields.Integer(
        string="Facturas de PDVSA",
        compute="_compute_pdvsa_invoice_count"
    )

    invoice_ids = fields.One2many(
        'account.move',
        'sale_order_id',
        string='Facturas'
    )

    @api.depends('partner_id.name')
    def _compute_is_pdvsa(self):
        for order in self:
            partner_name = order.partner_id.name or ''
            order.is_pdvsa = 'PDVSA PETROLEO' in partner_name.upper()
    
    @api.depends('invoice_ids', 'invoice_ids.state', 'partner_id.name')
    def _compute_pdvsa_invoice_count(self):
        for order in self:
            order.pdvsa_invoice_count = len(order.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice' and inv.state in ('draft', 'posted')
            ))

    def action_view_pdvsa_invoice(self):
        self.ensure_one()

        invoices = self.env['account.move'].search([
            ('sale_order_id', '=', self.id),
            ('move_type', '=', 'out_invoice'),
            ('state', 'in', ['draft', 'posted']),
        ])

        if not invoices:
            raise UserError(_("No se ha generado ninguna factura PDVSA para este pedido."))

    action = {
        'name': _('Factura PDVSA'),
        'type': 'ir.actions.act_window',
        'view_mode': 'form',
        'res_model': 'account.move',
        'context': {'default_move_type': 'out_invoice'},
    }

    def action_open_pdvsa_mass_invoice_wizard(self):
        return {
            'name': 'Generar Factura PDVSA',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.pdvsa.mass.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_ids': [(6, 0, self.ids)],
            },
        }

    def action_create_pdvsa_invoice(self):
        self.ensure_one()

        if not self.is_pdvsa:
            raise UserError(_("Este pedido no está marcado como PDVSA."))

        if not self.order_line.filtered(lambda l: l.qty_delivered > 0):
            raise UserError(_("No hay cantidades entregadas para facturar."))

        # Validar que no haya facturas existentes asociadas al pedido
        existing_invoice = self.env['account.move'].search([
            ('invoice_origin', '=', self.name),
            ('move_type', '=', 'out_invoice'),
            ('state', 'in', ('draft', 'posted'))
        ], limit=1)

        if existing_invoice:
            raise UserError(_("Ya la factura fue creada para este pedido."))

        # Crear la factura desde el pedido
        invoice = self._create_invoices()
        if not invoice:
            raise UserError(_("No se pudo generar la factura."))

        invoice = invoice[0]

        # Buscar producto FLETE
        flete_product = self.env['product.product'].search([('name', '=', 'MANEJO TRANSP Y DOTACION INSUMOS COMEDOR')], limit=1)
        if not flete_product:
            raise UserError(_("No se encontró el producto 'MANEJO TRANSP Y DOTACION INSUMOS COMEDOR'. Por favor créalo."))

        # Calcular y redondear monto FLETE
        total = sum(l.price_unit * l.qty_delivered for l in self.order_line if l.qty_delivered > 0)
        total = float_round(total, precision_digits=2)

        if total <= 0:
            raise UserError(_("El monto total de MANEJO TRANSP Y DOTACION INSUMOS COMEDOR es cero."))

        # Validar cuenta contable
        account = flete_product.property_account_income_id or flete_product.categ_id.property_account_income_categ_id
        if not account:
            raise UserError(_("El producto MANEJO TRANSP Y DOTACION INSUMOS COMEDOR no tiene una cuenta de ingreso configurada."))

        # Eliminar líneas originales
        invoice.invoice_line_ids.unlink()

        # Crear línea de factura con FLETE
        self.env['account.move.line'].create({
            'move_id': invoice.id,
            'product_id': flete_product.id,
            'quantity': 1,
            'price_unit': total,
            'name': flete_product.name,
            'account_id': account.id,
            'tax_ids': [(6, 0, flete_product.taxes_id.ids)],
        })

        # Relacionar con venta
        invoice.write({
            'invoice_origin': self.name,
            'invoice_user_id': self.user_id.id,
            'sale_order_id': self.id
        }) 

        # Marcar líneas como facturadas
        for line in self.order_line:
            line.qty_invoiced = line.qty_delivered

        # Actualizar estado de facturación
        self._compute_invoice_status()

        return {
            'name': _('Factura PDVSA'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'context': {'default_move_type': 'out_invoice'},
        }