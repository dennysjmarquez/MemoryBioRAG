# Plan: Visor Neuro-Cognitivo v2 — Panel de Inspección y Curación de Nodos

**Fecha:** 2026-07-15
**Estado:** En diseño
**Autor:** Athena-OEC + Dennys (con aporte de Arena AI)

---

## 1. Problema

La vista "Explorar" del dashboard actual usa un grafo force-directed que:

- Con 2 saltos de BFS explota a **304 nodos y 2,598 edges** (hairball ilegible)
- No muestra metadatos de las conexiones (peso, tipo, fecha, dirección)
- No permite navegar entre nodos de forma controlada
- No permite editar/curar las conexiones
- El nodo seleccionado no se centra
- "Saltos" no tiene explicación para el usuario

**Dato clave:** El nodo promedio tiene ~18 conexiones directas. Algunos tienen 100+. Un grafo force-directed con esto es siempre un hairball.

## 2. Decisión de diseño

**Cancelamos el grafo visual de la vista Explorar.**

Lo reemplazamos por un **Panel de Inspección y Curación de Nodos** — un inspector tipo IDE (como Chrome DevTools F12) donde se ve TODA la información de un nodo y se puede editar cada aspecto.

**Principio:** "Un grafo es una estructura de datos, no una interfaz de usuario. Los humanos navegan listas ordenadas y enlaces."

**Referentes:** Wikipedia, GitHub, LinkedIn — ninguno usa grafos para navegar. Usan listas + enlaces.

## 3. Filosofía de la vista

Dennys es un "cirujano del cerebro". Cuando entra a un nodo necesita:

1. **Ver TODO** lo que ese nodo "tiene detrás" (como abrir una entrada de DB con contexto humano completo)
2. **Ejecutar acciones CRUD** directamente sobre esa información
3. **Navegar** entre nodos siguiendo conexiones
4. **Mantenimiento** — quitar vínculos mal construidos, crear faltantes, editar contenido

## 4. Layout: 3 columnas + header

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔍 [buscar...]    ◀ ▶  🏠 > leccion_contenido > princ_gestion  │
├────────────────────┬────────────────────────┬───────────────────┤
│                    │                        │                   │
│  COLUMNA IZQ (25%) │ COLUMNA CENTRO (45%)   │ COLUMNA DER (30%) │
│  Identidad del     │ Conexiones directas    │ Contexto          │
│  nodo              │ (SINAPSIS)             │ extendido         │
│                    │                        │                   │
│  • Nombre          │  Tarjeta por cada      │  • Latentes       │
│  • Categoría       │  sinapsis directa:     │  • Similares      │
│  • Peso            │  - Dirección (→ ← ↔)  │  • Grupos WordNet │
│  • Estado          │  - Barra de peso       │                   │
│  • Fechas          │  - Tipo (badge color)  │                   │
│  • Sinónimos       │  - Último uso          │                   │
│  • Dimensiones     │  - Preview del nodo    │                   │
│  • WordNet         │  - Botón ❌ desvincular│                   │
│  • Contenido       │  - Botón [Ir →] navegar│                   │
│  • Acciones        │  - Botón [Ver por qué] │                   │
│                    │                        │                   │
│  [✏️ Editar]       │  Filtros:              │  Secciones        │
│  [😴 Dormir]       │  - Tipo de sinapsis    │  colapsables      │
│  [🗑️ Eliminar]    │  - Peso mínimo         │                   │
│                    │  - Orden               │                   │
│                    │  - Buscar en conexiones│                   │
└────────────────────┴────────────────────────┴───────────────────┘
```

## 5. Detalle de cada columna

### 5.1 Columna izquierda — Identidad del nodo

Muestra TODO sobre el nodo seleccionado:

| Campo | Descripción |
|-------|-------------|
| Nombre | Nombre del concepto (grande, bold) |
| Categoría | Badge de color: Lesson, Architecture, Principle, etc. |
| Peso sináptico | Barra visual + número decimal (0-1) |
| Estado | 🟢 activo / 😴 dormido |
| Creado | Timestamp formato "hace X días/horas" |
| Último acceso | Timestamp formato "hace X" |
| Comunidad | cluster_id si existe |
| Sinónimos | Chips clickeables |
| Dimensiones | Agrupadas por eje (emocion, entidad, accion, cualidad, coordenada, intencion, dominio) — chips clickeables |
| WordNet | Grupos lexname como chips |
| Contenido | Texto completo del nodo (scrolleable si es largo) |
| Acciones | [✏️ Editar] [😴 Dormir] [🌅 Despertar] [🗑️ Eliminar] |

### 5.2 Columna central — Conexiones directas (SINAPSIS)

Header: `🔗 Sinapsis Directas (N)` + botón `[+ Añadir vínculo]`

**Cada tarjeta de sinapsis contiene:**

```
┌─────────────────────────────────────────────────┐
│ [→] athena_oec                          [❌]    │
│ ████████████████░░░░ 0.85                       │
│ 🏷️ co_ocurrencia · último uso: hace 1d          │
│ 📁 Cognition · 🎭 accion.cognitiva              │
│ 📝 "Athena-OEC: sistema de orquestación..."     │
│ [Ir a este nodo →]  [Ver por qué están unidos]  │
└─────────────────────────────────────────────────┘
```

**Elementos de cada tarjeta:**

| Elemento | Descripción |
|----------|-------------|
| Dirección `→ ← ↔` | `→` yo apunto a él, `←` él me apunta, `↔` bidireccional |
| Barra de peso | Visual + número decimal (0-1) |
| Badge tipo | Color distintivo por tipo (ver tabla de colores abajo) |
| Último uso | De `sinapsis.ultimo_uso` formato "hace X" |
| Preview nodo | Categoría + primera dimensión + primeros 80 chars de contenido |
| [❌] | Ejecuta DELETE con confirmación |
| [Ir →] | Navega a ese nodo como nuevo centro |
| [Ver por qué] | Modal con explicación de la conexión |

**Colores de tipo de sinapsis (CSS variables):**

| Tipo | Color |
|------|-------|
| `manual` | `--color-manual: #8b5cf6` (morado) |
| `sinonimo_explicito` | `--color-sinonimo: #10b981` (verde) |
| `co_ocurrencia` | `--color-coocurrencia: #6b7280` (gris) |
| `rafaga_rememb` | `--color-rafaga: #f59e0b` (amarillo) |
| `co_nombre` | `--color-conombre: #3b82f6` (azul) |
| `co_semantica` | `--color-cosemantic: #06b6d4` (cyan) |

