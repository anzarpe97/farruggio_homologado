{
    'name': 'Intercompany Inventory Transfer',
    'version': '1.0',
    'summary': 'Transferencia de inventario entre compañías',
    'depends': ['stock'],
    'author': 'TuNombre',
    'category': 'Inventory',
    'description': """Este módulo permite crear transferencias entre empresas creando dos pickings: uno de salida y uno de entrada no confirmado.""",
    'data': [
        'security/ir.model.access.csv',
        'data/intercompany_sequence.xml',
        'data/intercompany_data.xml',
        'views/intercompany_transfer_views.xml'
    ],
    'installable': True,
    'application': True,
    'images': ['static/description/icon.png'],
}