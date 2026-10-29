# `core/` — el cerebro de BioRAG: mapa para orientarse

> **Para quién es esto:** cualquier persona (aunque sepa poco de programación) o cualquier IA que llegue a auditar o a trabajar, para saber **dónde está parada**.
> Regla de oro (Constitución, Pilares 9, 10 y 11): **nada monolítico, poco acoplamiento, mentalidad hexagonal**, y cada pieza documentada con **qué es, por qué existe, qué aporta y con qué se conecta**. Si agregas, quitas, apagas o mueves un archivo, **actualiza este mapa en el mismo cambio**, y si lo quitas, escribe **por qué**.
> Las conexiones salen del código, no de la memoria: `python3 scripts/mapa_dependencias_core.py` (todas) o `… --huerfanos` (las que nadie usa).
> Última revisión: 2026-10-28 (auditor). Solo documenta; no cambia ningún comportamiento.

## La idea en una frase

**BioRAG es un cerebro, no una base vectorial.** El agente piensa y trata de recordar; el cerebro recibe ese empuje y devuelve el recuerdo que mejor encaja, rápido y sin inventar. Un motor fijo y rápido (SQLite + Python) hace casi todo, y unas pocas **neuronas** pequeñas, con piso, techo y guardianes, ponen criterio donde una fórmula no alcanza. Visión completa: `docs/Mi neurona en el sistema/vision_como_recuerda_biorag/README.md`.

## Las tres carpetas

| Carpeta | Qué es | Su mapa |
|---|---|---|
| `core/mcp_server/` | **La puerta del agente.** Convierte el cerebro en herramientas MCP (`biorag_recordar`, `biorag_aprender`…). Es un adaptador: valida y traduce | [`mcp_server/README.md`](mcp_server/README.md) |
| `core/memory/` | **El motor de memoria.** Buscar, ordenar, guardar, consolidar, neuronas | [`memory/README.md`](memory/README.md) |
| `core/` (este nivel) | **Piezas de apoyo** que el motor usa: idioma, significado, grafo, sueño, certeza | Este archivo |

```
agente ─► core/mcp_server/ ─► core/memory_store.py (fachada) ─► core/memory/* ─► SQLite
                                            │
                                            └─► piezas de apoyo de core/ (idioma, significado, grafo, sueño…)
```

**Lo que ya está bien (medido el 2026-10-28):** 73 archivos, 186 conexiones internas, **ninguna conexión circular**, y el motor **no depende del MCP** (dirección hexagonal correcta).

## Las piezas de este nivel, por función

### Puerta y rutas

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `memory_store.py` | La clase `SQLiteMemoryBioRAG`: la **fachada** del motor | Un solo objeto por el que entra todo; reparte el trabajo entre `core/memory/*` | Usa **25** archivos. Lo usan el MCP, `memory_service`, `dmn_reflexion`, `neurona_examen` y 146 archivos fuera de `core/` (scripts, tests, raíz) | Activo. Es el punto más acoplado del sistema (deuda) |
| `memory_service.py` | Servicio único de lectura/escritura para MCP, CLI y dashboard | El dashboard escribía SQL crudo y se saltaba el motor. Esto obliga a todos a pasar por las mismas primitivas | `memory_store`, `lexical_learning`, `ppmi_hybrid_search`, `paths` | Activo |
| `paths.py` | Dónde está la base de datos | Antes cada interfaz calculaba la ruta por su cuenta y había bases divergentes. Una sola fuente de verdad | 5 archivos | Activo (`BIORAG_PATH`) |

