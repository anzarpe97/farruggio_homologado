# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    currency_id_dif = fields.Many2one("res.currency", string="Referencia en Divisa", default=lambda self: self.env.company.currency_id_dif)
    total_ref = fields.Monetary(store=True, readonly=True, compute="_total_ref", string="Total (REF)", default=0,
                                currency_field='currency_id_dif')
    dias = fields.Char(compute='_compute_dias', store=True, string="Días")
    horas = fields.Char(compute='_compute_dias', store=True, string="Horas")

    department_id = fields.Many2one('hr.department', string='Departamento', related='employee_id.department_id', store=True)

    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura', related='slip_id.struct_id', store=True)

    @api.depends('total', 'slip_id.tasa_cambio')
    def _total_ref(self):
        # tax_today_id = self.env['res.currency'].search([('name', '=', 'USD')])
        for record in self:
            if record.slip_id.tasa_cambio > 0:
                record[("total_ref")] = record.total * record.slip_id.tasa_cambio
            else:
                record[("total_ref")] = 0

    @api.depends('name', 'total_ref', 'salary_rule_id', 'slip_id.contract_id.anios_antiguedad')
    def _compute_dias(self):
        for rec in self:
            valor_dias = ""
            valor_horas = ""
            worked_days_line_ids = rec.slip_id.worked_days_line_ids
            
            # Cálculo especial para ADIVACA y ADIBONOVACA
            if rec.code == 'ADIVACA':
                if rec.slip_id.contract_id.anios_antiguedad <= 1:
                    valor_dias = rec.slip_id.contract_id.anios_antiguedad - 1
                else:
                    valor_dias = rec.slip_id.contract_id.anios_antiguedad - 1
            elif rec.code == 'GPSAB':
                prestaciones = self.env['hr.employee.prestaciones'].search(
                    [('employee_id', '=', rec.slip_id.employee_id.id)],
                    order='create_date desc',
                    limit=1
                )
                valor_dias = prestaciones.dias_acumulados if prestaciones else 0
            elif rec.code == 'GPSC':
                prestaciones = self.env['hr.employee.prestaciones'].search(
                    [('employee_id', '=', rec.slip_id.employee_id.id)],
                    order='create_date desc',
                    limit=1
                )
                valor_dias = prestaciones.dias_adici_acumulado if prestaciones else 0
            elif rec.code == 'VACAV':
                if rec.contract_id.anios_antiguedad > 0:
                    valor_dias = rec.slip_id.contract_id.anios_antiguedad + 15
                else:
                    valor_dias = 0
            elif rec.code == 'BONOVACAV':
                if rec.contract_id.anios_antiguedad > 0:
                    valor_dias = rec.slip_id.contract_id.anios_antiguedad + 16
                else:
                    valor_dias = 0
            elif rec.code == 'VACAF':
                if rec.contract_id.anios_antiguedad > 0:
                    valor_dias = rec.slip_id.x_studio_dias_de_vacaciones_no_disfrutados + 15
                else:
                    hoy = rec.slip_id.date_to
                    fecha_ingreso = rec.contract_id.date_start

                    if hoy and fecha_ingreso:
                        anios_antiguedad = rec.contract_id.anios_antiguedad
                        dias_antiguedad = rec.contract_id.dias_antiguedad

                        if anios_antiguedad > 0:
                            mes_actual = hoy.month
                        else:
                            mes_actual = hoy.month
                            if mes_actual < 0:
                                mes_actual = 0  # Evitar meses negativos si está en el mismo año y mes de ingreso futuro
                            elif dias_antiguedad > 28:
                                mes_actual = mes_actual + 1

                        valor_dias = ((15 + anios_antiguedad) / 12) * mes_actual
            elif rec.code == 'BONOVACAF':
                if rec.contract_id.anios_antiguedad > 0:
                    valor_dias = rec.slip_id.x_studio_bono_vacacional_no_disfrutado + 16
                else:
                    hoy = rec.slip_id.date_to
                    fecha_ingreso = rec.contract_id.date_start
                    dias_antiguedad = rec.contract_id.dias_antiguedad

                    if hoy and fecha_ingreso:
                        anios_antiguedad = rec.contract_id.anios_antiguedad

                        if anios_antiguedad > 0:
                            mes_actual = hoy.month
                        else:
                            mes_actual = hoy.month
                            if mes_actual < 0:
                                mes_actual = 0  # Evitar meses negativos si está en el mismo año y mes de ingreso futuro
                            elif dias_antiguedad > 28:
                                mes_actual = mes_actual + 1

                        valor_dias = ((16 + anios_antiguedad) / 12) * mes_actual
            elif rec.code == 'UTILIDF':
                hoy = rec.slip_id.date_to
                fecha_ingreso = rec.contract_id.date_start

                if hoy and fecha_ingreso:
                    anios_antiguedad = rec.contract_id.anios_antiguedad

                    if anios_antiguedad > 0:
                        mes_actual = hoy.month
                    else:
                        mes_actual = hoy.month
                        if mes_actual < 0:
                            mes_actual = 0  # Evitar meses negativos si está en el mismo año y mes de ingreso futuro

                    valor_dias = (60 / 12) * mes_actual
                else:
                    valor_dias = 0
            elif rec.code == 'ADIBONOVACA':
                    valor_dias = rec.slip_id.contract_id.anios_antiguedad

            elif rec.code == 'LITC':
                    anios = rec.slip_id.contract_id.anios_antiguedad
                    meses = rec.slip_id.contract_id.meses_antiguedad

                    if meses >= 6:
                        anios += 1

                    dias_litc = anios * 30 
                    valor_dias = dias_litc

            elif rec.code == 'BONOVACA':
                valor_dias = rec.slip_id.contract_id.dias_bono_vacacional
            elif rec.code == 'VACA':
                valor_dias = 15
            elif rec.category_id.code == 'BASIC':
                valor_dias = (
                    worked_days_line_ids.filtered(lambda x: x.code == 'WORK100').number_of_days +
                    worked_days_line_ids.filtered(lambda x: x.code == 'AUSEP').number_of_days
                )
            elif rec.code == 'ALIMEN':
                dias_codes = ['WORK100', 'AUSEP', 'DDESD', 'FERIT', 'DDESS']
                valor_dias = sum(worked_days_line_ids.filtered(lambda x: x.code in dias_codes).mapped('number_of_days'))
                if valor_dias > 30:
                    valor_dias = 30
                elif valor_dias < 30:
                    valor_dias = 30
            else:
                worked_days_line_ids = worked_days_line_ids.filtered(lambda x: x.code == rec.code)
                if rec.salary_rule_id.mostrar_cantidad == 'dias':
                    valor_dias = round(worked_days_line_ids.number_of_days, 2) if worked_days_line_ids else ""
                    valor_horas = ""
                elif rec.salary_rule_id.mostrar_cantidad == 'horas':
                    valor_horas = round(worked_days_line_ids.number_of_hours, 2) if worked_days_line_ids else ""
                    valor_dias = ""
                else:
                    valor_dias = ""
                    valor_horas = ""

            # Redondear si es un número antes de convertir a string
            if isinstance(valor_dias, (int, float)):
                valor_dias = round(valor_dias, 2)
            if isinstance(valor_horas, (int, float)):
                valor_horas = round(valor_horas, 2)

            rec.dias = str(valor_dias)
            rec.horas = str(valor_horas)