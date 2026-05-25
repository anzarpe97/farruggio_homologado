{
    'name': "Purchase Cattle",
    'version': '1.0',
    'depends': ['purchase', 'stock'],
    'author': "Samir Espina By Contables",
    'category': 'Purchases',
    'summary': "compras para reses por unidades y recepción por tipo y kg",
    'description': """Este módulo permite gestionar compras por reses y asociar recepciones de carnes por tipo y kg.""",
    'data': [
        'security/purchase_cattle_security.xml',
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
        'views/product_template_views.xml',
        #'views/stock_picking_views.xml',
        #'views/cattle_product_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
}
