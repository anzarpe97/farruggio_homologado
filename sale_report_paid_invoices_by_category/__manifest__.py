{
    "name": "Reporte de Facturas Pagadas por Categoría",
    "version": "16.0.1.0.0",
    "depends": ["sale", "account"],
    "category": "Sales",
    "description": "Genera un reporte de Excel con las facturas pagadas agrupadas por categoría y comercial.",
    "data": [
        "security/ir.model.access.csv",
        "wizard/sale_report_wizard_view.xml"
    ],
    "installable": True,
    "application": False,
}
