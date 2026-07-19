# Plan: Rediseño Toolbar + Feature Fusionar de Nodos

**Estado:** En ejecución
**Fecha:** 2026-07-18
**Contexto:** Página Explorar del dashboard-neuro-visor

---

## 1. Problema actual

- Los botones de acción están dispersos: Dormir/Eliminar al fondo del panel izquierdo, + Vincular en el panel central
- No hay forma de fusionar nodos (unir sinapsis, contenido y metadatos de múltiples nodos en uno solo)
- Los badges "activo"/"General" no tienen contexto visible
- `eliminarNodo()` no funciona (endpoint backend inexistente)

## 2. Dependencia: Radix Themes

**Instalación:** `npm install @radix-ui/themes`

**Regla de uso:** Siempre que creemos un componente nuevo, primero revisamos si Radix Themes tiene uno que sirva. Si lo tiene, lo usamos. Si no lo tiene o no encaja, construimos el nuestro con CSS modules.

**Override de tokens:** Selectivo — mantenemos nuestras variables CSS (`--bg-secondary`, `--accent-color`, etc.) y solo sobreescribimos los tokens de Radix que no coincidan.

### Componentes Radix a utilizar

| Componente nuevo | Radix Component | Uso |
|---|---|---|
| Modal de Fusionar | `Dialog` | Input con autocomplete + tags |
| Confirmar Eliminar | `AlertDialog` | Confirmación destructiva |
| Tags input (autocomplete) | `TextField` + custom | Buscar nodos existentes |
| Toolbar acciones | `Button` (variant="soft"/"ghost") | Vincular, Fusionar, Dormir, Eliminar |
| Badges de categoría | `Badge` | Reemplazar badges actuales |
| Select de filtros | `Select` | Filtros en panel de Sinapsis |
| Tooltips en badges | `Tooltip` | Info sobre badges y acciones |

## 3. Cambio: Barra de acciones unificada

**Actual:**
- Left panel: Dormir 😴 + Eliminar 🗑️ al fondo
- Center panel: + Vincular arriba a la derecha

**Propuesto:**
- Nueva barra de acciones arriba de las 3 columnas del Explorar
- Botones alineados a la derecha: `[ ✏️ Vincular ] [ 🔗 Fusionar ] [ 😴 Dormir ] [ 🗑️ Eliminar ]`
- Estilo: botones pequeños tipo toolbar, consistentes con el design system existente + Radix Button
- La columna izquierda (NodeIdentityPanel) queda limpia — solo muestra info del nodo

## 4. Feature: Fusionar nodos

### 4.1 Botón y modal

- **Botón:** `🔗 Fusionar` en la toolbar
- **Modal (MergeModal):** componente nuevo usando Radix `Dialog`
  - Input con autocomplete que busca nodos existentes via `GET /api/buscar?q=...`
  - Solo acepta nodos que existen en la DB (validación en tiempo real)
  - Cada nodo seleccionado aparece como tag removible
  - Botón "Fusionar X nodo(s)" con loading state
  - Confirmación antes de ejecutar

### 4.2 Lógica backend — `POST /api/nodo/fusionar`

**Request:**
```json
{
  "origen": "nodo_que_sobrevive",
  "destinos": ["nodo_a_eliminar_1", "nodo_a_eliminar_2"]
}
```

**Por cada nodo destino, en orden dentro de una transacción:**

1. **Mover sinapsis:** `UPDATE sinapsis SET origen = ? WHERE origen = ? AND destino NOT IN (SELECT destino FROM sinapsis WHERE origen = ?)` + idem con destino. Si ya existe la sinapsis duplicada, quedarse con la de mayor peso.
2. **Mover dimensiones:** INSERT OR IGNORE desde `largo_plazo_dimensiones` del destino al origen
3. **Mover WordNet groups:** INSERT OR IGNORE desde `nodo_grupos_semanticos` del destino al origen
4. **Combinar sinónimos:** Unión de los dos sets (sin duplicar)
5. **Contenido:** Si el origen está vacío → tomar el del destino. Si ambos tienen contenido → concatenar con separador `---`
6. **Eliminar latentes del destino:** `DELETE FROM sinapsis_latentes WHERE origen = ? OR destino = ?` (se recalcularán con el próximo consolidar)
7. **Eliminar nodo destino:** `DELETE FROM largo_plazo WHERE concepto = ?`

