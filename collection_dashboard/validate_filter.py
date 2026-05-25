# """
# Script de Validación - Collection Dashboard
# ============================================

# Este script se puede ejecutar desde el shell de Odoo para verificar
# que el filtro del diario financiero esté funcionando correctamente.

# EJECUTAR DESDE:
# ---------------
# odoo-bin shell -d nombre_base_datos

# LUEGO PEGAR ESTE CÓDIGO:
# """

# # ============================================================================
# # VERIFICACIÓN 1: Contar facturas del diario financiero en account.move
# # ============================================================================
# print("\n" + "="*70)
# print("VERIFICACIÓN 1: Facturas en account.move")
# print("="*70)

# # Buscar el diario financiero
# financial_journal = env['account.journal'].search([
#     ('name', '=', 'CUENTAS POR COBRAR FINANCIERAS')
# ], limit=1)

# if not financial_journal:
#     print("⚠️  ADVERTENCIA: No se encontró el diario 'CUENTAS POR COBRAR FINANCIERAS'")
#     print("   Si el diario tiene otro nombre, actualiza el código.")
# else:
#     print(f"✅ Diario encontrado: {financial_journal.name} (ID: {financial_journal.id})")
    
#     # Contar facturas en account.move
#     financial_invoices = env['account.move'].search([
#         ('journal_id', '=', financial_journal.id),
#         ('move_type', '=', 'out_invoice'),
#         ('state', '=', 'posted'),
#         ('amount_residual', '>', 0.0)
#     ])
    
#     print(f"📊 Facturas del diario financiero en account.move: {len(financial_invoices)}")
#     if financial_invoices:
#         print(f"   Ejemplos: {', '.join(financial_invoices[:3].mapped('name'))}")

# # ============================================================================
# # VERIFICACIÓN 2: Verificar que NO existan en cobranza.factura
# # ============================================================================
# print("\n" + "="*70)
# print("VERIFICACIÓN 2: Facturas en cobranza.factura")
# print("="*70)

# # Intentar buscar facturas del diario financiero
# # NOTA: Esta búsqueda debe retornar 0 resultados si el filtro funciona
# cobranza_financial = env['cobranza.factura'].sudo().search([
#     ('journal_id', '=', financial_journal.id if financial_journal else False)
# ])

# if len(cobranza_financial) > 0:
#     print(f"❌ ERROR: Se encontraron {len(cobranza_financial)} facturas del diario financiero en cobranza.factura")
#     print("   Esto NO debería ocurrir. El filtro NO está funcionando correctamente.")
#     print(f"   Facturas encontradas: {', '.join(cobranza_financial.mapped('factura'))}")
# else:
#     print("✅ CORRECTO: No hay facturas del diario financiero en cobranza.factura")
#     print("   El filtro está funcionando correctamente.")

# # ============================================================================
# # VERIFICACIÓN 3: Probar búsqueda como diferentes usuarios
# # ============================================================================
# print("\n" + "="*70)
# print("VERIFICACIÓN 3: Búsqueda por tipo de usuario")
# print("="*70)

# # Total de facturas normales (sin sudo)
# total_facturas = env['cobranza.factura'].search_count([])
# print(f"📊 Total de facturas visibles (usuario actual): {total_facturas}")

# # Como administrador
# total_admin = env['cobranza.factura'].sudo().search_count([])
# print(f"👑 Total de facturas como admin: {total_admin}")

# # Buscar gerentes y supervisores para probar
# manager_group = env.ref('collection_dashboard.group_collection_manager', raise_if_not_found=False)
# if manager_group:
#     managers = env['res.users'].search([('groups_id', 'in', manager_group.id)], limit=1)
#     if managers:
#         manager_facturas = env['cobranza.factura'].with_user(managers[0]).search_count([])
#         print(f"👔 Total de facturas como gerente ({managers[0].name}): {manager_facturas}")

# # ============================================================================
# # VERIFICACIÓN 4: Contar por diario
# # ============================================================================
# print("\n" + "="*70)
# print("VERIFICACIÓN 4: Distribución por diario")
# print("="*70)

# # Agrupar facturas por diario
# facturas_por_diario = env['cobranza.factura'].sudo().read_group(
#     domain=[],
#     fields=['journal_id'],
#     groupby=['journal_id']
# )

# print("📊 Facturas por diario:")
# for grupo in facturas_por_diario:
#     journal_name = grupo['journal_id'][1] if grupo['journal_id'] else 'Sin Diario'
#     count = grupo['journal_id_count']
    
#     # Marcar si es el diario financiero
#     if financial_journal and grupo['journal_id'] and grupo['journal_id'][0] == financial_journal.id:
#         print(f"   ⚠️  {journal_name}: {count} facturas (¡ESTE NO DEBERÍA APARECER!)")
#     else:
#         print(f"   ✅ {journal_name}: {count} facturas")

# # ============================================================================
# # VERIFICACIÓN 5: Probar reglas de seguridad
# # ============================================================================
# print("\n" + "="*70)
# print("VERIFICACIÓN 5: Reglas de seguridad activas")
# print("="*70)

# rules = env['ir.rule'].search([
#     ('model_id.model', '=', 'cobranza.factura')
# ])

# print(f"🔒 Reglas de seguridad encontradas: {len(rules)}")
# for rule in rules:
#     print(f"\n   Regla: {rule.name}")
#     print(f"   Domain: {rule.domain_force}")
#     print(f"   Global: {rule.global}")
#     print(f"   Grupos: {rule.groups.mapped('name') if rule.groups else 'TODOS (global)'}")

# # ============================================================================
# # RESUMEN FINAL
# # ============================================================================
# print("\n" + "="*70)
# print("RESUMEN DE VALIDACIÓN")
# print("="*70)

# issues = []

# if financial_journal and len(cobranza_financial) > 0:
#     issues.append("❌ Facturas del diario financiero están visibles en cobranza.factura")

# if not financial_journal:
#     issues.append("⚠️  Diario 'CUENTAS POR COBRAR FINANCIERAS' no encontrado")

# # Verificar que exista la regla global
# global_rule = env['ir.rule'].search([
#     ('model_id.model', '=', 'cobranza.factura'),
#     ('global', '=', True)
# ], limit=1)

# if not global_rule:
#     issues.append("⚠️  No se encontró regla de seguridad GLOBAL")

# if not issues:
#     print("\n✅✅✅ TODAS LAS VERIFICACIONES PASARON ✅✅✅")
#     print("\nEl filtro del diario financiero está funcionando correctamente:")
#     print("- Las facturas NO se sincronizan")
#     print("- Las facturas NO aparecen en búsquedas")
#     print("- La regla de seguridad GLOBAL está activa")
#     print("- NINGÚN usuario (ni siquiera gerentes) puede verlas")
# else:
#     print("\n❌❌❌ SE ENCONTRARON PROBLEMAS ❌❌❌")
#     for issue in issues:
#         print(f"\n{issue}")
    
#     print("\n🔧 ACCIONES CORRECTIVAS:")
#     print("1. Actualizar el módulo: odoo-bin -u collection_dashboard")
#     print("2. Verificar que collection_dashboard_security.xml esté cargado")
#     print("3. Limpiar registros existentes del diario financiero")
#     print("4. Re-sincronizar facturas")

# print("\n" + "="*70)
