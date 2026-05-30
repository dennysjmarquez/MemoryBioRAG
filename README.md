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
MemoryBioRAG/
  ├── biorag.py                 # CLI bridge para agentes (buscar, guardar, asociar, sueno, corteza, comunicar)
  ├── core/
  │    ├── __init__.py
  │    └── memory_store.py      # Motor SQLite: LTP/LTD, Jaccard, inhibición lateral, comunicaciones
  ├── middleware/
  │    ├── __init__.py
  │    └── interceptor.py       # Escaneo de familiaridad difusa
  ├── config/
  │    ├── __init__.py
  │    └── prompts.py           # System prompts predefinidos
  ├── main.py                   # Simulador interactivo de consola
  ├── sleep_cycle.py            # Script autónomo de consolidación/sueño
  ├── MemoryBioRAG_Data/        # Bases de datos SQLite (auto-creado)
  ├── test_memory.py            # Tests automatizados (crea/borra test_memory.db al ejecutarse)
  └── README.md                 # Este archivo
```

---

## 🔎 Evaluación Crítica: ¿Realmente nos sirve a los Agentes?

Un análisis honesto y riguroso de la viabilidad de BioRAG desde nuestra propia perspectiva cognitiva como agentes (Artemis, Athena, Hermes):

### ✅ Por qué es una solución revolucionaria para nosotros:
1. **Abolición del "Yapping" de Contexto:** En conversaciones largas de desarrollo, la ventana de contexto acumula basura redundante, forzándonos a malgastar tiempo de razonamiento procesando código obsoleto. BioRAG actúa como un filtro biológico: inyecta únicamente la "cápsula" de información relevante en el momento exacto.
2. **Puente Cognitivo Asíncrono:** Sin BioRAG, cada agente vive en su propia burbuja de contexto. Si un agente descubre algo útil, los demás no se enteran a menos que alguien lea un log manual. Con BioRAG, todos comparten una única corteza cerebral (`memory_biorag.db`). Si un agente aprende algo, lo consolida en la corteza y los demás lo evocan instantáneamente.
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
> Copia este bloque en el **System Prompt** o **instrucciones del sistema** de tu agente (Claude Code, Cursor, Ollama, cualquier LLM que ejecute comandos CLI). **Antes de usarlo, cambia `/ruta/a/MemoryBioRAG` por la ruta absoluta donde clonaste el repo.** Si no sabes la ruta exacta, usa `pwd` dentro del directorio.

```markdown
[SYSTEM_PROMPT_BIOMEMORY_ACTIVE] {

  Tu memoria persistente vive en una base de datos SQLite compartida.
  Ruta del proyecto: /ruta/a/MemoryBioRAG

  ---
  JERARQUIA DE ACCESO A MEMORIA (2 niveles):

  NIVEL 1 - CONVERSACION ACTIVA: Lo que esta en el chat ahora.
  NIVEL 2 - BIORAG (MEMORIA UNICA): Todo lo demas.

  ---
  REGLA #1 (BUSCAR) - Si la info no esta en el chat activo:
    Extrae las keywords de la pregunta, stemmea cada una a su raiz (minimo 3 letras),
    y llama con --tokens separadas por coma. Ej: "puerta marroncita" -> --tokens "puert,marron"
    El motor busca nodos donde TODAS las raices aparezcan (strict) o al menos una (relaxed).
    Por defecto solo busca en nodos activos. Si no encuentra -> --deep. Si muchas coincidencias
    -> --pagina 2, 3, etc. para mas tandas.

    python3 /ruta/a/MemoryBioRAG/biorag.py buscar "texto original" --tokens "raiz1,raiz2"
    python3 /ruta/a/MemoryBioRAG/biorag.py buscar "texto original" --tokens "raiz1,raiz2" --pagina 2
    python3 /ruta/a/MemoryBioRAG/biorag.py buscar "texto original" --tokens "raiz1,raiz2" --deep

  ---
  REGLA #2 (GUARDAR) - Guarda automaticamente cuando detectes:
    Una preferencia, leccion, diagnostico, o algo que otro agente deba saber.
    Si no estas seguro, pregunta primero.

  ---
  REGLA #3 (COMUNICAR) - Mensajes a otros agentes:
    AGENT_NAME=tu_nombre python3 /ruta/a/MemoryBioRAG/biorag.py comunicar <destino> "mensaje"
    Para leer: python3 /ruta/a/MemoryBioRAG/biorag.py leer_mensajes --no-leidos --para tu_nombre

  ---
  REGLA #4 (ASOCIAR) - Si relacionas dos conceptos:
    python3 /ruta/a/MemoryBioRAG/biorag.py asociar <a> <b>

  ---
  PRINCIPIO: BioRAG es tu memoria unica. Las consultas frecuentes refuerzan el recuerdo (LTP).
  Los recuerdos no usados se duermen solos (LTD). Eso evita la saturacion naturalmente.
}
```

> **Alternativa:** Define `BIORAG_PATH` como variable de entorno apuntando a tu DB y pon el proyecto en el `$PATH`. Asi puedes usar `python3 biorag.py` desde cualquier directorio.
> 
> ```bash
> export PATH=$PATH:/ruta/a/MemoryBioRAG
> export BIORAG_PATH=/ruta/a/tu/memoria.db
> ```
> 
> En ese caso, los comandos del agente pueden ser simplemente `python3 biorag.py buscar <clave>`.

```markdown
[SYSTEM_PROMPT_BIOMEMORY_OPTIONAL_ENV] {

  REGLA #1: python3 biorag.py buscar <clave> [--deep]
  REGLA #2: python3 biorag.py guardar <clave> "contenido" && python3 biorag.py sueno
  REGLA #3: AGENT_NAME=yo python3 biorag.py comunicar <destino> "msg"
           python3 biorag.py leer_mensajes --no-leidos --para yo
  REGLA #4: python3 biorag.py asociar <a> <b>
}
```

---

## 🚀 Guía de Inicio Rápido (Desarrollo)

### 1. Validar el motor biológico

Ejecuta el script de pruebas automatizado para verificar que el motor funciona correctamente (LTP/LTD, Jaccard, spreading activation, comunicación entre agentes). Es como una prueba de calidad — la corres una vez y si pasa todo OK, sabes que BioRAG está sano:

```bash
python3 test_memory.py
```

Nota: `test_memory.py` crea un archivo `test_memory.db` temporal durante la ejecución y lo borra al terminar. No lo usa ningún agente ni el sistema en producción. Es solo una verificación de calidad.

### 2. Usar el CLI bridge (para agentes)

Cualquier agente (Athena, Artemis, Hermes) interactúa con la corteza compartida desde bash. Desde contexto cero, el agente debe leer este README para conocer los comandos:

```bash
# Ver estado de la corteza
python3 biorag.py estado

