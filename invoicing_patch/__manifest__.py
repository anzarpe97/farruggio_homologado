# -*- coding: utf-8 -*-
{
    'name': 'Sale Force Fully Invoiced',
    'summary': 'Fuerza el estado de facturación del pedido de venta a totalmente facturado al existir cualquier factura, y revierte a A facturar si se elimina la última.',
    'version': '16.0.1.0.0',
    'category': 'Sales',
    'author': 'Custom Patch',
    'license': 'LGPL-3',
    'depends': ['sale_management','account','sale_stock'],
    'data': [],
    'installable': True,
    'application': False,
}