### Idioma y léxico — **futuro "puerto de idioma"** (E3: el cerebro no debe depender de un idioma)

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `identidad_unicode.py` | Identidad compartida: NFC y ancho U+FF00–FFEF; en contenido/sinónimos solo ancho de letras y números | Unir formas equivalentes sin quitar marcas; preservar signos y U+3000 en contenido/sinónimos y su fusión | `memory/search`, `memory/ingest`, `memory/consolidation`, `memory/constants`, `memory_service`, `concept_hub` y MCP | Propuesta E3 v2, pendiente de aprobación y QA; no migra datos. Investigación: `docs/e3_unicode_identidad_investigacion_20261028.md` |
| `stemmer_es.py` | Reduce palabras a su raíz (Snowball español e inglés) | Que "versión" y "versiones" se unan | Lo usan **11** archivos | Activo. **Solo es/en** |
| `stopwords.py` | Listas de palabras vacías (conectores) | Que "de", "la", "the" no cuenten como contenido | Lo usan **12** archivos | Activo. **Solo es/en** |
| `fallback_simbolico.py` | Rescate cuando la búsqueda literal falla: tokenizador, Levenshtein (tipeo), WordNet | Recuperar con errores de tipeo o variantes | `search`, `scoring`, `rafaga`, `evidence_convergence`, `ppmi_hybrid_search` | Activo. Quita tildes (NFKD) pensando en escritura latina |
| `clasificador_wordnet.py` | Clasifica palabras en grupos de sentido WordNet (*lexnames*) | Alimenta la señal `grupo_score` (fórmula y neurona 1) | 5 archivos | Activo. Centrado en inglés; su aporte se medirá sitio por sitio (visión §2t) |
| `lexical_learning.py` | Aprende "la expresión A, en este contexto, se refiere al recuerdo B" | Generar candidatos antes del ranking sin diccionario global | `search`, `schema`, `memory_service` | Activo |
| `srl_extractor.py` | Extrae sujeto/acción/objeto con reglas | Señal de predicados para la búsqueda | `search` | Activo. **Reglas y verbos en español** |
| `categorizador.py` | Sugiere categoría por palabras clave fijas | Ayuda a categorizar al guardar | `mcp_server/write` | Activo. ⚠️ **Lista fija de palabras en español** (choca con el Pilar 6, "nunca vocabularios fijos", y con la E3). Anotado para revisar |

### Significado, asociación y grafo

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `pmi_semantico.py` | Fuerza de asociación entre palabras (PMI/NPMI, Church & Hanks 1990) | Saber qué palabras van juntas **en tu memoria** | 7 archivos | Activo |
| `ppmi_vectorizer.py` | Construye la representación PPMI+SVD de la memoria | Significado aprendido del propio corpus, sin modelos preentrenados | `consolidation` | Activo |
| `ppmi_hybrid_search.py` | Búsqueda híbrida PPMI+SVD + rareza (IDF) | Encontrar por significado cercano, no solo por palabra | 7 archivos | Activo |
| `sdm.py` | Memoria distribuida dispersa (vectores binarios de 2048 bits) | Asociación por patrones de dimensiones | Lo usan **11** archivos | Activo |
| `sinapsis.py` | Crea y pondera sinapsis entre recuerdos | El grafo de asociaciones | 8 archivos | Activo. Su tokenizador es latino (`[a-zA-Záéíóúñ]{4,}`) y tiene una lista fija de siglas técnicas: pendiente E3 |
| `similitud_conceptual.py` | Similitud por vecinos compartidos en el grafo | Funciona desde el día uno, sin entrenamiento | `search` | Activo |
| `inferencia_transitiva.py` | Relaciones indirectas (A→B→C) por caminos del grafo | Encontrar lo que se conecta por un intermediario | `consolidation`, `similitud_conceptual` | Activo |
| `tematica.py` | Similitud temática por presencia **y ausencia** de dimensiones | Captar "de qué habla" un recuerdo | `search` | Activo |
| `concept_hub.py` (1.448 líneas) | **Hubs de concepto**: puentes para encontrar un recuerdo sin palabras en común; también valida los 5 puentes al guardar | Resolver el "abismo léxico" | `search`, `schema`, `mcp_server/write`, `mcp_server/concept_hub_tools`. Usa `neurona_puentes` | Activo. Motor de fábrica "escala" (v35.2); "idf" con `BIORAG_HUB_MOTOR=idf` |
| `adn_conceptual.py` | "Cromosomas" del grafo: grupos descubiertos por la topología | Búsqueda por esencia | `memory_store`, `dmn_engine`, `hipotesis_teleologica` | Activo |
| `auto_clustering.py` | Detecta comunidades en el grafo | Base del ADN conceptual y de dimensiones emergentes | `adn_conceptual`, `consolidation` | Activo |

