{
    "name": "Restrict Product Form",
    "version": "16.0.1.0.0",
    "summary": "Permite ver productos solo en vista lista, bloqueando la vista formulario",
    "category": "Product",
    "author": "Samir Espina - Contables",
    "depends": ["product"],
    "data": [
        "security/restrict_product_form_groups.xml",
        "security/ir.model.access.csv",
        "views/product_views_restrict.xml",
    ],
    "icon": "restrict_product_form/static/description/icon.png",
    "installable": True,
    "application": True,
}
