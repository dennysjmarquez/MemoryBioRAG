# `core/memory/` — las piezas del motor de memoria

> **Para quién es esto:** cualquier persona o IA que llegue al proyecto y necesite saber **dónde está parada**.
> Regla de oro (Constitución, Pilares 9 y 10): cada pieza dice **qué es, por qué existe, qué aporta y con qué se conecta**. Si agregas, quitas o apagas un archivo, **actualiza esta tabla en el mismo cambio**.
> Las conexiones salen del código, no de la memoria: compruébalas con `python3 scripts/mapa_dependencias_core.py memory`.
> Última revisión: 2026-10-28 (auditor). Solo documenta; no cambia ningún comportamiento.

## Cómo encaja en el sistema

```
agente ──► MCP (core/mcp_server/) ──► memory_store.py (la fachada) ──► core/memory/*  ──► SQLite
                                         │
                                         └─ SQLiteMemoryBioRAG: una clase "puerta" que reparte el trabajo
                                            entre los archivos de esta carpeta
```

- **`core/memory_store.py`** (un nivel arriba) define la clase `SQLiteMemoryBioRAG`. Casi todos los archivos de aquí son funciones que reciben esa clase como `self` (el "patrón A1": se sacaron de un archivo gigante sin cambiar su lógica).
- **Dirección correcta (hexagonal):** esta carpeta **no importa nada del MCP**. El MCP depende del motor, nunca al revés.

## Las piezas, por función

### 1. Buscar y ordenar (el corazón del recuerdo)

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `search.py` (2.896 líneas) | La búsqueda completa: `buscar_por_frase` y sus capas (FTS literal, rescate simbólico, hub, sinónimos, WordNet, filtros finales, guardia de orden) | Es el camino por el que pasa **cada** recuerdo que se devuelve | `memory_store` lo llama. Importa 16 piezas: `neurona`, `escala`, `evidence_convergence`, `constants`, `concept_hub`, `fallback_simbolico`, `ppmi_hybrid_search`, `sdm`, `similitud_conceptual`, `tematica`, `srl_extractor`, `lexical_learning`, `calibracion`, `clasificador_wordnet`, `stemmer_es`, `stopwords`. Llama a `scoring` a través de la fachada (`self`) | Activo. **Monolítico**: `buscar_por_frase` se trasladó intacta (~2.100 líneas) por deuda técnica. Se dividirá en subpaquetes (Fase 2 de modularización, antes de v36) |
| `scoring.py` | La **fórmula a mano**: suma ponderada de señales (BM25, dimensiones, concepto, sinónimos, grupo WordNet, temática, PPMI, hub…) más JSD, NCD y re-ranking Jaccard | Es el **piso** del ranking: lo que garantiza el orden aunque las neuronas estén apagadas | `memory_store`. Usa `fallback_simbolico`, `stopwords`, `constants` | Activo. Los pesos a mano solo cambian con prueba y OK de Dennys |
| `evidence_convergence.py` | Bono cuando la consulta coincide en **varios campos** del recuerdo (concepto, contenido, sinónimos, sustantivos clave) | Premia la evidencia que converge, sin reglas por categoría | `search`, `mcp_server/search`. Usa `fallback_simbolico`, `stemmer_es` | Activo |
| `escala.py` | Invariancia de escala (v35.1) | Agregar recuerdos del mismo tema bajaba el recall de 100 % a ~98 % sin que los nuevos ganaran (experimento 2026-10-25). Esto lo corrige | `search` | Activo (`BIORAG_ESCALA=1` por defecto) |
| `umbral.py` | Calibración conforme y umbral de **abstención** ("no sé") | Que el motor no invente: devolver nada si no hay un recuerdo que encaje | `memory_store`. Usa `calibracion` | Activo. Pendiente E4: una base **nueva** no tiene umbral propio |
| `rafaga.py` | La **ráfaga de reminiscencia**: unos pocos recuerdos más pistas que llevan a otros | Principio P7 de la visión: recordar como un humano, hilando | `memory_store`. Usa `sdm`, `fallback_simbolico`, `constants` | Activo |

