from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class HREmployeeLoanPayment(models.Model):
    _name = 'hr.employee.loan.payment'
    _description = 'Abonos de Préstamo'
    _order = 'date desc'

    loan_id = fields.Many2one(
        'hr.employee.loan',
        string='Préstamo',
        required=True,
        ondelete='cascade'
    )
    date = fields.Date(
        string='Fecha',
        default=fields.Date.today,
        required=True
    )
    amount = fields.Monetary(
        string='Monto Abonado',
        required=True,
        currency_field='currency_id_dif'
    )
    note = fields.Text(string='Notas')
    move_id = fields.Many2one(
        'account.move',
        string='Asiento Contable'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )
    currency_id_dif = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='company_id.currency_id',
        readonly=True
    )
    state = fields.Selection(
        [('draft', 'Borrador'), ('posted', 'Publicado')],
        string='Estado',
        default='draft',
        required=True
    )

    @api.model
    def default_get(self, fields):
        res = super(HREmployeeLoanPayment, self).default_get(fields)
        if not res.get('loan_id') and self.env.context.get('default_loan_id'):
            res['loan_id'] = self.env.context['default_loan_id']
        return res

    def post_payment(self):
        """
        Cambia el estado del abono a 'posted', actualiza las cuotas y el préstamo.
        """
        for payment in self:
            if payment.state != 'draft':
                raise ValidationError(_('El abono ya está publicado.'))

            loan = payment.loan_id

            # Validar si el abono supera el monto restante
            if payment.amount > loan.remaing_amount:
                raise ValidationError(_('El monto del abono no puede superar el monto restante del préstamo.'))

            # Actualizar cuotas
            remaining_amount = payment.amount

            # Filtrar cuotas no pagadas y procesarlas en orden inverso
            for installment in loan.installment_lines.filtered(lambda x: not x.is_paid and not x.is_skip).sorted(key=lambda i: i.date, reverse=True):
                if remaining_amount <= 0:
                    break

                if remaining_amount >= installment.total_installment:
                    # Paga completamente la cuota
                    remaining_amount -= installment.total_installment
                    installment.total_installment = 0
                    installment.installment_amt = 0
                    installment.ins_interest = 0
                    installment.is_paid = True
                else:
                    # Paga parcialmente la cuota
                    installment.total_installment -= remaining_amount
                    if remaining_amount <= installment.installment_amt:
                        installment.installment_amt -= remaining_amount
                    else:
                        remaining_amount -= installment.installment_amt
                        installment.installment_amt = 0
                        installment.ins_interest -= remaining_amount
                    remaining_amount = 0

            # Actualizar monto pagado y restante en el préstamo
            loan.paid_amount += payment.amount
            loan.remaing_amount -= payment.amount

            # Cambiar estado a 'posted'
            payment.state = 'posted'

            # Verificar si el préstamo está completamente pagado y cerrarlo
            if loan.remaing_amount <= 0:
                loan.state = 'close'

            # Registrar en el chatter
            loan.message_post(
                body=_("Se ha registrado un abono por un monto de %.2f.") % payment.amount,
                subtype_xmlid="mail.mt_note"
            )
