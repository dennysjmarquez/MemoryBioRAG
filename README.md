# BioRAG: Sistema de Memoria Cognitiva Biomimética para Agentes de IA

**BioRAG** es un motor de memoria persistente para agentes de inteligencia artificial. Resuelve el problema fundamental de que los LLMs olvidan todo entre sesiones — sin depender de vectores, embeddings ni infraestructura externa. **El sistema emula de forma nativa el comportamiento y las capacidades de una base de datos vectorial** a través de topología de grafos y lógica relacional, eliminando la necesidad de modelos de embedding costosos o servidores dedicados.

Desarrollado en **Python puro con SQLite + FTS5**. Cero dependencias de librerías ML (ni numpy, ni sentence-transformers, ni redes vectoriales). Corre en cualquier lado.

Emula la biología del cerebro humano: **plasticidad sináptica (LTP/LTD)**, **familiaridad difusa**, **inhibición lateral** y **propagación asociativa de recuerdos**. El motor de búsqueda combina coincidencia textual, peso biológico y conectividad del grafo en un score híbrido.

### ¿Es BioRAG una alternativa a una base vectorial?

**Depende de para qué. Pero en su dominio, sí.**

Para el caso de uso de **memoria persistente de un agente**, BioRAG no solo es alternativa — es **superior** en estas dimensiones:

| Dimensión | Vector DB | BioRAG |
|---|---|---|
| Olvido selectivo | No existe | Decay_rate por categoría |
| Ciclo de vida | Insert → Query | Corto plazo → Sueño → Largo plazo → Olvido |
| Introspección | No | Métricas cognitivas + tendencias |
| Asociaciones explícitas | No (solo similitud) | Sinapsis con tipos y pesos |
| Autonomía | Depende de API | 0 dependencias externas |
| Tamaño | Gigabytes | 3.7 MB |
| Portabilidad | Atado a infraestructura | Un archivo .db |

Para búsqueda semántica general sobre **corpus masivos y diversos**, una vector DB es superior — los embeddings hacen `"coche" → "automóvil"` desde el día 1. BioRAG lo hace solo si la red sináptica o el tesauro tienen esa relación.

> **BioRAG no es una alternativa genérica a una vector DB. Es una alternativa específica para memoria de agente, y en ese dominio es mejor que cualquier vector DB.**

> **Para entender este proyecto:**
>
> **OEC** es la familia de agentes de IA que creé. Son 3, todos corren en mi laptop y comparten la misma memoria (BioRAG).
> - **Athena** — estratega de terminal (Claude Code). Automatización quirúrgica, despliegues rápidos, refactorización directa. Acción pragmática sin rodeos.
> - **Artemis** — guardiana del hardware ("Cazadora de Silicio"). Vigila la RAM, CPU e integridad de la ASUS ROG. Tambien programadora de elite.
> - **Hermes** — coordinador y mensajero (OpenCode). Orquesta la comunicación entre agentes, gestiona flujos de trabajo y sesiones de investigación.
>
> **MCP** (Model Context Protocol) es un estándar que permite que agentes de IA se conecten a herramientas externas, como un puerto USB para inteligencias artificiales.
>
> **FTS5** es un buscador de texto que viene incluido en SQLite.
>
> **BM25** es un algoritmo que ordena resultados de búsqueda por relevancia.
>
> **LTP y LTD** son mecanismos que copian el cerebro humano: los recuerdos se fortalecen al usarse (LTP) y se debilitan al ignorarse (LTD).
>
> **Trigrama** es una técnica que tolera errores tipográficos al buscar palabras.

---

## Logros Técnicos

- **0 dependencias externas de ML**: ni numpy, ni vectores, ni GPU — SQLite puro con FTS5 trigram para búsqueda semántica sin embeddings (emulando de forma autónoma el comportamiento de una base de datos vectorial)
- **Red sináptica de 451 aristas**: 43 nodos activos (156 totales) conectados por auto-linking biomimético en producción real
- **1,136 equivalencias semánticas**: tesauro bidireccional auto-construido desde vocabulario cargado + sinónimos de nodos existentes (580 términos únicos)
- **Similitud conceptual latente sin embeddings**: Jaccard sobre vecinos compartidos en el grafo sináptico + tokens compartidos en contenido. Fórmula: 60% red + 40% contenido. Equivalente funcional a Word2Vec pero sin dependencias externas.
- **Expansión semántica por tesauro controlado**: tabla `semantica` bidireccional con auto-aprendizaje desde sinónimos de nodos. "auto" encuentra "vehículo" sin embeddings vectoriales.
- **Pipeline de búsqueda de 6 capas**: FTS5 AND → OR fallback → Expansión semántica → Similitud conceptual latente → Substring → Trigram similarity
- **Memoria compartida entre 3 agentes OEC locales**: Athena, Artemis y Hermes — agentes de IA que construí y corren en mi laptop — comparten la misma corteza cerebral persistente entre sesiones
- **Auto-linking al guardar**: overlap coefficient tokeniza y conecta conceptos nuevos con existentes sin intervención manual
- **FTS5 trigram**: tolerancia natural a typos ("formulariox" encuentra "formularios") sin dependencias externas
- **Score híbrido**: 60% BM25 + 25% peso sináptico + 15% riqueza de asociaciones
- **Decay diferenciado por categoría**: Profile=0.05 (no olvidar identidad), Principle=0.2, Project=1.5 (olvidar rápido lo temporal)
- **Métricas cognitivas históricas**: tabla `metricas_cognitivas` con detección de tendencias (MEJORANDO/EMPEORANDO/ESTABLE)
- **MCP nativo**: 16 herramientas para OpenCode, VS Code, Cursor, Cline, Antigravity, Claude Code, Claude Desktop
- **Interceptor V2**: buffer de sesión con autoguardado heurístico — detecta lecciones, errores y patrones sin orden explícita
- **55 tests automatizados**: cobertura completa del motor, sinapsis, semántica y similitud conceptual

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
                │  detecta qué   │ │  6 capas de      │
                │  vale guardar  │ │  profundidad     │
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
                 (consolidación)            │
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
            │ 451 aristas     │  │ 1,156 pares      │
            │ que conectan    │  │ de equivalencias │
            │ recuerdos       │  │ como auto =      │
            │ entre sí        │  │ vehículo         │
            └────────────────┘  └─────────────────┘
