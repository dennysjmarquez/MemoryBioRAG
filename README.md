# BioRAG: Sistema de Memoria Cognitiva Biomimética para Agentes de IA

**BioRAG** es un motor de memoria persistente para agentes de inteligencia artificial. Resuelve el problema fundamental de que los LLMs olvidan todo entre sesiones — sin depender de vectores, embeddings ni infraestructura externa. **El sistema emula de forma nativa el comportamiento y las capacidades de una base de datos vectorial** a través de topología de grafos y lógica relacional, eliminando la necesidad de modelos de embedding costosos o servidores dedicados.

Desarrollado en **Python puro con SQLite + FTS5**. Cero dependencias de librerías ML (ni numpy, ni sentence-transformers, ni redes vectoriales). Corre en cualquier lado.

Emula la biología del cerebro humano: **plasticidad sináptica (LTP/LTD)**, **familiaridad difusa**, **inhibición lateral** y **propagación asociativa de recuerdos**. El motor de búsqueda combina coincidencia textual, peso biológico y conectividad del grafo en un score híbrido.

---

## La Estrella: Ráfaga de Reminiscencia

**El logro más importante de BioRAG es que el sistema "intenta recordar" como un cerebro humano.**

Cuando no encuentras algo, no te rindes — empiezas a "tirar flechas" con palabras relacionadas hasta que una conecta. BioRAG hace exactamente eso:

```
  Usuario pregunta algo vago o abstracto
          │
          ▼
  El LLM interpreta la intención y genera una RÁFAGA
  de 10-15 palabras relacionadas (sinónimos, conceptos,
  analogías, palabras del mismo dominio)
          │
          ▼
  El script busca con CADA palabra de la ráfaga en SQLite
  (tanto nodos activos como dormidos)
          │
          ├─ Si encuentra un nodo dormido → lo DESPIERTA
          ├─ Si encuentra un match → crea SINAPSIS permanente
  │  entre la palabra de la ráfaga y el nodo encontrado
          │
          ▼
  El agente LEE el contenido del nodo encontrado y
  EXPLICA al usuario con sus propias palabras qué encontró
```

**¿Por qué esto es revolucionario?**

| Antes (RAG tradicional) | Ahora (BioRAG con Ráfaga) |
|---|---|
| Si no hay match exacto → "0 resultados" | El LLM "tira flechas" con palabras relacionadas |
| El script busca a ciegas | El LLM interpreta y genera la ráfaga |
| Nodos dormidos se pierden | La ráfaga los despierta y crea sinapsis |
| El usuario debe saber los nombres exactos | El usuario pregunta de forma vaga/coloquial |
| "No encontré nada" | "No encontré X pero encontré Y que dice que..." |

**La clave:** La inteligencia está en el LLM (que genera la ráfaga), la ejecución está en el script (SQLite + FTS5). El usuario no necesita saber los nombres exactos de los archivos ni la jerga técnica. Puede preguntar de forma vaga, errónea o coloquial, y el sistema "adivina" la intención.

**Ejemplo genérico:**
- Usuario: "¿Dónde guardé lo del proyecto nuevo?"
- LLM genera ráfaga: ["proyecto", "código", "desarrollo", "repositorio", "commit", "rama", "branch"]
- Script busca → encuentra un nodo dormido sobre el proyecto
- El nodo se despierta, se crea sinapsis, y el agente responde con lo que encontró

**El sistema se auto-alimenta:** Cada búsqueda exitosa crea nuevas sinapsis. La próxima vez que busques algo similar, el camino ya está pavimentado. El grafo crece con cada uso.

---

## ¿Es BioRAG una alternativa a una base vectorial?

**Depende de para qué. Pero en su dominio, sí.**

Para el caso de uso de **memoria persistente de un agente**, BioRAG no solo es alternativa — es **superior** en estas dimensiones:

| Dimensión | Vector DB | BioRAG |
|---|---|---|
| Olvido selectivo | No existe | Decay_rate por categoría |
| Ciclo de vida | Insert → Query | Corto plazo → Sueño → Largo plazo → Olvido |
| Introspección | No | Métricas cognitivas + tendencias |
| Asociaciones explícitas | No (solo similitud) | Sinapsis con tipos y pesos |
| Autonomía | Depende de API | 0 dependencias externas |
| Tamaño | Gigabytes | ~4 MB |
| Portabilidad | Atado a infraestructura | Un archivo .db |
| **Ráfaga de reminiscencia** | **No** | **LLM genera 10-15 términos, script ejecuta** |
| **Auto-aprendizaje** | **No** | **Co-ocurrencia + sinapsis automáticas** |
| **Entiende metáforas** | **Depende del embedding** | **Glosario cultural + ráfaga** |
| **Rescata nodos dormidos** | **No** | **La ráfaga los despierta en caliente** |
| **Funciona offline** | **No** | **Sí** |
| **Costo por query** | **Miles de tokens** | **~15 tokens (ráfaga)** |

