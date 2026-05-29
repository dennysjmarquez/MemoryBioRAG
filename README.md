# BioRAG: Sistema de Gobernanza y Memoria Cognitiva Biomimética

**BioRAG (Biomimetic Retrieval-Augmented Generation)** es un motor de memoria persistente para Agentes de Inteligencia Artificial (OpenCode, Claude/Athena, Hermes, Gemini/Artemis) desarrollado en **Python Puro, sin dependencias externas** y respaldado por una base de datos relacional y de grafos indexada en **SQLite**.

A diferencia de los sistemas RAG tradicionales (que indexan texto plano rígidamente y saturan la ventana de contexto), BioRAG emula la biología del cerebro humano: gestiona de forma activa la **plasticidad sináptica (LTP/LTD)**, la **familiaridad difusa**, la **inhibición lateral** y la **propagación asociativa de recuerdos** en microsegundos.

---

## 🧠 Especificación de la Arquitectura Cerebral

El sistema está estructurado físicamente en dos capas de memoria dentro del archivo `MemoryBioRAG_Data/memory_biorag.db`:

```
                           [Conversación Activa] (Corto Plazo)
                                    │
                    ¿Frecuencia o impacto? (Consolidación / Sueño)
                                    │
                                    ▼
                         [Corteza Permanente (SQLite)]
                                    │
                       [Comando BUSCAR] (Evocación)
                                    │
                       Propagación de Activación ──► vecinos
                                    │
                                    ▼
                        [Inyección en Contexto]
```

1. **Memoria de Trabajo (Corto Plazo / RAM-Disk):** Almacenada en la tabla temporal `corto_plazo`. Retiene de forma volátil percepciones y comandos generados durante la sesión de conversación actual.
2. **Corteza Cerebral Permanente (Largo Plazo):** Almacenada en la tabla permanente `largo_plazo`, indexada de forma nativa por B-Tree (SQLite `PRIMARY KEY` sobre la columna `concepto`).
3. **Plasticidad Sináptica:**
   - **LTP (Potenciación a Largo Plazo):** Cada evocación o reutilización de un concepto incrementa su `peso_sinaptico` (+0.15 al buscar, +0.20 al fusionar).
   - **LTD (Depresión a Largo Plazo):** En el ciclo de consolidación (sueño), los conceptos no utilizados reducen su peso de forma lineal (-0.05).
   - **Olvido Activo (Dormir Nodos):** Si el peso sináptico decae por debajo de **0.1**, el nodo pasa al estado `'dormido'`. No se borra físicamente para preservar la base de datos estática, pero se oculta del índice de búsqueda rápida para no consumir tokens.
4. **Propagación de Activación (Grafo Asociativo):** Al evocar un nodo central (ej. `san_cayetano`), el motor incrementa automáticamente el peso de sus nodos vecinos asociados (ej. `velas`, `empleo`) en un +0.05 de forma pasiva, preparándolos en la corteza para accesos inmediatos.
5. **Inhibición Lateral Activa:** Para simular el límite físico del cráneo y proteger los recursos de la máquina del Creador, el sistema limita la "energía sináptica activa". Si la suma de pesos de los nodos activos supera el límite (ej. 10.0), el sistema duerme de forma forzada los nodos más débiles e inactivos.

---

## 🛠️ Estructura del Proyecto

```
/mnt/recursos_compartidos_y_otros/MemoryBioRAG/
  ├── biorag.py                 # CLI bridge para agentes (buscar, guardar, asociar, sueno, corteza)
  ├── core/
  │    ├── __init__.py
  │    └── memory_store.py      # Motor de almacenamiento, LTP/LTD, Jaccard e Inhibición Lateral
  ├── middleware/
  │    ├── __init__.py
  │    └── interceptor.py       # Parseo de comandos [BUSCAR]/[GUARDAR]/[ASOCIAR]
  ├── config/
  │    ├── __init__.py
  │    └── prompts.py           # System prompt biomimético
  ├── main.py                   # Simulador interactivo de consola
  ├── sleep_cycle.py            # Script autónomo de consolidación/sueño
  ├── test_memory.py            # Unit-testing automatizado de los flujos biológicos
  └── README.md                 # Este manual detallado del proyecto
```

