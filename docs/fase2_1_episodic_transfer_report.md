# FASE 2.1: Auditoría Causal de Aprendizaje Episódico — Informe Formal

**Timestamp**: 2026-09-09T01:23:53Z  
**DB SHA-256**: `676827f6b4abc3acaee10b14e273c3c50cae5b2c180593dedcd58048265a2800`  
> **Invariantes:** core/ intacto. A0-TEST 100% ciego. Desglose formal de Generación vs Re-ranking.

## 1. Tabla Causal Completa por Caso

| Case | Gold | M0 Pool | Gold∈M0 | Ep Act? | Gold Added? | Ep Necessary? | M0 Rank | M2 NoBonus | M2 Bonus | Op Overlap | Veredicto |
|---|---|---:|---|---|---|---|---:|---:|---:|---|---|
| **CASE_01** | `scoring_pesos_bm25` | 135 | YES | NO | NO | NO | 64 | 64 | **64** | ∅ | `NO_EPISODE_ACTIVATION` |
| **CASE_02** | `desde_athena_biorag` | 235 | YES | YES | NO | NO | 68 | 68 | **1** | LINK | `EPISODE_RERANK_ONLY` |
| **CASE_03** | `docker_infrastructur` | 22 | NO | YES | YES | YES | – | 4 | **1** | SEPARATE | `EPISODE_GENERATED_CANDIDATE` |
| **CASE_04** | `coche_puente_condici` | 265 | YES | NO | NO | NO | 24 | 24 | **24** | ∅ | `NO_EPISODE_ACTIVATION` |
| **CASE_05** | `activos_dormidos_her` | 248 | YES | YES | NO | NO | 33 | 33 | **1** | MODIFY | `EPISODE_RERANK_ONLY` |

## 2. Tipificación de Transferencia

| Case | Transfer Type | Stem Overlap ($A \cap B$) | Operator Overlap ($A \cap B$) |
|---|---|---|---|
| **CASE_01** | `NOT_TRANSFERRED` | `∅` | `∅` |
| **CASE_02** | `LEXICAL_ZERO_STRUCTURAL_CUE` | `∅` | `['LINK']` |
| **CASE_03** | `LEXICAL_ZERO_STRUCTURAL_CUE` | `∅` | `['SEPARATE']` |
| **CASE_04** | `NOT_TRANSFERRED` | `∅` | `∅` |
| **CASE_05** | `LEXICAL_ZERO_STRUCTURAL_CUE` | `∅` | `['MODIFY']` |

## 3. Controles Negativos (M3 — Especificidad)

| Control ID | Query | Episodios Activados | Falso Positivo |
|---|---|---:|---|
| **NEG_01** | `receta culinaria de cocina mediterranea con aceite...` | 0 | NO (Limpio) |
| **NEG_02** | `mantenimiento preventivo de vehiculos hibridos y c...` | 0 | NO (Limpio) |

## 4. Conclusión Científica Calibrada (Aureon Benchmark)

1. **Candidate Generation Rescue:** **1/5 casos** (`CASE_03`: `docker_infrastructure_rog`) demostró `EPISODE_GENERATED_CANDIDATE`. El Gold estaba ausente de M0 (pool=22, rank=–) y fue introducido al pool exclusivamente por el episodio aprendido, alcanzando **Rank 4 (sin bonificación)** y **Rank 1 (con bonificación)**.
2. **Episodic Re-Ranking:** **2/5 casos** (`CASE_02` y `CASE_05`) demostraron `EPISODE_RERANK_ONLY`. El Gold ya estaba en el pool M0 y la activación episódica lo elevó a **Rank 1**.
3. **Tipificación Metodológica:** Los 3 casos exitosos corresponden a `LEXICAL_ZERO_STRUCTURAL_CUE` (cero solapamiento léxico de stems, pero transferencia mediante abstracción estructural de operador compartida).
4. **Controles Negativos (M3):** Cero falsos positivos (0/2).
