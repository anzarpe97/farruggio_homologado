# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    pos_customer_id = fields.Many2one('res.partner', string='Cliente Por Defecto')
    pos_default_invoice = fields.Boolean(string="Habilitar factura predeterminada de POS")
    customer_required = fields.Boolean('Cliente Requerido')
    pos_hide_product_info = fields.Boolean('Ocultar Información del Producto', default=False)
    hide_show_numpad = fields.Boolean('Ocultar Numpad', default=False)
    show_product_total_quantity = fields.Boolean('Mostrar el recuento y la cantidad de artículos en la pantalla POS y el recibo', default=False)
    delete_pos_orderline_all_cart = fields.Boolean('Eliminar la línea de pedido del POS y todo el carrito',
                                                 default=False)
    pos_product_limit = fields.Integer(string="Límite de productos POS")
    pos_show_internal_ref = fields.Boolean('Mostrar Referencia Interna en POS', default=False)
    pos_show_barcode = fields.Boolean('Mostrar Código de Barra en POS', default=False)
    pos_order_sync_button = fields.Boolean('Sincronizar pedidos con el backend mediante un botón', default=False)
    quickly_payment_full = fields.Boolean('Pago Rápido', default=False)
    quickly_payment_method_id = fields.Many2one('pos.payment.method', string='Diario de pago rápido')
    pos_allow_image = fields.Boolean(string="Permitir imagen del producto en línea de la orden")
    pos_logo = fields.Boolean(string="Logo de recibo de punto de venta")
    pos_receipt_logo = fields.Binary("Logo en Recibo")
    pos_session_report = fields.Boolean(string="Reporte de Sesión del POS")
    pos_auto_lock = fields.Boolean("Pantalla de bloqueo de punto de venta")
    pos_lock_timer = fields.Integer(string="Segundos del temporizador de bloqueo de POS")
    pos_zero_qty_restrict = fields.Boolean(string='Restricción de cantidad disponible en el punto de venta (POS)')
    pos_allow_salesperson = fields.Boolean('Permitir Vendedor')
    pos_bag_category = fields.Many2one('pos.category', 'Categoría de cargos por bolsas de punto de venta')
    pos_bag_charges = fields.Boolean('Cargos por bolsa POS')
    pos_order_note = fields.Boolean("Nota de pedido POS")
    pos_display_note_in_receipt = fields.Boolean("Mostrar nota de pedido en el recibo")

    @api.constrains('pos_lock_timer')
    def _check_validity_constrain(self):
        for record in self:
            if record and record.pos_lock_timer < 0:
                raise ValidationError(
                    _('Timer Must be Positive.'))



    #### disable options #######
    allow_pos_qty_button = fields.Boolean(default=True, string="Permitir Botón de Cantidad")
    allow_pos_discount_button = fields.Boolean(default=True, string="Permitir Botón de Descuento")
    allow_pos_price_button = fields.Boolean(default=True, string="Permitir Botón de Precio")
    allow_pos_customer_button = fields.Boolean(default=True, string="Permitir Botón de Cliente")
    allow_pos_delete_button = fields.Boolean(default=True, string="Permitir Botón de Borrar")
    allow_pos_payment_button = fields.Boolean(default=True, string="Permitir Botón de Pagos")
    allow_pos_add_product_button = fields.Boolean(default=True, string="Permitir Añadir Productos")




class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_customer_id = fields.Many2one('res.partner', related='pos_config_id.pos_customer_id', readonly=False)
    pos_enable_default_invoice = fields.Boolean(related="pos_config_id.pos_default_invoice", readonly=False)
    customer_required = fields.Boolean(related="pos_config_id.customer_required", readonly=False)
    pos_hide_product_info = fields.Boolean(related="pos_config_id.pos_hide_product_info", readonly=False)
    hide_show_numpad = fields.Boolean(related="pos_config_id.hide_show_numpad", readonly=False)
    show_product_total_quantity = fields.Boolean(related="pos_config_id.show_product_total_quantity", readonly=False)
    delete_pos_orderline_all_cart = fields.Boolean(related="pos_config_id.delete_pos_orderline_all_cart", readonly=False)
    pos_product_limit = fields.Integer(related="pos_config_id.pos_product_limit", readonly=False)
    pos_show_internal_ref = fields.Boolean(related="pos_config_id.pos_show_internal_ref", readonly=False)
    pos_show_barcode = fields.Boolean(related="pos_config_id.pos_show_barcode", readonly=False)
    pos_order_sync_button = fields.Boolean(related="pos_config_id.pos_order_sync_button", readonly=False)
    quickly_payment_full = fields.Boolean(related='pos_config_id.quickly_payment_full', readonly=False)
    quickly_payment_method_id = fields.Many2one(related='pos_config_id.quickly_payment_method_id', readonly=False)
    pos_allow_image = fields.Boolean(related='pos_config_id.pos_allow_image', readonly=False)
    pos_logo = fields.Boolean(related="pos_config_id.pos_logo", readonly=False)
    pos_receipt_logo = fields.Binary(related="pos_config_id.pos_receipt_logo", readonly=False)
    pos_session_report = fields.Boolean(related='pos_config_id.pos_session_report', readonly=False)
    pos_auto_lock = fields.Boolean(related='pos_config_id.pos_auto_lock', readonly=False)
    pos_lock_timer = fields.Integer(related='pos_config_id.pos_lock_timer', readonly=False)
    pos_zero_qty_restrict = fields.Boolean(related="pos_config_id.pos_zero_qty_restrict", readonly=False)
    pos_allow_salesperson = fields.Boolean(related='pos_config_id.pos_allow_salesperson',readonly=False)
    pos_bag_category = fields.Many2one(related='pos_config_id.pos_bag_category', readonly=False)
    pos_bag_charges = fields.Boolean(related='pos_config_id.pos_bag_charges', readonly=False)
    pos_order_note = fields.Boolean(related='pos_config_id.pos_order_note', readonly=False)
    pos_display_note_in_receipt = fields.Boolean(related='pos_config_id.pos_display_note_in_receipt', readonly=False)





    #### disable options #######
    allow_pos_qty_button = fields.Boolean(related="pos_config_id.allow_pos_qty_button", readonly=False)
    allow_pos_discount_button = fields.Boolean(related="pos_config_id.allow_pos_discount_button", readonly=False)
    allow_pos_price_button = fields.Boolean(related="pos_config_id.allow_pos_price_button", readonly=False)
    allow_pos_customer_button = fields.Boolean(related="pos_config_id.allow_pos_customer_button", readonly=False)
    allow_pos_delete_button = fields.Boolean(related="pos_config_id.allow_pos_delete_button", readonly=False)
    allow_pos_payment_button = fields.Boolean(related="pos_config_id.allow_pos_payment_button", readonly=False)
    allow_pos_add_product_button = fields.Boolean(related="pos_config_id.allow_pos_add_product_button", readonly=False)



