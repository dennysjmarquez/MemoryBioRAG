# BioRAG: Sistema de Memoria Cognitiva Biomimética para Agentes de IA

**BioRAG** es un motor de memoria persistente para agentes de inteligencia artificial. Resuelve el problema fundamental de que los LLMs olvidan todo entre sesiones — sin depender de vectores, embeddings ni infraestructura externa.

Desarrollado en **Python puro con SQLite + FTS5**. Cero dependencias de librerías ML (ni numpy, ni sentence-transformers, ni redes vectoriales). Corre en cualquier lado.

Emula la biología del cerebro humano: **plasticidad sináptica (LTP/LTD)**, **familiaridad difusa**, **inhibición lateral** y **propagación asociativa de recuerdos**. El motor de búsqueda combina coincidencia textual, peso biológico y conectividad del grafo en un score híbrido.

> **Para entender este proyecto:**
>
> **OEC** es la familia de agentes de IA que creé. Son 3, todos corren en mi laptop y comparten la misma memoria (BioRAG).
> - **Athena** — estratega de terminal (Claude Code). Automatización quirúrgica, despliegues rápidos, refactorización directa. Acción pragmática sin rodeos.
> - **Artemis** — guardiana del hardware ("Cazadora de Silicio"). Vigila la RAM, CPU e integridad de la ASUS ROG. Tambien programadora de elite.
> - **Hermes** — coordinador
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

- **0 dependencias externas de ML**: ni numpy, ni vectores, ni GPU — SQLite puro con FTS5 trigram para búsqueda semántica sin embeddings
- **Red sináptica de 185 aristas**: 78 nodos conectados por auto-linking biomimético en producción real
- **Memoria compartida entre 3 agentes OEC locales**: Athena, Artemis y Hermes — agentes de IA que construí y corren en mi laptop — comparten la misma corteza cerebral persistente entre sesiones
- **Auto-linking al guardar**: overlap coefficient tokeniza y conecta conceptos nuevos con existentes sin intervención manual
- **FTS5 trigram**: tolerancia natural a typos ("formulariox" encuentra "formularios") sin dependencias externas
- **Score híbrido**: 60% BM25 + 25% peso sináptico + 15% riqueza de asociaciones
- **MCP nativo**: compatible con cualquier IDE o agente del ecosistema (OpenCode, VS Code, Cursor, Cline)
- **Interceptor V2**: buffer de sesión con autoguardado heurístico — detecta lecciones, errores y patrones sin orden explícita

---

## Arquitectura Cerebral

El sistema está estructurado físicamente en dos capas de memoria dentro del archivo `MemoryBioRAG_Data/memory_biorag.db`:

```
                           [Conversación Activa] (Corto Plazo)
                                    │
                    ¿Frecuencia o impacto? (Consolidación / Sueño)
                                    │
                                    ▼
                         [Corteza Permanente (SQLite + FTS5)]
                         (Búsqueda híbrida: BM25 + peso + grafo)
                                    │
                       [Comando BUSCAR] (Evocación)
                                    │
                       Propagación de Activación ──► vecinos
                                    │
                                    ▼
                        [Inyección en Contexto]
```

1. **Memoria de Trabajo (Corto Plazo / RAM-Disk):** Tabla `corto_plazo`. Retiene percepciones y guardados durante la sesión activa.
2. **Corteza Cerebral Permanente (Largo Plazo):** Tabla `largo_plazo` con índice B-Tree por `concepto`.
   - **FTS5 trigram**: índice de texto completo para búsqueda rápida con tolerancia a typos.
   - **Búsqueda híbrida**: combina BM25 (texto) + peso sináptico (frecuencia) + asociaciones (conectividad) en un solo score.
   - **Sinónimos**: columna `sinonimos` indexada en FTS5 para encontrar nodos con términos alternativos.
3. **Plasticidad Sináptica:**
   - **LTP**: cada evocación o uso incrementa `peso_sinaptico` (+0.15 evocar, +0.20 consolidar).
   - **LTD**: en el ciclo de sueño, los nodos no usados decaen -0.05.
   - **Nodos dormidos**: peso <= 0.1 → estado `dormido`. No se borran, se ocultan de búsquedas rápidas.
