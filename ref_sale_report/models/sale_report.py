from odoo import models, fields, api

class SaleReport(models.Model):
    _inherit = 'sale.report'

    subtotal_usd = fields.Float(string="Subtotal en USD", readonly=True)
    invoice_date = fields.Date(string='Fecha de Factura', readonly=True)

    # Campos estándar que deben estar presentes
    name = fields.Char(string='Order Reference', readonly=True)
    date = fields.Datetime(string='Order Date', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)
    product_uom_qty = fields.Float(string='Qty Ordered', readonly=True)
    qty_delivered = fields.Float(string='Qty Delivered', readonly=True)
    qty_invoiced = fields.Float(string='Qty Invoiced', readonly=True)
    qty_to_invoice = fields.Float(string='Qty To Invoice', readonly=True)
    price_total = fields.Float(string='Total', readonly=True)
    price_subtotal = fields.Float(string='Subtotal', readonly=True)
    price_tax = fields.Float(string='Taxes', readonly=True)
    untaxed_amount_to_invoice = fields.Float(string="Untaxed Amount To Invoice", readonly=True)
    untaxed_amount_invoiced = fields.Float(string="Untaxed Amount Invoiced", readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    team_id = fields.Many2one('crm.team', string='Sales Team', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    nbr = fields.Integer(string='# of Lines', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
    ], string='Invoice Status', readonly=True)

    @api.model
    def _query(self):
        return """
            SELECT
                l.id AS id,
                s.name AS name,
                l.product_id AS product_id,
                t.categ_id AS categ_id,
                s.date_order AS date,
                s.state AS state,
                s.company_id AS company_id,
                s.user_id AS user_id,
                s.partner_id AS partner_id,
                s.pricelist_id AS pricelist_id,
                s.analytic_account_id AS analytic_account_id,
                s.team_id AS team_id,
                l.order_id AS order_id,
                l.currency_id AS currency_id,
                s.fiscal_position_id AS fiscal_position_id,
                l.discount AS discount,
                l.product_uom AS product_uom,
                l.product_uom_qty / u.factor * u2.factor AS product_uom_qty,
                l.qty_delivered / u.factor * u2.factor AS qty_delivered,
                l.qty_invoiced / u.factor * u2.factor AS qty_invoiced,
                l.qty_to_invoice / u.factor * u2.factor AS qty_to_invoice,
                l.price_total AS price_total,
                l.price_subtotal AS price_subtotal,
                l.price_tax AS price_tax,
                (l.price_total - l.price_subtotal) AS price_tax_value,
                s.invoice_status AS invoice_status,

                -- Agregar los campos que faltan
                l.untaxed_amount_to_invoice AS untaxed_amount_to_invoice,
                l.untaxed_amount_invoiced AS untaxed_amount_invoiced,
                p.product_tmpl_id AS product_tmpl_id,

                CASE
                    WHEN (l.qty_invoiced / u.factor * u2.factor) > 0 THEN
                        CASE
                            WHEN s.currency_id = rc.id THEN (l.qty_invoiced / u.factor * u2.factor) * l.price_unit
                            ELSE ((l.qty_invoiced / u.factor * u2.factor) * l.price_unit) / COALESCE(s.tax_today, 1)
                        END
                    ELSE 0
                END AS subtotal_usd,

                MIN(am.invoice_date) AS invoice_date

            FROM sale_order_line l
            JOIN sale_order s ON s.id = l.order_id
            LEFT JOIN product_product p ON p.id = l.product_id
            LEFT JOIN product_template t ON t.id = p.product_tmpl_id
            LEFT JOIN uom_uom u ON u.id = l.product_uom
            LEFT JOIN uom_uom u2 ON u2.id = t.uom_id
            LEFT JOIN res_currency rc ON rc.name = 'USD'

            LEFT JOIN account_move am ON am.invoice_origin = s.name
                AND am.move_type IN ('out_invoice', 'out_refund')
                AND am.state = 'posted'

            WHERE l.display_type IS NULL

            GROUP BY
                l.id, s.name, l.product_id, t.categ_id, s.date_order, s.state, s.company_id,
                s.user_id, s.partner_id, s.pricelist_id, s.analytic_account_id, s.team_id,
                l.order_id, l.currency_id, s.fiscal_position_id, l.discount, l.product_uom,
                u.factor, u2.factor, l.price_unit, s.invoice_status, rc.id, s.currency_id, 
                s.tax_today, 
                -- Agregar los nuevos campos al GROUP BY
                l.untaxed_amount_to_invoice, l.untaxed_amount_invoiced, p.product_tmpl_id,
                -- Agregar campos de precio que pueden necesitar agrupación
                l.price_total, l.price_subtotal, l.price_tax
        """

    def _auto_init(self):
        self.env.cr.execute("DROP MATERIALIZED VIEW IF EXISTS sale_report CASCADE")
        return super()._auto_init()