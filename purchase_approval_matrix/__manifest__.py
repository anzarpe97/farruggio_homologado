{
    "name": "Purchase Approval Matrix",
    "version": "16.0.1.0.0",
    "depends": ["purchase","purchase_dual_currency"],
    "author": "Aecas / ChatGPT",
    "description": "Flujo de aprobación de compras basado en matriz de aprobadores por categoría, descripción, clasificación y monto.",
    "category": "Purchases",
    "data": [
        "security/ir.model.access.csv",
        "views/purchase_approval_matrix_views.xml",
        "views/purchase_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
