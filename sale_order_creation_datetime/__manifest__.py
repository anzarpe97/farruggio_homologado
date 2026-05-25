{
    'name': 'Fecha de creación en Presupuesto de Venta',
    'version': '16.0.1.0.0',
    'summary': 'Muestra la fecha y hora de creación del presupuesto en el pedido de venta.',
    'category': 'Sales',
    'depends': ['sale'],
    'data': [
        'actions/sale_order_actions.xml',
        'views/sale_order_view.xml',
    ],
    'installable': True,
    'application': False,
}
