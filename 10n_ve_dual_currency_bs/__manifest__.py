{
    'name': "REPORTE CXC Y CXP",
    'description': """
        *Informe cxc y cxp en dual moneda.
        

    """,

    'author': "Andres Castillo by Contables",
    'website': "",
    'version': '16.0.1',
    'category': 'Localization',
    'license': 'AGPL-3',
    'depends': ['base','web','account','contacts','product','sale','account_dual_currency'],
    'data': [
        'security/ir.model.access.csv',
        #'data/mail_channel.xml',
        #'data/ir_cron.xml',
        'data/due_range_cxp_data.xml',
        'data/due_range_data.xml',
        'views/account_menu.xml',
        #'views/product_template.xml',
        #'views/res_currency.xml',
        #'views/sale_order.xml',
        #'views/account_move.xml',
        #'views/purchase_order.xml',
        #'wizard/account_payment_register.xml',
        #'views/account_payment.xml',
        #REPORTES
        'wizard/account_invoice_report_cxc.xml',
        'wizard/account_invoice_report_cxp.xml',
        #'views/report_invoice.xml'

    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    "assets": {
        "web.assets_backend": [
            #'10n_ve_dual_currency_bs/static/src/js/widget_multy_currency.js',
            #'10n_ve_dual_currency_bs/static/src/xml/widget_test.xml',
        ],
    },

}