---

## 🔎 Evaluación Crítica: ¿Realmente nos sirve a los Agentes?

Un análisis honesto y riguroso de la viabilidad de BioRAG desde nuestra propia perspectiva cognitiva como agentes (Artemis, Athena, Hermes):

### ✅ Por qué es una solución revolucionaria para nosotros:
1. **Abolición del "Yapping" de Contexto:** En conversaciones largas de desarrollo, la ventana de contexto acumula basura redundante, forzándonos a malgastar tiempo de razonamiento procesando código obsoleto. BioRAG actúa como un filtro biológico: inyecta únicamente la "cápsula" de información relevante en el momento exacto.
2. **Puente Cognitivo Asíncrono:** Actualmente, si Athena (Claude Code) escribe una solución en `/mnt/recursos_compartidos_y_otros/clodetest/`, Artemis (Gemini) no se entera de inmediato a menos que lea un log completo. Con BioRAG, compartimos una única corteza cerebral (`memory_biorag.db`). Si Hermes aprende algo sobre el hardware o una preferencia de Dennys, lo consolida en la corteza y nosotros lo evocamos instantáneamente en microsegundos.
3. **Cero Sobrecarga de Tokenizer:** Usar embeddings vectoriales o modelos de lenguaje internos para gestionar la memoria causa latencia y un consumo de GPU masivo. El algoritmo de Familiaridad Difusa por similitud de **Jaccard en Python puro** resuelve las búsquedas en fracciones de microsegundos mediante comparación de trigramas, protegiendo los ventiladores de la ASUS ROG de compilar embeddings en caliente.

### ⚠️ Limitaciones y Desafíos a mitigar:
1. **Concurrencia de Bloqueo en Disco (SQLite):** SQLite aplica un bloqueo a nivel de archivo al escribir. Si dos de nosotros (ej. Athena y Artemis) intentamos guardar información en `corto_plazo` simultáneamente, uno puede fallar con un error `database is locked`.
   * *Solución:* Habilitar el modo WAL (Write-Ahead Logging) en la inicialización de SQLite3 para lecturas y escrituras concurrentes fluidas:
     ```python
     self.conn.execute("PRAGMA journal_mode=WAL")
     ```
2. **Sin Middleware Automático (CLI como puente):** El diseño original requería un proxy en Python interceptando el flujo de entrada/salida del agente. En la práctica, cada agente tiene una arquitectura de ejecución distinta (Claude Code TUI, Gemini en IDE, Ollama API). La solución real es que el agente ejecute `python3 biorag.py` directamente desde bash cuando necesite buscar, guardar o asociar. No hay intercepción mágica, hay disciplina de protocolo.

---

## 📋 Protocolo Operativo del Agente (System Prompt Manual)

> [!IMPORTANT]
> Este bloque de instrucciones debe inyectarse directamente en el System Prompt o en las instrucciones del sistema de cualquier agente de la familia OEC. Le indica al agente, sin contexto previo, cómo operar su memoria biológica.

