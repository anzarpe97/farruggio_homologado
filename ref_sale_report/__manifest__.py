{
    'name': 'Subtotal en USD en Reporte de Ventas',
    'version': '16.0.1.0.0',
    'summary': 'Agrega una medida de Subtotal en USD al análisis de ventas y costos en facturas',
    'description': '''
        Este módulo agrega:
        - Una medida personalizada "Subtotal en USD" en el informe de ventas (sale.report)
        - Campos de costo en las líneas de factura tomados del pedido de venta
        - Cálculo de margen y margen porcentual en facturas
        La medida se calcula tomando el subtotal del pedido y convirtiéndolo a USD con base en la tasa del documento.
    ''',
    'category': 'Sales',
    'author': 'Samir Espina',
    'website': 'https://tusitio.com',
    'depends': ['sale', 'account', 'sale_margin', 'purchase_REF'],
    'data': [
        'views/account_move_views.xml',
        'views/account_move_actions.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
