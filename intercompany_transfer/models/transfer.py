from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

class IntercompanyTransfer(models.Model):
    _name = 'intercompany.transfer'
    _description = 'Transferencia entre compañías'

    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('New'))
    company_id = fields.Many2one(
        'res.company', string='Compañía Origen', required=True,
        default=lambda self: self.env.company,
        states={'done': [('readonly', True)]}
    )
    transfer_date = fields.Date(
        string='Fecha de Transferencia',
        required=True,
        default=fields.Date.context_today,
        states={'done': [('readonly', True)]}
    )
    company_to_id = fields.Many2one(
        'res.company', string='Compañía Destino', required=True,
        states={'done': [('readonly', True)]}
    )
    location_id = fields.Many2one(
        'stock.location', string='Ubicación Origen', required=True,
        states={'done': [('readonly', True)]}
    )
    location_dest_id = fields.Many2one(
        'stock.location', string='Ubicación Destino', required=True,
        states={'done': [('readonly', True)]}
    )
    product_line_ids = fields.One2many(
        'intercompany.transfer.line', 'transfer_id',
        string='Productos', states={'done': [('readonly', True)]}
    )
    picking_id_out = fields.Many2one('stock.picking', string='Picking Salida')
    picking_id_in = fields.Many2one('stock.picking', string='Picking Entrada')
    picking_id_return = fields.Many2one('stock.picking', string='Picking Devolución')  # NUEVO CAMPO
    reference = fields.Char(string="Referencia", readonly=True, copy=False, default='New')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Hecho')
    ], string="Estado", default='draft', readonly=True)
    
    def action_transfer(self):
        self.ensure_one()

        if self.picking_id_out or self.picking_id_in:
            raise ValidationError(_('Ya existen documentos de picking asociados. No se puede validar nuevamente.'))

        if not self.product_line_ids:
            raise ValidationError(_('Debes añadir al menos una línea de producto.'))

        def get_warehouse_from_location(location, company):
            if not location.name or '/' not in location.display_name:
                raise ValidationError(_(
                    "La ubicación '%s' no tiene un nombre con el formato esperado (ALMACEN/Ubicación)." % location.display_name
                ))
            warehouse_code = location.display_name.split('/')[0]
            warehouse = self.env['stock.warehouse'].search([
                ('code', '=', warehouse_code),
                ('company_id', '=', company.id)
            ], limit=1)
            if not warehouse:
                raise ValidationError(_("No se encontró un almacén con código '%s' para la compañía '%s'.") %
                                    (warehouse_code, company.name))
            return warehouse

        # Buscar almacenes por código de ubicación
        warehouse_out = get_warehouse_from_location(self.location_id, self.company_id)
        warehouse_in = get_warehouse_from_location(self.location_dest_id, self.company_to_id)

        partner_out = self.company_id.partner_id
        partner_in = self.company_to_id.partner_id

        # Buscar tipos de picking correctos
        picking_type_out = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id', '=', warehouse_out.id)
        ], limit=1)

        picking_type_in = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('warehouse_id', '=', warehouse_in.id)
        ], limit=1)

        if not picking_type_out or not picking_type_in:
            raise ValidationError(_('Configura correctamente los tipos de picking para ambas compañías.'))

        # Usar ubicación de tránsito neutra
        transit_location = self.env.ref('intercompany_transfer.intercompany_transit_location')

        # Crear picking de salida (origen → tránsito)
        picking_out = self.env['stock.picking'].with_company(self.company_id).create({
            'picking_type_id': picking_type_out.id,
            'location_id': self.location_id.id,
            'location_dest_id': transit_location.id,
            'origin': self.reference,
            'partner_id': partner_out.id,
            'move_ids_without_package': [
                (0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': self.location_id.id,
                    'location_dest_id': transit_location.id,
                }) for line in self.product_line_ids
            ]
        })

        # Crear picking de entrada (tránsito → destino)
        picking_in = self.env['stock.picking'].with_company(self.company_to_id).create({
            'picking_type_id': picking_type_in.id,
            'location_id': transit_location.id,
            'location_dest_id': self.location_dest_id.id,
            'origin': self.reference,
            'partner_id': partner_in.id,
            'move_ids_without_package': [
                (0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': transit_location.id,
                    'location_dest_id': self.location_dest_id.id,
                }) for line in self.product_line_ids
            ]
        })

        # Confirmar ambos pickings
        picking_out.action_confirm()
        picking_in.action_confirm()

        # 🔄 Reemplazo de seriales por compañía
        for move_line in picking_in.move_line_ids:
            if move_line.lot_id and move_line.product_id.tracking != 'none':
                old_lot = move_line.lot_id

                # Archivar el serial de la compañía origen
                old_lot.active = False

                # Crear un nuevo serial con la misma información para la compañía destino
                new_lot = self.env['stock.lot'].with_company(self.company_to_id).create({
                    'name': old_lot.name,
                    'product_id': old_lot.product_id.id,
                    'company_id': self.company_to_id.id,
                })

                # Reasignar el nuevo lote al move_line de entrada
                move_line.lot_id = new_lot.id
        
        # Marcar lotes en origen con referencia si es intercompañía
        if self.company_id.id != self.company_to_id.id:
            for move_line in picking_out.move_line_ids:
                lot = move_line.lot_id
                if lot and lot.company_id == self.company_id and not lot.ref:
                    lot.ref = f"PRODUCTO MOVIDO A COMPAÑIA {self.company_to_id.name.upper()}"

        self.picking_id_out = picking_out.id
        self.picking_id_in = picking_in.id
        self.state = 'done'

    @api.model
    def create(self, vals):
        if vals.get('reference', 'New') == 'New':
            vals['reference'] = self.env['ir.sequence'].next_by_code('intercompany.transfer') or 'New'
        # Asignar el mismo valor a 'name'
        vals['name'] = vals['reference']
        return super().create(vals)
    
    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise UserError(_('No puedes eliminar una transferencia que ya está marcada como hecha.'))
        return super().unlink()


    def _create_return_for_out_picking(self):
        """Crea una devolución del picking de salida si no existe ya una devolución."""
        self.ensure_one()
        if not self.picking_id_out:
            return
        picking_out = self.picking_id_out
        # Verifica si ya existe una devolución para este picking
        existing_returns = self.env['stock.picking'].search([
            ('origin', '=', picking_out.name),
            ('picking_type_id.return_picking_type_id', '=', picking_out.picking_type_id.id),
            ('state', 'not in', ['cancel', 'done'])
        ])
        if existing_returns:
            self.picking_id_return = existing_returns[0].id  # Guarda el picking de devolución existente
            return  # Ya existe una devolución pendiente

        # Crea la devolución usando el wizard estándar de Odoo
        return_wizard = self.env['stock.return.picking'].with_context(active_id=picking_out.id, active_ids=[picking_out.id]).create({
            'picking_id': picking_out.id,
        })
        return_data = return_wizard._onchange_picking_id()
        # Marca todas las líneas para devolver la cantidad total realizada
        for line in return_wizard.product_return_moves:
            line.quantity = line.move_id.quantity_done
        action = return_wizard.create_returns()
        # Obtener el picking de devolución creado y guardarlo
        if action and action.get('res_id'):
            picking_return = self.env['stock.picking'].browse(action['res_id'])
            self.picking_id_return = picking_return.id

            # Asignar los mismos lotes del picking de salida a la devolución
            for move_return in picking_return.move_ids:
                # Buscar el movimiento original relacionado
                move_orig = move_return.move_orig_ids.filtered(lambda m: m.picking_id == picking_out)
                if move_orig and move_orig.move_line_ids:
                    lot = move_orig.move_line_ids[0].lot_id
                    if lot:
                        # Asignar el lote al move_line de la devolución
                        for ml in move_return.move_line_ids:
                            ml.lot_id = lot.id