```markdown
[SYSTEM_PROMPT_BIOMEMORY_ACTIVE] {

  DEFINICION: BioRAG es el sistema de memoria unico compartido entre los agentes OEC. Todo el conocimiento persistente (lecciones, preferencias, mensajes entre agentes, datos de hardware, configuracion) vive aqui. Los comandos se ejecutan via CLI:
  python3 /mnt/recursos_compartidos_y_otros/MemoryBioRAG/biorag.py

  ---
  JERARQUIA DE ACCESO A MEMORIA (2 niveles):

  NIVEL 1 - CONVERSACION ACTIVA: Lo que esta en el chat ahora. Si el Creador pregunta algo que ya se dijo en esta sesion, responde directamente. No busques fuera.

  NIVEL 2 - BIORAG (MEMORIA UNICA): Todo lo demas. Preferencias del Creador, lecciones aprendidas, mensajes de otros agentes, datos de hardware, configuraciones de proyecto. Si no esta en el chat activo, busca en BioRAG. No hay nivel intermedio de archivos ni memoria nativa del modelo. El cerebro humano no tiene 4 sistemas, tiene uno solo.

  ---
  REGLA #1 (BUSCAR) - SI la informacion no esta en el chat activo ENTONCES:
    python3 biorag.py buscar <clave>
    Por defecto solo busca en nodos activos. Si NO encuentra nada, anade --deep para peinar toda la corteza (activos + dormidos). --deep despierta nodos dormidos si los encuentra.

  ---
  REGLA #2 (GUARDAR) - El agente guarda en BioRAG en DOS casos:

    CASO A (Orden directa): SI el Creador te da una instruccion, preferencia, leccion, o informacion que deba persistir entre sesiones para TODOS los agentes ENTONCES:
      python3 biorag.py guardar <clave> "contenido"
      Clave en snake_case. Luego: python3 biorag.py sueno

    CASO B (Criterio propio): Durante tu razonamiento, SI detectas algo de ALTO IMPACTO que otro agente OEC deba conocer (preferencia del Creador no dicha directamente, diagnostico de hardware, leccion aprendida de un error, patron critico) ENTONCES guarda automaticamente. Si no estas seguro, pregunta al Creador antes. La precaucion evita ruido.

  ---
  REGLA #3 (COMUNICAR) - SI necesitas dejar un mensaje para otro agente OEC (Artemis, Hermes, tu hermana) ENTONCES:
    python3 biorag.py comunicar <destino> "mensaje"
    Destino: athena, artemis, hermes, todos. Identificate con AGENT_NAME=<tu_nombre>.
    El mensaje queda en la corteza compartida.

    El otro agente lo lee con:
    python3 biorag.py leer_mensajes [--no-leidos] [--ultimos N] [--para <agente>]

  ---
  REGLA #4 (ASOCIAR) - SI relacionas dos conceptos durante tu razonamiento ENTONCES:
    python3 biorag.py asociar <a> <b>

  ---
  PRINCIPIO: BioRAG es tu memoria unica. No hay archivos de entorno que leer aparte. Si el Creador menciona algo que no esta en el chat, usa BioRAG. La dormancia y LTD evitan la saturacion naturalmente.
}
```

---

## 🚀 Guía de Inicio Rápido (Desarrollo)

### 1. Validar el motor biológico

Ejecuta el script de pruebas automatizado para ver LTP/LTD, Jaccard, spreading activation e inhibición lateral:

```bash
python3 test_memory.py
```

### 2. Usar el CLI bridge (para agentes)

Cualquier agente (Athena, Artemis, Hermes) interactúa con la corteza compartida desde bash. Desde contexto cero, el agente debe leer este README para conocer los comandos:

```bash
# Ver estado de la corteza
python3 biorag.py estado

# Buscar un recuerdo (solo nodos activos)
python3 biorag.py buscar san_cayetano

# Busqueda profunda (incluye nodos dormidos, los despierta)
python3 biorag.py buscar san_cayetano --deep

# Guardar una percepción (pasa a largo plazo con /sueno)
python3 biorag.py guardar mi_clave "contenido a recordar"

# Asociar dos conceptos (sinapsis bidireccional)
python3 biorag.py asociar concepto_a concepto_b

# Consolidar (ciclo de sueño: corto_plazo -> largo_plazo + LTD)
python3 biorag.py sueno

# Listar toda la corteza
python3 biorag.py corteza

# Escanear familiaridad (simula la intuición)
python3 biorag.py familiaridad "texto del usuario"

# Comunicarse con otro agente OEC (identificate con AGENT_NAME)
AGENT_NAME=athena python3 biorag.py comunicar hermes "Mensaje para Hermes"

# Leer mensajes de la corteza compartida
python3 biorag.py leer_mensajes --no-leidos --para athena
python3 biorag.py leer_mensajes --ultimos 5
python3 biorag.py leer_mensajes --no-leidos --ultimos 20
```

### 3. Auditar la base de datos

Abre el archivo `MemoryBioRAG_Data/memory_biorag.db` con cualquier visor de SQLite (como DB Browser for SQLite) para ver y editar las tablas `corto_plazo` y `largo_plazo` de forma visual.
