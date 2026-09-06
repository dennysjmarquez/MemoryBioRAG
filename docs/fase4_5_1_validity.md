# Fase 4.5.1 — Auditoría de Validez Metodológica e Implementación

**Fecha:** 2026-09-05  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Objetivo:** Auditar el flujo de datos para certificar ausencia de leakage, diagnosticar causalmente las fallas de cada generador y establecer la conclusión rigurosa acordada.

---

## 1. PRUEBA FORMAL DE FLUJO DE DATOS (0% LEAKAGE DEMOSTRADO)

Inspección de las etapas de ejecución en `proto_fase4_5_1_provenance.py`:

| Etapa del Pipeline | Datos Recibidos | ¿Acceso a `gold`? | Evidencia en Código |
|---|---|:---:|---|
| **INPUT LINGÜÍSTICO** | `Solo el string 'query'` | No | `run_candidate_generation_pipeline(cur, node_meta, graph_adj, node_vectors, vocab, query, mode) no recibe 'gold' en sus parámetros de entrada.` |
| **GENERACIÓN DE CANDIDATOS (M2-M5)** | `String query + índices precomputados del corpus congelado` | No | `WordNet usa nltk.corpus; ConceptHub usa HUBS_INICIALES estáticos; PPMI usa node_vectors de largo_plazo; Grafo usa sinapsis de SQLite.` |
| **RE-RANKING Y SCORING** | `Diccionario de candidatos generados + metadatos léxicos de prefijo` | No | `El boost se aplica comparando 'node_type' de cada candidato con 'target_node_types' del Frame. No hay comparación con el gold.` |
| **EVALUACIÓN DE MÉTRICAS (POST-PIPELINE)** | `Lista final rankeada + string 'gold'` | **Sí** | `Única etapa donde entra el gold: rank = (concepts.index(gold) + 1) if gold in concepts else None. Ocurre estrictamente DESPUÉS de ordenar la lista.` |

> **Certificación:** El `gold` entra única y exclusivamente en la etapa de cálculo de métricas ($O(1)$ lookup post-ranking). Ninguna función de generación de candidatos ni de scoring tiene acceso al target.

---

## 2. AUDITORÍA DE LOS 19 CASOS VÁLIDOS ZERO-FTS

Tabla completa de los 19 casos que cumplen estrictamente:  
`gold ∉ FTS` $\land$ `intersection(query, gold) == ∅` $\land$ `aliases ∉ query`:

| ID | Query | Gold | WordNet | Concept Hub | PPMI | Grafo 1-Hop | ¿Gold en Pool Final? |
|---|---|---|:---:|:---:|:---:|:---:|:---:|
| **ZFTS_03** | `mitigacion ejecutada para neutralizar ...` | `fix_vulnerabilidad_inyeccion_sql` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_05** | `topologia estructural de guardado perm...` | `biorag_v11_1_detalle_tecnico` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_06** | `registro de celeridad maxima y consumo...` | `benchmark_algoritmos_rendimiento_python` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_07** | `canal de transmision externa y volcado...` | `notebooklm-memory-biorag-project` | ✗ | ✗ | ✗ | ✓ | **✓** |
| **ZFTS_08** | `estudio de comportamiento de carga mas...` | `analisis_escalabilidad_10k_v5_1` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_09** | `politica cautelar ineludible anterior ...` | `protocolo_de_seguridad_modificacion_codigo` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_10** | `tablas de contraste sobre agilidad y m...` | `benchmark_algoritmos_rendimiento_python` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_11** | `enmienda que subsana el agujero en las...` | `fix_vulnerabilidad_inyeccion_sql` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_14** | `volcado y enlace hacia el repositorio ...` | `notebooklm-memory-biorag-project` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_15** | `tasa de saturacion bajo volumenes giga...` | `analisis_escalabilidad_10k_v5_1` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_16** | `bloqueo de alteracion indebida en cabe...` | `fix_metadatos_corrupcion_v2` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_17** | `que es lo primero que no me puedo salt...` | `protocolo_de_seguridad_modificacion_codigo` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_19** | `el arreglo que le metieron al fallo de...` | `fix_vulnerabilidad_inyeccion_sql` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_21** | `las tripas y detalles de como se guard...` | `biorag_v11_1_detalle_tecnico` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_24** | `el parche para que no se machaquen los...` | `fix_metadatos_corrupcion_v2` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_26** | `experimento cuantitativo sobre latenci...` | `benchmark_latencia_hnsw_vs_ppmi` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_27** | `correccion estructural para prevenir c...` | `fix_sync_incremental_crash_v3` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_29** | `lecciones metodologicas extraidas de i...` | `leccion_sueno_consolidacion_memoria` | ✗ | ✗ | ✗ | ✗ | **✗** |
| **ZFTS_30** | `norma mandatoria de doble control y va...` | `protocolo_evaluacion_dual_obligatoria` | ✗ | ✗ | ✗ | ✗ | **✗** |

---

## 3. DIAGNÓSTICO CAUSAL DE FALLAS POR MECANISMO

Desglose de por qué cada generador no logró introducir el gold en los 19 casos:

### A) WordNet (0 / 19 Rescates)
- **IMPLEMENTATION_LIMIT (Sinónimos generados apuntaron a otros documentos disonantes):** 19 casos

### B) Concept Hub (0 / 19 Rescates en estos casos específicos)
- **IMPLEMENTATION_LIMIT (Hub activado pero no conectaba con el gold):** 16 casos
- **NO_RELATION (Ningún bridge de Concept Hub coincidió con los tokens de la query):** 3 casos

### C) PPMI Latente (0 / 19 Rescates)
- **IMPLEMENTATION_LIMIT (El espacio latente asoció la query a vecinos con mayor coocurrencia superficial):** 19 casos

### D) Grafo 1-Hop (1 / 19 Rescates)
- **IMPLEMENTATION_LIMIT (Las aristas salientes conectaban con otros conceptos):** 18 casos
- **SUCCESS_EXPLICIT_RELATION (Rescatado vía arista física de sinapsis):** 1 casos

---

## 4. AUDITORÍA DEL PRESUPUESTO DE CANDIDATOS

* **Promedio de candidatos generados (brutos):** **167.68421052631578**
* **Promedio de candidatos tras deduplicación:** **100.94736842105263**
* **Candidatos gold descartados por filtrado o poda:** **0** (ningún gold generado fue eliminado por límites de presupuesto).

---

## 5. CONCLUSIÓN CIENTÍFICA REFORMULADA Y RIGUROSA

> **Formulación Exacta Aprobada:**  
> *En los 19 casos que cumplen estrictamente Zero-FTS y Zero-Overlap, no se observó generación semántica nueva clasificable como D/E. El único rescate válido auditado fue atribuible a una relación explícitamente almacenada (Categoría B: sinapsis física preexistente). Esto constituye evidencia de dependencia del conocimiento previamente representado en el corpus, pero no demuestra que los mecanismos clásicos sean incapaces en general de producir generalización semántica.*

---

## 6. SÍNTESIS ARQUITECTÓNICA PARA MEMORYBIORAG

1. **`M1` queda formalizado como `Structural Seed Re-ranker`**: Su rol definitivo en el sistema es la reponderación y supresión de ruido (0% FP) sobre conjuntos de candidatos ya existentes.
2. **Generación de candidatos bajo Zero-Overlap**: Requiere conocimiento previamente representado (puentes estructurados de `Concept Hub` o aristas tipadas de `sinapsis`).
3. **Decisión Early vs Late Fusion**: Queda formalmente postergada hasta disponer de generadores de candidatos validados con representación de dominio enriquecida.
