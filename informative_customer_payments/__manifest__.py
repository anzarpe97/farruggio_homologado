{
    'name': 'Informative Customer Payments',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Registro informativo de pagos de clientes por parte de vendedores',
    'depends': ['base', 'sales_team', 'account', 'account_dual_currency'],
    'data': [
        'data/data.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/informative_payment_views.xml',
    ],
    'installable': True,
    'application': True,
}
