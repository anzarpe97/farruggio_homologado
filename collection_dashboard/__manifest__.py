{
    'name': 'Collection Dashboard',
    'version': '16.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Módulo personalizado para gestión de cobranzas',
    'description': """
        Collection Dashboard es un módulo para gestionar y supervisar las facturas por cobrar.
        Permite sincronizar facturas desde account.move, visualizar vencimientos por zona,
        identificar facturas vencidas y críticas, y ofrece vistas tipo lista, kanban, pivot y
        gráficas para un seguimiento operativo y analítico de la cobranza.
        Incluye filtros preconfigurados, agrupaciones y un estilo visual optimizado para
        resaltar estados y facilitar la toma de decisiones del equipo de cobranzas.
    """,
    'author': 'Contables',
    'website': 'https://www.tudominio.com',
    'depends': ['base', 'web', 'account', 'crm'],
    'data': [
        'security/collection_dashboard_security.xml',
        'security/ir.model.access.csv',
        'views/cobranza_views.xml',
        'data/cobranza_cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'collection_dashboard/static/src/css/styles.css',
            'collection_dashboard/static/src/js/cobranzas.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}       