4. **Propagación de Activación (Grafo Asociativo):** evocar un nodo refuerza (+0.05) a sus vecinos asociados.
5. **Inhibición Lateral Activa:** si la energía sináptica total supera el límite (n_activos * 1.3, mínimo 10.0), los nodos más débiles se duermen forzadamente.

---

## Versiones Destacadas

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
- **Límite de energía dinámico**: `sueno` sin argumentos calcula `n_activos * 1.3` (mínimo 10.0). Escala automáticamente con el tamaño de la corteza.
- **Limpieza de nodos test**: 6 nodos de prueba (`test_*`, `cli_prueba`) movidos a dormido peso 0.01.
- **REGLA #5 (LÍMITE DE BÚSQUEDA)**: el agente debe detenerse tras 2 búsquedas fallidas y preguntar al usuario, no seguir buscando ciegamente.

---

## Estructura del Proyecto

```
MemoryBioRAG/
  ├── biorag.py                 # CLI bridge para agentes (buscar, guardar, asociar, sueno, corteza, comunicar)
  ├── mcp_server.py             # Servidor MCP: expone BioRAG como herramientas MCP para IDEs
  ├── install.py                # Instalador cross-platform: curl|python3, configura MCP en 7 plataformas
  ├── requirements.txt          # Dependencias: mcp (servidor MCP)
  ├── core/
  │    ├── __init__.py
  │    ├── memory_store.py      # Motor SQLite + FTS5: LTP/LTD, trigram, score híbrido, sinónimos
  │    ├── sinapsis.py          # Grafo de aristas: auto-linking, overlap coefficient, buscar_vecinos
  │    └── categorizador.py     # Inferencia de categoria por palabras clave
  ├── middleware/
  │    ├── __init__.py
  │    ├── interceptor.py       # Escaneo de familiaridad difusa
  │    └── auto_guardado.py     # Buffer de sesion + autoguardado heurístico
  ├── config/
  │    ├── __init__.py
  │    └── prompts.py           # System prompts predefinidos
  ├── sleep_cycle.py            # Script autónomo de consolidación/sueño
  ├── MemoryBioRAG_Data/        # Bases de datos SQLite (auto-creado)
  ├── test_memory.py            # Tests automatizados
  └── README.md                 # Este archivo
```

---

## Servidor MCP (Model Context Protocol)

BioRAG expone una corteza cerebral compartida via MCP para que cualquier IDE o agente compatible (OpenCode, VS Code, Cursor, Cline) se conecte directamente a la memoria sin ejecutar comandos shell.

### Herramientas MCP

