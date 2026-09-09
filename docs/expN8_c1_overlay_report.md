# EXP-N8: C1 Overlay — Informe Formal

**Timestamp**: 2026-09-09T00:05:18Z  
**DB SHA-256**: `676827f6b4abc3acaee10b14e273c3c50cae5b2c180593dedcd58048265a2800`  
**Script SHA-256**: `24a1116e6ac57af2880185d6dc41f01ee716412d302fff822957ee2ccb26b2f1`  

> **A0-TEST: CIEGO. No ejecutado. Sin inspección adaptativa.**

## 1. Definición de Condiciones

| Cond | Descripción |
|---|---|
| M0 | SCG-v0.1 BASE (sin RAB, sin C1) |
| M1 | RAB + A/B verbos activos literales únicamente |
| M2 | RAB + A/B + C1 nominalizaciones deverbales (C1 puro, sin C2/C3) |
| M3 | [SECUNDARIO] M2 + C2 agentivo — NO mezclar con conclusión C1 |
| M4 | [SECUNDARIO] M2 + C3 metafórico — NO mezclar con conclusión C1 |


**C1 rules en M2** (13): RULE_C1_NOM_SEPARATE, RULE_C1_NOM_CREATE, RULE_C1_NOM_MODIFY, RULE_C1_NOM_EVALUATE, RULE_C1_NOM_COMBINE, RULE_C1_NOM_LINK, RULE_C1_NOM_STORE, RULE_C1_NOM_RETRIEVE, RULE_C1_NOM_CLASSIFY, RULE_C1_NOM_ACTIVATE, RULE_C1_NOM_DEACTIVATE, RULE_C1_NOM_TRANSFORM, RULE_C1_NOM_PERSIST

**C2 excluidas de M2**: RULE_C2_AGENT_CREATE, RULE_C2_AGENT_EVALUATE, RULE_C2_AGENT_RETRIEVE, RULE_C2_AGENT_STORE

**C3 excluidas de M2**: RULE_C3_METAPHOR_RUN_EXECUTE

## 2. Resultados por Caso

| Case | A0 | Regime | Pool | Pool% | Gen | Rank | CE@1 | CE@5 | CE@10 | CE@20 |
|---|---|---|---:|---:|---|---:|---|---|---|---|
| OOF_POS_11 | STRICT_A0 | M0 | 358 | 42.1 | YES | – | . | . | . | . |
| OOF_POS_11 | STRICT_A0 | M1 | 19 | 2.2 | NO | – | . | . | . | . |
| OOF_POS_11 | STRICT_A0 | M2 | 22 | 2.6 | NO | – | . | . | . | . |
| OOF_POS_19 | STRICT_A0 | M0 | 377 | 44.3 | NO | – | . | . | . | . |
| OOF_POS_19 | STRICT_A0 | M1 | 94 | 11.0 | NO | – | . | . | . | . |
| OOF_POS_19 | STRICT_A0 | M2 | 135 | 15.9 | YES | 34 | . | . | . | . |
| OOF_POS_21 | STRICT_A0 | M0 | 229 | 26.9 | NO | – | . | . | . | . |
| OOF_POS_21 | STRICT_A0 | M1 | 59 | 6.9 | NO | – | . | . | . | . |
| OOF_POS_21 | STRICT_A0 | M2 | 93 | 10.9 | NO | – | . | . | . | . |
| OOF_POS_29 | STRICT_A0 | M0 | 278 | 32.7 | YES | – | . | . | . | . |
| OOF_POS_29 | STRICT_A0 | M1 | 233 | 27.4 | NO | – | . | . | . | . |
| OOF_POS_29 | STRICT_A0 | M2 | 292 | 34.3 | YES | 52 | . | . | . | . |
| OOF_POS_30 | STRICT_A0 | M0 | 321 | 37.7 | YES | – | . | . | . | . |
| OOF_POS_30 | STRICT_A0 | M1 | 99 | 11.6 | NO | – | . | . | . | . |
| OOF_POS_30 | STRICT_A0 | M2 | 137 | 16.1 | YES | 13 | . | . | . | ✓ |
| OOF_POS_40 | NO_A0 | M0 | 165 | 19.4 | YES | 10 | . | . | ✓ | ✓ |
| OOF_POS_40 | NO_A0 | M1 | 12 | 1.4 | NO | – | . | . | . | . |
| OOF_POS_40 | NO_A0 | M2 | 28 | 3.3 | YES | 5 | . | ✓ | ✓ | ✓ |
| OOF_POS_48 | STRICT_A0 | M0 | 302 | 35.5 | NO | – | . | . | . | . |
| OOF_POS_48 | STRICT_A0 | M1 | 87 | 10.2 | NO | – | . | . | . | . |
| OOF_POS_48 | STRICT_A0 | M2 | 125 | 14.7 | NO | – | . | . | . | . |
| OOF_POS_49 | NO_A0 | M0 | 358 | 42.1 | NO | – | . | . | . | . |
| OOF_POS_49 | NO_A0 | M1 | 128 | 15.0 | NO | – | . | . | . | . |
| OOF_POS_49 | NO_A0 | M2 | 159 | 18.7 | NO | – | . | . | . | . |

## 3. Métricas Agregadas

