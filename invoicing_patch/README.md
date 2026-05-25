# Sale Force Fully Invoiced (Odoo 16)

## Propósito
Forzar que un pedido de venta se marque como **Totalmente facturado** solo cuando:
- Exista cualquier factura (o nota de crédito) no cancelada asociada
- El pedido esté completamente entregado (`delivery_status == full`)
- No queden líneas pendientes por facturar (ninguna línea con `invoice_status == to invoice`)

Si luego se elimina/cancela la última factura y aún hay líneas facturables, vuelve al estado **A facturar**.

## Lógica implementada
Overrides incluidos:
1. `_compute_invoice_status` en `sale.order`.
2. `unlink` y `write` (para transición a cancel) en `account.move` para forzar el recálculo del estado del pedido cuando se elimina o cancela la última factura.

Detalle `_compute_invoice_status`:
1. Ejecuta lógica estándar.
2. Si estado del pedido no está en `sale` o `done`, no hace nada extra.
3. Usa exclusivamente el campo `delivery_status` (módulo `sale_stock`), y solo cuando su valor es `full` considera el pedido completamente entregado.
4. Si hay al menos una factura (out_invoice/out_refund) no cancelada, `delivery_status == full` y NO hay líneas `to invoice` → `invoice_status = invoiced`.
5. Si existen líneas con `invoice_status == 'to invoice'` → `invoice_status = to invoice` (aunque haya facturas y entrega completa).
6. Si no hay facturas ni líneas facturables y el super lo había dejado en `invoiced`, se corrige a `no`.

## Instalación
1. Colocar la carpeta `sale_force_fully_invoiced` en tu ruta de addons custom.
2. Actualizar lista de aplicaciones.
3. Instalar el módulo.

## Pruebas rápidas
1. Confirmar pedido.
2. Crear factura parcial (borrador) sin entregar completamente → Pedido debe permanecer en A facturar (o estado base según líneas) hasta que todas las unidades estén entregadas.
3. Entregar completamente (validar picking) y mantener la factura → Pedido pasa a Totalmente facturado.
4. Eliminar la factura (unlink) → Pedido vuelve a A facturar si no hay facturas y hay líneas facturables.
5. Crear nueva factura, publicarla y luego cancelarla → Pedido vuelve a A facturar (si hay líneas pendientes) o Sin facturas.
6. Facturar completamente (con pedido ya entregado) y publicar → Permanece en Totalmente facturado.

## Notas
- Se depende únicamente de `delivery_status == full` para determinar entrega completa.
- Una factura (incluyendo borrador) + entrega completa + sin líneas pendientes por facturar => completo.
- Para contar solo facturas publicadas, editar la línea del filtro y exigir `m.state == 'posted'`.
- Para excluir notas de crédito, quitar `'out_refund'` del filtro.

## Reversión
Desinstalar el módulo o eliminar el override.

## Licencia
LGPL-3.
