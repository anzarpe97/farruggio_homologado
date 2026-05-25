{
    'name': 'Reporte de Productos Vendidos',
    'version': '1.0',
    'depends': ['sale', 'account'],
    'category': 'Accounting',
    'author': 'Veronica Pacheco',
    'description': 'Reporte de productos con precio y costo.',
    'data': [
        'security/ir.model.access.csv',
        'wizard/product_report_wizard_view.xml',
        'reports/report_product_template.xml',
    ],
    'installable': True,
    'application': False,
}
