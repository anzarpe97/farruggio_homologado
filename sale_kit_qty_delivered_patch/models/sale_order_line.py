from odoo import models, api
from odoo.exceptions import UserError
import logging
import re
import unicodedata

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_recalcular_ref_unit(self):
        """Recalcula ref_unit en las líneas, desbloqueando temporalmente el pedido si es necesario."""
        for order in self:
            original_state = order.state

            try:
                # Si está bloqueado, pasarlo a borrador
                if original_state not in ("draft", "sent"):
                    order.sudo().write({"state": "draft"})
                    _logger.info(f"[{order.name}] Pedido desbloqueado temporalmente para recalcular ref_unit.")

                for line in order.order_line:
                    if hasattr(line, "ref_unit") and order.tax_today:
                        new_ref_unit = line.price_unit / order.tax_today
                        line.sudo().write({"ref_unit": round(new_ref_unit, 6)})
                        _logger.info(
                            f"[{order.name}] ref_unit recalculado en línea {line.id}: "
                            f"{line.price_unit} / {order.tax_today} = {new_ref_unit}"
                        )

            finally:
                # Restaurar estado original
                if original_state not in ("draft", "sent"):
                    order.sudo().write({"state": original_state})
                    _logger.info(f"[{order.name}] Pedido devuelto a estado {original_state}.")


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.depends('move_ids.state', 'move_ids.quantity_done', 'product_id.bom_ids')
    def _compute_qty_delivered(self):
        kit_lines = self.filtered(lambda l: l.product_id.bom_ids and l.product_id.bom_ids[0].type == 'phantom')
        non_kit_lines = self - kit_lines

        # Buscar UoM por nombre (para huevos)
        uom_caja = self.env['uom.uom'].search([('name', 'ilike', 'Caja')], limit=1)
        uom_carton = self.env['uom.uom'].search([('name', 'ilike', 'Carton')], limit=1)

        SPECIAL_CONVERSIONS = {
            # Mortadelas -> por nombre
            'MORTADELA ESP PTM 10UND X 1KG (BOLOÑA)': {
                'Bulto x 10': {'kg': 10.0}
            },
            'MORTADELA ESP PTM 10UND X 1KG': {
                'Bulto x 10': {'kg': 10.0}
            },
            'MORTADELA ESPECIAL CAL#19 SALCHICHA IND': {
                'Bulto x 10': {'kg': 10.0}
            },
        }

        for line in kit_lines:
            # Considerar tanto salidas (outgoing) como devoluciones (incoming).
            # Las salidas incrementan entregado, las entradas (devoluciones) lo decrementan.
            component_moves = line.move_ids.filtered(lambda m: m.state == 'done' and m.sale_line_id == line and m.picking_type_code in ('outgoing', 'incoming'))

            if component_moves:
                total_delivered = 0.0
                for move in component_moves:
                    component_name = move.product_id.name
                    uom_from_name = move.product_uom.name
                    uom_to_name = line.product_uom.name

                    # Determinar signo: outgoing -> +1, incoming (devolución) -> -1
                    sign = 1.0 if move.picking_type_code == 'outgoing' else -1.0

                    conversion_applied = False

                    # Mortadelas (conversión especial por nombre)
                    for conv_product_name, conv_data in SPECIAL_CONVERSIONS.items():
                        if conv_product_name in (component_name or ''):
                            if uom_from_name in conv_data and uom_to_name in conv_data[uom_from_name]:
                                factor = conv_data[uom_from_name][uom_to_name]
                                converted_qty = abs(move.quantity_done) * factor * sign
                                total_delivered += converted_qty
                                _logger.info(f"Conversión especial (mortadela): {move.quantity_done} {uom_from_name} -> {converted_qty} {uom_to_name} para {component_name} (sign={sign})")
                                conversion_applied = True
                                break
                    if conversion_applied:
                        continue

                    # Huevos (reglas especiales entre Caja/Carton)
                    if 'huevo' in (component_name or '').lower():
                        if uom_from_name.lower() == 'caja' and uom_to_name.lower() == 'carton':
                            converted_qty = abs(move.quantity_done) * 12.0 * sign
                            total_delivered += converted_qty
                            conversion_applied = True
                        elif uom_from_name.lower() == 'carton' and uom_to_name.lower() == 'caja':
                            converted_qty = abs(move.quantity_done) * (1/12) * sign
                            total_delivered += converted_qty
                            conversion_applied = True

                        if conversion_applied:
                            _logger.info(f"Conversión especial (huevos): {move.quantity_done} {uom_from_name} -> {converted_qty} {uom_to_name} para {component_name} (sign={sign})")
                            continue

                    # Conversión automática estándar
                    try:
                        physical_qty = abs(move.quantity_done)
                        if move.product_uom != line.product_uom:
                            converted_qty = move.product_uom._compute_quantity(
                                physical_qty,
                                line.product_uom,
                            ) * sign
                            total_delivered += converted_qty
                            _logger.info(f"Conversión automática: {move.product_id.name} - {move.quantity_done} {move.product_uom.name} -> {converted_qty} {line.product_uom.name} (sign={sign})")
                        else:
                            total_delivered += physical_qty * sign
                    except UserError:
                        _logger.warning(f"No se pudo convertir {move.product_uom.name} a {line.product_uom.name} para {move.product_id.name}. Usando cantidad física.")
                        total_delivered += abs(move.quantity_done) * sign

                # Ajuste especial para pedido S16102: huevos = 40 cartones
                if line.order_id.name == "S16102" and any('huevo' in (m.product_id.name or '').lower() for m in component_moves):
                    _logger.warning(f"Ajuste manual: {line.product_id.name} en S16102 forzado a 40 Cartones")
                    total_delivered = 40.0

                line.qty_delivered = round(total_delivered, 3)
                _logger.info(f"KIT CALCULADO: {line.product_id.name} = {line.qty_delivered} {line.product_uom.name}")
            else:
                line.qty_delivered = 0.0

        super(SaleOrderLine, non_kit_lines)._compute_qty_delivered()

    # ===========
    # MÉTODO NUEVO PARA EL CRON
    # ===========
    @api.model
    def cron_recalcular_qty_delivered_pdvsa(self):
        """Recalcula qty_delivered y ref_unit solo para el pedido S16102."""
        SaleOrder = self.env["sale.order"]
        # Filtrar pedidos cuyo cliente sea PDVSA y la semana PDVSA sea SEM 39 o SEM 40
        orders = SaleOrder.search([
            ("partner_id.name", "ilike", "PDVSA"),
            ("x_studio_semana_pdvsa", "in", ["SEM 39"]),
        ])

        _logger.info(
            f"Encontrados {len(orders)} pedidos PDVSA con semana SEM 39 para recalcular qty_delivered."
        )

        for order in orders:
            try:
                # Solo recalcular qty_delivered usando el método _compute_qty_delivered
                for line in order.order_line:
                    # Llamamos al método compute en el registro de línea para que aplique la lógica personalizada
                    line._compute_qty_delivered()
                    _logger.info(
                        f"[{order.name}] Línea {line.id} ({line.product_id.display_name}) qty_delivered recalculado."
                    )

            except Exception as e:
                _logger.error(f"Error recalculando pedido {order.name}: {e}")
