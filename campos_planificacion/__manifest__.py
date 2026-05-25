# -*- coding: utf-8 -*-
{
    'name': 'Sale Order Total Kilos',
    'version': '16.0',
    'summary': 'Campo que suma los kilos totales en la orden de venta',
    'category': 'Sales',
    'author': 'Samir Espina by Contables',
    'depends': ['sale'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
