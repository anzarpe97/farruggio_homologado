# -*- coding: utf-8 -*-
{
"name": "Sale Kit Qty Delivered Patch",
"summary": "Corrige qty_delivered en SO lines para productos con BOM tipo Kit (phantom)",
"version": "16.0.1.0.0",
"category": "Sales",
"author": "Samir Espina",
"website": "",
"license": "LGPL-3",
"depends": [
"sale_stock", # qty_delivered por movimientos de stock
"mrp", # para detectar BOM phantom (kit)
"sale_mrp", # para manejar kits en ventas
],
"data": [],
"installable": True,
"application": False,
}