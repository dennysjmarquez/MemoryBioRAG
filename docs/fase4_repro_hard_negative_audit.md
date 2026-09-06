# Fase 4 — Auditoría de Reproducibilidad y Reconciliación

**Fecha:** 2026-09-05  
**Propósito:** Responder a las 5 objeciones de Aureon sobre el reporte de Fase 4.  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)

---

## 1. RECONCILIACIÓN DE DISCREPANCIA EN HARD NEGATIVES

### Causa raíz identificada

La discrepancia **0/60 FP (Fase 3.2) vs 57/60 FP (Fase 4)** para F0 FTS es completamente
explicada por un **cambio de umbral**. Los datos subyacentes son idénticos.

| Criterio | Ubicación en código | Umbral | F0 FP | F1 FP | F3 FP |
|---|---|---:|---:|---:|---:|
| **Fase 3.2** | `proto_seed_focusing.py:318` | `score > 2.0` | 0/60 (0.0%) | 0/60 (0.0%) | 19/60 (31.7%) |
| **Fase 4** | `proto_fase4_typed_graph.py:evaluate_hard_negatives` | `score > 0.40` | 57/60 (95.0%) | 57/60 (95.0%) | 52/60 (86.7%) |

> [!CAUTION]
> **Los porcentajes de Fase 3.2 y Fase 4 NO son comparables directamente.** Cambió la definición de FP, no los datos.  
> A partir de ahora se usa **criterio unificado `score > 2.0`** (el original de Fase 3.2) para todas las comparaciones de la Tabla Final.

---

## 2. AUDITORÍA DE LAS 1589 ARISTAS DERIVADAS

### Desglose por método de derivación

| Método | Cantidad | Veredicto Semántico | Nota Crítica |
|---|---:|---|---|
| **subject_action_object_triple** | 3 | ✅ VÁLIDA | Triple del predicado con acción mapeada |
| **fix_prefix_and_synapse** | 306 | ⚠️ PLAUSIBLE | Dirección semántica plausible; coocurrencia no garantiza el objeto del fix |
| **protocol_prefix_and_synapse** | 190 | ⚠️ PLAUSIBLE | PRECEDE puede ser espurio si el vecino no es el objeto gobernado |
| **benchmark_prefix_and_synapse** | 56 | ⚠️ PLAUSIBLE | MIDE es demasiado específico para inferirlo sólo de coocurrencia |
| **identity_prefix_and_synapse** | 870 | ⚠️ PLAUSIBLE | Puede activar DEFINE_IDENTIDAD con nodos técnicos no pertinentes |
| **sync_prefix_and_synapse** | 164 | ⚠️ PLAUSIBLE | Coocurrencia puede conectar nodos fuera del dominio de integración |

> [!WARNING]
> **Ninguna arista prefijada por taxonomía es VÁLIDA en el sentido de evidencia directa.**  
> Sólo las derivadas de triples Sujeto-Acción-Objeto (`predicados`) son **VÁLIDAS**.  
> El resto son **PLAUSIBLES pero no demostradas semánticamente.**

---

## 3. TABLA FINAL RECONCILIADA (criterio unificado: score_top1 > 2.0)

| Método | Type-2 R@5 | Type-2 R@1 | Type-2 MRR | Transfer R@5 | Paraphrase R@5 | Hard-Neg FP (>2.0) | Corpus Shift R@5 | Causal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **F0 (FTS)** | 0/8 (0.0%) | 0/8 (0.0%) | 0.0 | 0/8 (0.0%) | 0/8 (0.0%) | 0/60 (0.0%) [criterion>2.0] | 0/6 (0.0%) | — |
| **F1 (Graph Unrestricted)** | 0/8 (0.0%) | 0/8 (0.0%) | 0.0 | 0/8 (0.0%) | 0/8 (0.0%) | 0/60 (0.0%) [criterion>2.0] | 0/6 (0.0%) | — |
| **F3 (Typed+Constrained)** | **2/8 (25.0%)** | **1/8 (12.5%)** | **0.188** | **1/8 (12.5%)** | **2/8 (25.0%)** | **19/60 (31.7%) [criterion>2.0]** | **1/6 (16.7%)** | Ver §4 |

---

## 4. TRAZAS CAUSALES POR RESCUE DE F3

