from odoo import http
from odoo.http import request

class InvoiceApprovalController(http.Controller):

    @http.route('/approve/invoices', type='json', auth='user')
    def approve_invoices(self, ids):
        invoices = request.env['account.move'].sudo().browse(ids)
        invoices.action_approve_selected_invoices()
        return {'status': 'ok'}