> **BioRAG no es una alternativa genérica a una vector DB. Es una alternativa específica para memoria de agente, y en ese dominio es mejor que cualquier vector DB.**

---

## Logros Técnicos (v8.0)

- **0 dependencias externas de ML**: ni numpy, ni vectores, ni GPU — SQLite puro con FTS5 trigram
- **Red sináptica de 1,177 aristas**: 161 nodos activos conectados por auto-linking biomimético + co-ocurrencia automática
- **1,562 equivalencias semánticas**: tesauro bidireccional auto-construido desde vocabulario cargado + sinónimos
- **Dynamic Multiplicator**: cuando FTS5 falla, Jaccard toma el control con fórmula 70/20/10
- **Co-ocurrencia automática en sueño**: el ciclo de sueño crea sinapsis basándose en co-ocurrencia de conceptos
- **Ráfaga de Reminiscencia**: `rafaga_palabras` en MCP — emula el proceso humano de "tirar flechas" para recordar
- **PALABRA_COMPLETA en todas las capas FTS5**: previene falsos positivos de trigram ("culo" ≠ "artículos")
- **Protocolo de 3 pasos**: enriquecimiento → ráfaga → contingencia (buscar en contexto del chat)
- **Glosario Cultural**: Principle en BioRAG con mapa de traducción de metáforas del usuario
- **Explicar con propias palabras**: el agente lee los resultados y redacta respuestas claras (no JSON crudo)
- **Similitud conceptual latente**: Jaccard sobre vecinos compartidos + tokens en contenido (60% red + 40% contenido)
- **Expansión semántica por tesauro**: tabla `semantica` bidireccional con auto-aprendizaje
- **Pipeline de búsqueda de 8 capas**: FTS5 AND → OR → Semántica → Conceptual → Snap → Cadena → Substring → Trigram
- **Decay diferenciado por categoría**: Profile=0.05, Principle=0.2, Project=1.5
- **Métricas cognitivas históricas**: tabla `metricas_cognitivas` con detección de tendencias
- **MCP nativo**: 16 herramientas para OpenCode, VS Code, Cursor, Cline, Antigravity, Claude Code
- **62 tests automatizados**: cobertura completa del motor, sinapsis, semántica, similitud y ráfaga

---

## Arquitectura Cerebral

El sistema funciona como un cerebro artificial dentro de un solo archivo SQLite (`MemoryBioRAG_Data/memory_biorag.db`). Emula de forma nativa el comportamiento de una base de datos vectorial a través de topología de grafos sinápticos y lógica relacional — sin embeddings, sin GPU, sin servidores externos.

### Flujo General: cómo entra y sale la información

```
  Un agente de IA (Athena, Artemis o Hermes) interactúa con BioRAG
  a través de dos operaciones fundamentales:

                       ┌──────────────────────┐
                       │ AGENTE DE IA (entrada)│
                       └─────┬──────────┬─────┘
                             │          │
                        GUARDAR        BUSCAR
                             │          │
                             ▼          ▼
                ┌────────────────┐ ┌──────────────────┐
                │  Interceptor   │ │  Pipeline de     │
                │  Filtro que    │ │  Búsqueda con    │
                │  detecta qué   │ │  8 capas +       │
                │  vale guardar  │ │  Ráfaga          │
                └───────┬────────┘ └────────┬─────────┘
                        │                   │
                        ▼                   │
              ┌──────────────────┐          │
              │  CORTO PLAZO     │          │ Cada búsqueda
              │  Mesa de trabajo │          │ exitosa refuerza
              │  temporal        │          │ el recuerdo
              └────────┬─────────┘          │ encontrado (LTP)
                       │                    │
                 Ciclo de Sueño             │
                 (consolidación +           │
                  co-ocurrencia)            │
                       │                    │
                       ▼                    ▼
              ┌───────────────────────────────────┐
              │        LARGO PLAZO (corteza)       │
              │                                    │
              │  La memoria permanente. Aquí viven │
              │  todos los recuerdos consolidados  │
              │  con su peso, categoría y          │
              │  conexiones a otros recuerdos.     │
              └───────┬────────────────┬───────────┘
                      │                │
                      ▼                ▼
            ┌────────────────┐  ┌─────────────────┐
            │ RED DE          │  │ TESAURO          │
            │ CONEXIONES      │  │ SEMÁNTICO        │
            │                 │  │                  │
            │ 1,177 aristas   │  │ 1,562 pares      │
            │ (auto + co-     │  │ de equivalencias │
            │  ocurrencia)    │  │ (auto + manual)  │
            └────────────────┘  └─────────────────┘
```