**Todo dentro de `BEGIN TRANSACTION` / `COMMIT`**

### 4.3 Endpoint auxiliar — `DELETE /api/nodo/{concepto}`

Necesario para eliminación individual de nodos (botón 🗑️ Eliminar). Limpia en orden:
1. `DELETE FROM sinapsis WHERE origen = ? OR destino = ?`
2. `DELETE FROM sinapsis_latentes WHERE origen = ? OR destino = ?`
3. `DELETE FROM largo_plazo_dimensiones WHERE concepto = ?`
4. `DELETE FROM nodo_grupos_semanticos WHERE concepto = ?`
5. `DELETE FROM largo_plazo WHERE concepto = ?`

## 5. Badges con tooltip

- Badge "activo": sin cambio (se entiende solo)
- Badge "General": agregar title attribute → "Categoría del nodo en BioRAG. Puede ser: System, General, Lesson, Profile, etc."

## 6. Archivos a modificar

| Archivo | Cambios |
|---|---|
| `package.json` | +`@radix-ui/themes` |
| `src/App.tsx` | Agregar `<ThemeProvider>` de Radix |
| `backend/server.py` | +2 endpoints: `DELETE /api/nodo/{concepto}`, `POST /api/nodo/fusionar` |
| `src/pages/Explorar/ExplorarPage.tsx` | Toolbar arriba, handlers para fusionar/eliminar/dormir |
| `src/pages/Explorar/ExplorarPage.module.css` | Estilos toolbar |
| `src/components/NodeIdentityPanel/NodeIdentityPanel.tsx` | Quitar botones Dormir/Eliminar del fondo |
| `src/components/NodeIdentityPanel/NodeIdentityPanel.module.css` | Quitar estilos btnActionSm/btnSleep/btnDanger |
| `src/components/ConnectionsPanel/ConnectionsPanel.tsx` | Quitar botón "+ Vincular" |
| `src/components/ConnectionsPanel/ConnectionsPanel.module.css` | Quitar estilos de "+ Vincular" |
| **Nuevo:** `src/components/MergeModal/MergeModal.tsx` | Modal de fusión con Radix Dialog |
| **Nuevo:** `src/components/MergeModal/MergeModal.module.css` | Estilos del modal |
| `src/services/api.ts` | +`eliminarNodo()`, +`fusionarNodos()`, +`buscarNodos()`, +`eliminarDimension()`, +`agregarDimension()`, +`eliminarGrupo()`, +`agregarGrupo()` |
| `backend/server.py` | +4 endpoints: DELETE/POST para dimensiones y grupos WordNet |

## 7. Orden de ejecución

1. Instalar Radix Themes
2. Backend: `DELETE /api/nodo/{concepto}` (limpieza completa)
3. Backend: `POST /api/nodo/fusionar` (lógica de merge)
4. Frontend: Mover botones a toolbar unificada
5. Frontend: Crear MergeModal con Radix Dialog + autocomplete
6. Frontend: Conectar handlers con backend
7. Verificar build + funcionalidad manual

## 8. Feature: Edición inline de Sinónimos, Dimensiones y WordNet

**Estado:** Plan
**Fecha:** 2026-07-19
**Motivo:** La barra de herramientas es un "editor de nodos" — ya permite cortar sinapsis, vincular, fusionar, dormir y eliminar. Falta poder editar las partes internas del nodo directamente (dimensiones, WordNet, sinónimos). Actualmente son chips de solo lectura.

### 8.1 Problema actual

- **Sinónimos:** No se pueden borrar individualmente. Hay duplicados (broadcast, plan, fix aparecen repetidos).
- **Dimensiones:** No se pueden borrar ni agregar. Solo display.
- **WordNet:** No se pueden borrar ni agregar. Solo display.
- El único editable es el contenido (textarea con Save/Cancel).

