 # Inventario a la Fecha por Ubicaciones (Odoo 16)

Este módulo proporciona un asistente extendido "Inventario a la Fecha" que muestra detalle por ubicación histórica y permite agrupar por almacén.

Características
- Muestra cantidades por producto y por ubicación para la fecha seleccionada.
- Intenta mapear ubicaciones a almacenes para facilitar la agrupación.

Uso
1. Instala el módulo en Odoo 16 (coloca esta carpeta en tu `addons_path`).
2. Ve a Inventario -> Inventario a la Fecha -> Inventario a la Fecha (extendido).
3. Selecciona la fecha y, opcionalmente, las ubicaciones. Pulsa "Calcular".

Limitaciones y notas
- Esta implementación aproxima las cantidades históricas partiendo de los `stock.quant` actuales y revirtiendo el efecto de los `stock.move` realizados después de la fecha seleccionada. Para precisión absoluta es necesario un historial real de `stock.quant` o un módulo de auditoría.
- Rendimiento: en bases de datos con muchos movimientos, la operación puede ser lenta. Considera optimizaciones SQL o limitar el conjunto de ubicaciones/productos.

Próximos pasos
- Añadir tests unitarios y cálculo optimizado en SQL.
- Añadir exportación a CSV / XLSX.
