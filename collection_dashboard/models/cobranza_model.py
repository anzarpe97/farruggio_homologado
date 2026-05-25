from odoo import models, fields, api
from datetime import date as pydate, datetime as pydatetime

class CobranzaFactura(models.Model):
    _name = 'cobranza.factura'
    _description = 'Facturas de Cobranza'

    factura = fields.Char(string='Factura')
    cliente = fields.Char(string='Cliente', required=True)
    fecha_factura = fields.Date(string='Fecha Factura')
    monto_factura = fields.Float(string='Monto Factura')
    tax_today = fields.Float(
        string='Tasa (VES/USD)',
        compute='_compute_tax_today',
        store=True,
        readonly=True,
    )
    
    @api.depends('account_move_id', 'account_move_id.write_date')
    def _compute_tax_today(self):
        """Lee account.move.tax_today si existe; evita fallar cuando el campo no está definido aún.
        Deja 0.0 si el campo no existe o no es numérico.
        """
        for rec in self:
            rate = 0.0
            move = rec.account_move_id
            if move and 'tax_today' in move._fields:
                try:
                    val = getattr(move, 'tax_today', 0.0) or 0.0
                    if isinstance(val, (int, float)):
                        rate = float(val)
                except Exception:
                    rate = 0.0
            rec.tax_today = rate
    
    deuda_usd = fields.Float(string='Deuda USD', compute='_compute_deuda_usd', store=True, oldname='desde_usd')
    dias = fields.Integer(string='Días vencido', compute='_compute_dias', store=True)

    @api.depends('fecha_vencimiento', 'fecha_factura')
    def _compute_dias(self):
        """Calcular días vencidos: max(0, hoy - fecha_vencimiento).
        Si no hay fecha_vencimiento, fallback a días desde fecha_factura.
        """
        today = fields.Date.context_today(self)
        for rec in self:
            try:
                if rec.fecha_vencimiento:
                    due = rec.fecha_vencimiento if isinstance(rec.fecha_vencimiento, pydate) else fields.Date.from_string(rec.fecha_vencimiento)
                    dias_overdue = (today - due).days
                    # Solo muestra días positivos si está vencida, de lo contrario 0
                    rec.dias = dias_overdue if dias_overdue > 0 else 0
                else:
                    # Si no hay fecha_vencimiento, usa fecha_factura pero muestra 0 si no está vencida
                    if rec.fecha_factura:
                        inv = rec.fecha_factura if isinstance(rec.fecha_factura, pydate) else fields.Date.from_string(rec.fecha_factura)
                        dias_from_invoice = (today - inv).days
                        # Si la factura está en el futuro, muestra 0
                        rec.dias = dias_from_invoice if dias_from_invoice > 0 else 0
                    else:
                        rec.dias = 0
            except Exception:
                rec.dias = 0

    estado = fields.Selection([
        ('moroso', 'MOROSO'),
        ('critico', 'CRITICO'),
        ('vencido', 'VENCIDO'),
        ('a_vencer', 'A VENCER'),
    ], string='Estado', compute='_compute_estado', store=True)
    zona = fields.Many2one('crm.team', string='Zona (Equipo de Venta)')
    account_move_id = fields.Many2one('account.move', string='Origen (account.move)', copy=False, readonly=True)
    fecha_vencimiento = fields.Date(string='Fecha Vencimiento', readonly=True, copy=False)
    plazo_dias = fields.Integer(string='Plazo (días)', readonly=True, copy=False)
    journal_id = fields.Many2one('account.journal', string='Diario', readonly=True, copy=False)

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        """Override search para excluir automáticamente facturas del diario financiero.
        
        Esta exclusión se aplica SIEMPRE, independientemente del rol del usuario.
        Es una capa adicional de seguridad además de las reglas ir.rule.
        """
        # Agregar filtro para excluir el diario financiero
        # Nota: También existe una regla ir.rule global que hace esto,
        # pero este override asegura el filtrado en todas las búsquedas
        args = list(args) if args else []
        args.append(('journal_id.name', '!=', 'CUENTAS POR COBRAR FINANCIERAS'))
        
        return super(CobranzaFactura, self)._search(
            args, offset=offset, limit=limit, order=order, 
            count=count, access_rights_uid=access_rights_uid
        )

    @api.depends('monto_factura', 'tax_today')
    def _compute_deuda_usd(self):
        for rec in self:
            # If the related account.move stores a precomputed USD residual (amount_residual_usd), prefer it.
            move = rec.account_move_id
            if move and 'amount_residual_usd' in move._fields:
                try:
                    val = getattr(move, 'amount_residual_usd', 0.0) or 0.0
                    rec.deuda_usd = float(val)
                    continue
                except Exception:
                    # fallback to computed conversion below
                    pass

            tasa = rec.tax_today or 0.0
            monto = rec.monto_factura or 0.0
            # Si hay tasa válida (> 0), convertimos VES -> USD, si no, dejamos el monto tal cual
            rec.deuda_usd = (monto / tasa) if tasa and tasa > 0 else monto

    @api.depends('dias', 'plazo_dias')
    def _compute_estado(self):
        for record in self:
            dias_transcurridos = record.dias or 0
            plazo = record.plazo_dias or 0
            dias_mora = dias_transcurridos - plazo
            # Regla: hasta el día del plazo inclusive = A VENCER
            if dias_mora <= 0:
                record.estado = 'a_vencer'
            elif 1 <= dias_mora < 20:
                record.estado = 'vencido'
            elif 20 <= dias_mora < 31:
                record.estado = 'critico'
            else:
                record.estado = 'moroso'

    @api.model
    def sync_from_account_moves(self):
        """Importa facturas de cliente por cobrar desde account.move.

        Criterio: facturas de cliente publicadas (out_invoice) con amount_residual > 0.
        Excluye facturas del diario "CUENTAS POR COBRAR FINANCIERAS".
        Crea/actualiza registros en `cobranza.factura` buscando por `account_move_id`.
        """
        Move = self.env['account.move']
        Journal = self.env['account.journal']
        
        # Buscar el diario "CUENTAS POR COBRAR FINANCIERAS" para excluirlo
        financial_journal = Journal.search([('name', '=', 'CUENTAS POR COBRAR FINANCIERAS')], limit=1)
        
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0.0),
        ]
        
        # Excluir el diario financiero si existe
        if financial_journal:
            domain.append(('journal_id', '!=', financial_journal.id))
        
        moves = Move.search(domain)
        created = 0
        updated = 0

        today = fields.Date.context_today(self)
        for m in moves:
            invoice_date = m.invoice_date or m.date
            due_date = getattr(m, 'invoice_date_due', False) or False
            # 'dias' será calculado por el campo compute `_compute_dias` (dependiente de
            # `fecha_vencimiento` y `fecha_factura`). No calcular manualmente aquí para
            # evitar inconsistencias entre sync y el compute en el modelo.

            # Calcular plazo de días a partir de la fecha de vencimiento real
            plazo_dias_val = 0
            if invoice_date and due_date:
                try:
                    if not isinstance(due_date, pydate):
                        due_dt = fields.Date.from_string(due_date)
                    else:
                        due_dt = due_date
                    if not isinstance(invoice_date, pydate):
                        inv_dt_for_plazo = fields.Date.from_string(invoice_date)
                    else:
                        inv_dt_for_plazo = invoice_date
                    plazo_dias_val = max((due_dt - inv_dt_for_plazo).days, 0)
                except Exception:
                    plazo_dias_val = 0

            vals = {
                'factura': m.name or '',
                'cliente': m.partner_id.name or '',
                'fecha_factura': invoice_date,
                'monto_factura': float(m.amount_residual or 0.0),
                'deuda_usd': float(getattr(m, 'amount_residual_usd', m.amount_residual or 0.0) or 0.0),
                'fecha_vencimiento': due_date,
                'plazo_dias': int(plazo_dias_val),
                'zona': getattr(m, 'team_id', False).id if getattr(m, 'team_id', False) else False,
                'account_move_id': m.id,
                'journal_id': m.journal_id.id if m.journal_id else False,
            }

            existing = self.search([('account_move_id', '=', m.id)], limit=1)
            if existing:
                existing.write(vals)
                updated += 1
            else:
                self.create(vals)
                created += 1

        return {'created': created, 'updated': updated, 'total_found': len(moves)}


class CobranzaComercial(models.Model):
    _name = 'cobranza.comercial'
    _description = 'Comerciales de Cobranza'

    name = fields.Char(string='Nombre del Comercial', required=True)
    activo = fields.Boolean(string='Activo', default=True)