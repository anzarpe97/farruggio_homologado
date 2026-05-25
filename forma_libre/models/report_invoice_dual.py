from odoo import models, api
from odoo.tools.float_utils import float_compare


class ReportInvoiceDual(models.AbstractModel):
    _name = 'report.forma_libre.report_invoice_template_dual'
    _description = 'Factura Fiscal Dual'

    def _get_report_values(self, docids, data=None):
        docs = self.env['account.move'].browse(docids)

        for doc in docs:
            doc.sudo().print_count += 1
            if doc.print_count > 1:
                doc.sudo().invoice_template_dual_printed = True

        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': docs,
        }

from odoo import models, api
from odoo.tools.float_utils import float_compare

class ReportSaleOrder(models.AbstractModel):
    _name = "report.forma_libre.report_quotation_template"
    _description = "Reporte Presupuesto de Ventas"

    def _get_tax_amounts(self, order):
        tax_16 = 0.0
        tax_8 = 0.0
        tax_31 = 0.0

        for line in order.order_line:
            taxes = line.tax_id.compute_all(
                line.price_unit,
                quantity=line.product_uom_qty,
                product=line.product_id,
                partner=order.partner_id
            )
            for tax in taxes.get('taxes', []):
                amount = tax.get('amount', 0.0)
                tax_obj = self.env['account.tax'].browse(tax.get('id'))
                if float_compare(tax_obj.amount, 16.0, precision_digits=2) == 0:
                    tax_16 += amount
                elif float_compare(tax_obj.amount, 8.0, precision_digits=2) == 0:
                    tax_8 += amount
                elif float_compare(tax_obj.amount, 31.0, precision_digits=2) == 0:
                    tax_31 += amount

        return {
            'tax_16': tax_16,
            'tax_8': tax_8,
            'tax_31': tax_31,
        }


    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['sale.order'].browse(docids)
        res = []
        for order in docs:
            tax_amounts = self._get_tax_amounts(order)
            order_with_ctx = order.with_context(report_tax_16=tax_amounts["tax_16"],
                                               report_tax_8=tax_amounts["tax_8"],
                                               report_tax_31=tax_amounts["tax_31"])
            res.append(order_with_ctx)
        return {
            'docs': res,
        }