### Certeza

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `calibracion.py` | Platt, isotónica, umbral conforme, MMR | Convertir puntajes en certeza y saber cuándo callar | `search`, `umbral`, `memory_store` | Activo |

### Sueño, reposo y mantenimiento

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `dmn_engine.py` | Red por Defecto (DMN): explorar asociaciones en reposo | "Curiosidad" del cerebro cuando no se le pregunta nada | `consolidation`, `memory/dmn`, `memory_store` | Activo |
| `neocortex_teleologico.py` | Autoconocimiento: "sabe lo que sabe y lo que no sabe" | Razonar por significado y detectar huecos | `dmn_engine`, `memory_store` | Activo |
| `dmn_reflexion.py` (2.161 líneas) | La **hormiguita** (mantenimiento del grafo) + reflexión con un LLM externo (Gemini) | Cuidar las sinapsis en segundo plano | `mcp_server/daemon`, `memory/context`, `sueno_vacios` | ⚠️ La hormiguita está **decidida para quitarse** (apagarla mejoró la QA, experimento 13). Usa un LLM externo opcional (claves `GEMINI_API_KEY*`) |
| `sueno_vacios.py` | Consolida "vacíos" (preguntas sin respuesta) durante el sueño | Proponer hipótesis prudentes donde falta conocimiento | Lo llama `sleep_cycle.py` (raíz) | Activo solo vía el ciclo de sueño |
| `daemon_lifecycle.py` | Mantiene vivo el proceso de la hormiguita | Que el mantenimiento sobreviva al cierre del MCP | `mcp_server/server` | Activo (ligado a la hormiguita) |

### Neuronas de este nivel

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `neurona_asociativa.py` | Neurona 2: ¿dos recuerdos de verdad tienen que ver? (fuerza 0–1) | Juzgar enlaces; reemplazo propuesto de la hormiguita | **Nadie la llama** (a propósito) | Construida, calibrada y **cerrada**, pero **sin cablear**. Se probó como peso de nacimiento: QA idéntica → revertida (76fe11c). Cortar enlaces al nacer baja el recall (exp. 13). Lugar pendiente: elegir qué asociaciones ve el agente (canal 2). Irá a `core/memory/neuronas/` |

### Sin uso en el sistema (huérfanos: revisar, **no borrar sin decisión**)

| Archivo | Qué es | Qué se sabe | Siguiente paso |
|---|---|---|---|
| `rrf_fusion.py` | Fusión RRF + pesos dinámicos | **Nadie lo importa** (ni motor, ni scripts, ni tests) | Averiguar en git por qué quedó; documentar y decidir |
| `hipotesis_teleologica.py` | Hipótesis autónomas sobre el ADN conceptual | **Nadie lo importa**; hay una copia en `docs/¿Cuál es la Meta Final…/` | Igual |
| `feedback_implicito.py` | Deduce si una búsqueda fue útil sin preguntar | Solo lo usa un script de diagnóstico (`scripts/verificar_contaminacion_log.py`). Dennys decidió **no** tener sistemas de feedback en producción | Mantener solo como diagnóstico, o retirar con explicación |

## Lo que falta (Fase 2 de modularización, antes de v36)

1. **Puerto de idioma** (`core/lexico/`): `stemmer_es`, `stopwords`, la parte léxica de `fallback_simbolico`, `clasificador_wordnet`, `srl_extractor`, `categorizador`, como **adaptadores enchufables** (es/en hoy; cualquier idioma mañana).
2. **Subpaquetes en `core/memory/`**: `busqueda/`, `ranking/`, `neuronas/`, `sueno/` (ver su README).
3. **Agrupar este nivel**: significado/grafo, sueño/mantenimiento.
4. **Reglas para hacerlo:** lo hace el operador, **un paquete por cambio**; la ruta vieja queda como "puente" para no romper imports; las 4 QA deben dar **exactamente lo mismo** (mover código no cambia resultados); este mapa se actualiza en el mismo cambio.
