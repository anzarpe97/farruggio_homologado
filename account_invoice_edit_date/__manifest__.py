{
    'name': 'Editable Invoice Date on Posted Vendor Bills',
    'version': '16.0.1.0.0',
    'depends': ['account'],
    'category': 'Accounting',
    'summary': 'Allows editing the accounting date on posted vendor bills',
    'author': 'Samir Espina',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'data': [
        'views/account_move_view.xml',
    ],
}
