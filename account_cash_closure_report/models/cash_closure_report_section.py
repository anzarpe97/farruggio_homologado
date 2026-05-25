from odoo import models, fields

class CashClosureReportSection(models.Model):
    _name = 'cash.closure.report.section'
    _description = 'Sección de Reporte de Cierre de Caja'

    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True)
