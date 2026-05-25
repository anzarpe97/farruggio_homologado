# -*- coding: utf-8 -*-
# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.
from odoo import api, models, fields, _
from odoo.exceptions import AccessDenied


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    state = fields.Selection(
        selection=[
            ('draft', "Cotización"),
            ('sent', "Cotización Enviada"),
            ('sales_approval', "Aprobación de Ventas"),
            ('finance_approval', "Aprobación Financiera"),
            ('approved', "Aprobado"),
            ('reject', "Rechazado"),
            ('sale', "Pedido de Venta"),
            ('done', "Bloqueado"),
            ('cancel', "Cancelado"),
        ],
        string="Estado",
        readonly=True, copy=False, index=True,
        tracking=3,
        default='draft')
    
    credit_warning_usd = fields.Monetary(
        related='partner_id.credit_warning_usd',
        currency_field='company_currency_id',
        store=True,
    )
    
    currency_usd_id = fields.Many2one('res.currency', compute='_compute_currency_usd', store=False)
    currency_dif_id = fields.Many2one(related='company_id.currency_id_dif', store=False)

    amount_due_usd = fields.Monetary(related='partner_id.amount_due_usd', currency_field='currency_usd_id')
    customer_blocking_limit_usd = fields.Monetary(related='partner_id.credit_blocking_usd', currency_field='currency_usd_id')

    amount_due = fields.Monetary(related='partner_id.amount_due', currency_field='company_currency_id')
    customer_blocking_limit = fields.Monetary(related='partner_id.credit_blocking', currency_field='company_currency_id')

    company_currency_id = fields.Many2one(string='Moneda de la Compañía', readonly=True,
                                          related='company_id.currency_id')

    @api.depends_context('uid')
    def _compute_currency_usd(self):
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        for rec in self:
            rec.currency_usd_id = usd_currency

    @api.depends('amount_due_usd', 'customer_blocking_limit_usd')
    def _compute_montos_en_moneda_local(self):
        for rec in self:
            rate = rec.company_id.currency_id_dif.rate or 1.0
            rec.amount_due = rec.amount_due_usd * rate
            rec.customer_blocking_limit = rec.customer_blocking_limit_usd * rate

    def get_so_for_approval(self):
        web = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        so_base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url') + '/web#id=%d&menu_id=%d&cids=%d&action=%d&model=sale.order&view_type=form' % (
                          self.id, self.env.ref('sale.sale_menu_root').id,
                          self.env.company.id,
                          self.env.ref('sale.action_quotations_with_onboarding').id)
        return so_base_url

    @api.depends('amount_due_usd', 'amount_total_dual', 'customer_blocking_limit_usd', 'state', 'is_credit_limit_final_approved')
    def _compute_customer_credit_limit(self):
        for rec in self:
            rec.is_credit_limit_approval = False
            rec.is_credit_limit_warning = False
            if rec.partner_id and rec.partner_id.credit_check:
                # Condición 1: Deuda total + pedido actual supera el límite
                if (rec.amount_due_usd + rec.amount_total_dual) > rec.customer_blocking_limit_usd and not rec.is_credit_limit_final_approved:
                    rec.is_credit_limit_approval = True
                # Condición 2: Pedido solo (sin deuda) ya excede el límite
                elif rec.amount_total_dual > rec.customer_blocking_limit_usd and not rec.is_credit_limit_final_approved:
                    rec.is_credit_limit_approval = True
                # Condición 3: Solo advertencia (opcional si quieres mantenerlo)
                elif rec.partner_id.credit_warning_usd and \
                        rec.amount_due_usd + rec.amount_total_dual > rec.partner_id.credit_warning_usd:
                    rec.is_credit_limit_warning = True

    is_credit_limit_approval = fields.Boolean(compute='_compute_customer_credit_limit')
    is_credit_limit_final_approved = fields.Boolean()
    is_credit_limit_warning = fields.Boolean(compute='_compute_customer_credit_limit')


    def action_confirm(self):
        """
        Verifica el límite de crédito en USD y el monto total adeudado antes de confirmar el pedido.
        El pedido se bloquea solo si el monto total supera el límite establecido y no tiene aprobación.
        """
        partner_id = self.partner_id
        total_amount_usd = self.amount_due_usd

        if partner_id.credit_check:
            # Verificamos si existen movimientos contables posteados
            existing_move = self.env['account.move'].search([
                ('partner_id', '=', partner_id.id),
                ('state', '=', 'posted')
            ])

            # Condición 1: excede límite total sin aprobación final
            if self.amount_due_usd > self.customer_blocking_limit_usd and not self.is_credit_limit_final_approved:
                difference_amount = round((self.amount_due_usd + self.amount_total) - self.customer_blocking_limit_usd, 2)
                raise AccessDenied(_(
                    'No se puede confirmar el Pedido de Venta. '
                    'El cliente ha superado su límite de crédito aprobado en USD por %s. '
                    'Solicite aprobación para continuar.' % difference_amount
                ))

            # Condición 2: excede límite y no hay movimientos contables
            elif partner_id.credit_blocking_usd <= total_amount_usd and not existing_move:
                view_id = self.env.ref('sale_account_manager_customer_credit_limit_approval.view_warning_wizard_form')
                context = dict(self.env.context or {})
                context['message'] = (
                    "Límite de bloqueo de clientes excedido sin tener una cuenta por cobrar, ¿Quieres continuar?"
                )
                context['default_sale_id'] = self.id
                if not self._context.get('warning'):
                    return {
                        'name': 'Advertencia',
                        'type': 'ir.actions.act_window',
                        'view_mode': 'form',
                        'res_model': 'warning.wizard',
                        'view_id': view_id.id,
                        'target': 'new',
                        'context': context,
                    }

            # Condición 3: excede solo el límite de advertencia
            elif partner_id.credit_warning_usd <= total_amount_usd and partner_id.credit_blocking_usd > total_amount_usd:
                view_id = self.env.ref('sale_account_manager_customer_credit_limit_approval.view_warning_wizard_form')
                context = dict(self.env.context or {})
                context['message'] = "Límite de advertencia de cliente excedido, ¿Desea continuar?"
                context['default_sale_id'] = self.id
                if not self._context.get('warning'):
                    return {
                        'name': 'Advertencia',
                        'type': 'ir.actions.act_window',
                        'view_mode': 'form',
                        'res_model': 'warning.wizard',
                        'view_id': view_id.id,
                        'target': 'new',
                        'context': context,
                    }

            # Condición 4: bloqueo sin aprobación
            elif partner_id.credit_blocking_usd <= total_amount_usd and not self.is_credit_limit_final_approved:
                raise AccessDenied(_('Límite de crédito del cliente excedido.'))

        # Si pasa todas las validaciones, continúa con el proceso estándar
        return super(SaleOrder, self).action_confirm()
    
    def _assign_activity_to_group(self, group_xml_id, summary, note):
        group = self.env.ref(group_xml_id)
        users = self.env['res.users'].search([('groups_id', 'in', group.id)])
        activity_type = self.env.ref('mail.mail_activity_data_todo')

        for order in self:
            for user in users:
                existing_activity = self.env['mail.activity'].search([
                    ('res_model', '=', 'sale.order'),
                    ('res_id', '=', order.id),
                    ('user_id', '=', user.id),
                    ('activity_type_id', '=', activity_type.id),
                ], limit=1)
                if not existing_activity:
                    self.env['mail.activity'].create({
                        'activity_type_id': activity_type.id,
                        'summary': summary,
                        'note': note,
                        'res_model_id': self.env['ir.model']._get_id('sale.order'),
                        'res_id': order.id,
                        'user_id': user.id,
                        'date_deadline': fields.Date.context_today(order),
                    })

    
    def send_credit_limit_approval(self):
        self.ensure_one()

        group_sales = self.env.ref('sale_account_manager_customer_credit_limit_approval.group_sales_approval')
        template_id = self.env.ref(
            'sale_account_manager_customer_credit_limit_approval.sale_order_credit_limit_approval_sales_manager'
        )

        for user in group_sales.users.filtered(lambda u: u.email):
            template_id.with_context(email_to=user.email).send_mail(self.id, force_send=True)

        self.message_post(body="Enviar para aprobación de límite de crédito a: Departamento de Ventas")
        self.state = 'sales_approval'
        self.is_credit_limit_approval = False

        self._complete_pending_activities()
        self._assign_activity_to_group(
            'sale_account_manager_customer_credit_limit_approval.group_sales_approval',
            'Revisar límite de crédito (Ventas)',
            'Este pedido necesita aprobación de ventas por límite de crédito.'
        )

    def approved_credit_limit_from_sales_manager(self):
        self.ensure_one()

        if self.state != 'sales_approval':
            return

        group_finance = self.env.ref('sale_account_manager_customer_credit_limit_approval.group_finance_approval')
        template_id = self.env.ref(
            'sale_account_manager_customer_credit_limit_approval.sale_order_credit_limit_approval_account_manager'
        )

        for user in group_finance.users.filtered(lambda u: u.email):
            template_id.with_context(email_to=user.email).send_mail(self.id, force_send=True)

        self.message_post(body="Enviar para aprobación de límite de crédito al equipo de finanzas")
        self.state = 'finance_approval'

        self._complete_pending_activities()
        self._assign_activity_to_group(
            'sale_account_manager_customer_credit_limit_approval.group_finance_approval',
            'Revisar límite de crédito (Finanzas)',
            'Este pedido necesita aprobación financiera por límite de crédito.'
        )


    def approved_credit_limit_from_account_manager(self):
        if self.state == 'finance_approval':
            self.state = 'approved'
            self.is_credit_limit_final_approved = True

    def _complete_pending_activities(self):
        """
        Marca como hechas las actividades relacionadas con este pedido.
        """
        for order in self:
            activities = self.env['mail.activity'].search([
                ('res_model', '=', 'sale.order'),
                ('res_id', '=', order.id),
                ('activity_type_id', '!=', False),
                ('user_id', '!=', False),
                ('date_deadline', '!=', False),
                ('state', '=', 'planned'),
            ])
            for activity in activities:
                activity.action_feedback('Automáticamente completada por cambio de estado')


    def reject_sale_order(self):
        if self.state == 'sales_approval':
            template_data = {
                'subject': 'Límite de crédito del cliente rechazado',
                'body_html': """<p>
                Hola %s, <br/><br/>
                </p>
                <p>
                Este correo electrónico es para notificar que la cotización número %s, perteneciente a %s, ha sido rechazada por %s (Gerente de Cuentas del Cliente). Por favor, comuníquese con él para obtener más aclaraciones. </p>
                """ % (self.user_id.name, self.name, self.partner_id.name, self.env.user.name),
                'email_from': self.env.user.partner_id.email or self.env.user.email,
                'email_to': self.user_id.email or self.user_id.partner_id.email,
                'record_name': self.name,
            }
            template_id = self.env['mail.mail'].create(template_data)
            template_id.sudo().send()
            self.state = 'reject'
            msg = "Rechazado por el gerente de ventas: %s" % self.env.user.name
            self.message_post(body=msg)
        elif self.state == 'finance_approval':
            template_data = {
                'subject': 'Límite de crédito del cliente rechazado',
                'body_html': """<p>
                Hello %s, <br/><br/>
                </p>
                <p>
                Este correo electrónico es para notificarle que la cotización número %s, perteneciente a %s, ha sido rechazada por el equipo de Finanzas.

                Para más información, comuníquese con él.</p> 
                """ % (self.user_id.name, self.name, self.partner_id.name),
                'email_from': self.env.user.partner_id.email or self.env.user.email,
                'email_to': self.user_id.email or self.user_id.partner_id.email,
                'record_name': self.name,
            }
            template_id = self.env['mail.mail'].create(template_data)
            template_id.sudo().send()
            self.state = 'reject'
            msg = "Rechazado por el equipo de finanzas: %s" % self.env.user.name
            self.message_post(body=msg)

            if self.user_id:
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': 'Pedido rechazado',
                    'note': 'Este pedido fue rechazado. Revisa con el cliente.',
                    'res_model_id': self.env['ir.model']._get_id('sale.order'),
                    'res_id': self.id,
                    'user_id': self.user_id.id,
                    'date_deadline': fields.Date.context_today(self),
                })
