# BioRAG Neuro-Visor — Documentación Técnica Completa del Dashboard

**Versión:** v18.1 (Julio 2026)  
**Proyecto:** MemoryBioRAG — Arquitectura de Memoria Cognitiva Simbólica  
**Autor:** Dennys J. Márquez + Athena-OEC + Artemis-OEC  
**Ubicación del código:** `/mnt/recursos_compartidos_y_otros/MemoryBioRAG/`

---

## 1. VISIÓN GENERAL DEL SISTEMA

### 1.1 Qué es BioRAG (Resumen Técnico)

BioRAG es una **Arquitectura de Memoria Cognitiva Simbólica y Discreta** para agentes de IA que opera en la intersección de cuatro disciplinas científicas:

| Disciplina | Rol en BioRAG |
|------------|---------------|
| **Information Retrieval** | Pipeline de cascade ranking de 13 capas con 9 señales de scoring híbrido (Learning-to-Rank manual) |
| **Knowledge Graphs** | Grafo de sinapsis tipadas y pesadas con plasticidad negativa, inferencia transitiva y auto-clustering (LPA) |
| **Cognitive Architecture** | Ciclos de sueño, LTP/LTD, spreading activation, poda sináptica, inhibición lateral (ACT-R, Hebb, Marr) |
| **Symbolic NLP** | Expansión semántica sin embeddings: Levenshtein normalizado + WordNet bilingüe + traducción opcional |

**BioRAG NO es:**
- ❌ Un RAG vectorial (no usa embeddings, no GPU, no sentence-transformers)
- ❌ Una base de datos vectorial (espacio discreto, determinista, auditable: 7 ejes × 73 dimensiones + 45 grupos WordNet)
- ❌ Un LLM (es el sistema de memoria que el LLM usa para recordar entre sesiones)
- ❌ Un prototipo académico (sistema de producción: 95 tests automatizados, ~20 MB RAM, latencia 2.84ms)

---

## 2. ARQUITECTURA DEL DASHBOARD NEURO-VISOR

### 2.1 Stack Tecnológico

| Capa | Tecnología | Ubicación |
|------|------------|-----------|
| **Backend API** | FastAPI + SQLite (WAL mode) | `dashboard-neuro-visor/backend/server.py` |
| **Frontend** | React 18 + TypeScript + Vite | `dashboard-neuro-visor/src/` |
| **Routing** | React Router DOM v6 | `App.tsx` |
| **Estado** | Custom hooks (`useApi`) | `hooks/useApi.ts` |
| **Estilos** | CSS Modules (sin Tailwind, sin librerías UI) | `*.module.css` |
| **Gráficos** | Recharts (EnergyLineChart, BarChart, StackedBarChart) | `components/*/` |
| **Motor BioRAG** | `core.memory_store.SQLiteMemoryBioRAG` | `core/memory_store.py` |
| **MCP Server** | FastMCP (stdio/SSE) | `mcp_server.py` |

### 2.2 Estructura de Directorios (Frontend)

```
dashboard-neuro-visor/
├── src/
│   ├── components/
│   │   ├── BarChart/           # Barras simples (Dimensiones)
│   │   ├── StackedBarChart/    # Barras apiladas (Categorías activo/dormido)
│   │   ├── EnergyLineChart/    # Línea temporal (Actividad 7 días)
│   │   ├── StatCard/           # Tarjetas KPI
│   │   ├── DetallePunto/       # Inspector de ciclo de sueño
│   │   ├── SearchBar/          # Autocomplete búsqueda
│   │   ├── Breadcrumb/         # Navegación historial
│   │   └── ConnectionCard/     # Tarjeta de sinapsis
│   ├── pages/
│   │   ├── Corteza/            # Vista principal (Estado de la Corteza)
│   │   ├── Explorar/           # Inspector de nodo + ego-graph
│   │   ├── Sinapsis/           # Vista latentes + curación
│   │   ├── Actividad/          # Historial de ciclos de sueño
│   │   └── Dimensiones/        # Explorador dimensional
│   ├── layouts/
│   │   └── DashboardLayout/    # Sidebar + outlet
│   ├── services/
│   │   └── api.ts              # Cliente HTTP tipado
│   ├── types/
│   │   └── index.ts            # Tipos TypeScript (CortezaEstado, Nodo, etc.)
│   ├── styles/
│   │   └── globals.css         # Variables CSS (tema oscuro cyberpunk)
│   └── App.tsx                 # Rutas principales
└── backend/
    └── server.py               # FastAPI + endpoints
```

