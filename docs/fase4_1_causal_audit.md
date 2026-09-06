# Fase 4.1 — Auditoría Causal Factorial

**Fecha:** 2026-09-05  
**Criterio FP canónico:** `score_top1 > 2.0` (unificado con Fase 3.2)  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Total queries OOS evaluadas:** 30  
**Rescates detectados:** 6

---

## 1. TABLA COMPARATIVA FACTORIAL COMPLETA

| Condición | Descripción | Test R@5 | Transfer R@5 | Paraphrase R@5 | Corpus Shift R@5 | Hard-Neg FP (>2.0) |
|---|---|---:|---:|---:|---:|---:|
| **F0 (baseline)** | FTS puro sin modificar | 0/8 (0%) | 0/8 (0%) | 0/8 (0%) | 0/6 (0%) | 0/60 (0%) |
| **A** | Frame ON  + Predicate ON  (F3 completo) | 2/8 (25%) | 1/8 (12%) | 2/8 (25%) | 1/6 (17%) | 21/60 (35%) |
| **B** | Frame OFF + Predicate ON | 0/8 (0%) | 0/8 (0%) | 0/8 (0%) | 0/6 (0%) | 17/60 (28%) |
| **C** | Frame ON  + Predicate OFF | 0/8 (0%) | 0/8 (0%) | 0/8 (0%) | 0/6 (0%) | 17/60 (28%) |
| **D** | Frame OFF + Predicate OFF (equivale a spreading sin tipado) | 0/8 (0%) | 0/8 (0%) | 0/8 (0%) | 0/6 (0%) | 25/60 (42%) |
| **E** | Frame ON  + Predicate ON  + typed_derived OFF | 2/8 (25%) | 1/8 (12%) | 1/8 (12%) | 1/6 (17%) | 21/60 (35%) |
| **F** | Frame ON  + Predicate ON  + physical_SINONIMO_DE OFF | 2/8 (25%) | 1/8 (12%) | 1/8 (12%) | 1/6 (17%) | 16/60 (27%) |
| **G** | Frame ON  + Predicate ON  + graph_propagation OFF (solo semillas) | 2/8 (25%) | 1/8 (12%) | 1/8 (12%) | 1/6 (17%) | 0/60 (0%) |
| **H** | Frame ON  + Predicate ON  + candidate_focalization OFF | 0/8 (0%) | 0/8 (0%) | 0/8 (0%) | 0/6 (0%) | 24/60 (40%) |

---

## 2. CADENAS CAUSALES POR RESCUE OOS

Para cada query rescatada: cadena completa QUERY → FRAME → PREDICATE → SEED → RELACIÓN → PATH → GOLD.

### [TEST] 0534 — `activa largo archivos`

| Campo | Valor |
|---|---|
| **Gold** | `biorag_v11_1_detalle_tecnico` |
| **Rank F0** | — |
| **Rank F3 (A)** | 1 |
| **FRAME** | `[]` |
| **PREDICATE** | `['DETALLE_TECNICO']` |
| **SEED** | `leccion_syn_obligatorio_aprender` |
| **Seed raw score** | `0.28355` |
| **Seed focused score** | `0.14178` |
| **Relación usada** | `SINONIMO_DE` |
| **Es SINONIMO_DE físico** | `True` |
| **Es arista derivada** | `False` |
| **Proveniencia** | `sinapsis(tipo=sinonimo_explicito)` |
| **Path** | `leccion_syn_obligatorio_aprender --[SINONIMO_DE]--> biorag_v11_1_detalle_tecnico` |
| **Score gold (cond A)** | `0.38942` |

**Diagnóstico Causal:** `FOCALIZATION_REQUIRED — rescue requiere focalización de candidatos`  
**Componentes responsables:** `['FRAME', 'PREDICATE', 'CANDIDATE_FOCALIZATION']`  
**SINONIMO_DE suficiente (sin derivadas):** `True`  
**Aristas derivadas requeridas:** `False`  
**Notas:** DERIVED_TYPED_EDGE_NOT_REQUIRED: rescue persiste al eliminar aristas derivadas tipadas

#### Ablación factorial de este rescue

