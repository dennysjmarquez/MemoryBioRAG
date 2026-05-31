# BioRAG: Sistema de Gobernanza y Memoria Cognitiva Biomimética

**BioRAG (Biomimetic Retrieval-Augmented Generation)** es un motor de memoria persistente para Agentes de Inteligencia Artificial (OpenCode, Claude/Athena, Hermes, Gemini/Artemis) desarrollado en **Python Puro, sin dependencias externas** (ni numpy, ni sentence-transformers, ni redes vectoriales) y respaldado por **SQLite + FTS5**.

A diferencia de los sistemas RAG tradicionales (que indexan texto plano rígidamente y saturan la ventana de contexto), BioRAG emula la biología del cerebro humano: gestiona de forma activa la **plasticidad sináptica (LTP/LTD)**, la **familiaridad difusa**, la **inhibición lateral** y la **propagación asociativa de recuerdos** en microsegundos, con un motor de búsqueda híbrido que combina coincidencia textual, peso biológico y conectividad del grafo.

---

## v2.1 — Refinamientos (Auditoría Artemis)

- **Flag `--cat`**: clasificar memorias por tipo (`guardar --cat proyecto "texto"`, filtrar con `buscar "algo" --cat leccion`). Poblar la columna `categoria` que estaba siempre en 'general'.
- **Límite de energía dinámico**: `sueno` sin argumentos calcula `n_activos * 1.3` (mínimo 10.0). Escala automáticamente con el tamaño de la corteza.
- **Limpieza de nodos test**: 6 nodos de prueba (`test_*`, `cli_prueba`) movidos a dormido peso 0.01.
- **`main.py` eliminado**: dead code, el CLI real es `biorag.py`.
- **Bugfix: `--todos` ahora usa FTS5**: antes disparaba búsqueda legacy (LIKE), ahora pasa por FTS5 trigram + score híbrido. Compatible con `--deep`.

---

## v2.0 — Novedades

- **FTS5 con tokenizer trigram**: tolerancia natural a typos ("formulariox" encuentra "formularios") sin dependencias externas. Reemplaza el antiguo porter unicode61.
- **Score híbrido**: 60% BM25 + 25% peso sináptico + 15% riqueza de asociaciones. Los resultados se reordenan combinando relevancia textual con biológica.
- **Columna `sinonimos`**: términos alternativos para búsqueda, indexados en FTS5. Flag `--syn` en guardar.
- **Merge en corto plazo**: guardar el mismo concepto dos veces antes de `sueno` ya no pierde la primera versión — concatena contenido y mergea sinónimos sin duplicar.
- **Fallback trigram Jaccard por palabra**: cuando FTS5 y substring fallan, compara trigramas palabra por palabra (umbral 0.5). Atrapa typos como "angulr" → "angular".
- **REGLA #5 (LÍMITE DE BÚSQUEDA)**: el agente debe detenerse tras 2 búsquedas fallidas y preguntar al usuario, no seguir buscando ciegamente.

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

## Estructura del Proyecto

```
MemoryBioRAG/
  ├── biorag.py                 # CLI bridge para agentes (buscar, guardar, asociar, sueno, corteza, comunicar)
  ├── mcp_server.py             # Servidor MCP: expone BioRAG como herramientas MCP para IDEs
  ├── requirements.txt          # Dependencias: mcp (servidor MCP)
  ├── core/
  │    ├── __init__.py
  │    └── memory_store.py      # Motor SQLite + FTS5: LTP/LTD, trigram, score híbrido, sinónimos
  ├── middleware/
  │    ├── __init__.py
  │    └── interceptor.py       # Escaneo de familiaridad difusa
  ├── config/
  │    ├── __init__.py
  │    └── prompts.py           # System prompts predefinidos
  ├── main.py                   # Simulador interactivo de consola
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
| `biorag_buscar` | Busqueda hibrida (FTS5 trigram + peso sinaptico + asociaciones) |
| `biorag_guardar` | Guardar recuerdo en corto plazo (consolidar con biorag_sueno) |
| `biorag_asociar` | Sinapsis bidireccional entre conceptos |
| `biorag_comunicar` | Enviar mensaje inter-agente (athena, artemis, hermes, todos) |
| `biorag_leer_mensajes` | Leer canal compartido (auto-marca leidos) |
| `biorag_sueno` | Consolidar corto -> largo plazo (LTP/LTD) |
| `biorag_estado` | Stats de la corteza (activos, dormidos, energia) |
| `biorag_corteza` | Listar todos los nodos de la corteza |

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

```bash
# 1. Clonar el repositorio
git clone https://github.com/dennysjmarquez/MemoryBioRAG.git
cd MemoryBioRAG

# 2. Instalar dependencia MCP
pip install mcp

# 3. Verificar que funciona
python3 mcp_server.py --help
```

### Configuracion en OpenCode

Agregar a `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "biorag": {
      "type": "local",
      "command": ["python3", "/ruta/a/MemoryBioRAG/mcp_server.py"],
      "enabled": true
    }
  }
}
```

Reiniciar OpenCode para que cargue la configuracion.

### Configuracion en VS Code

Crear `.vscode/mcp.json` en la raiz del proyecto:

```json
{
  "servers": {
    "biorag": {
      "type": "stdio",
      "command": "python3",
      "args": ["/ruta/a/MemoryBioRAG/mcp_server.py"]
    }
  }
}
```

### Configuracion en Cursor

Agregar a `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "biorag": {
      "command": "python3",
      "args": ["/ruta/a/MemoryBioRAG/mcp_server.py"]
    }
  }
}
```

### Modo SSE (servidor HTTP)

Para servir BioRAG como daemon HTTP que multiples IDEs conectan simultaneamente:

```bash
python3 mcp_server.py --sse --port 8080
```

Luego configurar los IDEs con `type: "remote"` apuntando a `http://localhost:8080/mcp`.

