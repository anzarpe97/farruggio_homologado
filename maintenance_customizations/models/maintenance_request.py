from odoo import fields, models


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    maintenance_type = fields.Selection(
        selection_add=[("predictive", "Predictivo")],
    )

    responsable = fields.Selection(
        selection=[
            ("electricista", "Electricista"),
            ("mecanico", "Mecánico"),
            ("electromecanico", "Electromecánico"),
            ("soldador", "Soldador"),
            ("tecnico_refrigeracion", "Técnico de Refrigeración"),
            ("especialista", "Especialista"),
        ],
        string="Responsable",
        tracking=True,
    )
