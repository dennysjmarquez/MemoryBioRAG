# Informe Oficial: Fase 3 — Auditoría del Conocimiento Relacional Existente en MemoryBioRAG

**Fecha**: 2026-09-05  
**Snapshot auditado**: `snapshots/qa_escape_qcr_20260811.db` (Modo `READ-ONLY`)  
**Hash JSON de Datos Crudos**: `366a562922654813a5bd3d11c33f76971c833c3db2ff46fc3e5843a858dc901f` (`docs/fase3_grafo_relacional_auditoria.json`)  
**Script de Extracción**: `scripts/audit_fase3_grafo.py`  

---

## 1. Inventario del Grafo Actual

MemoryBioRAG almacena su estructura de conocimiento en un conjunto de tablas relacionales en SQLite:

| Tabla | Rol en el Sistema | Nº Registros | Columnas Clave | Provenance / Mecanismo de Creación |
| :--- | :--- | :---: | :--- | :--- |
| `largo_plazo` | Nodos de memoria canónicos | **866** | `id`, `concepto`, `categoria`, `contenido`, `resumen`, `creado_en` | Ingestión vía `aprender` (MCP) |
| `sinapsis` | Grafo sináptico explícito/asociativo | **13,848** | `origen`, `destino`, `peso`, `tipo`, `creado_en`, `ultimo_uso` | Ingestión (`sinonimo_explicito`, `manual`), Consolidación Hebbiana (`pmi_hebbiano`, `co_ocurrencia`), Co-dimensiones (`co_semantica`) |
| `sinapsis_latentes` | Aristas candidatas a 2 saltos | **8,893** | `origen`, `destino`, `peso_atenuado`, `saltos`, `pmi_score`, `tiene_dim_comun` | Calculadas en background por el daemon de consolidación (`sleep_cycle.py`) |
| `predicados` | Tripletas de extracción (S-V-O) | **187** | `id`, `concepto`, `sujeto`, `accion`, `objeto`, `contexto` | Extracción heurística SRL / metacognitiva |
| `largo_plazo_dimensiones` | Asignación de dimensiones | **5,535** | `concepto`, `dimension_id` | Clasificador dimensional de corteza (13 ejes) |
| `dimensiones_semanticas` | Catálogo de dimensiones | **104** | `id`, `name`, `description`, `tipo_id`, `confianza` | Catálogo ontológico base + auto-generadas |
| `nodo_grupos_semanticos` | Mapeo léxico a WordNet synsets | **101,028** | `concepto`, `palabra`, `grupo_id` | Indexación léxica de supersentidos WordNet |
| `grupos_semanticos` | Supersentidos WordNet | **63** | `id`, `nombre`, `fuente`, `descripcion` | Ontología estática WordNet (`noun.artifact`, etc.) |
| `concept_hubs` / `bridges` | Puentes Concept Hub | **0 bridges** | `hub_id`, `bridge_text`, `angle`, `weight` | Creados vía herramientas `concept_hub_*` |

---

## 2. Inventario de Tipos Relacionales

### A. Tipos de Aristas en `sinapsis` (13,848 Aristas)

| Relación | Existe | Nº Aristas | Peso Promedio | Rango Peso | Provenance / Mecanismo de Generación |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `sinonimo_explicito` | **SÍ** | **5,863** | 0.876 | [0.05, 0.93] | Extraído de links Markdown `[[...]]`, alias explícitos en `aprender()` |
| `pmi_hebbiano` | **SÍ** | **2,359** | 0.502 | [0.05, 0.96] | Calculado por daemon mediante Pointwise Mutual Information de co-búsquedas |
| `co_ocurrencia` | **SÍ** | **2,108** | 0.674 | [0.07, 1.00] | Nodos guardados o leídos juntos en la misma sesión/ventana temporal |
| `co_nombre` | **SÍ** | **1,558** | 0.419 | [0.05, 1.00] | Nodos que comparten tokens/prefijos en su slug (`biorag_*`, `v8_*`) |
| `co_semantica` | **SÍ** | **1,226** | 0.569 | [0.07, 1.00] | Nodos que comparten $\ge 3$ dimensiones semánticas en `largo_plazo_dimensiones` |
| `manual` | **SÍ** | **575** | 0.503 | [0.06, 0.90] | Creadas explícitamente vía herramienta `vincular(origen, destino)` |
| `latente_confirmada` | **SÍ** | **120** | 0.404 | [0.40, 0.44] | Promovidas desde `sinapsis_latentes` tras validación en búsquedas reales |
| `legacy_csv` | **SÍ** | **25** | 0.500 | [0.50, 0.50] | Importación de memoria pre-v10 |
| `manual_v7` | **SÍ** | **13** | 0.715 | [0.70, 0.90] | Vínculos históricos de la v7 |
| `test` | **SÍ** | **1** | 0.900 | [0.90, 0.90] | Arista de prueba unitaria |

