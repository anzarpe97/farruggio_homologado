# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date


class ResPartner(models.Model):
    _inherit = 'res.partner'

    credit_check = fields.Boolean('Activar Crédito', help='Activar los límites de crédito')

    credit_warning_usd = fields.Monetary('Monto de Advertencia USD', currency_field='currency_usd_id')
    credit_blocking_usd = fields.Monetary('Monto de Bloqueo USD', currency_field='currency_usd_id')
    amount_due_usd = fields.Monetary(
        string='Deuda en USD',
        currency_field='currency_usd_id',
        compute='_compute_amount_due_usd',
        store=False  # pon True si lo necesitas almacenado
    )

    credit_warning = fields.Monetary('Monto de Advertencia (Moneda Local)', compute='_compute_monto_moneda_local')
    credit_blocking = fields.Monetary('Monto de Bloqueo (Moneda Local)', compute='_compute_monto_moneda_local')
    amount_due = fields.Monetary('Monto de la Deuda (Moneda Local)', compute='_compute_monto_moneda_local')

    currency_usd_id = fields.Many2one(
        'res.currency',
        compute='_compute_currency_usd',
        store=False
    )

    @api.depends()
    def _compute_amount_due_usd(self):
        Move = self.env['account.move']
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        moves = Move.search(self._domain_invoices_for_credit())
        # Agrupar por partner para eficiencia
        partner_map = {p.id: 0.0 for p in self}
        for mv in moves:
            # Si la factura está en USD: usar amount_residual
            if usd and mv.currency_id == usd:
                residual = mv.amount_residual
            else:
                # Otras monedas: usar tu campo convertido
                residual = mv.amount_residual_usd
            # Evitar None
            residual = residual or 0.0
            partner_map[mv.partner_id.id] = partner_map.get(mv.partner_id.id, 0.0) + residual
        for partner in self:
            partner.amount_due_usd = partner_map.get(partner.id, 0.0)

    def _compute_currency_usd(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for rec in self:
            rec.currency_usd_id = usd

    def _allowed_credit_journal_ids(self):
        """
        Devuelve los IDs de los diarios permitidos para el cálculo de crédito.
        Ajusta la lista si cambian los nombres. Mejor aún si usas códigos internos.
        """
        allowed_names = [
            'FACTURAS DE CLIENTES',
            'NOTAS DE CREDITO DE CLIENTE',
            'NOTAS DE DEBITO DE CLIENTE',
        ]
        journals = self.env['account.journal'].search([
            ('name', 'in', allowed_names),
            ('type', '=', 'sale'),
        ])
        return journals.ids

    def _domain_invoices_for_credit(self):
        domain = [
            ('partner_id', 'in', self.ids),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('payment_state', 'not in', ('paid', 'reversed')),
        ]
        journal_ids = self._allowed_credit_journal_ids()
        if journal_ids:
            domain.append(('journal_id', 'in', journal_ids))
        else:
            # Si no encuentra los diarios, que no traiga nada (evita sumar otros)
            domain.append(('journal_id', '=', 0))
        return domain

    @api.depends('credit_warning_usd', 'credit_blocking_usd', 'amount_due_usd')
    def _compute_monto_moneda_local(self):
        CurrencyRate = self.env['res.currency.rate']
        today = date.today()
        for rec in self:
            currency = self.env.company.currency_id_dif
            rate = 1.0

            if currency:
                rate_record = CurrencyRate.search([
                    ('currency_id', '=', currency.id),
                    ('company_id', '=', self.env.company.id),
                    ('name', '<=', today)
                ], order='name desc', limit=1)

                rate = rate_record.rate if rate_record else 1.0

            rec.credit_warning = rec.credit_warning_usd / rate
            rec.credit_blocking = rec.credit_blocking_usd / rate
            rec.amount_due = rec.amount_due_usd / rate

    @api.constrains('credit_warning_usd', 'credit_blocking_usd')
    def _check_credit_amount(self):
        for rec in self:
            if rec.credit_warning_usd > rec.credit_blocking_usd:
                raise ValidationError(_('El monto de advertencia no debe ser mayor que el monto de bloqueo.'))
            if rec.credit_warning_usd < 0 or rec.credit_blocking_usd < 0:
                raise ValidationError(_('Los montos no deben ser menores a cero.'))

class ResCompany(models.Model):
    _inherit = 'res.company'

    accountant_email = fields.Char(string='Accountant email')

    currency_id_dif = fields.Many2one('res.currency', string='Moneda Dual')
