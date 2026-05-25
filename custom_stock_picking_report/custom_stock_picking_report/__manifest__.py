{
    'name': 'Custom Stock Picking Report',
    'version': '16.0.1.0.0',
    'summary': 'Reporte personalizado de picking con descripción de venta',
    'author': 'Tu Nombre',
    'category': 'Warehouse',
    'depends': ['stock', 'sale_management'],
    'data': [
        'report/stock_picking_report.xml',
        'report/report.xml',
        'report/report_action.xml',
        'views/stock_picking_report_menu.xml',
        'views/stock_move_notas.xml',
        'views/stock_picking_print_button.xml',
    ],
    'installable': True,
    'application': False,
}