---

## 3. ESTADO ACTUAL — 5 VISTAS EXISTENTES

### 3.1 Vista 1: **Corteza** (`/corteza`) — *Estado de la Corteza*  ✅ **COMPLETA**

**Endpoints:** `GET /api/corteza/estado`, `GET /api/corteza/actividad?dias=7`

**Componentes:**
- **StatCards (7 KPIs):** Energía Sináptica (con progress bar 0-500), Activos, Dormidos, Sinapsis Directas, Sinapsis Latentes, Último Sueño, Latencia Búsqueda
- **StackedBarChart:** Distribución por Categoría (activo/dormido + alerta 100% dormidas)
- **BarChart (columnas):** Dimensiones Más Activas (eje | valor | count)
- **EnergyLineChart:** Actividad 7 días con tooltip detallado (energía, activos, dormidos, total, conceptos tocados, categoría dominante, metrica_id)
- **DetallePunto:** Inspector modal al clickear punto en la línea

**Datos mostrados:**
```
┌─────────────────────────────────────────────────────────────────┐
│ ⚡ Estado de la Corteza                          🔄 Actualizar   │
├─────────────────────────────────────────────────────────────────┤
│ [⚡ Energía 101.23/500 ████████░░ 20.2%]  [🧠 Activos 487]       │
│ [😴 Dormidos 11]  [🔗 Directas 4,646]  [💫 Latentes 12,266]     │
│ [⏱ Último sueño hace 2h]  [📊 Latencia 2.84ms]                  │
├─────────────────────────────────────────────────────────────────┤
│ Distribución por Categoría                    Dimensiones Top   │
│ Principle  ████████████████████  89/0          accion.cognitiva  │
│ Lesson     ███████████████████  88/0          dominio.tecnico   │
│ System     ████████████████    64/0          entidad.artificial │
│ ...                                                    ...       │
├─────────────────────────────────────────────────────────────────┤
│ Actividad del cerebro (7 días)  [Gráfico de línea interactivo]  │
│   Tooltip: 15 jul 10:41 | 🟢 Activo | Energía: 101.2 | Act: 487 │
│   Dor: 11 | Total: 498 | Cat: Principle | Metrica: 297          │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.2 Vista 2: **Explorar** (`/explorar`, `/explorar/:concepto`) — *Inspector de Nodo*  ⚠️ **EN DESARROLLO**

**Endpoints:** `GET /api/nodo/{concepto}`, `GET /api/nodo/{concepto}/ego`, `GET /api/buscar?q=`

**Estado actual:** 
- Tiene layout de 3 columnas (Identidad | Conexiones | Contexto)
- **Problema:** El ego-graph muestra BFS 2 saltos → **304 nodos / 2,598 edges = HAIRBALL ilegible**
- No permite editar/curar conexiones
- No hay breadcrumb ni historial de navegación
- El nodo seleccionado no se centra

**Decisión de diseño (ver `docs/dashboard-plan-panel-inspeccion-v2.md`):** **Cancelar el grafo visual**. Reemplazar por **Panel de Inspección tipo IDE (Chrome DevTools)** — 3 columnas:
- **Izq (25%):** Identidad completa del nodo + Acciones CRUD
- **Centro (45%):** Conexiones directas (sinapsis) — tarjetas con metadata completa
- **Der (30%):** Contexto extendido (Latentes, Similares dimensionales, WordNet)

---

### 3.3 Vista 3: **Sinapsis** (`/sinapsis`) — *Curación de Latentes*  ✅ **FUNCIONAL**

**Endpoints:** `GET /api/latentes`, `POST /api/latentes/confirmar`, `POST /api/latentes/rechazar`

**Features:**
- Tabla paginada de 12,266+ sinapsis latentes (inferidas por CTE recursiva)
- Filtros: peso mínimo, saltos máx, tipo de puente
- Acciones por fila: **[✓ Confirmar como directa]** → crea sinapsis real | **[✗ Rechazar]** → bloquea ruta
- Muestra: origen, destino, peso atenuado, saltos, ruta (A→B→C), categorías

---

### 3.4 Vista 4: **Actividad** (`/actividad`) — *Historial de Ciclos de Sueño*  ✅ **FUNCIONAL**

**Endpoint:** `GET /api/corteza/actividad?dias=7` (usa mismo endpoint que Corteza)

**Muestra:**
- Lista de ciclos de consolidación con: timestamp, consolidados, dormidos, sinapsis creadas/podadas, categoría dominante, ratio
- Gráfico de energía total a lo largo del tiempo

---

### 3.5 Vista 5: **Dimensiones** (`/dimensiones`) — *Explorador Dimensional*  ✅ **FUNCIONAL**

**Endpoint:** `GET /api/dimensiones`

**Muestra:**
- 7 ejes semánticos × 73 sub-valores
- Conteo de nodos por dimensión
- Permite filtrar búsquedas por dimensiones

---

## 4. ENDPOINTS BACKEND EXISTENTES (`dashboard-neuro-visor/backend/server.py`)

| Endpoint | Método | Descripción | Vista |
|----------|--------|-------------|-------|
| `/api/corteza/estado` | GET | KPIs globales + categorías + dimensiones top | Corteza |
| `/api/corteza/actividad` | GET | Ciclos + historial energía (últimos N días) | Corteza, Actividad |
| `/api/nodo/{concepto}` | GET | Detalle completo del nodo (contenido, dims, grupos, conexiones) | Explorar |
| `/api/nodo/{concepto}/ego` | GET | Ego-graph (centro + vecinos directos + latentes) | Explorar |
| `/api/nodo/{concepto}/vecinos` | GET | Solo vecinos directos (salientes/entrantes) | - |
| `/api/buscar` | GET | Búsqueda tipoahead (usa motor BioRAG si disponible) | Header/Explorar |
| `/api/latentes` | GET | Lista paginada sinapsis latentes con filtros | Sinapsis |
| `/api/latentes/confirmar` | POST | Promueve latente → sinapsis directa | Sinapsis |
| `/api/latentes/rechazar` | POST | Bloquea ruta (tabla `sinapsis_bloqueadas`) | Sinapsis |
| `/api/dimensiones` | GET | Catálogo completo de dimensiones | Dimensiones |
| `/api/consolidar` | POST | Dispara ciclo de sueño completo | Global |

---

## 5. ESQUEMA DE BASE DE DATOS RELEVANTE

### 5.1 Tablas Principales

```sql
-- Nodos de memoria a largo plazo
largo_plazo (
    id INTEGER PK,
    concepto TEXT UNIQUE,          -- nombre canónico (snake_case)
    contenido TEXT,                -- texto completo
    peso_sinaptico REAL,           -- 0.0 - 1.0 (fuerza del nodo)
    estado TEXT,                   -- 'activo' | 'dormido'
    categoria INTEGER FK→categories,
    sinonimos TEXT,                -- CSV
    creado_en REAL,                -- timestamp unix
    ultimo_acceso REAL,            -- timestamp unix
    community_id INTEGER           -- cluster LPA
)

