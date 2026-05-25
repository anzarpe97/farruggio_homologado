from odoo import fields, models, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    last_payment_date = fields.Date(
        string='Última Fecha de Pago',
        compute='_compute_last_payment_date',
        store=True,
    )

    @api.depends(
        'payment_state',
        'line_ids.matched_debit_ids.debit_move_id.date',
        'line_ids.matched_credit_ids.credit_move_id.date',
    )
    def _compute_last_payment_date(self):
        for move in self:
            payment_dates = []

            if move.move_type == 'out_invoice' and move.payment_state in ('paid', 'in_payment'):
                for line in move.line_ids:
                    # matched_debit_ids → pagos o conciliaciones que afectan la factura
                    for matched in line.matched_debit_ids:
                        debit_move = matched.debit_move_id
                        # Preferimos la fecha del pago, si existe, si no usamos la fecha del movimiento contable
                        payment = debit_move.payment_id
                        if payment and payment.date:
                            payment_dates.append(payment.date)
                        elif debit_move.move_id.date:
                            payment_dates.append(debit_move.move_id.date)

                    # matched_credit_ids → devoluciones u otros movimientos que cierran la factura
                    for matched in line.matched_credit_ids:
                        credit_move = matched.credit_move_id
                        payment = credit_move.payment_id
                        if payment and payment.date:
                            payment_dates.append(payment.date)
                        elif credit_move.move_id.date:
                            payment_dates.append(credit_move.move_id.date)

            move.last_payment_date = max(payment_dates) if payment_dates else False
