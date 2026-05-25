# -*- coding: utf-8 -*-
{
    'name': "Duplicate Salesperson",

    'summary': "Copiar vendedor en facturas duplicadas",
    'description': """
        Este módulo asegura que el campo 'Vendedor' (invoice_user_id) 
        se copie correctamente al duplicar facturas en Odoo.
    """,
    'author': 'Samir Espina',
    'maintainer': 'Samir Espina',
    'category': 'Accounting',
    'version': '1.0.0',
    'depends': ['account'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'GPL-2',
}
