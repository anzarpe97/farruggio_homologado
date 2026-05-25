# from odoo import models, api
# from odoo.tools.float_utils import float_compare

# class ReportSaleOrder(models.AbstractModel):
#     _name = "report.forma_libre.report_saleorder_template"  # Ajusta el nombre según tu reporte
#     _description = "Reporte Presupuesto de Ventas"

#     def _get_tax_amounts(self, order):
#         tax_16 = 0.0
#         tax_8 = 0.0
#         tax_31 = 0.0
#         for line in order.order_line:
#             for tax in line.tax_id:
#                 if float_compare(tax.amount, 16.0, precision_digits=2) == 0:
#                     tax_16 += line.price_tax
#                 elif float_compare(tax.amount, 8.0, precision_digits=2) == 0:
#                     tax_8 += line.price_tax
#                 elif float_compare(tax.amount, 31.0, precision_digits=2) == 0:
#                     tax_31 += line.price_tax
#         return {
#             "tax_16": tax_16,
#             "tax_8": tax_8,
#             "tax_31": tax_31,
#         }

#     @api.model
#     def _get_report_values(self, docids, data=None):
#         docs = self.env['sale.order'].browse(docids)
#         res = []
#         for order in docs:
#             tax_amounts = self._get_tax_amounts(order)
#             res.append({
#                 'order': order,
#                 'tax_16': tax_amounts["tax_16"],
#                 'tax_8': tax_amounts["tax_8"],
#                 'tax_31': tax_amounts["tax_31"],
#             })
#         return {
#             'docs': docs,
#             'orders_data': res,
#         }