### Pipeline de Búsqueda: cómo encuentra recuerdos

Cuando un agente busca algo, BioRAG intenta encontrarlo con 8 estrategias
progresivas. Si la primera no da resultados, pasa a la siguiente:

```
  Agente pregunta: "días relax frente al océano"
          │
          ▼
  CAPA 1: Búsqueda exacta (FTS5 AND + PALABRA_COMPLETA)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 2: Búsqueda flexible (FTS5 OR)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 3: Expansión semántica (tesauro: "auto" → "vehículo")
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 4: Similitud conceptual (Jaccard vecinos compartidos)
          │ Encontró? ── Sí ──► Resultados (Dynamic Multiplicator)
          │
          No
          ▼
  CAPA 5: Snap reciente (últimos 7 días)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 6: Evocación por cadena (multi-hop 3 saltos)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 7: Substring (PALABRA_COMPLETA filtra falsos positivos)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 8: Trigram tolerance (typo ≥6 chars, PC solo ≤5 chars)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  RÁFAGA DE REMINISCENCIA (si el agente usa rafaga_palabras)
          │ "Tira flechas" con 10-15 términos relacionados
          │ Encuentra nodos dormidos, los despierta
          │ Crea sinapsis automáticamente
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CONTINGENCIA: Agente busca en contexto del chat
          │ Si encuentra → guarda con biorag_guardar
          │ Si no → responde "no tengo ese recuerdo"
```

### Dynamic Multiplicator:-score adaptativo

Cuando la búsqueda literal falla y la similitud conceptual (Jaccard) encuentra resultados, el score se recalcula dinámicamente:

```
  Score normal:    60% BM25 + 25% peso sináptico + 15% asociaciones
  Score latente:   70% Jaccard + 20% peso sináptico + 10% asociaciones

  Se activa cuando:
  - FTS5 no encontró el nodo (búsqueda literal falló)
  - Jaccard ≥ 0.15 (similitud conceptual mínima)
  - El nodo viene de capas 1.5, 1.7 o 1.9 (semánticas)
```

### Ráfaga de Reminiscencia: cómo el sistema "intenta recordar"

Emula el proceso humano de "tirar flechas" cuando no recuerdas algo:

```
  Usuario: "¿Dónde pasé mis días de relax frente al océano?"
          │
          ▼
  Búsqueda normal: "días relax frente al océano"
          │ Resultados: solo nodos técnicos (no personales)
          │
          ▼
  Agente activa RÁFAGA: ["playa","mar","costa","verano","descanso",
                          "sol","arena","olas","hotel","viaje"]
          │
          ▼
  Script busca con cada palabra (activos + dormidos)
          │
          ├─ "playa" → encuentra hermes_oec_identidad (dormido)
          │  "Yo fui para la playa en el verano pasado..."
          │
          ├─ "mar" → encuentra más nodos relacionados
          │
          ├─ "verano" → encuentra más nodos
          │
          ▼
  Auto-despertar: hermes_oec_identidad pasa a "activo"
  Auto-sinapsis: playa → hermes_oec_identidad (peso: 0.6)
  Auto-sinapsis: mar → hermes_oec_identidad (peso: 0.6)
          │
          ▼
  Agente lee el contenido y EXPlica al usuario:
  "Encontré que fuiste a la playa en el verano pasado.
   Disfrutaste del sol, la arena y las olas del mar."
```

### PALABRA_COMPLETA: word boundary en DB

FTS5 trigram matchea substrings de 3+ chars. PALABRA_COMPLETA evita falsos positivos:

```
  Sin filtro:    "culo" matchea "artículos" (comparte trigrama "cul")
  Con filtro:    "culo" NO matchea "artículos" (\bculo\b = word boundary)

  Aplicado en: Fallback 1.0, 1.7 (puentes), 1.8 (snap), 1.9 (semillas),
               2.5 (solo palabras ≤5 chars — preserva tolerancia a typos)
```