**Filtros (arriba de la lista):**

- `[Todas ▼]` — filtro por tipo de sinapsis
- `[Peso >= 0.0 ▼]` — filtro por peso mínimo
- `[Ordenar: peso ▼]` — peso / último uso / alfabético
- `[Buscar en conexiones...]` — filtro por texto

### 5.3 Columna derecha — Contexto extendido

Tres secciones colapsables:

**Sección A: 🌀 Sinapsis Latentes (inferidas)**
- Tarjetas más pequeñas, borde punteado
- Muestra: destino, peso_atenuado, saltos, ruta ("A → B → C")
- Botones: [✓ Confirmar como directa] [✗ Rechazar ruta]
- Filtradas por peso >= 0.3 por defecto

**Sección B: 🎭 Nodos con dimensiones similares**
- Otros nodos que comparten al menos 2 dimensiones semánticas
- Badge de dimensiones compartidas
- Botón [🔗 Crear vínculo manual]

**Sección C: 🏷️ Nodos con mismos grupos WordNet**
- Nodos que comparten lexnames
- Botón [🔗 Crear vínculo manual]

## 6. Header superior (fijo)

```
[🔍 Buscar concepto...]    [← Atrás] [→ Adelante]    🏠 > lecc_contenido > princ_gestion > athena_oec
```

- **Buscador:** autocomplete que llama a `/api/buscar`
- **Back/Forward:** navegan por historial de nodos visitados
- **Breadcrumb:** clickeable, cada crumb navega a ese nodo
- **Máximo 5 niveles** en breadcrumb, truncado en el medio si supera
- **Historial en localStorage** para persistir entre recargas

## 7. Operaciones CRUD soportadas

### 7.1 Sobre el nodo

| Acción | Botón | Endpoint | Confirmación |
|--------|-------|----------|-------------|
| Ver detalle | Click en nodo | GET `/api/nodo/{id}` | No |
| Editar contenido | ✏️ Editar | PATCH `/api/nodo/{id}` | Modal |
| Dormir | 😴 Dormir | POST `/api/nodo/{id}/dormir` | Sí |
| Despertar | 🌅 Despertar | POST `/api/nodo/{id}/despertar` | No |
| Eliminar | 🗑️ Eliminar | DELETE `/api/nodo/{id}` | Sí (warning cascada) |