### 8.2 Solución propuesta — Edit inline en NodeIdentityPanel

Cada chip gains un botón × para eliminar, y un input para agregar nuevos:

#### Sinónimos (ya existe endpoint PUT)
- **Eliminar:** Click en × sobre el chip → filtra el string de sinónimos → PUT `/api/nodo/{concepto}` con el nuevo string
- **Agregar:** Input inline "+ Agregar sinónimo..." → append al string → PUT
- **Deduplicar:** Eliminar duplicados existentes al mostrar (broadcast ×2, plan ×2, fix ×2)

#### Dimensiones (endpoint nuevo necesario)
- **Eliminar:** Click en × sobre el chip → DELETE `/api/nodo/{concepto}/dimension` con `{ eje, valor }`
- **Agregar:** Input inline con select de eje + input de valor → POST `/api/nodo/{concepto}/dimension`
- **Endpoint DELETE:** `DELETE FROM largo_plazo_dimensiones WHERE concepto = ? AND dimension_id = (SELECT id FROM dimensiones_semanticas WHERE name = ? AND tipo_id = (SELECT id FROM tipos_dimension WHERE nombre = ?))`

#### WordNet (endpoint nuevo necesario)
- **Eliminar:** Click en × sobre el chip → DELETE `/api/nodo/{concepto}/grupo`
- **Agregar:** Input inline → POST `/api/nodo/{concepto}/grupo`
- **Endpoint DELETE:** `DELETE FROM nodo_grupos_semanticos WHERE concepto = ? AND grupo_id = (SELECT id FROM grupos_semanticos WHERE nombre = ?)`

### 8.3 UX — Patrón común para las 3 secciones

```
🎭 Dimensiones                    [collapse/expand]
  ┌──────────────────────────────────────┐
  │ [emocion.alegria ×] [dominio.tec ×] │  ← chips con ×
  │ [accion.pers ×] [intencion.doc ×]   │
  │ + Agregar dimensión...              │  ← input inline
  └──────────────────────────────────────┘
```

- Los chips muestran un **×** pequeño (opacity 0.5, full opacity on hover)
- Click en × → eliminación inmediata (sin confirmación — es un chip, no un nodo)
- Input inline aparece al final de la lista
- Enter para agregar, Escape para cancelar
- Guardado automático (no necesita botón "Guardar" — cada operación es un PUT/DELETE inmediato)

### 8.4 Backend — Endpoints nuevos

| Endpoint | Método | Body | Descripción |
|---|---|---|---|
| `/api/nodo/{concepto}/dimension` | DELETE | `{ "eje": "...", "valor": "..." }` | Eliminar una dimensión |
| `/api/nodo/{concepto}/dimension` | POST | `{ "eje": "...", "valor": "..." }` | Agregar una dimensión |
| `/api/nodo/{concepto}/grupo` | DELETE | `{ "nombre": "..." }` | Eliminar un grupo WordNet |
| `/api/nodo/{concepto}/grupo` | POST | `{ "nombre": "...", "fuente": "manual" }` | Agregar un grupo WordNet |

### 8.5 Archivos a modificar

| Archivo | Cambios |
|---|---|
| `src/components/NodeIdentityPanel/NodeIdentityPanel.tsx` | Agregar edit inline: × en chips, inputs de agregar, handlers de eliminación/agregación |
| `src/components/NodeIdentityPanel/NodeIdentityPanel.module.css` | Estilos para ×, inputs inline, estado hover |
| `backend/server.py` | +4 endpoints: DELETE/POST para dimensiones y grupos |

## 9. Notas

- Las latentes NO se mueven — se eliminan del nodo fuente y se recalculan automáticamente con el próximo consolidar
- El contenido se concatena con separador `---` para preservar ambos textos
- Si el nodo destino tiene contenido vacío, se toma el del fuente sin separador
- El autocomplete debe paginarse o filtrarse para no sobrecargar con 10k+ nodos
- La edición inline usa guardado inmediato (cada operación es un PUT/DELETE al backend, no hay "Guardar todo")