### 2. Neuronas (criterio aprendido, con piso, techo y guardianes)

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `neurona.py` | La **neurona 1**: red pequeña (29 señales → 6 → 1) que **suma** una corrección a la fórmula a mano en el top-5 | Aprende sola, en vivo, a ordenar mejor. Es **el modelo** de toda neurona del proyecto (Pilar 11) | `search`, `ingest`, `consolidation`. Usa `neurona_examen` | Activa (`BIORAG_NEURONA=1`). Ojo: una de sus entradas es `grupo_score` (WordNet); quitar WordNet le cambia una entrada |
| `neurona_examen.py` | El **autoexamen**: cada recuerdo se hace sus propias preguntas | Para aprender hace falta la respuesta correcta; al consolidar, la respuesta es ese recuerdo | `neurona`. Usa `memory_store`, `stopwords` | Activo. Tiene un filtro ASCII (`[a-z0-9_ñ]`, líneas ~190 y 197) pendiente de la E3 |
| `neurona_puentes.py` | Neurona de puentes: ¿cuánto creer un puente del hub en **esta** consulta? | Mismo molde que la neurona 1, otro trabajo | `concept_hub` | Solo actúa con `BIORAG_HUB_MOTOR=idf`, que **no** es el de fábrica (el de fábrica es "escala") |

### 3. Guardar, consolidar y dormir

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `ingest.py` | Percepción: cómo entra un recuerdo nuevo | Un solo camino de entrada, con clasificación y sinapsis | `memory_store`. Usa `consolidation`, `neurona`, `sdm`, `sinapsis` | Activo |
| `consolidation.py` | Consolidación y **ciclo de sueño**: paso de corto a largo plazo, decaimiento, clasificación WordNet, ACT-R | Como el cerebro al dormir: ordenar lo aprendido | `memory_store`, `ingest`. Usa 11 piezas (`neurona`, `ppmi_vectorizer`, `sinapsis`, `sdm`, `clasificador_wordnet`, `auto_clustering`, `dmn_engine`…) | Activo. `ciclo_sueno_consolidacion` sigue monolítica (deuda Spec 003) |
| `quarantine.py` | Cuarentena y retiro de recuerdos | Apartar sin borrar a ciegas | `memory_store` | Activo |
| `episodes.py` | Memoria episódica y cercanía en el tiempo | Recuerdos que ocurrieron juntos se ayudan | `memory_store` | Activo |

### 4. Grafo, contexto y catálogo

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `synapses.py` | Operaciones del grafo de sinapsis: crear enlaces, refuerzo dopaminérgico, caminos, BFS | Las asociaciones entre recuerdos | `memory_store`. Usa `sinapsis`, `sdm` | Activo |
| `context.py` | Contexto epistémico y coherencia de dimensiones | Saber "qué tan seguro" y "de qué tipo" es un recuerdo | `memory_store`. Usa `dmn_reflexion` | Activo |
| `dmn.py` | Puente a la Red por Defecto (DMN) | Exploración en reposo | `memory_store`. Usa `dmn_engine` | Activo |
| `adn.py` | Integración con el ADN conceptual | Búsqueda por "esencia" (cromosomas del grafo) | `memory_store` | Activo |
| `catalog_methods.py` | Categorías y dimensiones: catálogo y sincronización | Las etiquetas que el agente usa al guardar | `memory_store` | Activo. Los valores de dimensión no latinos se descartan con aviso (pendiente E3) |
| `schema.py` (1.196 líneas) | Tablas SQLite, FTS5, migraciones | La forma de la base | `memory_store`. Usa `concept_hub`, `sinapsis`, `lexical_learning` | Activo. `_crear_estructura_cerebral` se trasladó intacta (deuda) |
| `constants.py` | Constantes, interruptores `BIORAG_*` y funciones puras | Un solo lugar para los parámetros | 11 archivos | Activo. Lee 63 de los ~200 interruptores `BIORAG_*` que hay en `core/` |

### 5. Apoyo

| Archivo | Qué es | Se conecta con | Estado |
|---|---|---|---|
| `comms.py` | Mensajes entre agentes (tablón) | `memory_store` | Activo |
| `telemetry.py` | Telemetría, benchmark e historial forense | `memory_store` | Activo |
| `__init__.py` | Marca el paquete | — | Vacío |

## Lo que falta (anotado para la Fase 2 de modularización)

- `search.py` y `schema.py` son monolíticos; `memory_store.py` depende de **25** archivos (es la puerta de todo).
- Propuesta de subpaquetes (la hará el operador, un paquete por cambio, con la QA **idéntica**): `busqueda/`, `ranking/`, `neuronas/` (aquí iría también `core/neurona_asociativa.py`), `sueno/`.
- Las piezas atadas al idioma (`stemmer_es`, `stopwords`, `fallback_simbolico`, `clasificador_wordnet`) irían a un **puerto de idioma** en `core/lexico/` (visión §2p y §2t).
