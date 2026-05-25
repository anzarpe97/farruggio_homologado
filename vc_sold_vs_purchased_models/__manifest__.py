{
    'name': 'Sold vs Purchased Report',
    'version': '16.0.1.0.0',
    'summary': 'Excel: Productos Vendidos vs Comprados con filtros por fecha, comercial y cliente (modelo/attachment).',
    'author': 'Veronica Pacheco',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'purchase', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/sold_vs_purchased_wizard.xml',
    ],
    'installable': True,
    'application': False,
}