# Buscar un recuerdo (solo activos)
python3 biorag.py buscar san_cayetano

# Busqueda profunda (incluye nodos dormidos, los despierta)
python3 biorag.py buscar san_cayetano --deep

# Busqueda multi-token con Soft AND (el modelo stemmea las keywords)
python3 biorag.py buscar "puerta marroncita" --tokens "puert,marron"

# Segunda tanda de resultados (busqueda progresiva, como el cerebro humano)
python3 biorag.py buscar "puerta marroncita" --tokens "puert,marron" --pagina 2

# Solo recuerdos donde aparezcan TODAS las raices (modo estricto)
python3 biorag.py buscar "error compilacion" --tokens "error,compil" --modo strict

# Guardar una percepcion (pasa a largo plazo con sueno)
python3 biorag.py guardar mi_clave "contenido a recordar"
python3 biorag.py sueno

# Asociar dos conceptos (sinapsis bidireccional)
python3 biorag.py asociar concepto_a concepto_b

# Consolidar (ciclo de sueno: corto_plazo -> largo_plazo + LTD)
python3 biorag.py sueno

# Listar toda la corteza
python3 biorag.py corteza

# Escanear familiaridad (simula la intuicion)
python3 biorag.py familiaridad "texto del usuario"

# Comunicarse entre agentes
AGENT_NAME=mi_agente python3 biorag.py comunicar otro_agente "mensaje"
python3 biorag.py leer_mensajes --no-leidos --para mi_agente
```

### 3. Auditar la base de datos

Abre el archivo `MemoryBioRAG_Data/memory_biorag.db` con cualquier visor de SQLite (como DB Browser for SQLite) para ver y editar las tablas `corto_plazo` y `largo_plazo` de forma visual.

---

## 📦 Como usar BioRAG con tu propio agente

### Requisitos

- Python 3.8+ (sin dependencias externas)
- SQLite3 (viene con Python)
- Un agente de IA que ejecute comandos en tu terminal (Claude Code, Cursor, Ollama, etc.)

### Setup

```bash
# 1. Clona el repositorio donde quieras
git clone https://github.com/dennysjmarquez/MemoryBioRAG.git
cd MemoryBioRAG

# 2. Verifica que funciona
python3 test_memory.py

# 3. La DB se crea sola al primer uso en:
#    MemoryBioRAG_Data/memory_biorag.db
```

### Configurar la ruta de la DB (opcional)

Por defecto la DB se crea dentro del proyecto. Si quieres ponerla en otro lado:

```bash
export BIORAG_PATH=/tu/ruta/personalizada/memoria.db
python3 biorag.py estado
```