{
    'name': 'Inventory Cost Update',
    'version': '16.0.1.0.0',
    'summary': 'Agrega costo en recepciones y actualiza precio estándar en USD',
    'author': 'Samir Espina by Contables',
    'depends': ['stock', 'product'],
    'data': [
        'security/inventory_cost_group.xml',
        'views/stock_move_views.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
}
