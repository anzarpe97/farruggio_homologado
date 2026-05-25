from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ResUsers(models.Model):
    _inherit = 'res.users'

    can_see_all_contacts = fields.Boolean(
        string="Puede ver todos los contactos",
        help="Si está activo, el usuario puede ver todos los contactos, no solo los asignados a él."
    )

class ResPartner(models.Model):
    _inherit = 'res.partner'

    user_id = fields.Many2one(
        'res.users',
        string='Vendedor Asignado',
        default=lambda self: self.env.user,
        help='Vendedor responsable de este contacto.'
    )

    @api.model
    def _default_user_id(self):
        return self.env.user

    _sql_constraints = [
        ('check_user_id_not_null', 'CHECK(user_id IS NOT NULL)', 'Debe asignarse un vendedor a cada contacto.')
    ]

    def _search(self, domain, offset=0, limit=None, order=None, count=False, **kwargs):
        current_user = self.env.user

        # Si el usuario es admin, gerente de ventas o tiene el permiso de ver todos
        if (current_user.has_group('base.group_system') or
                current_user.has_group('sales_team.group_sale_manager') or
                current_user.can_see_all_contacts):
            return super(ResPartner, self)._search(domain, offset, limit, order, count, **kwargs)

        # Vendedores normales solo ven sus propios contactos
        user_domain = [('user_id', '=', current_user.id)]
        if domain:
            domain = ['&'] + user_domain + domain
        else:
            domain = user_domain

        return super(ResPartner, self)._search(domain, offset, limit, order, count, **kwargs)

    @api.constrains('user_id')
    def _check_user_id(self):
        if not self.user_id:
            raise UserError(_("Cada contacto debe tener un vendedor asignado."))
