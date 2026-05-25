from odoo import models, fields

class PurchaseApprovalMatrix(models.Model):
    _name = 'purchase.approval.matrix'
    _description = 'Matriz de Aprobaciones de Compras'

    categoria = fields.Selection([
        ('materiales', 'Materiales'),
        ('compras_indirectas', 'Compras indirectas'),
        ('servicios', 'Servicios'),
        ('transporte', 'Transporte'),
        ('compras_estrategicas', 'Compras estratégicas'),
        ('compras_menores', 'Compras menores'),
        ('gestion_corporativa', 'Gestión corporativa'),
        ('empaque', 'Empaque'),
        ('nomina', 'Nómina'),
    ], string='Categoría de Compra', required=True)

    descripcion = fields.Selection([
        ('papeleria', 'Papelería, mobiliario, herramientas menores, consultorías, insumos de limpieza oficina'),
        ('publicidad', 'Publicidad y marketing'),
        ('seguros', 'Seguros y servicios financieros'),
        ('publicos', 'Servicios Públicos: agua, luz, teléfono, internet, gas'),
        ('mantenimiento_equipos', 'Mantenimiento de equipos y repuestos básicos de operaciones'),
        ('mantenimiento_vehiculos', 'Mantenimiento de vehiculos y Thermoking'),
        ('repuestos_vehiculos', 'Repuestos e insumos vehiculos'),
        ('contratos_largo_plazo', 'Contratos a largo plazo, Tecnología avanzada, desarrollos especializados, inversiones en infraestructura'),
        ('materia_prima', 'Materia Prima (Bovino, Porcino, Pollo, huevos, embutidos)'),
        ('compra_viveres', 'Compra de viveres y verduras en general'),
        ('equipos_tecnologicos', 'Equipos tecnológicos y maquinarias industriales'),
        ('materiales_suministros', 'Materiales y suministros básicos'),
        ('uniformes', 'Uniformes de personal, merchandising en general'),
        ('empaque', 'Bolsas, etiquetas, material para producto terminado'),
        ('nomina', 'Beneficios empleados'),
    ], string='Descripción', required=True)

    clasificacion = fields.Selection([
        ('operacionales', 'Operacionales'),
        ('estrategicos', 'Estratégicos'),
        ('especializados', 'Especializados'),
    ], string='Clasificación', required=True)

    aprobador_inicial_id = fields.Many2many('res.users', string='Aprobadores Iniciales (Hasta $1,500)', relation='approval_matrix_initial_rel', column1='matrix_id', column2='user_id')
    aprobador_nivel1_id = fields.Many2many('res.users', string='Aprobadores Nivel 1 (Hasta $5,000)', relation='approval_matrix_level1_rel', column1='matrix_id', column2='user_id')
    aprobador_nivel2_id = fields.Many2many('res.users', string='Aprobadores Nivel 2 (Más de $5,000)', relation='approval_matrix_level2_rel', column1='matrix_id', column2='user_id')
