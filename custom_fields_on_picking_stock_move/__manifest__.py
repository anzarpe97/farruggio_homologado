{
    'name': 'Campos en Líneas de Órdenes de Entrega',
    'version': '16.0.1.0.0',
    'summary': 'Agrega campos Und, Nro Paqts y Nro Cestas a líneas de entrega',
    'description': """
        Añade campos personalizados a las líneas de productos en órdenes de entrega.
        Campos: Und, Nro Paqts, Nro Cestas
    """,
    'author': 'Samir Espina by Contables',
    'website': 'https://contablesag.com',
    'depends': ['stock'],
    'category': 'Inventory',
    'data': [
        'views/stock_move_line_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}