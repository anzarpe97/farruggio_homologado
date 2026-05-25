{
    'name': 'Aprobación de Facturas',
    'version': '16.0.1.0.0',
    'category': 'Accounting',
    'depends': ['account'],
    'data': [
        'security/account_invoice_approval_security.xml',
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/account_invoice_approval_menu.xml',
    ],
    'installable': True,
    'application': False,

    'assets': {
        'web.assets_backend': [
            'account_invoice_approval/static/src/js/invoice_approve_button.js',
        ],
    },

}
