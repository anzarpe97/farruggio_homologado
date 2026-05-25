# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    amount = fields.Monetary(currency_field='currency_id', store=True, readonly=False)
    tax_today = fields.Float(string="Tasa Actual", digits='Dual_Currency_rate')
    tax_invoice = fields.Float(string="Tasa Factura", digits='Dual_Currency_rate')
    currency_id_dif = fields.Many2one("res.currency",string="Divisa de Referencia")
    currency_id_name = fields.Char(related="currency_id.name")
    amount_residual_usd = fields.Monetary(currency_field='currency_id_dif',string='Adeudado Divisa Ref.', readonly=True, digits='Dual_Currency')
    payment_difference_bs = fields.Monetary(string="Diferencia Bs", currency_field='company_currency_id', digits='Dual_Currency')
    payment_difference_usd = fields.Monetary(string="Diferencia $", currency_field='currency_id_dif',
                                            digits='Dual_Currency')
    journal_id_dif = fields.Many2one('account.journal', 'Diario de diferencia', store=True,
                                 domain="[('company_id', '=', company_id)]")
    amount_usd = fields.Monetary(currency_field='currency_id_dif',string='Importe $', readonly=True, digits='Dual_Currency')

    journal_igtf_id = fields.Many2one('account.journal', string='Diario IGTF', check_company=True)
    aplicar_igtf_divisa = fields.Boolean(string="Aplicar IGTF",
                                         default=lambda self: self._get_default_igtf())
    igtf_divisa_porcentage = fields.Float('% IGTF', related='company_id.igtf_divisa_porcentage')

    mount_igtf = fields.Monetary(currency_field='currency_id', string='Importe IGTF', readonly=True,
                                 digits='Dual_Currency')

    amount_total_pagar = fields.Monetary(currency_field='currency_id', string="Total Pagar(Importe + IGTF):",
                                         readonly=True)

    @api.onchange("payment_date")
    def onchange_date_change_tax_today(self):
        currency_USD = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        company_currency = self.env.company.currency_id
        self.tax_today = company_currency._get_conversion_rate(currency_USD, company_currency, self.env.company, self.payment_date)

    @api.depends('currency_id')
    def _get_default_igtf(self):
        if self.currency_id == self.company_id.currency_id:
            return False
        else:
            return self.company_id.aplicar_igtf_divisa
    @api.onchange('aplicar_igtf_divisa')
    def _mount_igtf(self):
        for wizard in self:
            if wizard.aplicar_igtf_divisa:
                if wizard.currency_id.name == 'USD':
                    wizard.mount_igtf = wizard.amount * wizard.igtf_divisa_porcentage / 100
                    wizard.amount_total_pagar = wizard.mount_igtf + wizard.amount
                else:
                    wizard.mount_igtf = 0
                    wizard.amount_total_pagar = wizard.amount
            else:
                wizard.mount_igtf = 0
                wizard.amount_total_pagar = wizard.amount


    @api.onchange('source_amount', 'source_amount_currency', 'source_currency_id', 'company_id', 'currency_id', "tax_today")
    def _compute_amount(self):
        for wizard in self:
            if wizard.source_currency_id == wizard.currency_id:
                # Same currency.
                #wizard.amount = wizard.source_amount_currency
                wizard.amount = wizard.source_amount

            elif wizard.currency_id == wizard.company_id.currency_id:
                # Payment expressed on the company's currency.
                if wizard.source_currency_id == wizard.company_id.currency_id:
                    if wizard.tax_today == wizard.tax_invoice:
                        wizard.amount = wizard.source_amount
                    else:
                        wizard.amount = wizard.amount_residual_usd * wizard.tax_today
                else:
                    wizard.amount = wizard.source_amount_currency * wizard.tax_today
            else:
                # Foreign currency on payment different than the one set on the journal entries.
                #amount_payment_currency = wizard.company_id.currency_id._convert(wizard.source_amount,
                #                                                                 wizard.currency_id, wizard.company_id,
                #                                                                 wizard.payment_date)
                wizard.amount = wizard.amount_residual_usd

            if wizard.aplicar_igtf_divisa:
                if wizard.currency_id.name == wizard.company_id.currency_id_dif.name:
                    wizard.mount_igtf = wizard.amount * wizard.igtf_divisa_porcentage / 100
                    wizard.amount_total_pagar = wizard.mount_igtf + wizard.amount
                else:
                    wizard.mount_igtf = 0
                    wizard.amount_total_pagar = wizard.amount
            else:
                wizard.mount_igtf = 0
                wizard.amount_total_pagar = wizard.amount

            if wizard.currency_id.name == "VEF":
                wizard.amount = wizard.amount_residual_usd * wizard.tax_today

    @api.depends('amount','tax_today')
    def _compute_payment_difference(self):
        for wizard in self:
            wizard.amount_usd = wizard.amount / (wizard.tax_today if wizard.tax_today > 0 else 1)
            if wizard.source_currency_id == wizard.currency_id:
                # Same currency.
                wizard.payment_difference = wizard.source_amount_currency - wizard.amount
                wizard.payment_difference_usd = round(wizard.amount_residual_usd - (wizard.amount / (wizard.tax_today if wizard.tax_today > 0 else 1)))
                wizard.payment_difference_bs = 0
                if wizard.currency_id == wizard.company_id.currency_id_dif:
                    wizard.payment_difference_usd = wizard.amount_residual_usd - wizard.amount
                    wizard.payment_difference_bs = (wizard.amount_residual_usd / wizard.tax_invoice) - (wizard.amount / (wizard.tax_today if wizard.tax_today > 0 else 1))
                ##print('diferencia 1')
            elif wizard.currency_id == wizard.company_id.currency_id:
                # Payment expressed on the company's currency.
                ##print('wizard.currency_id == wizard.company_id.currency_id')
                ##print('tasa factura: %s' % wizard.tax_invoice)
                ##print('tasa actual: %s' % wizard.tax_today)
                ##print('monto adeudado: %s' % wizard.amount_residual_usd)
                ##print('monto pagado: %s' % wizard.amount)
                ##print(wizard.currency_id)
                ##print(wizard.currency_id_dif)
                if wizard.source_currency_id == wizard.company_id.currency_id:
                    wizard.payment_difference = wizard.source_amount - wizard.amount
                else:
                    wizard.payment_difference = (wizard.source_amount * wizard.tax_invoice) - wizard.amount
                    wizard.payment_difference_usd = round(wizard.amount_residual_usd - (wizard.amount / (wizard.tax_today if wizard.tax_today > 0 else 1)))
            else:
                # Foreign currency on payment different than the one set on the journal entries.
                #amount_payment_currency = wizard.company_id.currency_id._convert(wizard.source_amount,
                #                                                                 wizard.currency_id, wizard.company_id,
                #                                                                 wizard.payment_date)
                #amount_payment_currency = wizard.source_amount * wizard.tax_today
                wizard.payment_difference = wizard.amount_residual_usd - wizard.amount
                ##print('tasa factura: %s' % wizard.tax_invoice)
                ##print('tasa actual: %s' % wizard.tax_today)
                ##print('monto adeudado: %s' % wizard.amount_residual_usd)
                ##print('monto pagado: %s' % wizard.amount)
                ##print(wizard.currency_id)
                ##print(wizard.currency_id_dif)
                if wizard.tax_today == wizard.tax_invoice and wizard.amount_residual_usd == wizard.amount and wizard.currency_id == wizard.company_id.currency_id_dif:
                    wizard.payment_difference_bs = wizard.source_amount - (wizard.amount * wizard.tax_today)
                else:
                    wizard.payment_difference_bs = wizard.source_amount - (wizard.amount * wizard.tax_today)

            _logger.info("PAYMENT DIFFERENCE NATIVO")
            _logger.info("PAYMENT DIFFERENCE NATIVO")
            _logger.info("PAYMENT DIFFERENCE NATIVO")
            _logger.info("PAYMENT DIFFERENCE NATIVO")
            _logger.info("PAYMENT DIFFERENCE NATIVO")
            _logger.info(wizard.payment_difference)

            _logger.info("BS")
            _logger.info(wizard.payment_difference_bs)

            _logger.info("USD")
            _logger.info(wizard.payment_difference_usd)

                ##print('wizard.payment_difference_bs', wizard.payment_difference_bs)

            if wizard.aplicar_igtf_divisa:
                if wizard.currency_id.name == wizard.company_id.currency_id_dif.name:
                    wizard.mount_igtf = wizard.amount * wizard.igtf_divisa_porcentage / 100
                    wizard.amount_total_pagar = wizard.mount_igtf + wizard.amount
                else:
                    wizard.mount_igtf = 0
                    wizard.amount_total_pagar = wizard.amount
            else:
                wizard.mount_igtf = 0
                wizard.amount_total_pagar = wizard.amount

    @api.model
    def _get_wizard_values_from_batch(self, batch_result):
        key_values = batch_result['payment_values']
        lines = batch_result['lines']
        company = lines[0].company_id

        # 1. Obtén la fecha de pago (o usa hoy si no está seteada)
        payment_date = self.payment_date or fields.Date.context_today(self)

        # 2. Busca el currency USD y la tasa más reciente válida según fecha y compañía
        usd = self.env.ref('base.USD', raise_if_not_found=False) or self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        tax_today = 1.0
        if usd:
            rate_obj = self.env['res.currency.rate'].search([
                ('currency_id', '=', usd.id),
                ('company_id', '=', company.id),
                ('name', '<=', payment_date),
            ], order='name desc', limit=1)
            if rate_obj:
                tax_today = rate_obj.inverse_company_rate or 1.0

        # 3. tax_invoice sigue siendo la tasa guardada en la factura (si existe)
        tax_invoice = getattr(lines[0].move_id, 'tax_today', 1.0) or 1.0

        currency_id_dif = lines[0].currency_id_dif
        amount_residual_usd = lines[0].move_id.amount_residual_usd
        source_amount = abs(sum(lines.mapped('amount_residual'))) if key_values['currency_id'] == company.currency_id.id else abs(sum(lines.mapped('amount_residual_currency')))
        if key_values['currency_id'] == company.currency_id.id:
            source_amount_currency = source_amount
        else:
            source_amount_currency = abs(sum(lines.mapped('amount_residual_currency')))

        return {
            'company_id': company.id,
            'partner_id': key_values['partner_id'],
            'partner_type': key_values['partner_type'],
            'payment_type': key_values['payment_type'],
            'source_currency_id': key_values['currency_id'],
            'source_amount': source_amount,
            'source_amount_currency': source_amount_currency,
            'tax_today': tax_today,      # <--- Ahora sí, última tasa válida
            'tax_invoice': tax_invoice,  # <--- Tasa guardada en la factura
            'currency_id_dif': currency_id_dif.id,
            'amount_residual_usd': amount_residual_usd,
            'aplicar_igtf_divisa': self.aplicar_igtf_divisa,
        }

    def _create_payment_vals_from_wizard(self, batch_result):
        # Determinar tasa correcta según la moneda del pago
        if self.currency_id == self.company_id.currency_id_dif:
            # Pago en USD → usar tasa de la factura
            tasa_aplicada = self.tax_invoice
        else:
            # Pago en VEF u otra moneda → usar tasa actual
            tasa_aplicada = self.tax_today

        payment_vals = {
            'date': self.payment_date,
            'amount': self.amount,
            'payment_type': self.payment_type,
            'partner_type': self.partner_type,
            'ref': self.communication,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'partner_bank_id': self.partner_bank_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'destination_account_id': self.line_ids[0].account_id.id,
            'tax_today': self.tax_today,  # 👈 Condicionado correctamente
            'currency_id_dif': self.currency_id_dif.id,
            'aplicar_igtf_divisa': self.aplicar_igtf_divisa,
            'journal_igtf_id': self.journal_igtf_id.id,
            'mount_igtf': self.mount_igtf,
            'amount_total_pagar': self.amount_total_pagar,
        }
        return payment_vals


    def _create_payments(self):
        self.env.context = dict(self.env.context, tasa_factura=self.tax_today, calcular_dual_currency=True)

        payments = super()._create_payments()
        payments.move_id._verificar_pagos()
        if payments.move_id_dif:
            payments.move_id_dif._verificar_pagos()

        self.env.context = dict(self.env.context, tasa_factura=None, calcular_dual_currency=False)

        pay_term_line_ids = payments.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')

        for partial in partials:
            if partial.amount_usd == 0:
                monto_usd = 0
                to_reconcile = payments.move_id.line_ids.filtered_domain([('account_id', '=', self.line_ids[0].account_id.id)])
                if abs(self.line_ids[0].amount_residual_usd) > 0:
                    if abs(self.line_ids[0].amount_residual_usd) > to_reconcile.amount_residual_usd:
                        monto_usd = abs(to_reconcile.amount_residual_usd)
                    else:
                        monto_usd = abs(self.line_ids[0].amount_residual_usd)
                partial.write({'amount_usd': monto_usd})
                to_reconcile._compute_amount_residual_usd()
                # Ajuste de amount en Bs según moneda
                tasa = self.tax_invoice if self.currency_id.name == "USD" else self.tax_today
                monto_bs = monto_usd * tasa if tasa else 0.0

        # ------------------ ASIENTO DE DIFERENCIA CAMBIARIA UNIVERSAL ------------------

        diferencia = (self.payment_difference or self.payment_difference_bs or self.payment_difference_usd)
        if diferencia and self.payment_difference_handling == 'reconcile':
            _logger.warning(f"[ASIENTO DIF CAMBIARIA] Diferencia detectada. payment_difference={self.payment_difference}, payment_difference_bs={self.payment_difference_bs}, payment_difference_usd={self.payment_difference_usd}")

            monto_bs = abs(self.payment_difference_bs) if self.payment_difference_bs else abs(self.payment_difference) if self.payment_difference else abs(self.payment_difference_usd)
            monto_moneda = self.payment_difference_bs or self.payment_difference or self.payment_difference_usd

            invoice_type = None
            if self.line_ids:
                invoice_type = self.line_ids[0].move_id.move_type

            if not invoice_type:
                raise UserError("No se pudo determinar el tipo de factura asociada para el asiento de diferencia.")

            lines = []
            account_dif = self.writeoff_account_id.id
            counter_account = self.line_ids[0].account_id.id

            # Lógica principal según el tipo de factura y el signo
            if invoice_type in ('out_invoice', 'out_refund'):  # VENTA
                if monto_moneda < 0:
                    # NEGATIVA → crédito
                    lines = [
                        (0, 0, {
                            'debit': 0,
                            'credit': abs(monto_bs),
                            'debit_usd': 0,
                            'credit_usd': 0,
                            'account_id': account_dif,
                            'partner_id': self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }),
                        (0, 0, {
                            'debit': abs(monto_bs),
                            'credit': 0,
                            'debit_usd': 0,
                            'credit_usd': 0,
                            'account_id': counter_account,
                            'partner_id': self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }),
                    ]
                else:
                    # POSITIVA → débito
                    lines = [
                        (0, 0, {
                            'debit': abs(monto_bs),
                            'credit': 0,
                            'debit_usd': 0,
                            'credit_usd': 0,
                            'account_id': account_dif,
                            'partner_id': self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }),
                        (0, 0, {
                            'debit': 0,
                            'credit': abs(monto_bs),
                            'debit_usd': 0,
                            'credit_usd': 0,
                            'account_id': counter_account,
                            'partner_id': self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }),
                    ]
            elif invoice_type in ('in_invoice', 'in_refund'):  # COMPRA
                if monto_moneda < 0:
                    # NEGATIVA → débito
                    lines = [
                        (0, 0, {
                            'debit': abs(monto_bs),
                            'credit': 0,
                            'debit_usd': 0,
                            'credit_usd': 0,
                            'account_id': account_dif,
                            'partner_id': self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }),
                        (0, 0, {
                            'debit': 0,
                            'credit': abs(monto_bs),
                            'debit_usd': 0,
                            'credit_usd': 0,
                            'account_id': counter_account,
                            'partner_id': self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }),
                    ]
                else:
                    # POSITIVA → crédito
                    lines = [
                        (0, 0, {
                            'debit': 0,
                            'credit': abs(monto_bs),
                            'debit_usd': 0,
                            'credit_usd': 0,
                            'account_id': account_dif,
                            'partner_id': self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }),
                        (0, 0, {
                            'debit': abs(monto_bs),
                            'credit': 0,
                            'debit_usd': 0,
                            'credit_usd': 0,
                            'account_id': counter_account,
                            'partner_id': self.partner_id.id,
                            'date': self.payment_date,
                            'currency_id': self.currency_id.id,
                            'name': self.writeoff_label + ' de ' + self.communication,
                        }),
                    ]
            else:
                raise UserError(f"Tipo de factura '{invoice_type}' no soportado.")

            move = {
                'ref': self.writeoff_label + ' de ' + self.communication,
                'line_ids': lines,
                'journal_id': self.journal_id_dif.id if self.journal_id_dif else self.journal_id.id,
                'date': self.payment_date,
                'state': 'draft',
                'type_name': 'entry',
                'tax_today': 0,
                'currency_id_dif': self.currency_id_dif.id,
            }
            move_new = self.env['account.move'].create(move)
            payments.move_id_dif = move_new
            payments.move_id_dif._post(soft=False)
            to_reconcile = payments.move_id.line_ids.filtered_domain(
                [('account_id', '=', self.line_ids[0].account_id.id)])
            payment_lines = move_new.line_ids.filtered_domain(
                [('account_id', '=', self.line_ids[0].account_id.id)])
            group_lines = payment_lines + to_reconcile
            _logger.warning(f"[RECONCILIACIÓN DIF] IDs: {[l.id for l in group_lines]} Conciliadas: {[l.id for l in group_lines if l.reconciled]}")
            # Evita reconcilia duplicada
            if group_lines and all(not l.reconciled for l in group_lines):
                group_lines.reconcile()
            else:
                _logger.warning("[RECONCILIACIÓN DIF] Saltado: Alguna línea ya estaba conciliada.")
        
        # --- PARCHE: Forzar recalculo de residuales nativos y duales ---
        if hasattr(payments, "move_id") and payments.move_id:
            for move in payments.mapped("move_id"):
                move.line_ids._compute_amount_residual()
                move._compute_amount()
                move._compute_amount_residual_usd()
        if hasattr(payments, "move_id_dif") and payments.move_id_dif:
            for move in payments.mapped("move_id_dif"):
                move.line_ids._compute_amount_residual()
                move._compute_amount()
                move._compute_amount_residual_usd()

        return payments

    @api.model
    def default_get(self, fields_list):
        # OVERRIDE
        ###print(fields_list)
        #if 'line_ids' in fields_list:
        #    fields_list.remove("line_ids")
        if 'line_ids' in fields_list:
            fields_list.remove("line_ids")
        res = super().default_get(fields_list)
        fields_list.append("line_ids")
        if 'line_ids' in fields_list and 'line_ids' not in res:

            # Retrieve moves to pay from the context.

            if self._context.get('active_model') == 'account.move':
                lines = self.env['account.move'].browse(self._context.get('active_ids', [])).line_ids
            elif self._context.get('active_model') == 'account.move.line':
                lines = self.env['account.move.line'].browse(self._context.get('active_ids', []))
            else:
                raise UserError(_(
                    "The register payment wizard should only be called on account.move or account.move.line records."
                ))

            # Keep lines having a residual amount to pay.
            available_lines = self.env['account.move.line']
            for line in lines:
                if line.move_id.state != 'posted':
                    raise UserError(_("You can only register payment for posted journal entries."))

                if line.account_type not in ('asset_receivable', 'liability_payable'):
                    continue
                if line.currency_id:
                    if line.move_id.amount_residual_usd == 0.0:
                        continue
                else:
                    if line.company_currency_id.is_zero(line.amount_residual) and line.move_id.amount_residual_usd == 0.0:
                        continue
                available_lines |= line

            # Check.
            if len(lines.company_id) > 1:
                raise UserError(_("You can't create payments for entries belonging to different companies."))
            if len(set(available_lines.mapped('account_type'))) > 1:
                raise UserError(
                    _("You can't register payments for journal items being either all inbound, either all outbound."))

            res['line_ids'] = [(6, 0, available_lines.ids)]
        
        # Parche: Set tax_invoice (tasa de la factura) correctamente al abrir el wizard
        if 'line_ids' in res and res['line_ids']:
            # Puede ser lista de comandos tipo [(6, 0, [ids...])] o lista de ints (ids)
            if isinstance(res['line_ids'][0], tuple) and res['line_ids'][0][0] == 6:
                # Comando Odoo: [(6, 0, [ids...])]
                lines_ids = res['line_ids'][0][2]
            else:
                # Ya es lista de IDs directamente
                lines_ids = res['line_ids']
            lines = self.env['account.move.line'].browse(lines_ids)
            factura = lines.mapped('move_id')
            if factura and hasattr(factura[0], 'tax_today'):
                res['tax_invoice'] = factura[0].tax_today or 1.0

        return res

    # def _create_payments(self):
    #     self.ensure_one()
    #     batches = self._get_batches()
    #     edit_mode = self.can_edit_wizard and (len(batches[0]['lines']) == 1 or self.group_payment)
    #
    #     to_reconcile = []
    #     if edit_mode:
    #         payment_vals = self._create_payment_vals_from_wizard()
    #         #payment_vals['tax_today'] = self.tax_today
    #         #payment_vals['currency_id_dif'] = self.currency_id_dif.id
    #         payment_vals_list = [payment_vals]
    #         to_reconcile.append(batches[0]['lines'])
    #     else:
    #         # Don't group payments: Create one batch per move.
    #         if not self.group_payment:
    #             new_batches = []
    #             for batch_result in batches:
    #                 for line in batch_result['lines']:
    #                     new_batches.append({
    #                         **batch_result,
    #                         'lines': line,
    #                     })
    #             batches = new_batches
    #
    #         payment_vals_list = []
    #         for batch_result in batches:
    #             payment_vals_list.append(self._create_payment_vals_from_batch(batch_result))
    #             to_reconcile.append(batch_result['lines'])
    #     payment_vals_list[0]['tax_today'] = self.tax_today
    #     payment_vals_list[0]['currency_id_dif'] = self.currency_id_dif.id
    #     payments = self.env['account.payment'].create(payment_vals_list)
    #
    #     # If payments are made using a currency different than the source one, ensure the balance match exactly in
    #     # order to fully paid the source journal items.
    #     # For example, suppose a new currency B having a rate 100:1 regarding the company currency A.
    #     # If you try to pay 12.15A using 0.12B, the computed balance will be 12.00A for the payment instead of 12.15A.
    #     if edit_mode:
    #         for payment, lines in zip(payments, to_reconcile):
    #             # Batches are made using the same currency so making 'lines.currency_id' is ok.
    #             if payment.currency_id != lines.currency_id:
    #                 liquidity_lines, counterpart_lines, writeoff_lines = payment._seek_for_lines()
    #                 source_balance = abs(sum(lines.mapped('amount_residual')))
    #                 payment_rate = liquidity_lines[0].amount_currency / liquidity_lines[0].balance
    #                 source_balance_converted = abs(source_balance) * payment_rate
    #
    #                 # Translate the balance into the payment currency is order to be able to compare them.
    #                 # In case in both have the same value (12.15 * 0.01 ~= 0.12 in our example), it means the user
    #                 # attempt to fully paid the source lines and then, we need to manually fix them to get a perfect
    #                 # match.
    #                 payment_balance = abs(sum(counterpart_lines.mapped('balance')))
    #                 payment_amount_currency = abs(sum(counterpart_lines.mapped('amount_currency')))
    #                 if not payment.currency_id.is_zero(source_balance_converted - payment_amount_currency):
    #                     continue
    #
    #                 delta_balance = source_balance - payment_balance
    #
    #                 # Balance are already the same.
    #                 if self.company_currency_id.is_zero(delta_balance):
    #                     continue
    #
    #                 # Fix the balance but make sure to peek the liquidity and counterpart lines first.
    #                 debit_lines = (liquidity_lines + counterpart_lines).filtered('debit')
    #                 credit_lines = (liquidity_lines + counterpart_lines).filtered('credit')
    #
    #                 payment.move_id.write({'line_ids': [
    #                     (1, debit_lines[0].id, {'debit': debit_lines[0].debit + delta_balance}),
    #                     (1, credit_lines[0].id, {'credit': credit_lines[0].credit + delta_balance}),
    #                 ]})
    #
    #     payments.action_post()
    #
    #     domain = [('account_internal_type', 'in', ('receivable', 'payable')), ('reconciled', '=', False)]
    #     for payment, lines in zip(payments, to_reconcile):
    #
    #         # When using the payment tokens, the payment could not be posted at this point (e.g. the transaction failed)
    #         # and then, we can't perform the reconciliation.
    #         if payment.state != 'posted':
    #             continue
    #
    #         payment_lines = payment.line_ids.filtered_domain(domain)
    #         for account in payment_lines.account_id:
    #             (payment_lines + lines)\
    #                 .filtered_domain([('account_id', '=', account.id), ('reconciled', '=', False)])\
    #                 .reconcile()
    #
    #     return payments