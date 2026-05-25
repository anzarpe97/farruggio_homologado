# -*- coding: utf-8 -*-
{
    'name': 'Account Payment Has Invoice',
    'summary': 'Adds a computed, stored checkbox on payments indicating if they are linked to invoices.',
    'version': '16.0.1.0.0',
    'category': 'Accounting/Accounting',
    'author': 'veronica pacheco',
    'license': 'LGPL-3',
    'website': '',
    'depends': ['account'],
    'data': [
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'application': False,
}