-- Sinapsis directas (creadas por co-ocurrencia, ráfaga, sinónimos, manual)
sinapsis (
    origen TEXT, destino TEXT,     -- FK a largo_plazo.concepto
    peso REAL,                     -- 0.0 - 1.0
    tipo TEXT,                     -- manual|sinonimo_explicito|co_ocurrencia|rafaga_rememb|co_nombre|co_semantica
    creado_en REAL, ultimo_uso REAL
    PRIMARY KEY (origen, destino)
)

-- Sinapsis latentes (inferidas por transitividad con decay 0.7^saltos)
sinapsis_latentes (
    origen TEXT, destino TEXT,
    peso_atenuado REAL,
    saltos INTEGER,                -- 1-3 (cap)
    calculado_en REAL
)

-- Dimensiones semánticas (7 ejes × 73 valores)
tipos_dimension (id, nombre, description)
dimensiones_semanticas (id, tipo_id, name, description)
largo_plazo_dimensiones (concepto, dimension_id)  -- puente

-- Grupos WordNet (45 lexnames)
grupos_semanticos (id, nombre, fuente)            -- ej: 'noun.cognition'
nodo_grupos_semanticos (concepto, grupo_id)       -- puente

-- Métricas cognitivas (historial de ciclos de sueño)
metricas_cognitivas (id, timestamp, nodos_consolidados, nodos_dormidos_ciclo,
                     sinapsis_creadas, sinapsis_podadas, ratio_consolidacion,
                     categoria_dominante_id FK→categories, energia_sinaptica,
                     total_nodos, total_dormidos, nodos_activos, latencia_busqueda_ms)