### Ciclo de Sueño: cómo el cerebro se mantiene sano

```
  1. CONSOLIDAR ─── Mover de corto a largo plazo (+0.20)
  2. CO-OCURRENCIA ─── Crear sinapsis entre conceptos que co-ocurren
  3. CONECTAR ───── Auto-linking por solapamiento de tokens
  4. DEBILITAR ──── LTD: -0.05 × velocidad según categoría
  5. DORMIR ─────── Recuerdos débiles (≤0.05) pasan a dormido
  6. EQUILIBRAR ─── Inhibición lateral (límite: n_activos × 1.6)
  7. REGISTRAR ──── Métricas cognitivas del ciclo
  8. PODAR ──────── (opcional) Borrar nodos dormidos con peso ≤0.01
```

### Protocolo de 3 pasos (MCP)

El agente sigue este flujo obligatorio al buscar:

```
  PASO 1: biorag_buscar(query="frase del usuario")
          Si es abstracta → interpretar + agregar 3-5 palabras clave

  PASO 2: Si PASO 1 da 0 resultados
          biorag_buscar(query="...", rafaga_palabras=[10-15 términos])

  PASO 3: Si PASO 2 da 0 resultados o puro ruido
          Buscar en contexto del chat → guardar con biorag_guardar

  DESPUÉS DE CADA PASO: Leer resultados y explicar con propias palabras
```

---

## Versiones Destacadas

### v8.0 — Ráfaga de Reminiscencia, Dynamic Multiplicator y Protocolo de 3 Pasos (Junio 2026)

**La mayor evolución de BioRAG: el sistema ahora "intenta recordar" como un cerebro humano.**

#### Nuevos componentes:
- **`buscar_por_rafaga()`** en `memory_store.py`: búsqueda por ráfaga de reminiscencia. Cuando la búsqueda normal falla, el agente "tira flechas" con 10-15 términos relacionados. El script busca con cada palabra (activos + dormidos), despierta nodos encontrados y crea sinapsis automáticamente.
- **`_auto_generar_co_ocurrencia()`** en `memory_store.py`: crea sinapsis automáticamente durante el ciclo de sueño basándose en co-ocurrencia de conceptos en `corto_plazo` y `comunicaciones`.
- **`rafaga_palabras`** parámetro en `biorag_buscar` MCP: lista de términos relacionados que el agente inyecta para la búsqueda de reminiscencia.
- **`contingencia_contexto`** señal en respuesta MCP: cuando no hay resultados, el tool indica al agente que busque en su contexto de conversación.
- **Dynamic Multiplicator** en `_calcular_score_hibrido()`: cuando FTS5 falla y Jaccard ≥ 0.15, cambia la fórmula de scoring a 70/20/10 (Jaccard/peso/asoc) en lugar de 60/25/15.

#### Mejoras al pipeline:
- **PALABRA_COMPLETA en todas las capas FTS5**: capas 1.0, 1.7 (puentes), 1.8 (snap), 1.9 (semillas) ahora filtran con word boundary en SQL.
- **PALABRA_COMPLETA incluye sinonimos**: `COALESCE(l.sinonimos, '')` en el WHERE preserva la búsqueda por sinónimo.
- **PALABRA_COMPLETA diferenciada en 2.5**: solo aplica a palabras ≤5 chars (preserva tolerancia a typos en palabras largas).
- **Co-ocurrencia en sueño**: el ciclo de sueño ahora crea sinapsis basándose en pares de conceptos que co-ocurren en la misma sesión.

#### Protocolo MCP:
- **Descripción de `biorag_buscar`** actualizada con protocolo de 3 pasos: enriquecimiento → ráfaga → contingencia.
- **`prompts.py` REGLA #1** actualizada: flujo de 3 pasos + "explicar con propias palabras".
- **Glosario Cultural**: Principle en BioRAG con mapa de traducción de metáforas del usuario.
- **Protocolo de enriquecimiento**: Principle en BioRAG con directiva de búsqueda cognitiva.

#### Producción:
- 161 nodos activos, 17 dormidos, 1,177 sinapsis, 1,562 equivalencias
- 62 tests automatizados (sin regressiones)
- 0 dependencias externas

### v7.1 — PALABRA_COMPLETA, Similitud Conceptual y Expansión Semántica (Junio 2026)