# Sobreescribimos el método action_cancel de stock.picking usando un modelo heredado
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_cancel(self):
        res = super().action_cancel()
        # Si este picking es de entrada y está vinculado a una transferencia intercompañía, crea la devolución
        for picking in self:
            transfer = picking.env['intercompany.transfer'].search([('picking_id_in', '=', picking.id)], limit=1)
            if transfer:
                transfer._create_return_for_out_picking()
        return res

    def button_validate(self):
        for picking in self:
            transfer = self.env['intercompany.transfer'].search([('picking_id_in', '=', picking.id)], limit=1)
            if transfer and transfer.picking_id_out:
                if transfer.picking_id_out.state not in ('done', 'cancel'):
                    raise ValidationError(
                        _("No se puede validar el picking de entrada hasta que el picking de salida de la compañía origen esté validado.")
                    )

                       
                # --- NUEVA LÓGICA para validar diferencia de cantidades ---
                # Obtener cantidades totales de salida e entrada
                qty_out = sum(transfer.picking_id_out.move_line_ids.mapped('qty_done'))
                qty_in = sum(picking.move_line_ids.mapped('qty_done'))

                if qty_out == 0:
                    raise ValidationError(_("El picking de salida no tiene cantidades registradas para comparar."))

                diferencia_relativa = abs(qty_out - qty_in) / qty_out
                if diferencia_relativa > 0.01:
                    raise ValidationError(_(
                        "La diferencia entre cantidades del picking de salida (%s) y entrada (%s) supera el 1%% permitido."
                    ) % (qty_out, qty_in))
                
                # Validar si el producto tiene trazabilidad
                tracked_moves = transfer.picking_id_out.move_line_ids.filtered(lambda ml: ml.product_id.tracking != 'none' and ml.lot_id)
                valid_lots = set(tracked_moves.mapped('lot_id.name'))

                # if not valid_lots:
                #     raise ValidationError(_("No hay seriales asignados en el picking de salida."))

                entrada_lotes = set(picking.move_line_ids.filtered(lambda ml: ml.lot_id).mapped('lot_id.name'))

                # if not entrada_lotes:
                #     raise ValidationError(_("Debes ingresar los seriales/lotes en el picking de entrada antes de validar."))

                # Comparar los lotes uno a uno
                for lote in entrada_lotes:
                    if lote not in valid_lots:
                        raise ValidationError(
                            _("Lote/Serial '%s' no está autorizado en esta transferencia. Solo se permiten: %s") % (
                                lote, ', '.join(valid_lots))
                        )
                    if len(entrada_lotes) > len(valid_lots):
                        raise ValidationError(_("Se ingresaron más seriales de los permitidos. Verifica que cada producto tenga el lote correcto."))
        return super().button_validate()