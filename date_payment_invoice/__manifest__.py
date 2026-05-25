{
    'name': 'Última Fecha de Pago en Factura',
    'version': '16.0.1.0.0',
    'summary': 'Agrega campo que muestra la última fecha de pago de una factura',
    'category': 'Accounting',
    'author': 'Samir / OpenAI',
    'depends': ['account'],
    'data': [
        'views/account_move_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    # 'post_init_hook': 'post_init_recalcular_fechas_pago',
}
