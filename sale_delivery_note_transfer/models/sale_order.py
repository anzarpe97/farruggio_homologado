from odoo import models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _prepare_note_lines_for_delivery(self):
        lines_text = []
        previous_product_line = None

        for line in self.order_line:
            if line.display_type == 'line_section':
                lines_text.append(f"\n🟦 SECCIÓN: {line.name}")
                previous_product_line = None  # Reiniciar para nueva sección
            elif not line.display_type:
                previous_product_line = line
            elif line.display_type == 'line_note' and previous_product_line:
                product = previous_product_line.product_id
                product_code = product.default_code or ''
                product_name = product.name
                qty = previous_product_line.product_uom_qty
                uom = previous_product_line.product_uom.name
                lines_text.append(
                    f"🔹 [{product_code}] {product_name} - {qty:.2f} {uom}\n"
                    f"    Nota: {line.name}"
                )

        return "\n".join(lines_text)

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            notes_text = order._prepare_note_lines_for_delivery()
            pickings = order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
            for picking in pickings:
                picking.sale_note_lines = notes_text
        return res