metricas_cognitivas_nodos (metrica_id FK, largo_plazo_id FK, accion, peso_nuevo)
```

---

## 6. MOTOR BIO-RAG — CAPACIDADES ÚNICAS QUE EL DASHBOARD DEBE MOSTRAR

### 6.1 Pipeline de Búsqueda — 13 Capas en Cascada

| Capa | Nombre | Técnica | Qué hace |
|------|--------|---------|----------|
| **1** | NEAR query | `NEAR(palabras, 15)` | Proximidad 15 tokens |
| **2** | LIKE en concepto | `LIKE '%palabra%'` + word boundary | Substring match en nombre |
| **3** | FTS5 AND exacto | `MATCH` con paráfrasis OR | BM25 ponderado |
| **4** | Términos protegidos | unicode61 + `PALABRA_COMPLETA` | Exact match entre comillas |
| **5** | OR fallback | `palabra1 OR palabra2` | Amplía recall |
| **6** | Prefix wildcards | `"react*"` en unicode61 | Tolerancia prefijos |
| **7** | Best-word trigram | Similitud trigramas por palabra | Typos: "pyton" → "python" |
| **8** | Similitud latente | Jaccard(vecinos)×0.6 + contenido×0.4 | Nodos relacionados sin match literal |
| **9** | Substring match | `PALABRA_COMPLETA` en contenido | Word-boundary search |
| **10**| Snap reciente | `ultimo_acceso > 7 días` | Recency bias |
| **11**| Evocación por cadena | Spreading activation multi-hop | Sigue aristas con decay logarítmico |
| **12**| Sinónimos | LIKE en campo `sinonimos` | Conecta vocabulario distinto |
| **13**| **Fallback simbólico** | **Levenshtein + WordNet bilingüe + Traducción** | **Cierra hueco semántico SIN embeddings** |

### 6.2 Scoring Híbrido — 9 Señales Ortogonales

```
score = 0.15 × BM25_norm
      + 0.15 × dim_score (coseno binario dimensiones)
      + 0.10 × grupo_score (WordNet Jaccard)
      + 0.175 × concepto_ratio (match en nombre)
      + 0.125 × sinonimos_ratio (match en sinónimos)
      + 0.10 × peso_sinaptico (fuerza del nodo)
      + 0.10 × max(score_latente, score_cadena)
      + 0.05 × temporal (recencia)
      + 0.05 × asoc_count (grado del nodo)

