# coding: utf-8
###########################################################################

import time
import base64
import logging

from odoo import models, api, _
from odoo.exceptions import UserError, Warning, ValidationError


_logger = logging.getLogger(__name__)

class IvaReport(models.AbstractModel):
    _name = 'report.l10n_ve_full.template_wh_vat'
    #_name = 'report.template_wh_vat'

    #_inherit = 'report.abstract_report'
    #_template = .template_wh_vat'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not docids:
            raise UserError("Se necesita seleccionar la data a Imprimir")
        data = {'form': self.env['account.wh.iva'].browse(docids)}
        res = dict()
        wh_iva = data['form']
        base_amount = []
        base_product = ''
        res_ali = []
        sum_base_general = 0
        sum_tax_general = 0
        sum_base_reducida = 0
        sum_tax_reducida = 0
        inv_nro_ctrl = ''
        inv_nro_fact = ''
        inv_refund = ''
        total_doc = 0
        inv_debit = ''
        sum_base_additional = 0
        sum_tax_additional = 0
        if wh_iva and len(wh_iva) == 1:
            if wh_iva.state == 'done':
                if (wh_iva.type == 'in_invoice' or wh_iva.type == 'in_refund' or wh_iva.type =='in_debit'):
                    if wh_iva.wh_lines:
                        base_product = 0
                        total_base_product = 0
                        total_base_exent = 0
                        total_amount_product = 0
                        base_exent = ' '

                    if wh_iva.wh_lines.type == 'in_invoice' or wh_iva.wh_lines.type == 'in_refund' or wh_iva.wh_lines.type == 'in_debit':


                        res_ali = []
                        total_alicuota = 0
                        base_product = 0
                        total_base_product = 0

                        total_amount_product = 0

                        base_general = 0
                        tax_general = 0
                        rate_general = ''
                        base_reducida = 0
                        tax_reducida = 0
                        rate_reducida = ''
                        base_additional = 0
                        tax_additional = 0
                        rate_additional = ' '
                        for line_tax in wh_iva.wh_lines.tax_line:


                            if not ((line_tax.alicuota == 16) and not (line_tax.alicuota == 8) and not (line_tax.alicuota == 31)) and line_tax.alicuota == 0:
                                total_base_exent +=  line_tax.base
                                base_exent = self.separador_cifra(total_base_exent)

                            if line_tax.alicuota == 16:
                                base_general = line_tax.base
                                tax_general = line_tax.amount
                                rate_general = str(line_tax.alicuota)[0:2] + ' %'
                                sum_base_general += line_tax.base
                                sum_tax_general += line_tax.amount
                            if line_tax.alicuota == 8:
                                base_reducida = line_tax.base
                                tax_reducida = line_tax.amount_ret
                                rate_reducida = str(line_tax.alicuota)[0:1] + ' %'
                                sum_base_reducida += line_tax.base
                                sum_tax_reducida += line_tax.amount
                            if line_tax.alicuota == 31:
                                base_additional = line_tax.base
                                tax_additional = line_tax.amount
                                rate_additional = str(line_tax.alicuota)[0:2] + ' %'
                                sum_base_additional += line_tax.base
                                sum_tax_additional += line_tax.amount

                            total_base_product += line_tax.base
                            base_product = self.separador_cifra(total_base_product)
                            total_amount_product += line_tax.amount
                            amount_product = self.separador_cifra(total_amount_product)


                            # if line_tax.alicuota and not line_tax.alicuota == 0:
                            #   total_alicuota = line_tax.alicuota
                            #   alicuota = self.separador_cifra(total_alicuota)
                            if base_general > 0:
                                base_general2 = self.separador_cifra(base_general)
                            else:
                                base_general2 = ' '
                            if tax_general > 0:
                                tax_general2 = self.separador_cifra(tax_general)
                            else:
                                tax_general2 = ''

                            ######################3
                            if base_reducida > 0:
                                base_reducida2 = self.separador_cifra(base_reducida)
                            else:
                                base_reducida2 = ' '
                            if tax_reducida >0:
                                tax_reducida2 = self.separador_cifra(tax_reducida)
                            else:
                                tax_reducida2 = ' '

                            ###################3
                            if base_additional > 0:
                                base_additional2 = self.separador_cifra(base_additional)
                            else:
                                base_additional2 = ' '
                            if tax_additional > 0:
                                tax_additional2 = self.separador_cifra(tax_additional)
                            else:
                                tax_additional2 = ''

                            base_amount.append({'base_general':base_general2,
                                                'tax_general' :tax_general2,
                                                'rate_general': rate_general,
                                                'base_reducida': base_reducida2,
                                                'tax_reducida': tax_reducida2,
                                                'rate_reducida': rate_reducida,
                                                'base_additional': base_additional2,
                                                'tax_additional': tax_additional2,
                                                'rate_additional': rate_additional,
                                                'base_exent': base_exent,
                                                })




                    if wh_iva.wh_lines.invoice_id.move_type == 'in_refund':
                         # Obtener la factura afectada para NC
                        affected_invoice_value = wh_iva.wh_lines.invoice_id.affected_invoice or ''
                        supplier_number_value = (wh_iva.wh_lines.invoice_id.supplier_invoice_number or '').strip()
                        name_value = (wh_iva.wh_lines.invoice_id.name or '').strip()
                        is_ncpro_value = supplier_number_value.upper().startswith('NCPRO') or name_value.upper().startswith('NCPRO')
                        
                        if affected_invoice_value and is_ncpro_value:
                            # Si hay Factura Afectada y es NCPRO, usar la lógica especial
                            inv_refund = wh_iva.wh_lines.invoice_id.supplier_invoice_number
                            inv_nro_fact = ''  # Vacío cuando se usa Factura Afectada en NC
                            inv_nro_ctrl = wh_iva.wh_lines.invoice_id.nro_ctrl
                        else:
                            # Comportamiento normal sin Factura Afectada
                            inv_refund = wh_iva.wh_lines.invoice_id.supplier_invoice_number
                            inv_nro_fact = wh_iva.wh_lines.invoice_id.invoice_reverse_purchase_id.supplier_invoice_number
                            inv_nro_ctrl = wh_iva.wh_lines.invoice_id.nro_ctrl
                    elif wh_iva.wh_lines.type == 'in_debit':
                        # Obtener la factura afectada primero
                        affected_invoice_value = wh_iva.wh_lines.invoice_id.affected_invoice or ''
                        supplier_number_value = (wh_iva.wh_lines.invoice_id.supplier_invoice_number or '').strip()
                        name_value = (wh_iva.wh_lines.invoice_id.name or '').strip()
                        is_ndpro_value = supplier_number_value.upper().startswith('NDPRO') or name_value.upper().startswith('NDPRO')
                        
                        if affected_invoice_value and is_ndpro_value:
                            # Si hay Factura Afectada, usar la lógica especial
                            inv_debit = wh_iva.wh_lines.invoice_id.supplier_invoice_number
                            inv_nro_fact = ''  # Vacío cuando se usa Factura Afectada
                            inv_nro_ctrl = wh_iva.wh_lines.invoice_id.nro_ctrl
                        else:
                            # Comportamiento normal sin Factura Afectada
                            factura_origin = self.env['account.move'].search([('id','=', wh_iva.wh_lines.invoice_id.debit_origin_id.id)])
                            inv_debit = wh_iva.wh_lines.invoice_id.supplier_invoice_number
                            inv_nro_fact = factura_origin.supplier_invoice_number
                            inv_nro_ctrl = wh_iva.wh_lines.invoice_id.nro_ctrl
                    elif  wh_iva.wh_lines.type == 'in_invoice':
                        inv_nro_ctrl = wh_iva.wh_lines.invoice_id.correlative
                    if wh_iva.wh_lines and wh_iva.wh_lines.invoice_id:
                        invoice = wh_iva.wh_lines.invoice_id
                        if invoice.currency_id and invoice.currency_id.name == 'USD':
                            # Usa tax_today como tasa de cambio
                            tasa = invoice.tax_today or 1.0
                            total_bs = invoice.amount_total * tasa
                            total_doc = self.separador_cifra(total_bs)
                        else:
                            total_doc = self.separador_cifra(invoice.amount_total)
                    else:
                        total_doc = '0,00'

                else:
                    raise UserError("El comprobante de Retencion de IVA se genera solo para los Proveedores")
            else:
                raise UserError("La Retencion del IVA debe estar en estado Confirmado para poder generar su Comprobante")
        else:
            raise UserError("Solo puede seleccionar una Retencion de IVA a la vez, Por favor Seleccione una y proceda a Imprimir")
        # --- Validación de firma (agente de retención) ---
        # La plantilla usa el usuario confirmador para renderizar la firma.
        # En algunos flujos, confirming_user_id puede quedar vacío; hacemos fallback
        # y registramos el motivo específico en log.
        confirming_user = wh_iva.confirming_user_id or self.env.user
        signature_problem = None
        if not wh_iva.confirming_user_id:
            signature_problem = (
                "confirming_user_id no está establecido; usando fallback write_uid/create_uid"
            )
        if not confirming_user:
            signature_problem = "No se pudo determinar el usuario firmante (confirming_user_id/write_uid/create_uid vacíos)"
        else:
            try:
                firma_digital = confirming_user.firma_digital
            except Exception as exc:
                firma_digital = False
                signature_problem = f"No se pudo leer firma_digital del usuario {confirming_user.id}: {exc}"

            if not firma_digital and not signature_problem:
                signature_problem = (
                    f"El usuario firmante {confirming_user.id} ({confirming_user.name}) no tiene firma_digital cargada"
                )
            elif firma_digital:
                # Verifica que el contenido sea base64 válido (evita <img> vacío por datos corruptos)
                try:
                    firma_bytes = firma_digital.encode() if isinstance(firma_digital, str) else firma_digital
                    base64.b64decode(firma_bytes, validate=True)
                except Exception as exc:
                    signature_problem = (
                        f"firma_digital del usuario {confirming_user.id} ({confirming_user.name}) no es base64 válido: {exc}"
                    )

        if signature_problem:
            # warning: el comprobante se genera, pero se deja constancia de por qué no podrá mostrar firma.
            _logger.warning(
                "[test IVA] No se puede renderizar firma. ret_id=%s number=%s state=%s confirming_user_id=%s write_uid=%s create_uid=%s. Motivo: %s",
                wh_iva.id,
                wh_iva.number or wh_iva.name,
                wh_iva.state,
                wh_iva.confirming_user_id.id if wh_iva.confirming_user_id else None,
                wh_iva.write_uid.id if wh_iva.write_uid else None,
                wh_iva.create_uid.id if wh_iva.create_uid else None,
                signature_problem,
            )

        partner_id = data['form'].partner_id
        if partner_id.company_type == 'person':
            if partner_id.vat:
                document = partner_id.vat
            else:
                if partner_id.nationality == 'V' or partner_id.nationality == 'E':
                    document = str(partner_id.nationality) + str(partner_id.identification_id)
                else:
                    document = str(partner_id.identification_id)
        else:
            if partner_id.vat:
                document = partner_id.vat
            else:
                document = 'N/A'
        fecha_op = data['form'].wh_lines.invoice_id.invoice_date

        # Obtener la factura afectada desde el campo del modelo account.move
        affected_invoice = data['form'].wh_lines.invoice_id.affected_invoice if hasattr(data['form'].wh_lines.invoice_id, 'affected_invoice') and data['form'].wh_lines.invoice_id.affected_invoice else ''

        invoice_supplier_number = (data['form'].wh_lines.invoice_id.supplier_invoice_number or '').strip()
        invoice_name = (data['form'].wh_lines.invoice_id.name or '').strip()