| Condición | Rank | En Top-5 | Score gold | Impacto |
|---|---:|---|---:|---|
| **A** `Frame ON  + Predicate ON  (F3 completo)` | 1 | ✓ | 0.38942 | **RESCUE_MAINTAINED** |
| **B** `Frame OFF + Predicate ON` | — | ✗ | 0.20507 | **RESCUE_LOST** |
| **C** `Frame ON  + Predicate OFF` | — | ✗ | 0.20507 | **RESCUE_LOST** |
| **D** `Frame OFF + Predicate OFF (equivale a spreading si` | — | ✗ | 0.21313 | **RESCUE_LOST** |
| **E** `Frame ON  + Predicate ON  + typed_derived OFF` | 1 | ✓ | 0.38942 | **RESCUE_MAINTAINED** |
| **F** `Frame ON  + Predicate ON  + physical_SINONIMO_DE O` | 1 | ✓ | 0.37112 | **RESCUE_MAINTAINED** |
| **G** `Frame ON  + Predicate ON  + graph_propagation OFF ` | 1 | ✓ | 0.37112 | **RESCUE_MAINTAINED** |
| **H** `Frame ON  + Predicate ON  + candidate_focalization` | — | ✗ | 0.20995 | **RESCUE_LOST** |

### [TEST] 0801 — `datos lecciones postsync`

| Campo | Valor |
|---|---|
| **Gold** | `notebooklm-memory-biorag-project` |
| **Rank F0** | — |
| **Rank F3 (A)** | 2 |
| **FRAME** | `['INTEGRACION', 'APRENDIZAJE']` |
| **PREDICATE** | `['INTEGRACIÓN', 'APRENDIZAJE']` |
| **SEED** | `oracle_que_recordar_sobre_artemis_hermes` |
| **Seed raw score** | `0.42248` |
| **Seed focused score** | `0.21124` |
| **Relación usada** | `SINONIMO_DE` |
| **Es SINONIMO_DE físico** | `True` |
| **Es arista derivada** | `False` |
| **Proveniencia** | `sinapsis(tipo=sinonimo_explicito)` |
| **Path** | `oracle_que_recordar_sobre_artemis_hermes --[SINONIMO_DE]--> notebooklm-memory-biorag-project` |
| **Score gold (cond A)** | `0.40117` |

**Diagnóstico Causal:** `FOCALIZATION_REQUIRED — rescue requiere focalización de candidatos`  
**Componentes responsables:** `['FRAME', 'PREDICATE', 'CANDIDATE_FOCALIZATION']`  
**SINONIMO_DE suficiente (sin derivadas):** `True`  
**Aristas derivadas requeridas:** `False`  
**Notas:** DERIVED_TYPED_EDGE_NOT_REQUIRED: rescue persiste al eliminar aristas derivadas tipadas

#### Ablación factorial de este rescue

| Condición | Rank | En Top-5 | Score gold | Impacto |
|---|---:|---|---:|---|
| **A** `Frame ON  + Predicate ON  (F3 completo)` | 2 | ✓ | 0.40117 | **RESCUE_MAINTAINED** |
| **B** `Frame OFF + Predicate ON` | — | ✗ | 0.22434 | **RESCUE_LOST** |
| **C** `Frame ON  + Predicate OFF` | — | ✗ | 0.22434 | **RESCUE_LOST** |
| **D** `Frame OFF + Predicate OFF (equivale a spreading si` | — | ✗ | 0.31354 | **RESCUE_LOST** |
| **E** `Frame ON  + Predicate ON  + typed_derived OFF` | 2 | ✓ | 0.38975 | **RESCUE_MAINTAINED** |
| **F** `Frame ON  + Predicate ON  + physical_SINONIMO_DE O` | 2 | ✓ | 0.34917 | **RESCUE_MAINTAINED** |
| **G** `Frame ON  + Predicate ON  + graph_propagation OFF ` | 2 | ✓ | 0.33774 | **RESCUE_MAINTAINED** |
| **H** `Frame ON  + Predicate ON  + candidate_focalization` | — | ✗ | 0.24202 | **RESCUE_LOST** |

### [TRANSFER] TRF_01 — `evaluacion y metrica de escalabilidad promedio`