- **`core/similitud_conceptual.py`** (módulo nuevo): Jaccard vecinos + contenido, score 60/40, umbral 0.10
- **`core/semantica.py`** (módulo nuevo): tesauro bidireccional + auto-aprendizaje, 1,562 equivalencias
- **PALABRA_COMPLETA SQLite function**: word boundary en SQL, previene "culo" → "artículos"
- **Pipeline de 8 capas**: FTS5 AND → OR → Semántica → Conceptual → Snap → Cadena → Substring → Trigram
- **Decay diferenciado**: Profile=0.05, Principle=0.2, Project=1.5
- **Métricas cognitivas**: tabla `metricas_cognitivas` + tool `biorag_metricas_historial`
- **62 tests automatizados**
- **Production**: 47 nodos activos, 451 sinapsis, 1,172 equivalencias

### v6.0 — Estandarización de Categorías e Instalador Multiplataforma (Junio 2026)

- **Esquema de categorías unificado**: 11 categorías madre predefinidas
- **Instalador multiplataforma**: `install.py` configura BioRAG en 7 plataformas
- **Base de sincronización incremental**: tabla `sync_log` + triggers selectivos
- **Nuevas herramientas MCP**: `biorag_listar_categorias`, `biorag_sync_status`, `biorag_export_sync`, `biorag_export_full`

### v5.1 — Optimizaciones de Motor (Junio 2026)

- **Truncado en el motor**: `preview_chars` ahorra RAM
- **Evicción condicional**: `BIORAG_PODAR=true` borra nodos dormidos con peso ≤0.01
- **FTS5 pre-filter en auto_vincular**: usa FTS5 MATCH para pre-filtrar candidatos

### v5.0 — Sinapsis y Red Semántica (Junio 2026)

- **Auto-linking al guardar**: overlap coefficient crea aristas automáticamente
- **Tabla `sinapsis` persistente**: aristas con tipos y pesos
- **`buscar_vecinos()`**: navegación del grafo
- **Categorización automática**: inferencia por palabras clave

### v4.0 — Interceptor V2 (Junio 2026)

- **Buffer de sesión con TTL**: autoguardado heurístico
- **Consolidación inmediata**: sin necesidad de `biorag_sueno`
- **Heurísticas biomiméticas**: detección de 30+ patrones léxicos

### v3.0 — MCP Server (Junio 2026)

- **Servidor MCP**: 16 herramientas nativas para IDEs
- **Resources MCP**: acceso directo a nodos
- **Prompt MCP**: system prompt inyectable

### v2.x — Cimientos (Junio 2026)

- **FTS5 trigram**: tolerancia a typos
- **Score híbrido**: BM25 + peso sináptico + asociaciones
- **Pipeline de búsqueda multi-capa**
- **LTP/LTD**: plasticidad sináptica

---

## BioRAG vs. Bases de Datos Vectoriales

| Capacidad | Base de Datos Vectorial | BioRAG |
|---|---|---|
| **Similitud semántica** | Embeddings (768-1536 dims) | Jaccard + co-ocurrencia + ráfaga |
| **Tolerancia a typos** | Depende del modelo | FTS5 trigram nativo |
| **Expansión de queries** | Embeddings implícitos | Tesauro explícito + ráfaga del agente |
| **Ranking** | Distancia coseno | Score híbrido + Dynamic Multiplicator |
| **Dependencias** | numpy, sentence-transformers, GPU | Cero. SQLite puro |
| **Latencia** | 10-100ms | 0.08-0.19ms |
| **Memoria adaptativa** | Estática | Dinámica: LTP/LTD, co-ocurrencia, ráfaga |
| **Auto-aprendizaje** | No | Co-ocurrencia + sinapsis automáticas |
| **Entiende metáforas** | Depende del embedding | Glosario cultural + ráfaga |
| **Funciona offline** | No | Sí |

---

## Estructura del Proyecto

