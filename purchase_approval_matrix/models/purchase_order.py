from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(selection_add=[
        ('to approve', 'Por Aprobar'),
        ('approved', 'Aprobado'),
    ])

    x_categoria = fields.Selection([
        ('materiales', 'Materiales'),
        ('compras_indirectas', 'Compras indirectas'),
        ('servicios', 'Servicios'),
        ('transporte', 'Transporte'),
        ('compras_estrategicas', 'Compras estratégicas'),
        ('compras_menores', 'Compras menores'),
        ('gestion_corporativa', 'Gestión corporativa'),
        ('empaque', 'Empaque'),
    ], string='Categoría de Compra', required=True)

    x_descripcion = fields.Selection([
        ('papeleria', 'Papelería, mobiliario, herramientas menores, consultorías, insumos de limpieza oficina'),
        ('publicidad', 'Publicidad y marketing'),
        ('seguros', 'Seguros y servicios financieros'),
        ('mantenimiento_equipos', 'Mantenimiento de equipos y repuestos básicos de operaciones'),
        ('mantenimiento_vehiculos', 'Mantenimiento de vehiculos y Thermoking'),
        ('repuestos_vehiculos', 'Repuestos e insumos vehiculos'),
        ('contratos_largo_plazo', 'Contratos a largo plazo, Tecnología avanzada, desarrollos especializados, inversiones en infraestructura'),
        ('materia_prima', 'Materia Prima (Bovino, Porcino, Pollo, huevos, embutidos)'),
        ('compra_viveres', 'Compra de viveres y verduras en general'),
        ('equipos_tecnologicos', 'Equipos tecnológicos y maquinarias industriales'),
        ('materiales_suministros', 'Materiales y suministros básicos'),
        ('uniformes', 'Uniformes de personal, merchandising en general'),
        ('empaque', 'Bolsas, etiquetas, material para producto terminado'),
    ], string='Descripción', required=True)

    x_clasificacion = fields.Selection([
        ('operacionales', 'Operacionales'),
        ('estrategicos', 'Estratégicos'),
        ('especializados', 'Especializados'),
    ], string='Clasificación', required=True)

    approval_state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por Aprobar'),
        ('approved', 'Aprobado')
    ], default='draft', string="Estado de Aprobación", tracking=True)

    approval_matrix_id = fields.Many2one('purchase.approval.matrix', string='Matriz de Aprobación', compute='_compute_approval_matrix', store=True)

    approver_user_ids = fields.Many2many('res.users', 
                                         string='Aprobadores Asignados', 
                                         compute='_compute_approvers', 
                                         store=True, 
                                         compute_sudo=True
                                         )
    
    x_is_approver = fields.Boolean(compute='_compute_is_approver')

    def _compute_is_approver(self):
        for order in self:
            order.x_is_approver = self.env.uid in order.approver_user_ids.ids

    @api.depends('x_categoria', 'x_descripcion', 'x_clasificacion')
    def _compute_approval_matrix(self):
        for order in self:
            matrix = self.env['purchase.approval.matrix'].search([
                ('categoria', '=', order.x_categoria or ''),
                ('descripcion', '=', order.x_descripcion or ''),
                ('clasificacion', '=', order.x_clasificacion or ''),
            ], limit=1)
            order.approval_matrix_id = matrix

    @api.depends('amount_total', 'approval_matrix_id')
    def _compute_approvers(self):
        for order in self:
            matrix = order.approval_matrix_id
            if not matrix:
                order.approver_user_ids = [(5, 0, 0)]
                continue
            amount = order.amount_total if order.currency_id.name == 'USD' else order.amount_total_dual
            if amount <= 1500:
                order.approver_user_ids = [(6, 0, matrix.aprobador_inicial_id.ids)]
            elif amount <= 5000:
                order.approver_user_ids = [(6, 0, matrix.aprobador_nivel1_id.ids)]
            else:
                order.approver_user_ids = [(6, 0, matrix.aprobador_nivel2_id.ids)]

    def action_submit_for_approval(self):
        for order in self:
            if order.approval_state != 'draft':
                continue
            if not order.approver_user_ids:
                raise UserError(_("No se pudo determinar los aprobadores para este pedido."))
            order.write({'approval_state': 'to_approve'})
            # Aquí podrías notificar a los aprobadores

    # def action_approve(self):
    #     for order in self:
    #         if order.approval_state != 'to_approve':
    #             continue
    #         # Verifica que el usuario esté autorizado
    #         if self.env.uid not in order.approver_user_ids.ids:
    #             raise UserError(_(
    #                 "El usuario '%s' no está autorizado para aprobar este pedido. "
    #                 "Solo los aprobadores asignados pueden hacerlo."
    #             ) % self.env.user.name)
    #         order.write({'approval_state': 'approved'})
    #         order.button_confirm()

    def button_approve(self):
        for order in self:
            if order.approval_state != 'to_approve':
                continue

            # Validación: el usuario debe estar en la lista de aprobadores
            if self.env.uid not in order.approver_user_ids.ids:
                raise UserError(_(
                    "El usuario '%s' no está autorizado para aprobar este pedido. "
                    "Solo los aprobadores asignados pueden hacerlo."
                ) % self.env.user.name)

            # Marcar como aprobado
            order.write({'approval_state': 'approved'})
            order.mark_all_todo_activities_done()

        # Continuar con el proceso normal de aprobación
        return super(PurchaseOrder, self).button_approve()


    def button_confirm(self):
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        orders_to_confirm = self.browse()

        for order in self:
            if not order.approver_user_ids:
                raise UserError(_("No se puede confirmar el pedido porque no hay aprobadores asignados."))

            if order.approval_state != 'approved' and order.approver_user_ids and self.env.user not in order.approver_user_ids:
                order.write({
                    'approval_state': 'to_approve',
                    'state': 'to approve'
                })
                summary = _("Aprobación pendiente de Pedido de Compra")
                note = _("Por favor revise y apruebe el pedido %s.") % order.name

                # 🔄 Crear nuevas actividades para los aprobadores asignados
                for user in order.approver_user_ids:
                    order.activity_schedule(
                        activity_type_id=activity_type.id,
                        user_id=user.id,
                        summary=summary,
                        note=note,
                    )
                continue

            if order.approval_state != 'approved':
                if self.env.uid not in order.approver_user_ids.ids:
                    raise UserError(_("Solo los aprobadores asignados pueden confirmar el pedido."))
                order.approval_state = 'approved'

            orders_to_confirm |= order

        res = super(PurchaseOrder, orders_to_confirm).button_confirm()

        for order in orders_to_confirm:
            if order.state == 'purchase' and order.approval_state == 'approved':
                order.mark_all_todo_activities_done()

        return res


    def write(self, vals):
        res = super(PurchaseOrder, self).write(vals)
        for order in self:
            if vals.get('state') == 'purchase' or order.state == 'purchase':
                if order.approval_state != 'approved':
                    order.approval_state = 'approved'
                order.mark_all_todo_activities_done()
        return res
    
    def copy(self, default=None):
        default = dict(default or {})
        default['approval_state'] = 'draft'
        return super(PurchaseOrder, self).copy(default)

    def activity_unlink(self, activity_types_xmlids):
        """Borra actividades pendientes del pedido para esos tipos"""
        for activity_type_xmlid in activity_types_xmlids:
            activity_type = self.env.ref(activity_type_xmlid, raise_if_not_found=False)
            if activity_type:
                self.activity_ids.filtered(lambda act: act.activity_type_id == activity_type).unlink()

    def mark_all_todo_activities_done(self):
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            _logger.warning("No se encontró el tipo de actividad 'To Do'")
            return

        for order in self:
            _logger.info("Analizando orden: %s", order.name)
            all_acts = order.activity_ids.sudo()
            _logger.info("Actividades totales: %s", all_acts)

            for act in all_acts:
                _logger.info("Actividad: id=%s, tipo=%s, estado=%s, asignado=%s",
                            act.id, act.activity_type_id.name, act.state, act.user_id.name)

            activities = all_acts.filtered(
                lambda act: act.activity_type_id.id == activity_type.id and act.state in ('planned', 'overdue', 'today')
            )

            _logger.info("Actividades por cerrar: %s", activities)

            for act in activities:
                act.sudo().action_feedback(feedback=_("Pedido aprobado."))
                _logger.info("Actividad marcada como hecha: %s", act.id)