# NUEVA LÓGICA: Identificación por Diario
        journal = data['form'].wh_lines.invoice_id.journal_id
        journal_name = (journal.name or '').upper()
        journal_code = (journal.code or '').upper()
        
        # Es ND si el diario contiene la palabra DEBITO, código ND, o es de tipo in_debit nativo
        is_nd = 'DÉBITO' in journal_name or 'DEBITO' in journal_name or 'ND' in journal_code or data['form'].wh_lines.type in ('in_debit', 'out_debit')
        
        # Es NC si el diario contiene la palabra CREDITO, código NC, o es de tipo in_refund nativo
        is_nc = 'CRÉDITO' in journal_name or 'CREDITO' in journal_name or 'NC' in journal_code or data['form'].wh_lines.type in ('in_refund', 'out_refund')
        sum_base_general = self.separador_cifra(sum_base_general)
        sum_tax_general = self.separador_cifra(sum_tax_general)
        sum_base_reducida = self.separador_cifra(sum_base_reducida)
        sum_tax_reducida = self.separador_cifra(sum_tax_reducida)
        sum_base_additional = self.separador_cifra(sum_base_additional)
        sum_tax_additional = self.separador_cifra(sum_tax_additional)
        _logger.warning("DEBUG: El usuario enviado al XML es %s con firma %s", confirming_user.name, bool(confirming_user.firma_digital))
        return {
            'data': data['form'],
            'confirming_user': confirming_user,
            'model': self.env['report.l10n_ve_full.template_wh_vat'],
            'lines': res, #self.get_lines(data.get('form')),
            #date.partner_id
            'fecha_op': fecha_op,
            'fecha_retencion': wh_iva.date or '',  # <--- Esto es lo que necesitas
            'rate_general': rate_general,
            'rate_reducida': rate_reducida,
            'rate_additional': rate_additional,
            'inv_nro_ctrl': inv_nro_ctrl,
            'inv_nro_fact': inv_nro_fact,
            'inv_refund': inv_refund,
            'inv_debit':inv_debit,
            'affected_invoice': affected_invoice,
            'is_nd': is_nd,
            'is_nc': is_nc,
            'document': document,
            'base_amount': base_amount,
            'base_product': base_product,
            'base_exent': base_exent,
            'alicuota': res_ali,
            'total_doc': total_doc,
            'sum_base_general' : sum_base_general,
            'sum_tax_general': sum_tax_general,
            'sum_base_reducida' : sum_base_reducida,
            'sum_tax_reducida' : sum_tax_reducida,
            'sum_base_additional' : sum_base_additional,
            'sum_tax_additional': sum_tax_additional,
        }

    def separador_cifra(self,valor):
        monto = '{0:,.2f}'.format(valor).replace('.', '-')
        monto = monto.replace(',', '.')
        monto = monto.replace('-', ',')
        return  monto

    def get_period(self, date):
        if not date:
            raise Warning (_("You need date."))
        split_date = (str(date).split('-'))
        return str(split_date[1]) + '/' + str(split_date[0])

    def get_date(self, date):
        if not date:
            raise Warning(_("You need date."))
        split_date = (str(date).split('-'))
        return str(split_date[2]) + '/' + (split_date[1]) + '/' + str(split_date[0])

    def get_direction(self, partner):
        direction = ''
        direction = ((partner.street and partner.street + ', ') or '') +\
                    ((partner.street2 and partner.street2 + ', ') or '') +\
                    ((partner.city and partner.city + ', ') or '') +\
                    ((partner.state_id.name and partner.state_id.name + ',')or '')+ \
                    ((partner.country_id.name and partner.country_id.name + '') or '')
        #if direction == '':
        #    raise ValidationError ("Debe ingresar los datos de direccion en el proveedor")
            #direction = 'Sin direccion'
        return direction

    def get_tipo_doc(self, tipo=None):
        if not tipo:
            return []
        types = {'out_invoice': '1', 'in_invoice': '1', 'out_refund': '2',
                 'in_refund': '2'}
        return types[tipo]

    def get_t_type(self, doc_type=None, name=None):
        tt = ''
        if doc_type:
            if doc_type == "in_debit" or doc_type == "out_debit":
                tt = '02-COMP'
            elif name and name.find('PAPELANULADO') >= 0:
                tt = '03-ANU'
            if doc_type == "out_refund" or doc_type == "in_refund":
                tt = '03-ANU'
            elif doc_type == "in_invoice" or doc_type == "out_invoice":
                tt = '01-REG'
        return tt
    