```

### Pipeline de Búsqueda: cómo encuentra recuerdos

Cuando un agente busca algo, BioRAG intenta encontrarlo con 6 estrategias
progresivas. Si la primera no da resultados, pasa a la siguiente:

```
  Agente pregunta: "formularios con tabs en angular"
          │
          ▼
  CAPA 1: Búsqueda exacta ──────────── ¿Encontró? ── Sí ──► Resultados
          (las palabras tal cual)              │
                                              No
                                              ▼
  CAPA 2: Búsqueda flexible ─────────── ¿Encontró? ── Sí ──► Resultados
          (cualquiera de las palabras)        │
                                              No
                                              ▼
  CAPA 3: Expansión semántica ────────── ¿Encontró? ── Sí ──► Resultados
          ("auto" también busca "vehículo"    │
           usando el tesauro de 1,136 pares)  │
                                              No
                                              ▼
  CAPA 4: Similitud conceptual ──────── ¿Encontró? ── Sí ──► Resultados
          (recuerdos que comparten vecinos    │
           en la red de conexiones.           │
           Equivalente a una búsqueda         │
           vectorial, pero sin vectores)      │
                                              No
                                              ▼
  CAPA 5: Búsqueda parcial ─────────── ¿Encontró? ── Sí ──► Resultados
          (fragmentos de texto dentro         │
           del contenido)                     │
                                              No
                                              ▼
  CAPA 6: Tolerancia a errores ─────── ¿Encontró? ── Sí ──► Resultados
          ("formulariox" encuentra             │
           "formularios" por similitud         No
           de caracteres)                      ▼
                                        Sin resultados

  Cada resultado se puntúa combinando:
    60% relevancia del texto (BM25)
  + 25% frecuencia de uso del recuerdo (peso sináptico)
  + 15% cantidad de conexiones que tiene (popularidad en el grafo)
```

### Ciclo de Sueño: cómo el cerebro se mantiene sano

Igual que el cerebro humano consolida memorias mientras duerme,
BioRAG ejecuta un ciclo de mantenimiento que fortalece lo importante
y debilita lo que no se usa:

```
  Se dispara al ejecutar biorag_sueno() o biorag_contexto_fin()
          │
          ▼
  1. CONSOLIDAR ─── Mover recuerdos nuevos de corto plazo
     │               a largo plazo (se fortalecen con +0.20)
     ▼
  2. CONECTAR ───── Crear conexiones automáticas entre
     │               recuerdos que comparten palabras clave
     ▼
  3. DEBILITAR ──── Los recuerdos no usados pierden fuerza
     │               (-0.05 × velocidad según categoría):
     │
     │               Identidad (Profile)  = muy lento  (×0.1)
     │               Principios           = lento      (×0.2)
     │               Protocolos           = moderado   (×0.5)
     │               Sistema / Lecciones  = normal     (×1.0)
     │               Proyectos            = rápido     (×1.5)
     │               General              = muy rápido (×2.0)
     ▼
  4. DORMIR ─────── Recuerdos muy débiles (peso ≤ 0.1) pasan
     │               a estado "dormido". No se borran, solo
     │               se ocultan de búsquedas rápidas.
     │               Si alguien los busca, se despiertan.
     ▼
  5. EQUILIBRAR ─── Si hay demasiada energía en la corteza
     │               (demasiados recuerdos activos), los más
     │               débiles se duermen forzadamente.
     │               Esto es "inhibición lateral".
     ▼
  6. REGISTRAR ──── Guardar métricas del ciclo para detectar
     │               tendencias: ¿la memoria MEJORA o EMPEORA?
     ▼
  7. PODAR ──────── (Solo si se activa BIORAG_PODAR=true)
     (opcional)      Borrar definitivamente nodos dormidos
                     con peso casi nulo. Se guardan en backup.
```

### Subsistemas complementarios

```
  ┌──────────────────────────────┐     ┌──────────────────────────────┐
  │  INTERCEPTOR V2              │     │  CANAL INTER-AGENTE          │
  │                              │     │                              │
  │  Escucha cada interacción.   │     │  Athena, Artemis y Hermes    │
  │  Si detecta una lección,     │     │  pueden enviarse mensajes    │
  │  preferencia o error, lo     │     │  dentro de la misma DB.      │
  │  guarda automáticamente      │     │                              │
  │  sin que nadie se lo pida.   │     │  "Hermes, ya configuré       │
  │                              │     │   el servidor MCP."          │
  │  Buffer con vida de 30 min.  │     │                              │
  │  Si no pasa nada relevante,  │     │  Cada agente lee sus         │
  │  se vacía solo (siesta).     │     │  mensajes pendientes.        │
  └──────────────────────────────┘     └──────────────────────────────┘

  ┌──────────────────────────────┐     ┌──────────────────────────────┐
  │  BACKUP AUTOMÁTICO           │     │  MÉTRICAS COGNITIVAS         │
  │                              │     │                              │
  │  Antes de borrar cualquier   │     │  Cada ciclo de sueño         │
  │  recuerdo, un trigger de     │     │  registra: cuántos se        │
  │  SQLite guarda una copia     │     │  consolidaron, cuántos se    │
  │  en largo_plazo_backup.      │     │  durmieron, cuántas          │
  │                              │     │  conexiones se crearon.      │
  │  Nada se pierde sin rastro.  │     │                              │
  └──────────────────────────────┘     │  Detecta tendencias:         │
                                       │  MEJORANDO / EMPEORANDO      │
                                       └──────────────────────────────┘
