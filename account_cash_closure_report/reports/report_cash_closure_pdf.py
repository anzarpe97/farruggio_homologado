# -*- coding: utf-8 -*-
from odoo import api, models

class ReportCashClosure(models.AbstractModel):
    # Debe coincidir EXACTAMENTE con el <report name="..."> del XML
    _name = 'report.account_cash_closure_report.report_cash_closure_pdf_template'
    _description = 'Reporte PDF Cierre de Caja'
    _auto = False                      # no crear tabla
    _table = 'r_acc_cash_closure_pdf'  # nombre corto para pasar la validación

    @api.model
    def _get_report_values(self, docids, data=None):
        # Robustez para docids
        if not docids and data and data.get('docids'):
            docids = data['docids']
        if not docids:
            docids = self.env.context.get('active_ids', [])

        wizards = self.env['cash.closure.report.wizard'].browse(docids).exists()
        if not wizards:
            return {
                'doc_ids': [],
                'doc_model': 'cash.closure.report.wizard',
                'docs': [],
                'company': self.env.company,
                'lines': [],
                'totals': {},
            }

        wiz = wizards[0]
        lines, totals = wiz._compute_lines()
        cobros_lines, cobros_totals = wiz._get_cobros_summary()
        general_summary = wiz._get_general_summary()

        # Obtener los códigos de las secciones seleccionadas
        selected_section_codes = set(wiz.report_section_ids.mapped('code')) if wiz.report_section_ids else set()

        return {
            'doc_ids': wizards.ids,
            'doc_model': 'cash.closure.report.wizard',
            'docs': wizards,             # el QWeb puede iterar sobre docs
            'company': self.env.company,
            'lines': lines,
            'totals': totals,
            'cobros_lines': cobros_lines,
            'cobros_totals': cobros_totals,
            'general_summary': general_summary,
            'selected_section_codes': selected_section_codes,
        }
