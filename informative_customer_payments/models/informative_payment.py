from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.exceptions import AccessError
from odoo.exceptions import ValidationError

class InformativePayment(models.Model):
    _name = 'informative.payment'
    _description = 'Pago Informativo de Cliente'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Referencia', required=True, default='Nuevo', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True)
    amount = fields.Float(string='Monto', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id.id, tracking=True)
    banco = fields.Selection([
        ('bancaribe', 'BANCARIBE'),
        ('bancaribe_custodio', 'BANCARIBE CUSTODIO'),
        ('bancaribe_puertorico', 'BANCARIBE PUERTORICO'),
        ('bancaribe_curacao', 'BANCARIBE CURACAO'),
        ('banesco', 'BANCO BANESCO'),
        ('banplus', 'BANCO BANPLUS'),
        ('banplus_custodio', 'BANPLUS CUSTODIO'),
        ('banco_de_venezuela', 'BANCO DE VENEZUELA'),
        ('banco_mercantil', 'BANCO MERCANTIL'),
        ('banco_nacional_de_credito', 'BANCO NACIONAL DE CRÉDITO'),
        ('banco_plaza', 'BANCO PLAZA'),
        ('banco_plaza_custodio', 'BANCO PLAZA CUSTODIO'),
        ('banco_provincial', 'BANCO PROVINCIAL'),
        ('bnc_custodio', 'BNC CUSTODIO'),
        ('bnc_curazao', 'BNC CURAZAO'),
        ('efectivo_usd', 'EFECTIVO USD'),
        ('mercantil_custodio', 'MERCANTIL CUSTODIO'),
        ('mercantil_panama', 'MERCANTIL PANAMA'),
        ('provincial_custodio', 'PROVINCIAL CUSTODIO'),
        ('provincial_curazao', 'PROVINCIAL CURAZAO'),
        ('transferencia_internacional', 'TRANSFERENCIA INTERNACIONAL'),
        ('venezuela_custodio', 'VENEZUELA CUSTODIO'),
    ], string='Banco Destino', tracking=True)
    payment_method = fields.Selection([
        ('efectivo', 'EFECTIVO'),
        ('transferencia_bancaria', 'TRANSFERENCIA BANCARIA'),
        ('pago_movil', 'PAGO MÓVIL'),
    ], string='Método de Pago', tracking=True)
    note = fields.Text(string='Observaciones')
    date = fields.Date(string='Fecha del Pago', default=fields.Date.context_today, tracking=True)
    user_id = fields.Many2one('res.users', string='Vendedor', default=lambda self: self.env.user, tracking=True)
    invoice_ids = fields.Many2many(
        'account.move',
        string='Facturas Pagadas',
        domain="[('move_type', '=', 'out_invoice')]",
        tracking=True,
    )
    payment_type = fields.Selection([
        ('anticipado', 'Pago Anticipado'),
        ('factura', 'Pago a Facturas'),
    ], string='Tipo de Pago', tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('related', 'Relacionado'),
        ('anulado', 'Anulado'),
    ], string='Estado', default='draft', tracking=True)
    # image = fields.Binary(string="Comprobante de Pago", attachment=True, required=True, tracking=True)
    # comprobante_filename = fields.Char(string="Nombre del archivo")

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'informative_payment_attachment_rel',  # nombre de la tabla relacional
        'payment_id', 'attachment_id',
        string="Comprobantes",
        domain=[('res_model', '=', 'informative.payment')],
    )

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nuevo') == 'Nuevo':
            vals['name'] = self.env['ir.sequence'].next_by_code('informative.payment') or 'Nuevo'
        return super().create(vals)
    
     # --- Opcional pero recomendado: limpiar selección si cambia el cliente
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.invoice_ids = [(5, 0, 0)]  # limpia el many2many

    @api.onchange('partner_id')
    def _onchange_invoice_ids(self):
        for rec in self:
            if not rec.partner_id:
                continue

            vef_id = self.env.ref('base.VEF').id
            usd_id = self.env.ref('base.USD').id

            rec_domain = [
                ('partner_id', '=', rec.partner_id.id),
                ('move_type', '=', 'out_invoice'),  # 🔥 solo facturas cliente
                '|',
                    '&', ('currency_id', '=', vef_id), ('amount_residual_usd', '>', 0),
                    '&', ('currency_id', '=', usd_id), ('payment_state', 'in', ['not_paid', 'partial'])
            ]

            return {'domain': {'invoice_ids': rec_domain}}

    def action_confirm(self):
        for rec in self:
            rec.state = 'confirmed'
            group = self.env.ref('informative_customer_payments.group_cxc_analyst')
            # Filtrar usuarios que NO pertenezcan al grupo "no_notify"
            no_notify_group = self.env.ref('informative_customer_payments.group_cxc_analyst_no_notify')
            recipients = group.users - no_notify_group.users
            if not recipients:
                raise UserError("No hay usuarios en el grupo 'Analista de Cuentas por Cobrar' disponibles")
            rec.message_post(
                body=_("Este pago ha sido confirmado y requiere validación."),
                partner_ids=recipients.mapped('partner_id').ids
            )

            for user in recipients:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    note=_("Validar el pago del cliente: %s") % rec.partner_id.display_name
                )

    def action_related(self):
        group = self.env.ref('informative_customer_payments.group_cxc_analyst')
        no_notify_group = self.env.ref('informative_customer_payments.group_cxc_analyst_no_notify')
        if not self.env.user in group.users - no_notify_group.users:
            raise AccessError("Solo los Analistas de Cuentas por Cobrar pueden realizar esta acción.")
        
        for rec in self:
            rec.state = 'related'
            activities = self.env['mail.activity'].search([
                ('res_model', '=', rec._name),
                ('res_id', '=', rec.id),
                ('user_id', '=', self.env.user.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                ('summary', '=', False)
            ])
            activities.action_feedback(feedback="Pago relacionado con facturas.")

            if not rec.user_id:
                continue
            rec.message_post(
                body=_("El pago ha sido relacionado con las facturas correspondientes."),
                partner_ids=[rec.user_id.partner_id.id]
            )

    def action_cancel(self):
        for rec in self:
            if rec.state == 'anulado':
                raise UserError(_("No se puede anular un pago que ya está relacionado."))
            if rec.state != 'anulado':
                rec.state = 'anulado'
                rec.message_post(
                    body=_("El Pago fue anulado por no estar en banco."),
                    message_type="notification",
                    subtype_xmlid="mail.mt_note"
                )

    @api.constrains('image')
    def _check_image_required(self):
        for rec in self:
            if not rec.image:
                raise UserError(_("Debe adjuntar una imagen del comprobante de pago."))
            
    @api.constrains('payment_type', 'invoice_ids')
    def _check_invoice_required(self):
        for rec in self:
            if rec.payment_type == 'factura' and not rec.invoice_ids:
                raise ValidationError(_("Debe seleccionar al menos una factura cuando el tipo de pago es 'Pago a Facturas'."))

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Solo se pueden eliminar pagos en estado Borrador."))
        return super().unlink()