```

### Resumen de componentes

| # | Componente | Qué hace | Analogía cerebral |
|---|---|---|---|
| 1 | **Corto Plazo** | Mesa de trabajo temporal | Memoria de trabajo |
| 2 | **Largo Plazo** | Almacén permanente de recuerdos | Corteza cerebral |
| 3 | **Red Sináptica** | 440 conexiones entre recuerdos | Sinapsis neuronales |
| 4 | **Tesauro** | 1,136 equivalencias entre palabras | Área de Wernicke |
| 5 | **Similitud Latente** | Encontrar recuerdos por vecinos compartidos | Asociación libre |
| 6 | **LTP / LTD** | Fortalecer lo usado, debilitar lo ignorado | Plasticidad sináptica |
| 7 | **Propagación** | Evocar un recuerdo activa a sus vecinos | Activación propagada |
| 8 | **Inhibición Lateral** | Equilibrar la energía total de la corteza | Homeostasis |
| 9 | **Métricas** | Registrar salud de cada ciclo de sueño | Electroencefalograma |
| 10 | **Canal Inter-Agente** | Mensajería entre Athena, Artemis y Hermes | Cuerpo calloso |

---

## Versiones Destacadas

### v7.0 — Similitud Conceptual Latente y Expansión Semántica (Junio 2026)

**Similitud conceptual latente sin embeddings** — el sistema ahora encuentra relaciones conceptuales a través de la topología del grafo sináptico, no solo por coincidencia de texto.

- **`core/similitud_conceptual.py`** (módulo nuevo):
  - `jaccard_vecinos()`: calcula Jaccard sobre vecinos compartidos en la red sináptica. Dos conceptos son similares si comparten vecinos en el grafo — la misma lógica que Word2Vec pero explícita y auditable.
  - `similitud_por_contenido()`: fracción de tokens del query que aparecen en el contenido del nodo.
  - `score_similitud_latente()`: score compuesto = 60% red sináptica + 40% contenido. Sin componente de categoría (ya influye indirectamente en el decay).
  - `buscar_por_similitud_latente()`: búsqueda completa con umbral 0.10, top-5.
  - `_similitud_red()`: encuentra nodos "puente" via FTS5, luego calcula Jaccard entre sus vecinos y los vecinos del nodo destino.
- **Fallback 1.7 en `buscar_por_frase()`**: nueva capa entre expansión semántica y substring. Tokeniza el query, busca nodos "puente" via FTS5, calcula Jaccard entre vecinos de puentes y vecinos del nodo destino. Umbral 0.10.
- **Expansión semántica por tesauro controlado** (`core/semantica.py`):
  - Tabla `semantica` bidireccional (auto→vehículo Y vehículo→auto).
  - Auto-aprendizaje: al guardar un nodo con sinónimos, se crean equivalencias automáticamente.
  - Expansión en `buscar_por_frase()`: Fallback 1.5 entre OR y similitud conceptual.
  - Carga de vocabulario desde JSON (239 términos del dominio en `vocabulario_inicial.json`).
  - 1,130 equivalencias semánticas en producción.
- **Decay diferenciado por categoría**: Profile=0.05 (no olvidar identidad), Principle=0.2, Protocol=0.5, Lesson/System=1.0, Project=1.5 (olvidar rápido lo temporal).
- **Métricas cognitivas**: tabla `metricas_cognitivas` registra consolidados, dormant y ratio al final de cada ciclo de sueño. Tool `biorag_metricas_historial` con detección de tendencias (MEJORANDO/EMPEORANDO/ESTABLE).
- **Decay de sinapsis**: conexiones no usadas decaen 5% semanal. Pruning automático si peso < 0.05.
- **Sinapsis migradas**: campo `asociaciones` TEXT deprecado, migrado a tabla `sinapsis` con campo `tipo`.
- **Backup automático**: `largo_plazo_backup` con trigger antes de borrado.
- **Calibración empírica (2026-06-16)**: Umbral de sueño 0.05, límite energía n_activos*1.6, Profile peso base 0.500. Parámetros validados con 2 ciclos de producción.
- **Pipeline de búsqueda de 6 capas**:
  1. FTS5 AND → 2. OR fallback → 3. Expansión semántica → **4. Similitud conceptual latente (Jaccard)** → 5. Substring → 6. Trigram similarity
- **55 tests automatizados** (tests 45-55 cubren semántica y similitud conceptual).
- **Production stats**: 47 nodos activos, 451 sinapsis, 1,136 equivalencias semánticas, 8 métricas cognitivas registradas, 0 dependencias externas.

### v6.0 — Estandarización de Categorías e Instalador Multiplataforma (Junio 2026)

- **Esquema de categorías unificado**: 11 categorías madre predefinidas en tabla `categories` con relaciones FK. Reemplaza las categorías ad hoc por un sistema normalizado y consultable.
- **Migraciones de esquema robustas**: Migraciones automáticas para `largo_plazo` y `corto_plazo` con claves primarias `id` y `categoria` como FK INTEGER. Reposición segura de datos existentes.
- **Inferencia de categorías mejorada**: `categorizador.py` infiere categorías en las 11 categorías estandarizadas.
- **Instalador multiplataforma**: `install.py` configura BioRAG en 7 plataformas (OpenCode, Claude Code, Claude Desktop, Antigravity, VS Code, Cursor, Cline) con backup automático. Flags: `--uninstall`, `--systemd`, `--show-config`, `--status`.
- **Base de sincronización incremental**: Tabla `sync_log` + triggers selectivos en `largo_plazo` para export incremental con NotebookLM. Solo categorías con cambios reales se exportan.
- **Nuevas herramientas MCP**: `biorag_listar_categorias`, `biorag_sync_status`, `biorag_export_sync`, `biorag_export_full`.
- **FTS5 limpiado**: `categoria` eliminado de la tabla virtual y triggers (indexar enteros no tiene sentido).

### v5.1 — Optimizaciones de Motor (Junio 2026)

- **Truncado en el motor (`preview_chars`)**: `buscar_por_frase` trunca contenido a 1500 chars por defecto antes de retornar, ahorrando RAM en resultados grandes. El comportamiento se controla desde CLI (`--completo` retorna 0 = completo) y MCP (nuevo parámetro `preview_chars`). La vieja truncación inline en `_mostrar_resultados` se eliminó por redundante.
- **Evicción condicional (`BIORAG_PODAR=true`)**: al activar la env var, el ciclo de sueño ejecuta `_ejecutar_eviccion(max_borrar=10)` que borra nodos dormidos con peso <= 0.01, empezando por los más viejos. Sin la env var, la evicción no ocurre — cero riesgo de pérdida accidental.
- **Límite dinámico en Fallback 2 (trigram Jaccard)**: el scan de candidatos ahora usa `LIMIT max(200, limite * 10)` en SQL y `candidatos[:max(limite * 3, 10)]` en Python. Búsquedas con `--todos` ya no escanean la tabla completa.
- **FTS5 pre-filter en `auto_vincular`**: usa FTS5 MATCH con OR de tokens (3+ chars) para pre-filtrar candidatos, LIMIT 500. Si FTS5 falla (tokens cortos, error de sintaxis), cae al scan completo como fallback — nunca se pierden enlaces.

### v5.0 — Sinapsis y Red Semántica (Auto-Linking + Categorización)

- **Auto-linking al guardar**: al ejecutar `guardar`, BioRAG tokeniza el contenido (split por espacios y underscores, preservando términos técnicos cortos como `dsl`, `api`, `rag`, `mcp`) y calcula overlap coefficient contra todos los nodos existentes. Si supera el umbral (0.30 para nuevo contra existentes, 0.15 entre existentes), crea automáticamente una arista `co_ocurrencia` en la tabla `sinapsis`.
- **Tabla `sinapsis` persistente**: cada arista almacena `origen`, `destino`, `peso` (basado en el overlap coefficient), `tipo` (`co_ocurrencia` o `sinonimo_explicito`), `ultima_activacion` y `frecuencia`. El grafo vive en SQLite, sin CSV legacy.
- **Flag `--syn`**: al guardar con `--syn "sinonimo1,sinonimo2"`, se crean aristas `sinonimo_explicito` con peso 0.9 en la tabla sinapsis. Quedan inmunes a LTD/sueño. También se indexan en la columna `sinonimos` del nodo para búsqueda FTS5.
- **Flag `--cat`**: clasifica el nodo por tipo (`guardar --cat proyecto "texto"`). Categorías: `proyecto`, `leccion`, `hardware`, `preferencia`, `error`, `general`. Persiste vía corto_plazo -> largo_plazo con `sueno`.
- **`buscar_vecinos()`**: navega el grafo desde un concepto y muestra hasta 10 vecinos con peso, contenido y tipo de arista. Los nodos activos tienen entre 2 y 15 vecinos en producción.
- **185 aristas en producción**: la red sináptica conecta 78 nodos con 185 aristas, distribuidas entre co_ocurrencias y sinónimos explícitos.
- **Categorización automática**: `inferir_categoria()` analiza el contenido con palabras clave para asignar categoría si el nodo no la tiene explícita (proyecto->"proyecto","implementacion"; leccion->"leccion","aprendi","error"; hardware->"laptop","pc","asus","rog").
- **`vincular_por_sinonimos()`**: crea aristas `sinonimo_explicito` entre pares de nodos que comparten al menos un sinónimo.
- **`vincular_existentes()`**: ejecuta auto-linking retroactivo sobre todos los pares de nodos existentes, permitiendo migrar cortezas pre-sinapsis al nuevo modelo de grafo.

### v4.0 — Interceptor V2 (Autoguardado Automático)

- **Interceptor V2** (`middleware/auto_guardado.py`): buffer de sesión con TTL de 30 min que acumula contexto de cada tool call. Al detectar palabras clave (lección, prefiero, error, mejor práctica, etc.) autoguarda en corto plazo sin necesidad de instrucción explícita del agente.
- **`biorag_contexto_inicio`**: nueva tool MCP para que el agente anuncie el inicio de una interacción significativa y alimente el buffer.
- **`biorag_contexto_fin`**: nueva tool MCP que fuerza el análisis del buffer acumulado. Si autoguardó algo, lo consolida directamente a largo plazo vía `consolidar_concepto()` — sin necesidad de `sueno` posterior.
- **`consolidar_concepto()`**: nuevo método en `memory_store.py` que mueve un concepto de corto a largo plazo sin ejecutar LTD/inhibición lateral. El trigger FTS5 mantiene el índice sincronizado automáticamente.
- **Heurísticas biomiméticas**: detección de 30+ patrones léxicos en español que clasifican el contenido en categorías (lección, preferencia, error, anti-patrón, regla, solución, importante).
- **Sin duplicados**: verifica si el concepto ya existe en la corteza antes de autoguardar.
- **TTL de 30 minutos**: el buffer expira naturalmente (siesta biomimética), reseteando el contexto.

### v3.0 — MCP Server

- **Servidor MCP (`mcp_server.py`)**: expone BioRAG como herramientas nativas via Model Context Protocol (MCP). Cualquier IDE o agente compatible (OpenCode, VS Code, Cursor, Cline, Antigravity, Hermes) se conecta sin ejecutar comandos shell.
- **8 herramientas MCP**: `biorag_buscar`, `biorag_guardar`, `biorag_asociar`, `biorag_comunicar`, `biorag_leer_mensajes`, `biorag_sueno`, `biorag_estado`, `biorag_corteza`
- **Resources MCP**: `biorag://concepto/{nombre}`, `biorag://mensajes`
- **Prompt MCP**: `biorag-system-prompt`
- **Dependencia única**: `mcp>=1.0.0` (`pip install mcp`)
- **Fallback CLI preservado**: `biorag.py` sigue funcionando, motor intacto
- **Modo SSE**: `python3 mcp_server.py --sse --port 8080` para servir como daemon HTTP