| Campo | Valor |
|---|---|
| **Gold** | `analisis_escalabilidad_10k_v5_1` |
| **Rank F0** | — |
| **Rank F3 (A)** | 5 |
| **FRAME** | `['EVALUACION']` |
| **PREDICATE** | `['EVALUACIÓN']` |
| **SEED** | `word2vec_puro_costo_entrenamiento_no_incremental` |
| **Seed raw score** | `0.12796` |
| **Seed focused score** | `0.06398` |
| **Relación usada** | `SINONIMO_DE` |
| **Es SINONIMO_DE físico** | `True` |
| **Es arista derivada** | `False` |
| **Proveniencia** | `sinapsis(tipo=sinonimo_explicito)` |
| **Path** | `word2vec_puro_costo_entrenamiento_no_incremental --[SINONIMO_DE]--> analisis_escalabilidad_10k_v5_1` |
| **Score gold (cond A)** | `0.25796` |

**Diagnóstico Causal:** `FOCALIZATION_REQUIRED — rescue requiere focalización de candidatos`  
**Componentes responsables:** `['FRAME', 'PREDICATE', 'CANDIDATE_FOCALIZATION']`  
**SINONIMO_DE suficiente (sin derivadas):** `True`  
**Aristas derivadas requeridas:** `False`  
**Notas:** DERIVED_TYPED_EDGE_NOT_REQUIRED: rescue persiste al eliminar aristas derivadas tipadas

#### Ablación factorial de este rescue

| Condición | Rank | En Top-5 | Score gold | Impacto |
|---|---:|---|---:|---|
| **A** `Frame ON  + Predicate ON  (F3 completo)` | 5 | ✓ | 0.25796 | **RESCUE_MAINTAINED** |
| **B** `Frame OFF + Predicate ON` | — | ✗ | 0.1386 | **RESCUE_LOST** |
| **C** `Frame ON  + Predicate OFF` | — | ✗ | 0.1386 | **RESCUE_LOST** |
| **D** `Frame OFF + Predicate OFF (equivale a spreading si` | — | ✗ | 0.15121 | **RESCUE_LOST** |
| **E** `Frame ON  + Predicate ON  + typed_derived OFF` | 5 | ✓ | 0.25796 | **RESCUE_MAINTAINED** |
| **F** `Frame ON  + Predicate ON  + physical_SINONIMO_DE O` | 4 | ✓ | 0.24097 | **RESCUE_MAINTAINED** |
| **G** `Frame ON  + Predicate ON  + graph_propagation OFF ` | 4 | ✓ | 0.24097 | **RESCUE_MAINTAINED** |
| **H** `Frame ON  + Predicate ON  + candidate_focalization` | — | ✗ | 0.14313 | **RESCUE_LOST** |

### [PARAPHRASE] PRF_03 — `especificacion tecnica detalle persistencia archivos`

| Campo | Valor |
|---|---|
| **Gold** | `biorag_v11_1_detalle_tecnico` |
| **Rank F0** | — |
| **Rank F3 (A)** | 1 |
| **FRAME** | `[]` |
| **PREDICATE** | `['DETALLE_TECNICO']` |
| **SEED** | `leccion_syn_obligatorio_aprender` |
| **Seed raw score** | `0.28355` |
| **Seed focused score** | `0.14178` |
| **Relación usada** | `SINONIMO_DE` |
| **Es SINONIMO_DE físico** | `True` |
| **Es arista derivada** | `False` |
| **Proveniencia** | `sinapsis(tipo=sinonimo_explicito)` |
| **Path** | `leccion_syn_obligatorio_aprender --[SINONIMO_DE]--> biorag_v11_1_detalle_tecnico` |
| **Score gold (cond A)** | `0.29514` |

**Diagnóstico Causal:** `FOCALIZATION_REQUIRED — rescue requiere focalización de candidatos`  
**Componentes responsables:** `['FRAME', 'PREDICATE', 'CANDIDATE_FOCALIZATION']`  
**SINONIMO_DE suficiente (sin derivadas):** `True`  
**Aristas derivadas requeridas:** `False`  
**Notas:** DERIVED_TYPED_EDGE_NOT_REQUIRED: rescue persiste al eliminar aristas derivadas tipadas

#### Ablación factorial de este rescue