### B. Relaciones Semánticas Ontológicas Faltantes

| Relación Semántica Estructural | ¿Existe como tipo de arista en `sinapsis`? | Estado Actual en MemoryBioRAG |
| :--- | :---: | :--- |
| `ES_UN` (Hiperonimia / Taxonomía) | **NO** | No tipada; absorbida genéricamente en `co_semantica` o `sinonimo_explicito` |
| `PARTE_DE` (Meronimia / Componente) | **NO** | No tipada; implícita en texto o en `co_nombre` |
| `RESUELVE` (Solución $\rightarrow$ Bug/Problema) | **NO** | Implícita en texto (`PROBLEMA: ... SOLUCIÓN:`) y en `predicados` (`corrigio`) |
| `PROVOCA` (Causa $\rightarrow$ Efecto) | **NO** | Ausente del grafo sináptico |
| `REQUIERE` (Prerrequisito / Dependencia) | **NO** | Implícita en texto de reglas y protocolos (`ANTES:`, `debo`) |
| `EJEMPLO_DE` (Instanciación) | **NO** | No tipada |
| `CONTRASTA_CON` (Comparativa / Antinomia) | **NO** | Implícita en benchmarks (`ANTES: ... DESPUÉS:`) |

---

## 3. Auditoría Específica de los 8 Casos Type-2 (Brecha Asociativa)

Para cada uno de los 8 casos que fallan en el benchmark QA por brecha asociativa, se rastreó la conectividad en el grafo sináptico desde las semillas léxicas de la consulta hasta el nodo `gold`:

| Caso | Query | Gold | ¿Es Semilla Directa (0 saltos)? | Camino más corto en Grafo | Saltos | Peso Acumulado | Tipos de Aristas en Ruta |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| **0497** | `relevantes biomimética mejor` | `benchmark_antes_despues_fix3` | **SÍ (0-hop)** | `benchmark_antes_despues_fix3` | **0** | 1.000 | Coincidencia léxica directa en texto |
| **0516** | `real más sistemas` | `dennys-identidad-profunda` | **SÍ (0-hop)** | `dennys-identidad-profunda` | **0** | 1.000 | Coincidencia léxica directa en texto |
| **0534** | `activa largo archivos` | `biorag_v11_1_detalle_tecnico` | NO | `oracle_sintesis...` $\rightarrow$ `ajuste_tejedora...` $\rightarrow$ `biorag_v11_1...` | **2** | 0.648 | `sinonimo_explicito_rev` (0.72) $\rightarrow$ `sinonimo_explicito` (0.90) |
| **0583** | `debo biorag preacción` | `identificacion_obligatoria_oraculo_athena` | **SÍ (0-hop)** | `identificacion_obligatoria_oraculo_athena` | **0** | 1.000 | Coincidencia léxica directa en texto |
| **0640** | `ráfaga después resultado` | `mentalidad_biorag_para_agentes` | NO | `biorag_v8_glosario...` $\rightarrow$ `leccion_motivacion...` $\rightarrow$ `mentalidad_biorag...` | **2** | 0.648 | `sinonimo_explicito_rev` (0.72) $\rightarrow$ `sinonimo_explicito` (0.90) |
| **0724** | `learning paso regla` | `protocolo_autoinferencia_metacognitiva` | **SÍ (0-hop)** | `protocolo_autoinferencia_metacognitiva` | **0** | 1.000 | Coincidencia léxica directa en texto |
| **0795** | `insert storepy comunicadosdestino` | `fix_mensajeria_broadcast_tracking_por_agente` | NO | `v13_2_limpieza_tabla_semantica` $\rightarrow$ `fix_mensajeria_broadcast...` | **1** | 0.720 | `sinonimo_explicito_rev` (0.72) |
| **0801** | `datos lecciones postsync` | `notebooklm-memory-biorag-project` | **SÍ (0-hop)** | `notebooklm-memory-biorag-project` | **0** | 1.000 | Coincidencia léxica directa en texto |