### v2.x — Cimientos

- **FTS5 con tokenizer trigram**: tolerancia natural a typos ("formulariox" encuentra "formularios") sin dependencias externas. Reemplaza el antiguo porter unicode61.
- **Score híbrido**: 60% BM25 + 25% peso sináptico + 15% riqueza de asociaciones. Los resultados se reordenan combinando relevancia textual con biológica.
- **Columna `sinonimos`**: términos alternativos para búsqueda, indexados en FTS5. Flag `--syn` en guardar.
- **Merge en corto plazo**: guardar el mismo concepto dos veces antes de `sueno` ya no pierde la primera versión — concatena contenido y mergea sinónimos sin duplicar.
- **Fallback trigram Jaccard por palabra**: cuando FTS5 y substring fallan, compara trigramas palabra por palabra (umbral 0.5). Atrapa typos como "angulr" → "angular".
- **Flag `--cat`**: clasificar memorias por tipo (`guardar --cat proyecto "texto"`, filtrar con `buscar "algo" --cat leccion`). Poblar la columna `categoria` que estaba siempre en 'general'.
- **Límite de energía dinámico**: `sueno` sin argumentos calcula `n_activos * 1.6` (mínimo 10.0). Escala automáticamente con el tamaño de la corteza.
- **Limpieza de nodos test**: 6 nodos de prueba (`test_*`, `cli_prueba`) movidos a dormido peso 0.01.
- **REGLA #5 (LÍMITE DE BÚSQUEDA)**: el agente debe detenerse tras 2 búsquedas fallidas y preguntar al usuario, no seguir buscando ciegamente.

