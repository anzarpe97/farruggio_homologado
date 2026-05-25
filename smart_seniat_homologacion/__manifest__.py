# -*- coding: utf-8 -*-
{
    'name': "Smart Seniat Homologacion",
    'summary': """
    """,
    'description': """
    """,
    'author': 'Smart Systems',
    'company': 'Smart Systems, C.A.',
    'maintainer': 'Smart Systems',
    'website': 'https://smartsystems.com.ve/',
    'category': 'Smart Systems/Desarrollos',
    'version': '2.1.0',
    'depends': ['base','l10n_ve_full','account','account_reports','account_followup','web',
                'stock_account','account_accountant','analytic','stock_landed_costs','account_debit_note','mail',
                'account_reports_cash_basis', 'account_asset'],
    'data': [
        'views/category.xml',
        'views/account_move.xml',
        'wizard/account_move_reversal_view.xml',
        'data/sequence.xml'
    ],
    'images': [
        'static/description/icon.png',
    ],
    "currency": "USD",
    'installable': True,
    'application': True,
    'license': 'OEEL-1',
    
    'assets': {
    'web.assets_backend': [
        'smart_seniat_homologacion/static/src/css/styles.css',
        'smart_seniat_homologacion/static/src/js/**/*',
        'smart_seniat_homologacion/static/src/xml/**/*',
    ],
    }
}
