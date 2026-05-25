{
    "name": "Cash Closure Report",
    "summary": "Reporte de Cierre de Caja (PDF y XLSX) con filtros por fechas, cliente, comercial y equipo de ventas",
    "version": "16.0.1.0.0",
    "author": "Veronica pacheco",
    "license": "LGPL-3",
    "website": "https://example.com",
    "depends": ["account", "crm",],
    "data": [
        "security/ir.model.access.csv",
        "wizard/cash_closure_wizard_views.xml",
        "views/account_move_views.xml",
        "reports/report_cash_closure_pdf.xml",
        "data/cash_closure_report_section_data.xml",
    ],
    "installable": True,
    "application": False,
}
