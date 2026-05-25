{
    'name': 'Aviso en Facturas',
    'version': '1.0',
    'summary': 'Muestra alerta estática en facturas',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml', 
        'views/ventana_emergente.xml'  
    ],
    'installable': True,
    'application': False  # Cambiado a False para módulos técnicos
}