| ID | Query | Gold | Rank F0 | Rank F1 | Rank F3 | Frame? | Predicate | Seed | Typed Edge | Path | Causal Verdict |
|---|---|---|---:|---:|---:|---|---|---|---|---|---|
| 0497 | `relevantes biomimética mejor` | `benchmark_antes_despues_fix3` | — | — | — | ✗ | — | `—` | `—` | `—` | **NOT_A_RESCUE** |
| 0516 | `real más sistemas` | `dennys-identidad-profunda` | — | — | — | ✗ | — | `—` | `—` | `—` | **NOT_A_RESCUE** |
| 0534 | `activa largo archivos` | `biorag_v11_1_detalle_tecnico` | — | — | 1 | ✓ | DETALLE_TECNICO | `leccion_syn_obligatorio_aprender` | `SINONIMO_DE` | `leccion_syn_obligatorio_aprender --[SINO` | **TYPED_EDGE_NOT_PROVEN_CAUSAL** |
| 0583 | `debo biorag preacción` | `identificacion_obligatoria_ora` | — | — | — | ✗ | — | `—` | `—` | `—` | **NOT_A_RESCUE** |
| 0640 | `ráfaga después resultado` | `mentalidad_biorag_para_agentes` | — | — | — | ✗ | — | `—` | `—` | `—` | **NOT_A_RESCUE** |
| 0724 | `learning paso regla` | `protocolo_autoinferencia_metac` | — | — | — | ✗ | — | `—` | `—` | `—` | **NOT_A_RESCUE** |
| 0795 | `insert storepy comunicadosdest` | `fix_mensajeria_broadcast_track` | — | — | — | ✗ | — | `—` | `—` | `—` | **NOT_A_RESCUE** |
| 0801 | `datos lecciones postsync` | `notebooklm-memory-biorag-proje` | — | — | 2 | ✓ | INTEGRACIÓN | `oracle_que_recordar_sobre_artemis_hermes` | `SINONIMO_DE` | `oracle_que_recordar_sobre_artemis_hermes` | **TYPED_EDGE_NOT_PROVEN_CAUSAL** |

---

## 5. ABLACIÓN INDIVIDUAL POR RESCUE

Para cada rescue de F3, se muestra si eliminar un componente destruye el rescue:

| ID | Rescue? | -Frame | -Predicate | -CriticalRel | -CriticalSeed | Diagnóstico |
|---|---|---|---|---|---|---|
| 0497 | ❌ | N/A | N/A | N/A | N/A | NOT_A_RESCUE |
| 0516 | ❌ | N/A | N/A | N/A | N/A | NOT_A_RESCUE |
| 0534 | ✅ | LOST ❌ | LOST ❌ | OK ✓ | OK ✓ | TYPED_EDGE_NOT_PROVEN_CAUSAL |
| 0583 | ❌ | N/A | N/A | N/A | N/A | NOT_A_RESCUE |
| 0640 | ❌ | N/A | N/A | N/A | N/A | NOT_A_RESCUE |
| 0724 | ❌ | N/A | N/A | N/A | N/A | NOT_A_RESCUE |
| 0795 | ❌ | N/A | N/A | N/A | N/A | NOT_A_RESCUE |
| 0801 | ✅ | LOST ❌ | LOST ❌ | OK ✓ | OK ✓ | TYPED_EDGE_NOT_PROVEN_CAUSAL |

---

## 6. VEREDICTO PROVISIONAL (POST-AUDITORÍA)

### ✅ Lo que quedó demostrado

1. **La discrepancia 0/60 → 57/60 es completamente explicada** por cambio de definición de FP, no por diferencias en datos. Con criterio unificado (`>2.0`), ver Tabla §3.
2. **F3 supera a F0 y F1 en Type-2** (primer resultado positivo consistente).
3. **La ablación de Frame y Predicate destruye completamente los rescates** (F3-noFrame = 0/8, F3-noPredicate = 0/8): el mecanismo de interpretación estructural es **necesario** para los rescates observados.
4. **Las 1.589 aristas derivadas son auditadas**: 3 son VÁLIDAS (triples de predicados); el resto son PLAUSIBLES pero no demostradas semánticamente.

### ⚠️ Lo que NO está demostrado aún

1. **Las aristas tipadas por prefijo taxonómico** (`fix_* → RESUELVE`, `protocolo_* → PRECEDE`) son PLAUSIBLES, no VÁLIDAS. La ablación de `no_critical_relation` no destruyó los rescates: las relaciones tipadas derivadas de prefijos **no son la causa causal principal** de los rescates en este prototipo.
2. **Hard negatives con criterio unificado**: ver tabla §3 con criterio `>2.0`.
3. **Generalización**: los resultados actuales son GENERALIZACIÓN PARCIAL hasta que corpus-shift y transfer mejoren significativamente.

### 🔬 Interpretación Científica Correcta

> Los rescates de F3 sobre F0/F1 se deben principalmente al **Structural Frame + Predicate Classifier** (que redirigen la selección de semillas y el scoring de candidatos), **no** a las aristas tipadas por prefijo. Esto significa que la hipótesis de Fase 4 tiene una parte correcta (interpretación estructural es necesaria) y una parte pendiente de demostración (que las relaciones tipadas específicas aportan recuperación adicional más allá del frame).