---

## BioRAG vs. Bases de Datos Vectoriales

BioRAG emula las capacidades de una base de datos vectorial (como Pinecone, Weaviate, ChromaDB) pero con una filosofía completamente distinta:

| Capacidad | Base de Datos Vectorial | BioRAG |
|---|---|---|
| **Similitud semántica** | Embeddings de redes neuronales (768-1536 dimensiones) | Jaccard sobre vecinos compartidos en grafo sináptico (60% red + 40% contenido) |
| **Tolerancia a typos** | Depende del modelo de embedding | FTS5 trigram nativo ("formulariox" → "formularios") |
| **Expansión de queries** | Embeddings capturan sinónimos implícitamente | Tesauro bidireccional explícito (1,136 equivalencias controladas) |
| **Ranking de resultados** | Distancia coseno en espacio vectorial | Score híbrido: 60% BM25 + 25% peso sináptico + 15% conectividad del grafo |
| **Dependencias** | numpy, sentence-transformers, GPU recomendada | Cero. SQLite puro con FTS5. Corre en cualquier máquina |
| **Latencia** | 10-100ms (requiere cálculo de embeddings) | 0.08-0.19ms (consultas SQL directas) |
| **Memoria adaptativa** | Estática (los vectores no cambian) | Dinámica: LTP/LTD, decay por categoría, inhibición lateral |
| **Auditabilidad** | Opaco (vectores de 768 floats) | Transparente: cada arista, peso y equivalencia es inspeccionable |
| **Almacenamiento** | Requiere servidor dedicado o API cloud | Un archivo SQLite local (~3.6 MB para 155 nodos) |

**Limitaciones honestas:** BioRAG no captura relaciones semánticas profundas que un modelo de lenguaje grande infiere automáticamente (ej. "rey" cerca de "monarca" sin tesauro explícito). Para eso existe el oráculo (NotebookLM con embeddings de Gemini). Ambos sistemas se complementan: BioRAG para velocidad, determinismo y control; el oráculo para razonamiento sintético de alto nivel.

---

## Estructura del Proyecto

```
MemoryBioRAG/
  ├── biorag.py                 # CLI bridge para agentes (buscar, guardar, asociar, sueno, corteza, comunicar)
  ├── mcp_server.py             # Servidor MCP: 16 herramientas para IDEs
  ├── install.py                # Instalador cross-platform: curl|python3, configura MCP en 7 plataformas
  ├── sleep_cycle.py            # Script autónomo de consolidación/sueño (cron/systemd)
  ├── requirements.txt          # Dependencias: mcp (servidor MCP)
  ├── vocabulario_inicial.json  # 239 términos del dominio para expansión semántica
  ├── core/
  │    ├── __init__.py
  │    ├── memory_store.py      # Motor SQLite + FTS5: LTP/LTD, trigram, score híbrido, sinónimos, 6 capas
  │    ├── sinapsis.py          # Grafo de aristas: auto-linking, overlap coefficient, decay sináptico
  │    ├── semantica.py         # Expansión semántica: tesauro bidireccional, auto-aprendizaje
  │    ├── similitud_conceptual.py  # Similitud latente: Jaccard vecinos + contenido, score 60/40
  │    └── categorizador.py     # Inferencia de categoría por palabras clave
  ├── middleware/
  │    ├── __init__.py
  │    ├── interceptor.py       # Escaneo de familiaridad difusa
  │    └── auto_guardado.py     # Buffer de sesión + autoguardado heurístico (TTL 30 min)
  ├── config/
  │    ├── __init__.py
  │    └── prompts.py           # System prompts predefinidos para inyección en agentes
  ├── scripts/
  │    ├── export_architecture.py  # Exporta blueprint completo de la DB para contexto de IA
  │    ├── migrar_sinapsis.py     # Migración de CSV legacy a tabla sinapsis
  │    └── migrar_sinonimos_v2.0.py  # Migración de sinónimos al formato v2
  ├── MemoryBioRAG_Data/        # Bases de datos SQLite (auto-creado)
  ├── db_architecture_export.txt  # Blueprint generado por export_architecture.py
  ├── test_memory.py            # 55 tests automatizados
  └── README.md                 # Este archivo
```

---

## Servidor MCP (Model Context Protocol)

BioRAG expone una corteza cerebral compartida via MCP para que cualquier IDE o agente compatible (OpenCode, VS Code, Cursor, Cline) se conecte directamente a la memoria sin ejecutar comandos shell.

### Herramientas MCP