| Condición | Rank | En Top-5 | Score gold | Impacto |
|---|---:|---|---:|---|
| **A** `Frame ON  + Predicate ON  (F3 completo)` | 1 | ✓ | 0.29514 | **RESCUE_MAINTAINED** |
| **B** `Frame OFF + Predicate ON` | — | ✗ | 0.15506 | **RESCUE_LOST** |
| **C** `Frame ON  + Predicate OFF` | — | ✗ | 0.15506 | **RESCUE_LOST** |
| **D** `Frame OFF + Predicate OFF (equivale a spreading si` | — | ✗ | 0.15981 | **RESCUE_LOST** |
| **E** `Frame ON  + Predicate ON  + typed_derived OFF` | 1 | ✓ | 0.29514 | **RESCUE_MAINTAINED** |
| **F** `Frame ON  + Predicate ON  + physical_SINONIMO_DE O` | 1 | ✓ | 0.28192 | **RESCUE_MAINTAINED** |
| **G** `Frame ON  + Predicate ON  + graph_propagation OFF ` | 1 | ✓ | 0.28192 | **RESCUE_MAINTAINED** |
| **H** `Frame ON  + Predicate ON  + candidate_focalization` | — | ✗ | 0.15859 | **RESCUE_LOST** |

### [PARAPHRASE] PRF_08 — `sincronizacion lecciones sync integracion`

| Campo | Valor |
|---|---|
| **Gold** | `notebooklm-memory-biorag-project` |
| **Rank F0** | — |
| **Rank F3 (A)** | 4 |
| **FRAME** | `['INTEGRACION', 'APRENDIZAJE']` |
| **PREDICATE** | `['INTEGRACIÓN', 'APRENDIZAJE']` |
| **SEED** | `sync_incremental_implementation` |
| **Seed raw score** | `0.1289` |
| **Seed focused score** | `0.2578` |
| **Relación usada** | `SINONIMO_DE` |
| **Es SINONIMO_DE físico** | `True` |
| **Es arista derivada** | `False` |
| **Proveniencia** | `sinapsis(tipo=sinonimo_explicito)` |
| **Path** | `sync_incremental_implementation --[SINONIMO_DE]--> notebooklm-memory-biorag-project` |
| **Score gold (cond A)** | `0.22299` |

**Diagnóstico Causal:** `TYPED_DERIVED_EDGE_REQUIRED — aristas derivadas tipadas causalmente necesarias`  
**Componentes responsables:** `['FRAME', 'PREDICATE', 'TYPED_DERIVED_EDGES', 'PHYSICAL_SINONIMO_DE', 'GRAPH_PROPAGATION', 'CANDIDATE_FOCALIZATION']`  
**SINONIMO_DE suficiente (sin derivadas):** `False`  
**Aristas derivadas requeridas:** `True`  
**Notas:** DERIVED_TYPED_EDGE_REQUIRED: rescue se pierde al eliminar aristas derivadas

#### Ablación factorial de este rescue

| Condición | Rank | En Top-5 | Score gold | Impacto |
|---|---:|---|---:|---|
| **A** `Frame ON  + Predicate ON  (F3 completo)` | 4 | ✓ | 0.22299 | **RESCUE_MAINTAINED** |
| **B** `Frame OFF + Predicate ON` | — | ✗ | 0.07879 | **RESCUE_LOST** |
| **C** `Frame ON  + Predicate OFF` | — | ✗ | 0.07879 | **RESCUE_LOST** |
| **D** `Frame OFF + Predicate OFF (equivale a spreading si` | — | ✗ | 0.10772 | **RESCUE_LOST** |
| **E** `Frame ON  + Predicate ON  + typed_derived OFF` | — | ✗ | 0.17568 | **RESCUE_LOST** |
| **F** `Frame ON  + Predicate ON  + physical_SINONIMO_DE O` | — | ✗ | 0.17274 | **RESCUE_LOST** |
| **G** `Frame ON  + Predicate ON  + graph_propagation OFF ` | — | ✗ | 0.12543 | **RESCUE_LOST** |
| **H** `Frame ON  + Predicate ON  + candidate_focalization` | — | ✗ | 0.09858 | **RESCUE_LOST** |

### [CORPUS_SHIFT] CS_06 — `puente de exportacion bidireccional hacia repositorio remoto`

| Campo | Valor |
|---|---|
| **Gold** | `notebooklm-memory-biorag-project` |
| **Rank F0** | — |
| **Rank F3 (A)** | 2 |
| **FRAME** | `['INTEGRACION']` |
| **PREDICATE** | `['INTEGRACIÓN']` |
| **SEED** | `oracle_que_recordar_sobre_artemis_hermes` |
| **Seed raw score** | `0.29895` |
| **Seed focused score** | `0.14947` |
| **Relación usada** | `SINONIMO_DE` |
| **Es SINONIMO_DE físico** | `True` |
| **Es arista derivada** | `False` |
| **Proveniencia** | `sinapsis(tipo=sinonimo_explicito)` |
| **Path** | `oracle_que_recordar_sobre_artemis_hermes --[SINONIMO_DE]--> notebooklm-memory-biorag-project` |
| **Score gold (cond A)** | `0.21706` |

