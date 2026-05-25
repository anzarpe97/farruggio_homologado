from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_round


class SemanaPdvsaOpcion(models.TransientModel):
    _name = 'semana.pdvsa.opcion'
    _description = 'Opción Semana PDVSA'

    name = fields.Char(string='Semana', required=True, index=True)


class SaleOrderPdvsaMassInvoiceWizard(models.TransientModel):
    _name = 'sale.order.pdvsa.mass.invoice.wizard'
    _description = 'Generar factura consolidada PDVSA'

    date_from = fields.Date(string="Fecha Desde")
    date_to = fields.Date(string="Fecha Hasta")
    
    semana_pdvsa_ids = fields.Many2many(
        'semana.pdvsa.opcion',
        string='Filtrar por Semana PDVSA'
    )
    order_ids = fields.Many2many('sale.order', string='Pedidos PDVSA')
    
    @api.model
    def default_get(self, fields_list):
        """Carga las semanas automáticamente al abrir el wizard"""
        self.populate_semanas_pdvsa()
        return super().default_get(fields_list)

    @api.model
    def populate_semanas_pdvsa(self):
        semanas = self.env['sale.order'].search([]).mapped('x_studio_semana_pdvsa')
        semanas = list(set(filter(None, semanas)))  # Únicas y no vacías
        SemanaModel = self.env['semana.pdvsa.opcion']
        for semana in semanas:
            if not SemanaModel.search([('name', '=', semana)]):
                SemanaModel.create({'name': semana})

    def action_search_orders(self):
        pdvsa_partner = self.env['res.partner'].search([('name', '=', 'PDVSA PETROLEO')], limit=1)
        if not pdvsa_partner:
            raise UserError(_("No se encontró el proveedor PDVSA PETROLEO."))

        domain = [
            ('partner_id', '=', pdvsa_partner.id),
            ('invoice_status', '!=', 'invoiced')
        ]

        if self.date_from:
            domain.append(('date_order', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_order', '<=', self.date_to))
        if self.semana_pdvsa_ids:
            semanas = self.semana_pdvsa_ids.mapped('name')
            domain.append(('x_studio_semana_pdvsa', 'in', semanas))

        orders = self.env['sale.order'].search(domain)
        self.order_ids = orders

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_confirm(self):
        self.ensure_one()
        if not self.order_ids:
            raise UserError(_("Debe seleccionar al menos un pedido."))

        flete_product = self.env['product.product'].search([('name', '=', 'MANEJO TRANSP Y DOTACION INSUMOS COMEDOR')], limit=1)
        if not flete_product:
            raise UserError(_("No se encontró el producto 'MANEJO TRANSP Y DOTACION INSUMOS COMEDOR'."))

        account = flete_product.property_account_income_id or flete_product.categ_id.property_account_income_categ_id
        if not account:
            raise UserError(_("El producto MANEJO TRANSP Y DOTACION INSUMOS COMEDOR no tiene cuenta de ingreso configurada."))

        total = sum(
            sum(line.qty_delivered * line.price_unit for line in order.order_line)
            for order in self.order_ids
        )
        total = float_round(total, precision_digits=2)

        if total <= 0:
            raise UserError(_("El total facturable es 0."))

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.order_ids[0].partner_id.id,
            'invoice_origin': ", ".join(self.order_ids.mapped('name')),
            'invoice_user_id': self.env.user.id,
            'invoice_line_ids': [(
                0, 0, {
                    'product_id': flete_product.id,
                    'name': flete_product.name,
                    'quantity': 1,
                    'price_unit': total,
                    'account_id': account.id,
                    'tax_ids': [(6, 0, flete_product.taxes_id.ids)],
                }
            )],
        }

        invoice = self.env['account.move'].create(invoice_vals)

        for order in self.order_ids:
            order.write({'invoice_status': 'invoiced'})
            order.message_post(body=_("Este pedido fue facturado en la factura %s", invoice.name))

        return {
            'name': _('Factura Consolidada'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': invoice.id,
        }
