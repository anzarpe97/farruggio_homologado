# Guía de Actualización Rápida - Collection Dashboard

## ✅ Cambios Implementados

### 1. 🔐 Sistema de Seguridad por Roles
- **Ejecutivos**: Solo ven documentos de su equipo de ventas
- **Supervisores**: Ven todos los documentos, pueden crear
- **Gerentes**: Acceso total (CRUD completo)

### 2. 🚫 Filtro de Diario Financiero
- Se excluyen automáticamente documentos del diario "CUENTAS POR COBRAR FINANCIERAS"
- Aplica tanto en sincronización como en búsquedas
- **IMPORTANTE**: Esta exclusión aplica a TODOS los usuarios, incluyendo gerentes y administradores
- Implementado con regla de seguridad GLOBAL + override del método _search

---

## 🚀 Pasos para Actualizar (REQUERIDO)

### Opción 1: Desde la Interfaz Web
1. Ir a **Aplicaciones**
2. Quitar filtro "Aplicaciones"
3. Buscar "Collection Dashboard"
4. Click en los 3 puntos → **Actualizar**

### Opción 2: Desde Línea de Comandos
```bash
# Windows
python odoo-bin -u collection_dashboard -d NOMBRE_BASE_DATOS --stop-after-init

# Linux/Mac
./odoo-bin -u collection_dashboard -d NOMBRE_BASE_DATOS --stop-after-init
```

---

## 👥 Configurar Usuarios (IMPORTANTE)

### Para Ejecutivos de Ventas:
1. Ir a **Configuración → Usuarios**
2. Seleccionar usuario
3. En **Derechos de Acceso** → **Dashboard de Cobranzas** → Marcar **"Ejecutivo de Ventas"**
4. **IMPORTANTE**: Ir a **CRM → Configuración → Equipos de Ventas**
5. Agregar al usuario como miembro del equipo correspondiente

### Para Supervisores:
1. Ir a **Configuración → Usuarios**
2. En **Derechos de Acceso** → **Dashboard de Cobranzas** → Marcar **"Supervisor de Cobranzas"**

### Para Gerentes:
1. Ir a **Configuración → Usuarios**
2. En **Derechos de Acceso** → **Dashboard de Cobranzas** → Marcar **"Gerente de Cobranzas"**

---

## 🧪 Verificar que Funciona

### Test 1: Ejecutivo de Ventas
```
✅ Iniciar sesión como ejecutivo
✅ Ir al Dashboard de Cobranza
✅ Verificar que SOLO se muestran documentos de su zona/equipo
❌ No debería ver documentos de otros equipos
```

### Test 2: Supervisor/Gerente
```
✅ Iniciar sesión como supervisor o gerente
✅ Ir al Dashboard de Cobranza
✅ Verificar que se muestran TODOS los documentos
✅ Sin restricciones por zona
```

### Test 3: Filtro de Diario
```
✅ Verificar que NO aparezcan facturas del diario "CUENTAS POR COBRAR FINANCIERAS"
✅ Ejecutar sincronización manual desde Cobranzas → Sincronizar
✅ Confirmar que documentos financieros siguen excluidos
```

---

## 📁 Archivos Modificados

```
✅ NUEVO: security/collection_dashboard_security.xml
✅ MODIFICADO: security/ir.model.access.csv
✅ MODIFICADO: models/cobranza_model.py
✅ MODIFICADO: __manifest__.py
✅ NUEVO: README.md
✅ NUEVO: INSTALACION.md (este archivo)
```

---

## ⚠️ Problemas Comunes

### Problema: "El usuario no ve ningún documento"
**Solución:**
- Verificar que el usuario esté en un equipo de ventas
- Verificar que las facturas tengan el campo `team_id` (Equipo de Ventas) configurado
- En `account.move`, el campo `team_id` debe estar lleno

### Problema: "Aún aparecen documentos del diario financiero"
**Solución:**
- Verificar que el diario se llame EXACTAMENTE: "CUENTAS POR COBRAR FINANCIERAS"
- Si tiene otro nombre, modificar en `cobranza_model.py` líneas 51 y 91
- Re-sincronizar los documentos

### Problema: "No aparece la categoría Dashboard de Cobranzas"
**Solución:**
- Actualizar el módulo correctamente
- Reiniciar el servidor Odoo
- Verificar que `collection_dashboard_security.xml` esté en la carpeta `security/`

---

## 📞 Soporte

Si encuentras algún problema:

1. Verificar los logs de Odoo: `odoo.log`
2. Buscar errores con: `grep -i error odoo.log`
3. Verificar que todos los archivos estén en su lugar
4. Contactar al desarrollador con los detalles del error

---

**¡Listo!** 🎉

Después de seguir estos pasos, tu sistema de cobranzas tendrá:
- ✅ Seguridad por roles funcional
- ✅ Filtrado automático del diario financiero
- ✅ Ejecutivos viendo solo su información
- ✅ Supervisores y gerentes con acceso completo