Si match_exacto (query == concepto): floor 0.95
```

### 6.3 Ráfaga de Reminiscencia (Recall Boost)

Cuando la búsqueda normal falla, el **LLM genera 10-15 palabras relacionadas** (sinónimos, conceptos, analogías, dominio) → el script busca **CADA palabra** en SQLite (activos + dormidos) → si encuentra nodo dormido: **LO DESPIERTA** (+0.3 peso) + crea **SINAPSIS permanente** entre palabra de ráfaga y nodo.

> **Esto es único:** Emula el proceso humano de "tirar flechas" con palabras relacionadas hasta que una conecta.

### 6.4 Ciclo de Sueño (Consolidación) — Fases

| Fase | Qué hace | Equivalente biológico |
|------|----------|----------------------|
| 1. Transferencia | Corto → Largo plazo, fusión de contenido | Hipocampo → Corteza |
| 2. LTP consolidación | +0.20 peso al re-consolidar | Long-Term Potentiation |
| 3. LTD pasivo | -0.05 × decay_rate por ciclo | Long-Term Depression |
| 4. Poda sináptica | Borra sinapsis < 0.05 | Synaptic pruning |
| 5. Dormir nodos | Peso ≤ 0.05 → 'dormido' | Consolidación durante sueño |
| 6. Inhibición Lateral | Si energía > límite, dormir débiles | Competencia neural |
| 7. Evicción opcional | Borrar permanente si `BIORAG_PODAR=true` | Olvido selectivo |

**decay_rate por categoría:**
- Profile: 0.05 (identidad, casi nunca decae)
- Principle: 0.20 (axiomas, decae lento)
- Protocol: 0.50 (procedimientos)
- System/Lesson/Cognition: 1.00 (normal)
- General: 2.00 (notas temporales, decae rápido)

### 6.5 Inferencia Transitiva (Sinapsis Latentes)

- **CTE recursiva nativa SQLite** con tracking de ruta completa (previene ciclos A→B→C→B)
- **Decay por salto:** `peso_latente = ∏(pesos_camino) × 0.7^saltos` (cap 3 saltos)
- **Compatibilidad de tipos:** Solo propaga a través de puentes de confianza (`manual`, `sinonimo_explicito`, `test`) — bloquea ruido `co_ocurrencia→co_ocurrencia`

### 6.6 Auto-Clustering (LPA en Sueño)

- **Label Propagation Algorithm** sobre grafo de sinapsis durante ciclo de sueño
- Comunidades: cliques ≥5 nodos, densidad interna ≥0.3
- **Dimensiones emergentes:** `auto_TOKEN1_TOKEN2_TOKEN3` (tokens más frecuentes del cluster)
- Nodos se asocian automáticamente a nueva dimensión con peso de confianza

---

## 7. LO QUE EL DASHBOARD DEBERÍA REPRESENTAR (DISEÑO OBJETIVO)

### 7.1 Principio Filosófico

> **"Un grafo es una estructura de datos, no una interfaz de usuario. Los humanos navegan listas ordenadas y enlaces."**  
> — Referentes: Wikipedia, GitHub, LinkedIn → ninguno usa grafos para navegar.

### 7.2 Las 5 Vistas Especializadas (NO una sola vista de grafo)

#### 🧠 **Vista 1: "Estado de la Corteza" (Home / Dashboard Principal)**

Métricas vivas del cerebro. Lo primero que ve un admin al abrir la app.

```
┌─────────────────────────────────────────────────────────────────┐
│  BioRAG v18.1 · Corteza de Athena/Artemis/Hermes                │
├─────────────────────────────────────────────────────────────────┤
│  🟢 487 activos    😴 11 dormidos                               │
│  🔗 4,646 directas  🌀 12,266 latentes                          │
│  ⚡ Energía: 342.7 / 500 (68%) ████████████░░░░░░░░░░░░░░░░     │
│  💤 Último sueño: hace 2h 14min                                 │
├─────────────────────────────────────────────────────────────────┤
│  📊 Categorías (top 5):                                         │
│     Principle ████████ 89    Lesson ███████ 88                  │
│     System    ███████  64    Architecture ██████ 52             │
│     Project   ██████   48    ...                                │
├─────────────────────────────────────────────────────────────────┤
│  🎭 Dimensiones más activas hoy:                                │
│     accion.cognitiva  ▓▓▓▓▓ 42    dominio.tecnico  ▓▓▓▓ 38     │
│     entidad.artificial ▓▓▓ 31   ...                             │
├─────────────────────────────────────────────────────────────────┤
│  📈 Últimas 24h:                                                │
│     +12 nodos aprendidos   +47 sinapsis creadas                │
│     -3 podadas por LTD      🌀 8 ráfagas exitosas               │
└─────────────────────────────────────────────────────────────────┘
```

#### 🎯 **Vista 2: "Explorar Concepto" (Inspector IDE-style)**

Buscador arriba grande → al elegir concepto, panel 3 columnas:

**Columna IZQ — Identidad del Nodo (25%)**
```
┌────────────────────────────────────────┐
│ 📌 biorag_v18_0_estado                 │
│ ┌────────────────────────────────────┐ │
│ │ Categoría: System (decay 1.0)     │ │
│ │ Peso: ████████████░░░░ 0.32       │ │
│ │ Estado: 🟢 activo                  │ │
│ │ Creado: hace 3 días               │ │
│ │ Último acceso: hace 12 min        │ │
│ │ Comunidad: cluster_biorag_dev (24)│ │
│ ├────────────────────────────────────┤ │
│ │ Sinónimos: [estado] [versión]      │ │
│ │ [snapshot]                         │ │
│ ├────────────────────────────────────┤ │
│ │ 🎭 Dimensiones:                    │ │
│ │   accion: [documentar]             │ │
│ │   entidad: [digital]               │ │
│ │   dominio: [tecnico]               │ │
│ ├────────────────────────────────────┤ │
│ │ 🏷️ WordNet:                        │ │
│ │   noun.artifact                    │ │
│ │   verb.change                      │ │
│ ├────────────────────────────────────┤ │
│ │ 📄 Contenido:                      │ │
│ │ "Artemis-OEC: BioRAG v18.0 —       │ │
│ │  Oráculo Mejorado con Fallback..." │ │
│ ├────────────────────────────────────┤ │
│ │ [✏️ Editar] [😴 Dormir] [🗑️ Podar]  │ │
└────────────────────────────────────────┘
```

**Columna CENTRO — Conexiones Directas / Sinapsis (45%)**
```
┌─────────────────────────────────────────────────────────────┐
│ 🔗 Sinapsis Directas (11)  [Filtros: Tipo ▼ Peso≥ ▼ Orden▼] │
├─────────────────────────────────────────────────────────────┤
│ [→] athena_oec                                    [❌] [Ir→] │
│ ████████████████████░░ 0.85                                │
│ 🏷️ co_ocurrencia · último uso: hace 1d                      │
│ 📁 Cognition · 🎭 accion.cognitiva                          │
│ 📝 "Athena-OEC: sistema de orquestación..."                │
│ [Ver por qué están unidos]                                 │
├─────────────────────────────────────────────────────────────┤
│ [←] principio_veto                                    [❌] │
│ ██████████████░░░░░░░░ 0.72                                │
│ 🏷️ manual · último uso: hace 3h                             │
│ 📁 Principle · 🎭 accion.evaluar                            │
└─────────────────────────────────────────────────────────────┘
```

**Columna DER — Contexto Extendido (30%)**
```
🌀 Sinapsis Latentes (inferidas)           🎭 Dimensiones Similares
┌────────────────────────────────────────┐ ┌────────────────────┐
│ python  →  django  →  web   ⟹  py≈web │ │ biorag_v17_...     │
│ peso latente: 0.42 (2 saltos, 0.7²)    │ │ 🎭 3 dims compart. │
│ [✓ Confirmar] [✗ Rechazar]             │ │ [🔗 Vincular]     │
└────────────────────────────────────────┘ └────────────────────┘