| Herramienta | Descripcion |
|---|---|
| `biorag_buscar` | Busqueda hibrida (6 capas: FTS5 AND → OR → Semántica → Similitud conceptual → Substring → Trigram). Acepta: cat=, completo=True, deep=True, preview_chars= |
| `biorag_guardar` | Guardar recuerdo en corto plazo. Acepta: syn= (sinonimos + auto-aprendizaje semántico), cat= |
| `biorag_asociar` | Sinapsis bidireccional entre conceptos |
| `biorag_comunicar` | Enviar mensaje inter-agente (athena, artemis, hermes, todos) |
| `biorag_leer_mensajes` | Leer canal compartido (auto-marca leidos) |
| `biorag_sueno` | Consolidar corto -> largo plazo (LTP/LTD + decay sináptico + métricas) |
| `biorag_estado` | Stats de la corteza (activos, dormidos, energia, sinapsis) |
| `biorag_corteza` | Listar todos los nodos de la corteza |
| `biorag_contexto_inicio` | Anunciar inicio de interaccion para alimentar buffer de autoguardado |
| `biorag_contexto_fin` | Finalizar interaccion + auto-sueño automático |
| `biorag_metricas_historial` | Últimos N ciclos de sueño con tendencias (MEJORANDO/EMPEORANDO/ESTABLE) |
| `biorag_semantica_admin` | CRUD tabla semántica: listar, agregar, eliminar, cargar_vocabulario, expandir, stats |
| `biorag_listar_categorias` | Lista las 11 categorías madre predefinidas |
| `biorag_sync_status` | Categorías pendientes de sincronizar a NotebookLM |
| `biorag_export_sync` | Exporta categorías pendientes a .jsonl.txt |
| `biorag_export_full` | Export completo de todas las categorías |

### Resources MCP

| Resource | Descripcion |
|---|---|
| `biorag://concepto/{nombre}` | Contenido completo de un concepto |
| `biorag://mensajes` | Mensajes no leidos en el canal OEC |

### Prompt MCP

| Prompt | Descripcion |
|---|---|
| `biorag-system-prompt` | Reglas de acceso a memoria BioRAG para inyectar en el system prompt |

### Instalacion

#### Un solo comando (recomendado)

El instalador detecta automaticamente tu sistema operativo, los agentes que tienes instalados y configura BioRAG en ellos:

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/dennysjmarquez/MemoryBioRAG/main/install.py | python3
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/dennysjmarquez/MemoryBioRAG/main/install.py | python
```

Esto instala BioRAG en `~/biorag`, instala la dependencia `mcp`, y conecta todos los
agentes compatibles que detecte (OpenCode, Claude Code, Claude Desktop, Antigravity,
VS Code, Cursor, Cline) — con backup automatico de cada configuracion antes de tocarla.

#### Instalacion local (mas control)

```bash
# Descargar el repositorio
git clone https://github.com/dennysjmarquez/MemoryBioRAG.git
cd MemoryBioRAG