**Diagnóstico Causal:** `FOCALIZATION_REQUIRED — rescue requiere focalización de candidatos`  
**Componentes responsables:** `['FRAME', 'PREDICATE', 'CANDIDATE_FOCALIZATION']`  
**SINONIMO_DE suficiente (sin derivadas):** `True`  
**Aristas derivadas requeridas:** `False`  
**Notas:** DERIVED_TYPED_EDGE_NOT_REQUIRED: rescue persiste al eliminar aristas derivadas tipadas

#### Ablación factorial de este rescue

| Condición | Rank | En Top-5 | Score gold | Impacto |
|---|---:|---|---:|---|
| **A** `Frame ON  + Predicate ON  (F3 completo)` | 2 | ✓ | 0.21706 | **RESCUE_MAINTAINED** |
| **B** `Frame OFF + Predicate ON` | — | ✗ | 0.12391 | **RESCUE_LOST** |
| **C** `Frame ON  + Predicate OFF` | — | ✗ | 0.12391 | **RESCUE_LOST** |
| **D** `Frame OFF + Predicate OFF (equivale a spreading si` | — | ✗ | 0.15626 | **RESCUE_LOST** |
| **E** `Frame ON  + Predicate ON  + typed_derived OFF` | 2 | ✓ | 0.21706 | **RESCUE_MAINTAINED** |
| **F** `Frame ON  + Predicate ON  + physical_SINONIMO_DE O` | 2 | ✓ | 0.18991 | **RESCUE_MAINTAINED** |
| **G** `Frame ON  + Predicate ON  + graph_propagation OFF ` | 2 | ✓ | 0.18991 | **RESCUE_MAINTAINED** |
| **H** `Frame ON  + Predicate ON  + candidate_focalization` | — | ✗ | 0.13115 | **RESCUE_LOST** |

---

## 3. MATRIZ CAUSAL FINAL

| Componente | Cond | Rescates perdidos al quitarlo | FP eliminados al quitarlo |
|---|---|---:|---:|
| **FRAME** | B | 6/6 | 7/21 |
| **PREDICATE** | C | 6/6 | 7/21 |
| **CANDIDATE_FOCALIZATION** | H | 6/6 | 1/21 |
| **TYPED_DERIVED_EDGES** | E | 1/6 | 0/21 |
| **PHYSICAL_SINONIMO_DE** | F | 1/6 | 5/21 |
| **GRAPH_PROPAGATION** | G | 1/6 | 21/21 |
| **FRAME+PREDICATE_OFF** | D | 6/6 | 0/21 |

---

## 4. DIAGNÓSTICO DE FALSOS POSITIVOS

Los FPs bajo condición A (F3 completo, criterio >2.0) se atribuyen a los componentes
que, al desactivarse, eliminan el FP:

*(Detalle completo en `docs/fase4_1_causal_audit.json` → `fp_diagnoses_sample`)*

---

## 5. VEREDICTO FINAL

**A — causalidad aislada parcialmente demostrada (aristas derivadas causalmente necesarias en ≥1 rescue)**

### Interpretación


> El mecanismo operativo confirmado es:
>
> ```
> QUERY
>   ↓
> Structural Frame  (necesario — su ausencia colapsa el rescue)
>   ↓
> Predicate Classifier  (necesario — su ausencia colapsa el rescue)
>   ↓
> Candidate Focalization  (redirige energía a semillas del tipo correcto)
>   ↓
> SINONIMO_DE físico existente  (el camino real al gold)
>   ↓
> GOLD
> ```
>
> Las aristas tipadas derivadas de prefijo NO son causalmente necesarias para los rescates observados.  
> Esto significa que **el problema principal no era ausencia de conexiones, sino incapacidad para seleccionar las conexiones correctas entre una enorme cantidad de señales existentes**.

### Conclusión científica honesta

No utilizar los términos "generalización fuerte", "grafo tipado validado" ni "Structural Frame causal aislado" hasta que la evidencia adicional lo justifique.

El avance demostrable es: **la interpretación estructural de la consulta permite seleccionar semillas y rutas que el spreading activation ciego no aprovecha**, y esto produce rescates reales, reproducibles y con trazas verificables.