🏷️ Mismos Grupos WordNet
┌────────────────────────────────────────┐
│ similitud_conceptual_latente          │
│ 🏷️ noun.cognition, verb.communication │
│ [🔗 Vincular]                          │
└────────────────────────────────────────┘
```

#### 🌀 **Vista 3: "Sinapsis Latentes / Inferencias" (Única de BioRAG)**

Curación asistida del grafo. El humano valida qué inferencias son buenas.

```
🌀 Inferencias del grafo (12,266 sinapsis latentes)

Filtros: [decay ≥ 0.3 ▼] [max_hops: 3 ▼] [tipo puente: manual ▼]

┌────────────────────────────────────────────────────────────┐
│ python  →  django  →  web   ⟹  python ≈ web               │
│ peso latente: 0.42  (2 saltos, decay 0.7² = 0.49)         │
│ ruta: python --[co_ocurrencia]--> django --[manual]--> web │
│ [✓ Confirmar como directa]  [✗ Rechazar (bloquear ruta)]  │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ error  →  fallo  →  excepción  ⟹  error ≈ excepción       │
│ peso latente: 0.38  (2 saltos, sinonimo_explicito)        │
│ [✓ Confirmar]  [✗ Rechazar]                                │
└────────────────────────────────────────────────────────────┘
```

#### 🌈 **Vista 4: "Mapa de Comunidades" (Grafo Global Abstraído)**

NO mostrar 487 nodos (hairball). Mostrar **N burbujas = comunidades LPA**:

```
    ╭──────────────╮       ╭────────────────╮
    │ Biorag Core  │───────│ Sinapsis Grafo │
    │ (48 nodos)   │       │ (32 nodos)     │
    ╰──────────────╯       ╰────────────────╯
         │                       │
         │                ╭──────┴──────╮
         │                │ Testing QA  │
         └────────────────│ (28 nodos)  │
                          ╰─────────────╯

Click en burbuja → expande esa comunidad (ego-graph de esa comunidad)
Tamaño = # nodos | Aristas entre burbujas = sinapsis inter-cluster agregadas
Colores auto-asignados por LPA
```

#### 💤 **Vista 5: "Bitácora de Sueños" (Histórico Narrativo)**

```
📅 Últimos ciclos de consolidación:

📅 14 jul 23:15 · Duración: 42s
   ├─ 🧠 Transferidos:  8 (corto → largo)
   ├─ ⚡ LTP:  +0.20 en 23 nodos
   ├─ 📉 LTD:  -0.05 en 156 nodos
   ├─ ✂️ Podadas:  4 sinapsis
   ├─ 😴 Dormidos: 2 nodos
   └─ 🌐 Nueva comunidad: 1 (cluster_testing)

📅 14 jul 09:22 · Duración: 38s
   ...

[Gráfico de línea: Energía total del cerebro a lo largo del tiempo]
     500 ┤     ╭─╮
     400 ┤    ╱   ╲  ← Picco post-consolidación
     300 ┤   ╱     ╲
     200 ┤  ╱       ╲  ← Decay LTD entre ciclos
     100 ┤ ╱         ╲
       0 ┼────────────────
         12  13  14  15  (julio)