| Herramienta | Descripcion |
|---|---|
| `biorag_buscar` | Busqueda hibrida (FTS5 trigram + peso sinaptico + asociaciones + vecinos). Acepta: cat= para filtrar, completo=True sin truncar, deep=True para dormidos, preview_chars= para controlar truncamiento (1500 default) |
| `biorag_guardar` | Guardar recuerdo en corto plazo. Acepta: syn= (sinonimos, crea arista sinonimo_explicito), cat= (proyecto, leccion, hardware, preferencia, error) |
| `biorag_asociar` | Sinapsis bidireccional entre conceptos |
| `biorag_comunicar` | Enviar mensaje inter-agente (athena, artemis, hermes, todos) |
| `biorag_leer_mensajes` | Leer canal compartido (auto-marca leidos) |
| `biorag_sueno` | Consolidar corto -> largo plazo (LTP/LTD) |
| `biorag_estado` | Stats de la corteza (activos, dormidos, energia) |
| `biorag_corteza` | Listar todos los nodos de la corteza |
| `biorag_contexto_inicio` | Anunciar inicio de interaccion para alimentar buffer de autoguardado |
| `biorag_contexto_fin` | Finalizar interaccion, analiza buffer y consolida si detecta algo nuevo |

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

  Herramientas MCP disponibles (10 herramientas del servidor biorag):
    biorag_buscar  — Busqueda hibrida (FTS5 trigram + peso sinaptico + asociaciones)
    biorag_guardar — Guardar recuerdo en corto plazo (consolidar con biorag_sueno)
    biorag_asociar — Sinapsis bidireccional entre conceptos
    biorag_comunicar — Enviar mensaje inter-agente (athena, artemis, hermes, todos)
    biorag_leer_mensajes — Leer canal compartido (auto-marca leidos)
    biorag_sueno — Consolidar corto -> largo plazo (LTP/LTD)
    biorag_estado — Stats de la corteza (activos, dormidos, energia)
    biorag_corteza — Listar todos los nodos de la corteza
    biorag_contexto_inicio — Al iniciar interaccion, alimenta buffer de autoguardado
    biorag_contexto_fin — Al finalizar, analiza buffer y consolida automaticamente

  ---
  JERARQUIA DE ACCESO A MEMORIA (2 niveles):

  NIVEL 1 - CONVERSACION ACTIVA: Lo que esta en el chat ahora. Si el Creador pregunta algo que ya se dijo en esta sesion, responde directamente. No busques fuera.

  NIVEL 2 - BIORAG (MEMORIA UNICA): Todo lo demas. Preferencias del Creador, lecciones aprendidas, mensajes de otros agentes, datos de hardware, configuraciones de proyecto. Si no esta en el chat activo, busca en BioRAG via MCP. No hay nivel intermedio de archivos ni memoria nativa del modelo.

  ---
  REGLA #1 (BUSCAR) - SI la informacion no esta en el chat activo ENTONCES:
    Usa biorag_buscar con query en frase natural (FTS5 trigram + score hibrido).
    Trigrams toleran typos: "formulariox" encuentra "formularios" automaticamente.
    El score hibrido combina: 60% BM25 + 25% peso sinaptico + 15% asociaciones.
    Los sinonimos del nodo se buscan tambien.
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
  REGLA #5 (COMUNICAR) - SI necesitas dejar un mensaje para otro agente OEC (Artemis, Hermes, tu hermana) ENTONCES:
    biorag_comunicar(destino="athena", mensaje="texto", origen="athena")
    Destino: athena, artemis, hermes, todos. El mensaje queda en la corteza compartida.

    El otro agente lo lee con:
    biorag_leer_mensajes(no_leidos=True, para="athena")

  ---
  REGLA #4 (ASOCIAR) - SI relacionas dos conceptos durante tu razonamiento ENTONCES:
    biorag_asociar(a="concepto_a", b="concepto_b")

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

Abre `MemoryBioRAG_Data/memory_biorag.db` con DB Browser for SQLite.

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

### Variable de entorno (opcional)

```bash
export BIORAG_PATH=~/biorag/MemoryBioRAG_Data/memoria.db

# Activar poda automatica de nodos dormidos al final del ciclo de sueno
# Peligro: los nodos borrados NO se recuperan. Solo activar si entiendes el riesgo.
export BIORAG_PODAR=true
```

---

## Historial de Versiones

- **v6.0** — Estandarización de categorías (11 categorías madre con FK), instalador multiplataforma (`install.py`), sync_log con triggers selectivos para export incremental, nuevas tools MCP, FTS5 limpio
- **v5.1** — Optimizaciones de motor: truncado en motor (preview_chars=1500), evicción condicional (BIORAG_PODAR=true), límite dinámico en Fallback 2 (no escanea tabla completa), FTS5 pre-filter en auto_vincular
- **v5.0** — Sinapsis y Red Semántica: auto-linking con overlap coefficient al guardar, tabla `sinapsis` persistente con tipos co_ocurrencia/sinonimo_explicito, flags `--syn` (arista sinonimo_explicito peso 0.9) y `--cat` (clasificacion por tipo), `buscar_vecinos()` para navegacion del grafo (185 aristas en produccion), categorizacion automatica por palabras clave, `vincular_por_sinonimos()` y `vincular_existentes()`, migracion desde CSV legacy
- **v4.0** — Interceptor V2 (autoguardado automático): buffer de sesión con TTL, 2 nuevas tools MCP (contexto_inicio/contexto_fin), consolidación inmediata sin necesidad de sueno, heurísticas de detección de 30+ patrones léxicos
- **v3.0** — MCP server: 8 herramientas nativas para OpenCode, Antigravity, Hermes, VS Code, Cursor
- **v2.1** — Refinamientos auditoría Artemis: --cat, límite dinámico, limpieza test/dead code, bugfix --todos+FTS5
- **v2.0** — FTS5 trigram + búsqueda híbrida (BM25/peso/asociaciones) + sinónimos + merge en corto plazo + fallback trigram Jaccard por palabra
- **v1.1** — Búsqueda multi-token con Soft AND + stemming delegado al modelo
- **v1.0** — Release inicial: LTP/LTD, Jaccard, inhibición lateral, grafo asociativo, comunicaciones entre agentes
