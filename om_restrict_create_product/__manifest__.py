# -*- coding: utf-8 -*-
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2019 OM Apps 
#    Email : omapps180@gmail.com
#################################################

{
    'name': 'Disable Quick Create Product',
    'category': 'Sales',
    'version': '16.0.1.0',
    'sequence':5,
    'summary': "Plugin Will help to disable create product in sale, purchase and invoice, Restrict Create Product, Restric Create Quick Product, Disable Quick product Create, Restrict Product Create, Product Create, Quick Create Product",
    'description': "Plugin will help to Disable quick create product for user",
    'author': 'OM Apps',
    'website': '',
    'depends': ['sale_management','purchase','account'],
    'data': [
        'views/sale_views.xml',
        'views/purchase_views.xml',
        'views/invoice_views.xml',
    ],
    'installable': True,
    'application': True,
    'images' : ['static/description/banner.png'],
    "price": 4,
    "currency": "EUR",
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