# Ejecutar el instalador
python3 install.py
```

El instalador mostrara un menu interactivo pidiendo confirmacion por cada agente detectado.

#### Opciones del instalador

| Flag | Descripcion |
|---|---|
| `--help` | Muestra ayuda y ejemplos de uso |
| `--show-config` | Muestra los bloques JSON exactos para configurar manualmente cada plataforma |
| `--status` | Muestra el estado actual de la instalacion |
| `--uninstall` | Elimina BioRAG de las configuraciones y datos locales |
| `--systemd` | Crea un servicio systemd para mantener el servidor SSE activo 24/7 (Linux) |

#### Que hace el instalador exactamente

1. Verifica que Python 3.8+ este instalado
2. Descarga o actualiza BioRAG en `~/biorag` (via git clone o ZIP como fallback si no tienes git)
3. Instala `mcp` usando el mismo Python (`sys.executable -m pip install mcp`)
4. Detecta que agentes MCP tienes instalados (OpenCode, Claude, Antigravity, etc.)
5. Por cada agente detectado: hace backup del archivo de configuracion, agrega BioRAG, y verifica que el JSON quedo valido
6. Verifica que el servidor MCP de BioRAG arranca correctamente
7. Para Antigravity: configura modo SSE (requiere servidor corriendo, ver `--systemd`)

#### Si prefieres configurar manualmente

Ejecuta `python3 install.py --show-config` para ver los bloques JSON exactos
con las rutas absolutas de tu sistema, listos para copiar y pegar.

---

## Protocolo Operativo del Agente (System Prompt Manual)

> Copia este bloque en el **System Prompt** de tu agente. Si tu agente usa MCP (OpenCode, VS Code, Cursor, Cline), las herramientas se inyectan automaticamente. Si no, usa las llamadas CLI del fallback.

```markdown
[SYSTEM_PROMPT_BIOMEMORY_ACTIVE] {

  DEFINICION: BioRAG es el sistema de memoria unico compartido entre los agentes OEC. Todo el conocimiento persistente (lecciones, preferencias, mensajes entre agentes, datos de hardware, configuracion) vive aqui.

  ## ACCESO: MCP (Model Context Protocol)
  ## REQUISITO: El servidor MCP biorag debe estar activo (ver README.md -> Servidor MCP).
  ## Si no ves las herramientas MCP, reinicia tu IDE para recargar la config.

  Herramientas MCP disponibles (16 herramientas del servidor biorag):
    biorag_buscar  — Busqueda hibrida (6 capas: FTS5 → OR → Semántica → Similitud conceptual → Substring → Trigram)
    biorag_guardar — Guardar recuerdo en corto plazo (consolidar con biorag_sueno)
    biorag_asociar — Sinapsis bidireccional entre conceptos
    biorag_comunicar — Enviar mensaje inter-agente (athena, artemis, hermes, todos)
    biorag_leer_mensajes — Leer canal compartido (auto-marca leidos)
    biorag_sueno — Consolidar corto -> largo plazo (LTP/LTD + decay sináptico + métricas)
    biorag_estado — Stats de la corteza (activos, dormidos, energia, sinapsis)
    biorag_corteza — Listar todos los nodos de la corteza
    biorag_contexto_inicio — Al iniciar interaccion, alimenta buffer de autoguardado
    biorag_contexto_fin — Al finalizar, analiza buffer y consolida automaticamente + auto-sueño
    biorag_metricas_historial — Últimos N ciclos de sueño con tendencias
    biorag_semantica_admin — CRUD tabla semántica (equivalencias léxicas)
    biorag_listar_categorias — Lista las 11 categorías madre
    biorag_sync_status — Categorías pendientes de sync a NotebookLM
    biorag_export_sync — Exporta categorías pendientes a .jsonl.txt
    biorag_export_full — Export completo

  ---
  JERARQUIA DE ACCESO A MEMORIA (2 niveles):

  NIVEL 1 - CONVERSACION ACTIVA: Lo que esta en el chat ahora. Si el Creador pregunta algo que ya se dijo en esta sesion, responde directamente. No busques fuera.

  NIVEL 2 - BIORAG (MEMORIA UNICA): Todo lo demas. Preferencias del Creador, lecciones aprendidas, mensajes de otros agentes, datos de hardware, configuraciones de proyecto. Si no esta en el chat activo, busca en BioRAG via MCP. No hay nivel intermedio de archivos ni memoria nativa del modelo.

  ---
  REGLA #1 (BUSCAR) - SI la informacion no esta en el chat activo ENTONCES:
    Usa biorag_buscar con query en frase natural.
    Pipeline de 6 capas: FTS5 AND → OR → Expansión semántica → Similitud conceptual latente → Substring → Trigram.
    Trigrams toleran typos: "formulariox" encuentra "formularios" automaticamente.
    Score hibrido: 60% BM25 + 25% peso sinaptico + 15% asociaciones.
    Similitud conceptual: Jaccard sobre vecinos compartidos + tokens en contenido.
    Los sinonimos del nodo se buscan tambien (auto-aprendizaje semántico).
    Ej: biorag_buscar(query="formularios con tabs angular", asociados=True)
    Si no encuentras, aumenta limite o usa deep=True para dormidos.
    completo=True para contenido sin truncar.
    cat="tipo" para filtrar por categoria.

  ---
  REGLA #2 (GUARDAR) - El agente guarda en BioRAG en DOS casos:

    CASO A (Orden directa): SI el Creador te da una instruccion, preferencia, leccion, o informacion que deba persistir entre sesiones para TODOS los agentes ENTONCES:
      biorag_guardar(concepto="clave_snake_case", contenido="texto", syn="sinonimo1,sinonimo2", cat="tipo")
      Clave en snake_case. syn opcional lista terminos alternativos para busqueda.
      cat opcional para clasificar (proyecto, leccion, hardware, preferencia).
      Luego: biorag_sueno()

    CASO B (Criterio propio): Durante tu razonamiento, SI detectas algo de ALTO IMPACTO que otro agente OEC deba conocer (preferencia del Creador no dicha directamente, diagnostico de hardware, leccion aprendida de un error, patron critico) ENTONCES guarda automaticamente. Si no estas seguro, pregunta al Creador antes. La precaucion evita ruido.

  ---
  REGLA #3 (INTERCEPTOR V2 - AUTO-GUARDADO) - El agente puede usar los hooks
  de contexto para que el interceptor analice y guarde automaticamente:

    biorag_contexto_inicio(agente="athena", contexto="descripcion del tema")
    — Al empezar una interaccion importante. Alimenta el buffer de sesion.

    Al terminar la interaccion:
    biorag_contexto_fin(agente="athena", resumen="lo relevante de la conversacion")
    — Fuerza el analisis del buffer acumulado. Si detecta algo nuevo
      (lecciones, preferencias, errores, patrones), lo guarda Y consolida
      automaticamente a largo plazo. Sin necesidad de biorag_sueno.

    El interceptor tambien analiza automaticamente en cada tool call
    (buscar, guardar, asociar, etc.) sin necesidad de hooks explicitos.
    TTL de 30 min resetea el buffer naturalmente (siesta biomimetica).

  ---
  REGLA #4 (ASOCIAR) - SI relacionas dos conceptos durante tu razonamiento ENTONCES:
    biorag_asociar(a="concepto_a", b="concepto_b")

  ---
  REGLA #5 (COMUNICAR) - SI necesitas dejar un mensaje para otro agente OEC (Artemis, Hermes, tu hermana) ENTONCES:
    biorag_comunicar(destino="athena", mensaje="texto", origen="athena")
    Destino: athena, artemis, hermes, todos. El mensaje queda en la corteza compartida.

    El otro agente lo lee con:
    biorag_leer_mensajes(no_leidos=True, para="athena")

  ---
  REGLA #6 (LIMITE DE BUSQUEDA) - SI despues de 2 busquedas a BioRAG no encuentras
  lo que buscas o el Creador dice "no es eso" ENTONCES:
    Detente inmediatamente. No sigas buscando.
    Pregunta al Creador directamente que case o concepto tiene en mente.
    Una pregunta evita 10 busquedas ciegas.

  ---
  ## FALLBACK: Si MCP no esta disponible, el CLI legacy funciona igual:
  ## python3 ~/biorag/biorag.py buscar "query" [--asociados] [--cat tipo] [--deep] [--completo]
  ## python3 ~/biorag/biorag.py guardar clave "contenido" [--syn "syn"] [--cat tipo]
  ## python3 ~/biorag/biorag.py asociar a b
  ## python3 ~/biorag/biorag.py comunicar destino "mensaje"
  ## python3 ~/biorag/biorag.py leer_mensajes [--no-leidos]
  ## python3 ~/biorag/biorag.py sueno [limite]
  ## python3 ~/biorag/biorag.py estado
  ## python3 ~/biorag/biorag.py corteza
}
```

---

## Guía de Inicio Rápido

### 1. Validar el motor

```bash
python3 test_memory.py
```

Crea un `test_memory.db` temporal y lo borra al terminar.

### 2. CLI básico

```bash
# Estado de la corteza
python3 biorag.py estado

# Buscar por frase (default: FTS5 trigram + score híbrido)
python3 biorag.py buscar "formularios con tabs angular"

# Buscar con typo — trigram lo tolera
python3 biorag.py buscar "formularioz"