```
MemoryBioRAG/
  ├── biorag.py                 # CLI bridge (buscar, guardar, asociar, sueno, corteza, comunicar)
  ├── mcp_server.py             # Servidor MCP: 16 herramientas + ráfaga + contingencia
  ├── install.py                # Instalador cross-platform para 7 plataformas
  ├── sleep_cycle.py            # Script autónomo de consolidación/sueño
  ├── requirements.txt          # Dependencias: mcp (servidor MCP)
  ├── vocabulario_inicial.json  # 239 términos del dominio para expansión semántica
  ├── core/
  │    ├── memory_store.py      # Motor: LTP/LTD, 8 capas, Dynamic Multiplicator,
  │    │                        #   co-ocurrencia, ráfaga, PALABRA_COMPLETA
  │    ├── sinapsis.py          # Grafo: auto-linking, overlap coefficient, decay
  │    ├── semantica.py         # Tesauro: bidireccional, auto-aprendizaje
  │    ├── similitud_conceptual.py  # Jaccard vecinos + contenido, score 60/40
  │    └── categorizador.py     # Inferencia de categoría por palabras clave
  ├── middleware/
  │    ├── __init__.py
  │    ├── interceptor.py       # Escaneo de familiaridad difusa
  │    └── auto_guardado.py     # Buffer de sesión + autoguardado heurístico
  ├── config/
  │    ├── __init__.py
  │    └── prompts.py           # System prompts con protocolo de 3 pasos
  ├── scripts/
  │    ├── export_architecture.py  # Exporta blueprint completo de la DB
  │    ├── migrar_sinapsis.py     # Migración de CSV legacy a tabla sinapsis
  │    └── migrar_sinonimos_v2.0.py
  ├── MemoryBioRAG_Data/        # Bases de datos SQLite (auto-creado)
  ├── db_architecture_export.txt  # Blueprint generado
  ├── test_memory.py            # 62 tests automatizados
  └── README.md                 # Este archivo
```

---

## Servidor MCP (Model Context Protocol)

BioRAG expone una corteza cerebral compartida via MCP para que cualquier IDE o agente compatible se conecte directamente a la memoria sin ejecutar comandos shell.

### Herramientas MCP

| Herramienta | Descripcion |
|---|---|
| `biorag_buscar` | Búsqueda híbrida + ráfaga + contingencia. Params: `query`, `rafaga_palabras`, `cat`, `deep`, `completo`, `asociados` |
| `biorag_guardar` | Guardar recuerdo en corto plazo. Params: `concepto`, `contenido`, `syn`, `cat` |
| `biorag_asociar` | Sinapsis bidireccional entre conceptos |
| `biorag_comunicar` | Enviar mensaje inter-agente (athena, artemis, hermes, todos) |
| `biorag_leer_mensajes` | Leer canal compartido (auto-marca leidos) |
| `biorag_sueno` | Consolidar + co-ocurrencia + métricas |
| `biorag_estado` | Stats de la corteza (activos, dormidos, energia, sinapsis) |
| `biorag_corteza` | Listar todos los nodos de la corteza |
| `biorag_contexto_inicio` | Anunciar inicio de interacción |
| `biorag_contexto_fin` | Finalizar + auto-sueño automático |
| `biorag_metricas_historial` | Últimos N ciclos de sueño con tendencias |
| `biorag_semantica_admin` | CRUD tabla semántica |
| `biorag_listar_categorias` | Lista las 11 categorías madre |
| `biorag_sync_status` | Categorías pendientes de sync a NotebookLM |
| `biorag_export_sync` | Exporta categorías pendientes |
| `biorag_export_full` | Export completo |

### Protocolo de 3 pasos en `biorag_buscar`

```python
# PASO 1: Búsqueda con interpretación
biorag_buscar(query="días relax frente al océano playa vacaciones")

# PASO 2: Si falla, ráfaga de términos relacionados
biorag_buscar(
    query="días relax frente al océano",
    rafaga_palabras=["playa","mar","costa","verano","descanso","sol","arena","olas"]
)

# PASO 3: Si todo falla, contingencia_contexto=True
# → El agente busca en su contexto de conversación
# → Si encuentra, guarda con biorag_guardar
```

---

## Variables de entorno (opcionales)

```bash
# Ruta personalizada a la base de datos
export BIORAG_PATH=~/biorag/MemoryBioRAG_Data/memoria.db

# Nombre del agente para comunicaciones inter-agente
export AGENT_NAME=athena

# Activar poda automática (peligro: nodos borrados se guardan en backup)
export BIORAG_PODAR=true
```

---

## Producción (v8.0)

| Métrica | Valor |
|---|---|
| Nodos activos | 161 |
| Nodos dormidos | 17 |
| Sinapsis | 1,177 |
| Equivalencias | 1,562 |
| Tests | 62/62 pasando |
| Dependencias externas | 0 |
| Tamaño DB | ~4 MB |

---

## Licencia

MIT — Dennys J. Marquez (dennysjmarquez@gmail.com)