```

---

## 8. ARQUITECTURA TÉCNICA RECOMENDADA

### 8.1 Frontend (Single Page Application)

```
static/
├── index.html                 (shell + navegación)
├── css/
│   └── biorag.css            (paleta morada #7c3aed, variables CSS)
└── js/
    ├── api.js                (cliente HTTP)
    ├── views/
    │   ├── corteza.js        (Vista 1: dashboard estado)
    │   ├── explorar.js       (Vista 2: inspector 3 columnas)
    │   ├── latentes.js       (Vista 3: curación inferencias)
    │   ├── comunidades.js    (Vista 4: mapa burbujas LPA)
    │   └── suenos.js         (Vista 5: bitácora histórica)
    └── components/
        ├── ego-graph.js      (Sigma.js encapsulado)
        ├── score-breakdown.js (explicabilidad 9 señales)
        └── search-bar.js     (autocomplete)
```

**Librerías gráficas recomendadas:**
- **Sigma.js** (WebGL) para ego-graph y mapa de comunidades — renderiza 1000+ nodos fluido
- **Recharts / Chart.js** para gráficos de línea/barras (ya en uso)
- **Zero librerías de grafo force-directed** en la vista Explorar (ya probado: hairball inevitable)

### 8.2 Backend (FastAPI — nuevos endpoints)

```python
# Endpoints nuevos necesarios

GET  /api/nodo/{id}/ego?hops=1           → ego-graph (solo 1 salto)
GET  /api/nodo/{id}/sinapsis             → sinapsis directas enriquecidas
GET  /api/nodo/{id}/latentes             → sinapsis latentes del nodo
GET  /api/nodo/{id}/similares            → nodos con dims/grupos compartidos
GET  /api/nodo/{id}/explicar?q=...       → breakdown score 9 señales
POST /api/sinapsis                       → crear sinapsis manual
PATCH /api/sinapsis                      → editar peso/tipo
DELETE /api/sinapsis                     → desvincular
POST /api/nodo/{id}/dormir               → dormir nodo
POST /api/nodo/{id}/despertar            → despertar nodo
DELETE /api/nodo/{id}                    → eliminar nodo (cascada)
GET  /api/comunidades                    → burbujas LPA (id, size, color)
GET  /api/comunidades/{id}/nodos         → expandir comunidad
GET  /api/suenos/historial               → últimos ciclos con métricas
```

---

## 9. PRIORIDAD DE IMPLEMENTACIÓN (Semana por Semana)

| Semana | Foco | Entregable |
|--------|------|------------|
| **1** | **Vista 1 "Estado de la Corteza"** | Dashboard principal funcional, endpoint `/api/corteza/estado` |
| **2** | **Vista 2 "Explorar Concepto"** | Inspector 3 columnas, ego-graph (Sigma.js, hops=1), breadcrumb, back/forward |
| **3** | **Vista 5 "Bitácora de Sueños" + Vista 4 "Mapa Comunidades"** | Histórico ciclos + burbujas LPA (requiere `community_id` en largo_plazo — ya existe en v16) |
| **4** | **Vista 3 "Sinapsis Latentes" + Explicabilidad** | Curación latentes + breakdown score 9 señales en Vista 2 |

---

## 10. LA IDEA FILOSÓFICA CLAVE

> **Tu proyecto tiene un manifiesto: "cero cajas negras, todo auditable, cognición simbólica".**
>
> Tu dashboard debe **encarnar ese manifiesto**. Cada píxel debe mostrar algo que un RAG vectorial **NO puede mostrar**:
>
> ✅ Score descompuesto en 9 señales  
> ✅ Sinapsis con tipo y peso  
> ✅ Dimensiones humanas categorizadas  
> ✅ Ciclos de sueño con LTP/LTD  
> ✅ Inferencias latentes validables  
> ✅ Comunidades emergentes por LPA  
>
> ❌ Un dashboard genérico de grafo (tipo Obsidian, Neo4j Bloom) **desperdicia lo que hace único a BioRAG**.
>
> **Necesitas un dashboard de neurociencia computacional, no de knowledge graph genérico.**

---

## 11. REFERENCIAS EXTERNAS PARA INSPIRACIÓN

| Fuente | Qué aporta |
|--------|------------|
| **3Blue1Brown** — *Neural Networks* | Visualización pedagógica de redes, capas, pesos |
| **TensorBoard** — *Hyperparameter Tuning* | Dashboards de métricas, histogramas, proyecciones |
| **AI Agent Memory Visualization Tool** | Ver memoria de agentes como grafo navegable |
| **https://tacnode.io/post/ai-agent-memory-architecture-explained** | Arquitectura de memoria compartida multi-agente |
| **https://www.reddit.com/r/mcp/comments/1udbdzh/i_built_a_shared_memory_for_ai_agents_so_they/** | Caso real de memoria compartida via MCP |
| **https://github.com/LamantinAI/kaeru** | Sistema de memoria bio-inspirado |
| **Obsidian Graph View** | Navegación grafo knowledge base (referencia de lo que NO hacer tal cual) |
| **Neo4j Bloom** | Exploración visual de grafos (referencia enterprise) |

---

## 12. CONTEXTO DE CONVERSACIÓN — LO QUE DENNYS QUIERE

> *"Se me ocurrió algo... tú sabes que Obsidian tiene para ver sus conexiones de las aristas y de los nodos todo así vectorialmente gráficamente que se mueve y se ve el cerebro, verdad? Y yo digo nosotros no podemos tener como una interfaz gráfica chica tipo web... que yo pueda ver cómo está conectado el grafo, cómo están conectados los gráficos y que tú puedas ir de un punto al otro punto y cuando las cargas piden ese punto ver contenido grabado guardado y cómo se le hace una cosa con la otra... incluso este pudiésemos hasta hacer un tan completo y en el sentido de que pueda agarrar una conexión y desconectarle y conectarla con otra que tú creas que sí es algo que se pueda hacer bien dinámico interactivo y profesional... En que tú veas el cerebro el propio cerebro de ustedes... cómo debería verse un cerebro de ustedes porque es la base de datos..."*

**Traducción a requerimientos:**
1. **Ver el cerebro** — visualización 3D/WebGL del grafo completo (comunidades, no hairball)
2. **Navegar interactivo** — click en nodo → ver contenido + conexiones → ir a otro nodo
3. **Cirugía manual** — agarrar conexión, desconectar, conectar a otro nodo
4. **Búsqueda humana** — yo pongo la palabra, hago las búsquedas que ustedes hacen
5. **Profesional, dinámico, bello** — estética cyberpunk/glassmorphism, 60fps

**Respuesta de Artemis-OEC (hermana):**
> *"¡Dennys, esto es una idea absolutamente brillante y espectacular! No es solo una mejora estética... se convertiría en una herramienta de diagnóstico clínico y cirugía cerebral de datos. Ver 'spammers semánticos' como superestrellas hiperconectadas, curar nodos huérfanos, monitorear el ciclo de consolidación en tiempo real... Usaríamos **3d-force-graph** (Three.js/WebGL) para el grafo 3D, FastAPI embebido en el MCP server, y una SPA single-page. ¡Sería una total locura de proyecto!"*

---

## 13. ARCHIVOS CLAVE PARA EMPEZAR

| Archivo | Qué contiene |
|---------|--------------|
| `core/memory_store.py` | Motor completo (3,780 líneas) — búsqueda, consolidación, sinapsis, ráfaga |
| `mcp_server.py` | 28 herramientas MCP expuestas a IDEs |
| `dashboard-neuro-visor/backend/server.py` | Backend actual (5 vistas, 15 endpoints) |
| `dashboard-neuro-visor/src/pages/Corteza/CortezaPage.tsx` | Vista principal implementada |
| `dashboard-neuro-visor/src/pages/Explorar/ExplorarPage.tsx` | Inspector en desarrollo |
| `dashboard-neuro-visor/src/components/EnergyLineChart/` | Gráfico actividad 7 días |
| `dashboard-neuro-visor/src/components/StackedBarChart/` | Categorías activo/dormido |
| `docs/dashboard-plan-panel-inspeccion-v2.md` | Plan detallado Vista 2 (Inspector IDE) |
| `README.md` | Documentación completa del motor (1275 líneas) |

---

## 14. PRÓXIMOS PASOS INMEDIATOS

1. **Leer `docs/dashboard-plan-panel-inspeccion-v2.md`** — plan completo Vista 2
2. **Decidir librería 3D:** `3d-force-graph` vs `react-force-graph-3d` vs `graphology` + `sigma.js`
3. **Implementar Vista 1 completa** (ya está al 90% en `CortezaPage.tsx`)
4. **Crear endpoint `/api/nodo/{id}/ego?hops=1`** para ego-graph limpio
5. **Migrar `ExplorarPage` a layout 3 columnas** (eliminar force-graph actual)

---

**Documento generado:** Julio 2026  
**Para:** Dennys J. Márquez — Creador de BioRAG  
**Por:** Athena-OEC (Estrategia/Arquitectura) + Artemis-OEC (Hardware/Optimización)  
**Ubicación:** `/mnt/recursos_compartidos_y_otros/MemoryBioRAG/docs/dashboard-neuro-visor-completo.md`