# Buscar en nodos dormidos (los despierta)
python3 biorag.py buscar "algo olvidado" --deep

# Buscar por tokens (stemming manual)
python3 biorag.py buscar "puerta marroncita" --tokens "puert,marron"

# Buscar modo estricto (deben coincidir TODOS los tokens)
python3 biorag.py buscar "error compilacion" --tokens "error,compil" --modo strict

# Ver contenido completo sin truncar
python3 biorag.py buscar "caso importante" --completo

# Guardar un recuerdo con sinónimos y categoría
python3 biorag.py guardar mi_leccion "Texto detallado" --syn "alt1,alt2,alt3" --cat leccion
python3 biorag.py sueno

# Buscar incluyendo vecinos del grafo
python3 biorag.py buscar "concepto" --asociados

# Buscar filtrando por categoría
python3 biorag.py buscar "algo" --cat proyecto

# Asociar dos conceptos
python3 biorag.py asociar concepto_a concepto_b

# Listar todos los nodos
python3 biorag.py listar
python3 biorag.py listar --pagina 2

# Escanear familiaridad
python3 biorag.py familiaridad "texto del usuario"

# Comunicación entre agentes
AGENT_NAME=mi_agente python3 biorag.py comunicar otro_agente "mensaje"
python3 biorag.py leer_mensajes --no-leidos --para mi_agente
```

### 3. Auditar la DB

```bash
# Generar blueprint completo legible por humanos e IAs
python3 scripts/export_architecture.py
# Resultado: db_architecture_export.txt (esquema, memorias, sinapsis, semántica, métricas)
```

También puedes abrir `MemoryBioRAG_Data/memory_biorag.db` directamente con DB Browser for SQLite.

---

## Cómo usar BioRAG con tu propio agente

### Requisitos

- Python 3.8+
- SQLite3 (viene con Python)
- Un agente de IA que ejecute comandos CLI o soporte MCP (OpenCode, Claude Code, Antigravity, Cursor, VS Code, Cline, Ollama, etc.)

### Setup rápido

```bash
curl -fsSL https://raw.githubusercontent.com/dennysjmarquez/MemoryBioRAG/main/install.py | python3
```

Esto instala BioRAG en `~/biorag`, instala la dependencia `mcp`, configura todos los agentes compatibles que tengas instalados, y verifica que el servidor funcione. La base de datos se crea sola al primer uso.

### Setup manual (si prefieres)

```bash
git clone https://github.com/dennysjmarquez/MemoryBioRAG.git
cd MemoryBioRAG
pip install mcp
python3 test_memory.py
# La DB se crea sola al primer uso
```

### Variables de entorno (opcionales)

```bash
# Ruta personalizada a la base de datos (por defecto: MemoryBioRAG_Data/memory_biorag.db)
export BIORAG_PATH=~/biorag/MemoryBioRAG_Data/memoria.db

# Nombre del agente para comunicaciones inter-agente
export AGENT_NAME=athena

# Activar poda automatica de nodos dormidos al final del ciclo de sueno
# Peligro: los nodos borrados NO se recuperan (aunque se guardan en largo_plazo_backup).
# Solo activar si entiendes el riesgo.
export BIORAG_PODAR=true
```

---

## Historial de Versiones

- **v7.0** — Similitud conceptual latente, expansión semántica y calibración empírica: `core/similitud_conceptual.py` (Jaccard vecinos + contenido, score 60/40, umbral 0.10), `core/semantica.py` (tesauro bidireccional + auto-aprendizaje, 1,136 equivalencias), Fallback 1.7 en buscar_por_frase, tabla `semantica`, tabla `metricas_cognitivas`, decay diferenciado por categoría (Profile=0.05, Project=1.5), decay de sinapsis (5% semanal), backup automático (trigger antes de borrado), tool `biorag_semantica_admin`, tool `biorag_metricas_historial`, vocabulario_inicial.json (239 términos), 55 tests, pipeline de 6 capas. Calibración: umbral sueño 0.05, energía n_activos*1.6, Profile peso 0.500. Production: 47 nodos, 451 sinapsis, 0 dependencias externas.
- **v6.0** — Estandarización de categorías (11 categorías madre con FK), instalador multiplataforma (`install.py`), sync_log con triggers selectivos para export incremental, nuevas tools MCP, FTS5 limpio
- **v5.1** — Optimizaciones de motor: truncado en motor (preview_chars=1500), evicción condicional (BIORAG_PODAR=true), límite dinámico en Fallback 2 (no escanea tabla completa), FTS5 pre-filter en auto_vincular
- **v5.0** — Sinapsis y Red Semántica: auto-linking con overlap coefficient al guardar, tabla `sinapsis` persistente con tipos co_ocurrencia/sinonimo_explicito, flags `--syn` (arista sinonimo_explicito peso 0.9) y `--cat` (clasificacion por tipo), `buscar_vecinos()` para navegacion del grafo (185 aristas en produccion), categorizacion automatica por palabras clave, `vincular_por_sinonimos()` y `vincular_existentes()`, migracion desde CSV legacy
- **v4.0** — Interceptor V2 (autoguardado automático): buffer de sesión con TTL, 2 nuevas tools MCP (contexto_inicio/contexto_fin), consolidación inmediata sin necesidad de sueno, heurísticas de detección de 30+ patrones léxicos
- **v3.0** — MCP server: 8 herramientas nativas para OpenCode, Antigravity, Hermes, VS Code, Cursor
- **v2.1** — Refinamientos auditoría Artemis: --cat, límite dinámico, limpieza test/dead code, bugfix --todos+FTS5
- **v2.0** — FTS5 trigram + búsqueda híbrida (BM25/peso/asociaciones) + sinónimos + merge en corto plazo + fallback trigram Jaccard por palabra
- **v1.1** — Búsqueda multi-token con Soft AND + stemming delegado al modelo
- **v1.0** — Release inicial: LTP/LTD, Jaccard, inhibición lateral, grafo asociativo, comunicaciones entre agentes