### Hallazgo Fundamental sobre los 8 Casos:
- **5 de los 8 casos (62.5%)** ya son **semillas directas (0 saltos)**: el nodo `gold` contiene tokens de la query en su texto o título, pero FTS/BM25 lo clasifica entre las posiciones 6 y 25 porque otros nodos en el corpus tienen mayor solapamiento superficial.
- **1 caso (12.5%)** está conectado a **1 salto** (`0795`).
- **2 casos (25.0%)** están conectados a **2 saltos** (`0534` y `0640`).
- **El 100% de los 8 casos Type-2 tiene camino relacional existente a $\le 2$ saltos**.

---

## 4. Clasificación de Causas Raíz para los 24 Fallos del Baseline v30.2

Se auditó la totalidad de los 24 fallos residuales de la versión oficial v30.2 bajo las 6 categorías estructurales:

| Categoría | Descripción Causal | Casos Afectados | % del Total | Casos Específicos |
| :---: | :--- | :---: | :---: | :--- |
| **A** | Existe ruta relacional suficiente en grafo ($\le 2$ saltos) | **3** | 12.5% | `0534`, `0640`, `0795` |
| **B** | Existe grafo pero falta una relación clave | **4** | 16.7% | `0744`, `0763`, `0848`, `0862` |
| **C** | Existe relación/nodo pero peso o ranking actual lo diluye | **5** | 20.8% | `0497`, `0516`, `0583`, `0724`, `0801` |
| **D** | No existe conocimiento relacional / Ambigüedad en dataset | **2** | 8.3% | `0012`, `0035` |
| **E** | Problema principalmente lingüístico/morfológico (stemming/typo) | **4** | 16.7% | `0518`, `0560`, `0666`, `0803` |
| **F** | Polisemia / Ambigüedad de término genérico | **6** | 25.0% | `0489`, `0493`, `0504`, `0528`, `0768`, `0771` |

---

## 5. Auditoría de Spreading Activation y el "Efecto Atractor de Hubs"

### Top-10 Nodos Hub por Grado de Entrada (`In-Degree`) en el Snapshot:
1. `research-pipeline-ownership-oec` — In-degree: **55**
2. `dennys-working-style` — In-degree: **49**
3. `perfil_respuesta_experiencia_ia` — In-degree: **47**
4. `bio_rag_overview_completo` — In-degree: **45**
5. `identidad_dennys_perfil_completo` — In-degree: **44**
6. `hermes_agente_hermes` — In-degree: **42**
7. `notebooklm-memory-biorag-project` — In-degree: **40**
8. `juramento_athena_verdad` — In-degree: **38**
9. `auto-consulta-permanente-biorag` — In-degree: **37**
10. `athena_alma` — In-degree: **36**

### Diagnóstico Físico del Fallo en Spreading Activation (1/8 Top-5):
En el prototipo previo, Spreading Activation operaba mediante propagación de energía sin normalización por grado de entrada:
$$E_{t+1}(v) = \gamma E_t(v) + \sum_{u \in N(v)} w(u,v) \cdot E_t(u)$$
Debido a que nodos como `research-pipeline-ownership-oec` tienen 55 conexiones entrantes, cualquier conjunto de semillas a 2 saltos canaliza múltiples flujos convergentes de energía hacia estos hubs, elevando su score artificialmente a $> 25.0$ y monopolizando el Top-5.
Para que Spreading Activation funcione, la propagación debe incluir **normalización simétrica por grado (tipo Graph Convolution / PageRank Personalizado)**:
$$W_{\text{norm}}(u,v) = \frac{w(u,v)}{\sqrt{\text{deg}(u) \cdot \text{deg}(v)}}$$

