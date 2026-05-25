# -*- coding: utf-8 -*-
from odoo import fields, models

class ResUsers(models.Model):
    _inherit = "res.users"

    firma_digital = fields.Binary(
        string='Firma Digital', 
        help='Imagen de la firma digital del usuario'
    )