### 7.2 Sobre las sinapsis

| Acción | Botón | Endpoint | Confirmación |
|--------|-------|----------|-------------|
| Ver conexiones | Automático | GET `/api/nodo/{id}/sinapsis` | No |
| Crear sinapsis | [+ Añadir] | POST `/api/sinapsis` | Modal |
| Desvincular | ❌ en tarjeta | DELETE `/api/sinapsis` | Sí ("¿Cortar vínculo A ↔ B?") |
| Editar peso/tipo | En modal | PATCH `/api/sinapsis` | No |

### 7.3 Sobre latentes

| Acción | Botón | Endpoint | Confirmación |
|--------|-------|----------|-------------|
| Confirmar como directa | ✓ | POST `/api/sinapsis` (copia de latente a directa) | No |
| Rechazar ruta | ✗ | DELETE de la latente | Sí |

### 7.4 Operaciones globales

| Acción | Ubicación | Endpoint |
|--------|-----------|----------|
| Consolidar cerebro | Botón sidebar | POST `/api/consolidar` |
| Buscar nodo | Barra búsqueda | GET `/api/buscar?q=...` |
| Ver estado del cerebro | Vista Corteza | GET `/api/corteza/estado` |

## 8. Endpoints backend necesarios

### 8.1 GET `/api/nodo/{concepto}` — Expandido

Retorna TODO del nodo:

```json
{
  "concepto": "leccion_contenido_...",
  "categoria": {"id": 4, "name": "Lesson"},
  "peso_sinaptico": 0.25,
  "estado": "activo",
  "contenido": "...",
  "sinonimos": ["a", "b"],
  "creado_en": 1234567890,
  "ultimo_acceso": 1234567890,
  "community_id": 12,
  "dimensiones": {
    "emocion": ["afecto"],
    "dominio": ["tecnico"]
  },
  "grupos_wordnet": ["noun.cognition", "verb.communication"]
}
```

### 8.2 GET `/api/nodo/{concepto}/sinapsis` — Nueva

Retorna sinapsis directas con datos del nodo destino enriquecidos:

```json
{
  "total": 11,
  "sinapsis": [
    {
      "id": 123,
      "direccion": "salida",
      "destino_concepto": "athena_oec",
      "peso": 0.85,
      "tipo": "co_ocurrencia",
      "ultimo_uso": 1234567890,
      "creado_en": 1234567890,
      "destino_categoria": "Cognition",
      "destino_preview": "Athena-OEC: sistema...",
      "destino_dimensiones_top": ["accion.cognitiva"],
      "destino_estado": "activo"
    }
  ]
}
```

Ordenado por peso DESC. Un solo JOIN entre sinapsis y largo_plazo.

### 8.3 GET `/api/nodo/{concepto}/latentes` — Nueva

Query a `sinapsis_latentes` filtrado por `origen = ? OR destino = ?`, ordenado por `peso_atenuado DESC`, con datos del nodo destino enriquecidos.

### 8.4 GET `/api/nodo/{concepto}/similares` — Nueva

Nodos que comparten dimensiones o grupos WordNet. Query a `largo_plazo_dimensiones` y `nodo_grupos_semanticos`.

### 8.5 DELETE `/api/sinapsis` — CRUD

Body: `{"origen": "a", "destino": "b"}` → `DELETE FROM sinapsis WHERE origen=? AND destino=?`

### 8.6 POST `/api/sinapsis` — CRUD

Body: `{"origen": "a", "destino": "b", "peso": 0.5, "tipo": "manual"}`

### 8.7 PATCH `/api/sinapsis` — CRUD

Para ajustar peso o tipo de una sinapsis existente.

### 8.8 POST `/api/nodo/{concepto}/dormir` y `/despertar` y DELETE `/api/nodo/{concepto}`

CRUD sobre el nodo entero.

### 8.9 GET `/api/sinapsis/{origen}/{destino}/explicar` — Nueva

"¿Por qué están unidos?" Retorna tokens compartidos, tipo, fecha creación, dimensiones en común, etc.

## 9. Reglas técnicas