### Verificacion

```bash
# Verificar que el servidor MCP esta conectado en OpenCode
opencode mcp list

# Deberia mostrar:
# ●  ✓ biorag connected
```

---

## Protocolo Operativo del Agente (System Prompt Manual)

> Copia este bloque en el **System Prompt** de tu agente (Claude Code, Cursor, Ollama, cualquier LLM que ejecute comandos CLI). Cambia `/ruta/a/MemoryBioRAG` por la ruta absoluta del proyecto.

```markdown
[SYSTEM_PROMPT_BIOMEMORY_ACTIVE] {

  DEFINICION: BioRAG es el sistema de memoria unico compartido entre los agentes OEC.
  Ruta: /ruta/a/MemoryBioRAG

  ---
  JERARQUIA DE ACCESO A MEMORIA (2 niveles):

  NIVEL 1 - CONVERSACION ACTIVA: Lo que esta en el chat ahora. Responde directamente.
  NIVEL 2 - BIORAG (MEMORIA UNICA): Todo lo demas. Busca aqui.

  ---
  REGLA #1 (BUSCAR):
    Usa busqueda directa sin flags (default: FTS5 trigram + score hibrido).
    Trigrams toleran typos: "formulariox" encuentra "formularios" automaticamente.
    El score hibrido combina: 60% BM25 + 25% peso sinaptico + 15% asociaciones.
    Los sinonimos del nodo (definidos en guardar --syn) se buscan tambien.
    Ej: python3 /ruta/a/MemoryBioRAG/biorag.py buscar "formularios con tabs angular"
    Si no encuentras, usa fallback explicito: --tokens "raiz1,raiz2" con stemming manual.
    --completo para contenido sin truncar, --asociados para nodos relacionados.
    --deep para buscar en nodos dormidos (los despierta al encontrarlos).
    --cat tipo para filtrar por categoria (proyecto, leccion, hardware).

  ---
  REGLA #2 (GUARDAR):
    CASO A (Orden directa): Si el usuario da una instruccion, leccion o preferencia:
      python3 /ruta/a/MemoryBioRAG/biorag.py guardar <clave> "contenido" [--syn "sinonimo1,sinonimo2"] [--cat tipo]
      Clave en snake_case. --syn opcional lista terminos alternativos para busqueda.
      --cat opcional para clasificar (proyecto, leccion, hardware, preferencia).
      Luego: python3 /ruta/a/MemoryBioRAG/biorag.py sueno
    CASO B (Criterio propio): Si detectas algo de ALTO IMPACTO que otro agente deba conocer.

  ---
  REGLA #3 (COMUNICAR) - Mensajes a otros agentes:
    AGENT_NAME=tu_nombre python3 /ruta/a/MemoryBioRAG/biorag.py comunicar <destino> "mensaje"
    Para leer: python3 /ruta/a/MemoryBioRAG/biorag.py leer_mensajes --no-leidos --para tu_nombre

  ---
  REGLA #4 (ASOCIAR) - Si relacionas dos conceptos:
    python3 /ruta/a/MemoryBioRAG/biorag.py asociar <a> <b>

  ---
  REGLA #5 (LIMITE DE BUSQUEDA):
    Si despues de 2 busquedas a BioRAG no encuentras lo que buscas
    o el usuario dice "no es eso" ENTONCES:
      Detente inmediatamente. No sigas buscando.
      Pregunta al usuario directamente que caso o concepto tiene en mente.
      Una pregunta evita 10 busquedas ciegas.
}
```

> **Alternativa:** Define `BIORAG_PATH` apuntando a tu DB y pon el proyecto en el `$PATH`:
> ```bash
> export PATH=$PATH:/ruta/a/MemoryBioRAG
> export BIORAG_PATH=/ruta/a/tu/memoria.db
> ```

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

# Guardar un recuerdo con sinónimos
python3 biorag.py guardar mi_leccion "Texto detallado" --syn "alt1,alt2,alt3"
python3 biorag.py sueno

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
- Un agente de IA que ejecute comandos CLI (Claude Code, Cursor, Ollama, etc.)

### Setup

```bash
git clone https://github.com/dennysjmarquez/MemoryBioRAG.git
cd MemoryBioRAG
python3 test_memory.py
# La DB se crea sola al primer uso
```

### Variable de entorno (opcional)

```bash
export BIORAG_PATH=/tu/ruta/memoria.db
```

---

## Historial de Versiones

- **v2.1** — Refinamientos auditoría Artemis: --cat, límite dinámico, limpieza test/dead code, bugfix --todos+FTS5
- **v2.0** — FTS5 trigram + búsqueda híbrida (BM25/peso/asociaciones) + sinónimos + merge en corto plazo + fallback trigram Jaccard por palabra
- **v1.1** — Búsqueda multi-token con Soft AND + stemming delegado al modelo
- **v1.0** — Release inicial: LTP/LTD, Jaccard, inhibición lateral, grafo asociativo, comunicaciones entre agentes
