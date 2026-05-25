# Dashboard de Cobranzas - Configuración de Seguridad

## 🔐 Grupos de Seguridad Implementados

Este módulo implementa tres niveles de acceso para gestionar la seguridad y visibilidad de los documentos:

### 1. **Ejecutivo de Ventas** (`group_collection_sales_executive`)
- ✅ **Solo ve documentos de su zona/equipo**
- ✅ Puede modificar sus documentos
- ❌ No puede crear ni eliminar documentos
- 📍 Los documentos se filtran automáticamente según el equipo de ventas al que pertenece el usuario

### 2. **Supervisor de Cobranzas** (`group_collection_supervisor`)
- ✅ **Ve todos los documentos de todas las zonas**
- ✅ Puede leer y modificar cualquier documento
- ✅ Puede crear nuevos documentos
- ❌ No puede eliminar documentos

### 3. **Gerente de Cobranzas** (`group_collection_manager`)
- ✅ **Acceso total sin restricciones**
- ✅ Puede leer, modificar, crear y eliminar documentos
- ✅ Acceso completo a todas las configuraciones

## 🚫 Filtro de Diario Financiero

El sistema excluye automáticamente todos los documentos del diario **"CUENTAS POR COBRAR FINANCIERAS"**:

- ❌ No aparecen en la sincronización desde `account.move`
- ❌ No aparecen en las búsquedas ni vistas
- ❌ Se filtran automáticamente en todas las consultas
- 🔒 **Regla GLOBAL**: Aplica a TODOS los usuarios, incluyendo gerentes y administradores
- 🛡️ **Doble capa de protección**: 
  - Regla de seguridad `ir.rule` con `global=True`
  - Override del método `_search()` en el modelo

**Nota crítica**: Los documentos del diario financiero son completamente invisibles para el sistema de cobranzas, nadie puede verlos.

## 📋 Instrucciones de Configuración

### Paso 1: Actualizar el Módulo

Después de actualizar el código, actualiza el módulo en Odoo:

```bash
# Desde la línea de comandos de Odoo
odoo-bin -u collection_dashboard -d nombre_base_datos
```

O desde la interfaz web:
1. Ve a **Aplicaciones**
2. Busca "Collection Dashboard"
3. Haz clic en **Actualizar**

### Paso 2: Asignar Grupos a Usuarios

1. Ve a **Configuración → Usuarios y Compañías → Usuarios**
2. Selecciona un usuario
3. En la pestaña **Derechos de Acceso**, busca la sección **Dashboard de Cobranzas**
4. Selecciona el grupo apropiado:
   - **Ejecutivo de Ventas**: Para vendedores
   - **Supervisor de Cobranzas**: Para supervisores
   - **Gerente de Cobranzas**: Para gerentes

### Paso 3: Configurar Equipos de Ventas

Para que los ejecutivos solo vean sus documentos, debes:

1. Ve a **CRM → Configuración → Equipos de Ventas**
2. Abre cada equipo de ventas
3. En la pestaña **Miembros**, agrega los usuarios ejecutivos correspondientes
4. Los documentos (facturas) deben tener el campo `team_id` (Equipo de Ventas) configurado

### Paso 4: Verificar el Diario

Asegúrate de que el diario se llame exactamente:
```
CUENTAS POR COBRAR FINANCIERAS
```

Si tiene un nombre diferente, actualiza el código en:
- `models/cobranza_model.py` línea 91 y 51

## 🔄 Sincronización de Datos

El sistema sincroniza automáticamente las facturas desde `account.move` con las siguientes reglas:

✅ **Incluye:**
- Facturas de cliente (`move_type = 'out_invoice'`)
- Estado publicado (`state = 'posted'`)
- Con saldo pendiente (`amount_residual > 0`)

❌ **Excluye:**
- Facturas del diario "CUENTAS POR COBRAR FINANCIERAS"
- Facturas con saldo 0
- Facturas en borrador o canceladas

## 🧪 Pruebas de Seguridad

### Probar acceso de Ejecutivo:
1. Crea un usuario de prueba
2. Asígnale el grupo "Ejecutivo de Ventas"
3. Agrégalo como miembro de un equipo de ventas específico
4. Inicia sesión con ese usuario
5. Verifica que solo vea documentos de su equipo

### Probar acceso de Supervisor/Gerente:
1. Asigna el grupo correspondiente
2. Verifica que vea todos los documentos sin filtros

## ⚠️ Consideraciones Importantes

1. **Los usuarios necesitan estar en un equipo de ventas** para ver documentos como ejecutivos
2. **El filtro del diario es permanente** - los documentos financieros nunca aparecerán
3. **Las reglas de seguridad se aplican a nivel de base de datos** - no se pueden omitir desde el código
4. **Los supervisores heredan los permisos de ejecutivos** y luego obtienen acceso ampliado

## 📊 Estructura de Archivos Modificados

```
collection_dashboard/
├── security/
│   ├── collection_dashboard_security.xml  [NUEVO]
│   └── ir.model.access.csv               [MODIFICADO]
├── models/
│   └── cobranza_model.py                 [MODIFICADO]
└── __manifest__.py                       [MODIFICADO]
```

## 🐛 Solución de Problemas

**Problema:** Un ejecutivo no ve ningún documento
- ✅ Verifica que esté en un equipo de ventas
- ✅ Verifica que las facturas tengan el campo `team_id` configurado

**Problema:** Los documentos financieros aún aparecen
- ✅ Verifica el nombre exacto del diario
- ✅ Ejecuta la sincronización manualmente desde el cron
- ✅ Verifica que el campo `journal_id` esté guardado en los registros

**Problema:** Un supervisor no ve todos los documentos
- ✅ Verifica que tenga el grupo correcto asignado
- ✅ Limpia la caché del navegador
- ✅ Verifica que no haya reglas de registro conflictivas

---

**Versión del Módulo:** 16.0.1.0.0  
**Última Actualización:** Noviembre 2025
