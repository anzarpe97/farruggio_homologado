# -*- coding: utf-8 -*-
from odoo import models, fields

class DiscountConfig(models.Model):
    _name = "discount.config"
    _description = "Configuración de Descuentos"

    name = fields.Char(string="Nombre", required=True)

    discount_type = fields.Selection([
        ("negotiation", "Descuento por negociación"),
        ("early_payment", "Descuento por pronto pago"),
    ], string="Tipo de descuento", required=True)

    apply_to = fields.Selection([
        ("all", "Todas las facturas"),
        ("customers", "Clientes en específico"),
    ], string="Aplica en", required=True)

    partner_ids = fields.Many2many(
        "res.partner",
        string="Clientes específicos",
        help="Si seleccionas 'Clientes en específico', indica aquí los clientes a los que aplica el descuento."
    )

    discount_percent = fields.Float(
        string="Porcentaje de descuento (%)",
        required=True,
        help="Porcentaje de descuento que se aplicará."
    )

    early_payment_days = fields.Integer(
        string="Días para pronto pago",
        help="Número de días después de la fecha de factura en los que aplica el descuento por pronto pago.",
    )

    currency_payment = fields.Selection(
        [
            ("VEF", "VEF"),
            ("USD", "USD"),
            ("any", "Cualquiera"),
        ],
        string="Moneda de pago",
        help="La moneda en la que se aplicarán los descuentos.",
        required=True,
        default="any"
    )