1. **NO usar D3, NO Sigma.js, NO ForceGraph.** HTML puro + CSS + JS vanilla. Zero librerías de grafo.
2. **Optimistic UI:** al clickear ❌, quitar del DOM inmediatamente y luego llamar DELETE. Si falla, volver a poner.
3. **Cascada al eliminar nodo:** warning "Esto borrará también N sinapsis, M dimensiones, K grupos. ¿Confirmar?"
4. **Confirmación en desvinculación:** modal "¿Cortar vínculo A ↔ B?" con [Cancelar] [Cortar]
5. **Breadcrumb máximo 5 niveles** con truncado en el medio
6. **Historial en localStorage** para persistir back/forward entre recargas
7. **Timestamps formato "hace X"** (función custom, sin dependencias)
8. **Colores de tipo de sinapsis** como CSS variables, consistentes en toda la app
9. **Máximo 500 sinapsis** por carga (paginar si un nodo tiene más)
10. **NO mezclar** sinapsis directas con latentes en la misma lista
11. **NO hacer BFS** de segundo nivel automáticamente
12. **NO mostrar visualización de grafo** ni siquiera mini-mapa

## 10. Fases de implementación

### Fase 1 — Inspector de nodo + conexiones (AHORA)

**Objetivo:** Poder ver un nodo y sus conexiones directas, navegar entre nodos, desvincular sinapsis.

- [ ] Backend: Reescribir endpoint `/ego` → solo conexiones directas
- [ ] Backend: Crear endpoint `/api/nodo/{id}/sinapsis`
- [ ] Backend: Crear endpoint `/api/nodo/{id}/latentes`
- [ ] Backend: Crear DELETE `/api/sinapsis`
- [ ] Frontend: Reemplazar grafo force-directed por layout de 3 columnas
- [ ] Frontend: Tarjetas de sinapsis con metadata completa
- [ ] Frontend: Navegación breadcrumb + back/forward
- [ ] Frontend: Búsqueda con autocomplete
- [ ] Frontend: Acción desvincular con confirmación

### Fase 2 — Edición de nodos y creación (próxima)

**Objetivo:** Poder crear, editar y eliminar nodos desde la UI.

- [ ] Backend: PATCH `/api/nodo/{id}` (editar contenido, categoría, etc.)
- [ ] Backend: POST `/api/nodo` (crear nodo nuevo)
- [ ] Backend: DELETE `/api/nodo/{id}` con cascada
- [ ] Backend: POST `/api/sinapsis` (crear conexión)
- [ ] Backend: PATCH `/api/sinapsis` (editar peso/tipo)
- [ ] Frontend: Modal de edición de nodo
- [ ] Frontend: Modal de creación de nodo
- [ ] Frontend: Botón [+ Añadir vínculo]
- [ ] Frontend: Sección de latentes con confirmar/rechazar
- [ ] Frontend: Dormir/despertar nodo

### Fase 3 — Consolidar + métricas (futuro)

**Objetivo:** Consolidar desde la UI, ver métricas, comunicacion.

- [ ] Frontend: Botón Consolidar con feedback
- [ ] Frontend: Vista de métricas/historial de sueño
- [ ] Frontend: Panel de mensajes entre agentes
- [ ] Frontend: Export/import
- [ ] Frontend: Operaciones por lotes

## 11. Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `dashboard/server.py` | Reescribir `/ego`, agregar endpoints nuevos |
| `dashboard/static/js/app.js` | Eliminar ForceGraph, crear renderExplorerView() |
| `dashboard/static/index.html` | Reemplazar graph-container por layout 3 columnas |
| `dashboard/static/css/biorag.css` | Estilos de tarjetas, columnas, modales |

## 12. Lo que NO cambia

- Vista Corteza (ya funciona)
- Vista Latentes (ya funciona)
- Vista Comunidades
- Vista Sueños
- Endpoint `/api/corteza/*`
- Endpoint `/api/buscar`
- Endpoint `/api/latentes` (para la vista Latentes)
- Sidebar y navegación entre vistas

## 13. Decisiones tomadas

| Decisión | Razón |
|----------|-------|
| Sin grafo visual | 2 iteraciones fallidas, hairball inevitable |
| 3 columnas | Inspector IDE-like, toda la info visible |
| HTML/CSS puro | Sin dependencias de grafos, más mantenible |
| hops=1 fijo | No mezclar directas con latentes |
| Breadcrumb + back/forward | Navegación tipo navegador web |
| Optimistic UI | Sensación de rapidez al editar |
| Confirmación en destructive | Prevenir errores de cirugía |
| Colores CSS variables | Consistencia en toda la app |