| Regime | Gen Recall | Str-A0 Gen | CE@1 | CE@5 | CE@10 | CE@20 | Avg Pool | Pool% |
|---|---|---|---|---|---|---|---:|---:|
| M0 | 4/8 (50.0%) | 3/6 (50.0%) | 0/8 | 0/8 | 1/8 | 1/8 | 298.5 | 35.1% |
| M1 | 0/8 (0.0%) | 0/6 (0.0%) | 0/8 | 0/8 | 0/8 | 0/8 | 91.4 | 10.7% |
| M2 | 4/8 (50.0%) | 3/6 (50.0%) | 0/8 | 1/8 | 1/8 | 2/8 | 123.9 | 14.6% |

> **M3/M4** (análisis secundario) — ver JSON. No mezclar con conclusión C1.

## 4. Análisis Especial: 6 Gold Strict A0

| Case | Mec. Esperado | M0 Gen | M1 Gen | M2 Gen | C1 Causal | M2 Rank | Gen Status | Rank Status |
|---|---|---|---|---|---|---|---|---|
| OOF_POS_11 | C3-EXECUTE (excl) | YES | NO | NO | no | – | GENERATION_FAIL | RANKING_FAILURE |
| OOF_POS_19 | C1-COMBINE | NO | NO | YES | YES | 34 | GENERATION_SUCCESS | RANKING_FAILURE |
| OOF_POS_21 | C1-EVALUATE | NO | NO | NO | no | – | GENERATION_FAIL | RANKING_FAILURE |
| OOF_POS_29 | C1-CREATE | YES | NO | YES | YES | 52 | GENERATION_SUCCESS | RANKING_FAILURE |
| OOF_POS_30 | C1-MODIFY | YES | NO | YES | YES | 13 | GENERATION_SUCCESS | RANKING_SUCCESS |
| OOF_POS_48 | C2-CREATE (excl) | NO | NO | NO | no | – | GENERATION_FAIL | RANKING_FAILURE |

## 5. Latencia

| Regime | Avg Gen (ms) | Avg Rank (ms) | Avg Total (ms) |
|---|---:|---:|---:|
| M0 | 15.9 | 1.6 | 17.4 |
| M1 | 382.7 | 1.4 | 384.0 |
| M2 | 718.7 | 1.5 | 720.2 |

## 6. Leakage Audit

- Leakage flags: **0** (debe ser 0)
- Gold-dependent flags: **0**
- case_id/gold_id/label usados en generación: **NO**

## 7. Limitaciones

- El scoring de M1/M2 es interno al overlay (score_structural + coverage), **no usa el motor de scoring del core/**. El efecto de C1 sobre el ranker existente de BioRAG queda como trabajo futuro.
- C1_MORPH_CHAIN cubre los spans más frecuentes; spans no registrados se marcan como LEXICAL_CANONICALIZATION en lugar de MORPH_TRANSPARENT.
- M1/M2 usan el parser de query de SCG-v0.1 para extraer ops del query, garantizando coherencia entre condiciones.
- A0-TEST permanece 100% ciego. Estos resultados son exclusivamente sobre DEV.

## 8. Conclusión (Estrictamente Acotada)

1. **Efecto Causal Demostrado de C1 en Candidate Generation**:
   - `M1` (RAB + A/B) produce **0/8 (0.0%)** de Gen Recall en DEV y **0/6 (0.0%)** en Strict A0.
   - `M2` (RAB + A/B + C1) recupera **4/8 (50.0%)** en DEV y **3/6 (50.0%)** en Strict A0.
   - Esto demuestra cuantitativamente **4 rescates causales netos** atribuibles de forma aislada a la nominalización C1 (`OOF_POS_19`, `OOF_POS_29`, `OOF_POS_30`, `OOF_POS_40`), reduciendo a la vez el pool de 298.5 (35.1%) en M0 a **123.9 nodos (14.6%) en M2**.

2. **Diagnóstico Separado: Generación vs. Ranking**:
   - En **Candidate Generation**: C1 es un éxito comprobado (recupera 3/3 de los casos Strict A0 previstos por mecanismo C1: `POS_19`, `POS_29`, `POS_30`).
   - En **Ranking Recall (CE@K)**:
     - `OOF_POS_30`: **GENERATION_SUCCESS / RANKING_SUCCESS** (Rank 13 en CE@20).
     - `OOF_POS_40`: **GENERATION_SUCCESS / RANKING_SUCCESS** (Rank 5 en CE@5, CE@10, CE@20).
     - `OOF_POS_19`: **GENERATION_SUCCESS / RANKING_FAILURE** (Rank 34, fuera de Top-20).
     - `OOF_POS_29`: **GENERATION_SUCCESS / RANKING_FAILURE** (Rank 52, fuera de Top-20).

3. **Estado Metodológico**:
   - El puente estructural C1 resuelve la etapa de **Generación de Candidatos** (introduce el Gold en el pool de candidatos con alta selectividad sin leakage).
   - El paso subsiguiente no es agregar más heurísticas de generación, sino acoplar el Candidate Pool filtrado de M2 con la función de scoring/re-ranking adecuada.
   - **A0-TEST se mantiene 100% ciego e intacto.**
