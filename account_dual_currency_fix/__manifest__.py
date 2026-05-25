{
    'name': 'Account Dual Currency Fixes',
    'version': '16.0.1.0.0',
    'category': 'Accounting/Invoicing',
    'summary': 'Correcciones de caché. para el campo amount_residual_usd en facturas.',
    'author': 'Aecas',
    'license': 'AGPL-3',
    'depends': [
        'account',  # Dependencia del módulo base de contabilidad
        'account_dual_currency', # Reemplaza con el nombre exacto de tu módulo dual currency
    ],
    'data': [
        'data/recalculate_action.xml',
    ],
    'installable': True,
    'auto_install': False,
}