---

## 6. Conocimiento Relacional Implícito en el Corpus

Se constató que existen cientos de relaciones estructuradas actualmente atrapadas en forma de texto y nomenclatura:

1. **Patrones Problema-Solución en Contenido**: **48 nodos** contienen encabezados explícitos del tipo `PROBLEMA: ... SOLUCIÓN:` o `POR QUÉ SE HIZO:`, equivalentes a la relación `RESUELVE(nodo_fix, nodo_problema)`.
2. **Patrones de Regla / Protocolo**: **142 nodos** contienen declaraciones explícitas `REGLA: ...` o `PROTOCOLO: ...`, equivalentes a `TIENE_NORMA(dominio, nodo_regla)`.
3. **Patrones de Benchmark Antes/Después**: **18 nodos** contienen tablas comparativas `ANTES: ... DESPUÉS:`, equivalentes a `EVALUA_OPTIMIZACION(nodo_benchmark, nodo_modulo)`.
4. **Nombres de Concepto Prefijados**: **114 nodos** usan prefijos taxonómicos deterministas (`fix_*`, `leccion_*`, `principio_*`, `protocolo_*`).

---

## 7. Propuesta de Estructura Mínima de Arista Relacional

Estructura de tupla relacional formal:
$$\mathbf{e} = (\text{source}, \text{relation\_type}, \text{target}, \text{weight}, \text{provenance}, \text{confidence})$$

| Tipo de Relación (`relation_type`) | Método de Extracción | Portabilidad | Riesgo de Leakage |
| :--- | :--- | :---: | :---: |
| `ES_UN` | Mapeo determinista por dimensión de corteza + WordNet | **Universal** | Nulo |
| `PARTE_DE` | Extracción de prefijos/módulos en slugs y Markdown links | **Universal** | Nulo |
| `RESUELVE` | Parser determinista de secciones `PROBLEMA/SOLUCIÓN` | **Universal** | Nulo |
| `REQUIERE` | Detección de patrones de prerrequisito (`antes de`, `depende de`) | **Universal** | Nulo |
| `EVALUA` | Parser de métricas y bloques `ANTES/DESPUÉS` | **Universal** | Nulo |
| `EJEMPLO_DE` | Parser de bloques `EJEMPLO:` o links bidireccionales | **Universal** | Nulo |

---

## 8. Respuesta Empírica a la Pregunta Fundamental

> **¿Los 8 casos Type-2 fallan porque MemoryBioRAG no posee las relaciones necesarias, o porque posee relaciones que el recuperador actual no sabe explotar?**

### Veredicto Científico:
**MemoryBioRAG SÍ posee las relaciones en su base de conocimiento.** 
- En el **62.5% de los casos (5/8)**, el nodo `gold` ya es alcanzado directamente por los tokens de la consulta (0 saltos), pero el recuperador actual (FTS/BM25) lo clasifica fuera del Top-5 por dilución léxica.
- En el **37.5% restante (3/8)**, el nodo `gold` está conectado a **1 o 2 saltos** mediante sinapsis existentes en el snapshot.

El cuello de botella no radica en la ausencia de información en la base de datos, sino en que:
1. El grafo actual trata todas las aristas como pesos escalares indiferenciados sin tipado semántico (`ES_UN`, `RESUELVE`, `REQUIERE`).
2. Spreading Activation sobre el grafo no dirigido colapsa ante el efecto atractor de los hubs densos si no cuenta con normalización por grado de entrada.

---

### Verificación Criptográfica de Artefactos de la Fase 3

- `docs/fase3_grafo_relacional_auditoria.json`: `366a562922654813a5bd3d11c33f76971c833c3db2ff46fc3e5843a858dc901f`
- `scripts/audit_fase3_grafo.py`: Verificado y ejecutable contra el snapshot canónico.
- `core/memory_store.py`: **100% intacto**.
- `snapshots/qa_escape_qcr_20260811.db`: **100% intacto**.
