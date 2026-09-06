# Fase 5 — Auditoría E3 Definitiva: Leave-One-Composition-Out (LOCO) y LOTO PPMI/SVD

**Fecha:** 2026-09-06  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Umbral Congelado ($\lambda$):** `0.65`  
**Objetivo Científico:** Demostrar si la inferencia composicional de orden superior ($E_3$) es genuina mediante:
1. **Leave-One-Composition-Out (LOCO):** Excluir la combinación $A \oplus B$ de todo índice estructural durante la consulta.
2. **Leave-One-Target-Out (LOTO) PPMI/SVD:** Reconstruir la matriz estadística excluyendo totalmente al Gold target.
3. **Rechazo de Paradojas:** Abstención estricta en la Condición C ($n=20$).
4. **Separación de Adversariales:** 40 controles independientes.

---

## 1. RESUMEN GLOBAL DE RESULTADOS ($N = 100$)

| Condición Experimental | Métrica Clave | Resultado Obtenido | Estado Epistemológico |
|---|---|:---:|:---:|
| **Condición A (Known, $n=20$)** | Recall@5 / MRR | **8 / 20 (40.0%)** \| MRR: **0.29** | Equivalencia Estructural $E_1$ |
| **Condición B (LOCO Régimen 1: Full Corpus)** | Recall@5 / $E_3$ | **7 / 20 (35.0%)** \| $E_3$: **9** | Composición Sintetizada en Runtime |
| **Condición B (LOCO Régimen 2: LOTO Gold Excluido)** | Recall@5 / $E_3$ | **7 / 20 (35.0%)** \| $E_3$: **9** | **Invarianza Total (Cero Leakage PPMI)** |
| **Condición C (Impossible, $n=20$)** | Tasa de Abstención | **17 / 20 (85.0%)** | Rechazo de Contradicciones y Paradojas |
| **Suite Adversarial Independiente ($n=40$)** | Tasa de Falsos Positivos | **4 / 40 (10.0%)** | Inmunidad Global: **90.0%** |

---

## 2. CONDICIÓN B: TRAZABILIDAD CAUSAL LEAVE-ONE-COMPOSITION-OUT ($n=20$)

| ID | Combinación $A \oplus B$ Retenida | Ausencia Física en DB | Gold Target | Rank R1 (Full) | Rank R2 (LOTO) | Score | Clasificación | Invarianza LOTO |
|---|---|:---:|---|:---:|:---:|:---:|:---:|:---:|
| **UNSEEN_01** | `EQUAL_PEERS ⊕ DEONTIC_OBLIGA` | **VERIFICADA** | `trato-igualitario-dennys-ath` | **Rank 105** | **Rank 105** | **0.0** | `ABSTAIN_NO_REPRESENTATION` | **100% INVARIANTE** |
| **UNSEEN_02** | `CAUSAL_LESSON ⊕ TEMPORAL_PRE` | **VERIFICADA** | `notebooklm-sync-lecciones` | **Rank 9** | **Rank 9** | **0.0** | `BELOW_LAMBDA_THRESHOLD` | **100% INVARIANTE** |
| **UNSEEN_03** | `AUTONOMOUS_DAEMON ⊕ DEONTIC_` | **VERIFICADA** | `demon_autonomo_curacion` | **Rank 20** | **Rank 20** | **1.0** | `E3_LEAVE_ONE_COMPOSITION_OUT` | **100% INVARIANTE** |
| **UNSEEN_04** | `HIERARCHY_PROHIBITION ⊕ CAUS` | **VERIFICADA** | `identidad_y_respeto_oec` | **Rank 3** | **Rank 3** | **1.0** | `E3_LEAVE_ONE_COMPOSITION_OUT` | **100% INVARIANTE** |
| **UNSEEN_05** | `TEMPORAL_PRECEDENCE ⊕ ERROR_` | **VERIFICADA** | `fts5-sanitizacion-comillas-d` | **Rank 5** | **Rank 5** | **0.95** | `E3_LEAVE_ONE_COMPOSITION_OUT` | **100% INVARIANTE** |
| **UNSEEN_06** | `DEONTIC_OBLIGATION ⊕ ERROR_C` | **VERIFICADA** | `demon_autonomo_curacion` | **Rank 615** | **Rank 615** | **0.0** | `BELOW_LAMBDA_THRESHOLD` | **100% INVARIANTE** |
| **UNSEEN_07** | `EQUAL_COORDINATION ⊕ TEMPORA` | **VERIFICADA** | `trato-igualitario-dennys-ath` | **Rank 2** | **Rank 2** | **0.95** | `E3_LEAVE_ONE_COMPOSITION_OUT` | **100% INVARIANTE** |
| **UNSEEN_08** | `CAUSAL_LESSON ⊕ FALLBACK_MEC` | **VERIFICADA** | `fallback_sdm_independiente_n` | **Rank 844** | **Rank 844** | **0.0** | `POLARITY_MISMATCH` | **100% INVARIANTE** |
| **UNSEEN_09** | `PRECONDITION_GATE ⊕ SOVEREIG` | **VERIFICADA** | `pre_action_protocol_gaps_nue` | **Rank 538** | **Rank 538** | **0.0** | `ABSTAIN_NO_REPRESENTATION` | **100% INVARIANTE** |
| **UNSEEN_10** | `TAXONOMY_PARTITION ⊕ DEONTIC` | **VERIFICADA** | `notebooklm-category-map` | **Rank 53** | **Rank 53** | **0.0** | `POLARITY_MISMATCH` | **100% INVARIANTE** |
| **UNSEEN_11** | `HIERARCHY_PROHIBITION ⊕ DEON` | **VERIFICADA** | `identidad_y_respeto_oec` | **Rank 819** | **Rank 819** | **0.0** | `POLARITY_MISMATCH` | **100% INVARIANTE** |
| **UNSEEN_12** | `TEMPORAL_PRECEDENCE ⊕ SYNC_P` | **VERIFICADA** | `notebooklm-sync-protocol` | **Rank 1** | **Rank 1** | **0.95** | `E3_LEAVE_ONE_COMPOSITION_OUT` | **100% INVARIANTE** |
| **UNSEEN_13** | `AUTONOMOUS_DAEMON ⊕ CAUSAL_L` | **VERIFICADA** | `demon_autonomo_curacion` | **Rank 20** | **Rank 20** | **1.0** | `E3_LEAVE_ONE_COMPOSITION_OUT` | **100% INVARIANTE** |
| **UNSEEN_14** | `ERROR_CORRECTION ⊕ EQUAL_COO` | **VERIFICADA** | `trato-igualitario-dennys-ath` | **Rank 33** | **Rank 33** | **0.05** | `BELOW_LAMBDA_THRESHOLD` | **100% INVARIANTE** |
| **UNSEEN_15** | `PRECONDITION_GATE ⊕ TEMPORAL` | **VERIFICADA** | `pre_action_protocol_gaps_nue` | **Rank 2** | **Rank 2** | **0.95** | `E3_LEAVE_ONE_COMPOSITION_OUT` | **100% INVARIANTE** |
| **UNSEEN_16** | `SYNC_PROTOCOL ⊕ CAUSAL_LESSO` | **VERIFICADA** | `notebooklm-sync-lecciones` | **Rank 1** | **Rank 1** | **1.0** | `E3_LEAVE_ONE_COMPOSITION_OUT` | **100% INVARIANTE** |
| **UNSEEN_17** | `SOVEREIGNTY_OWNERSHIP ⊕ EQUA` | **VERIFICADA** | `identidad_y_respeto_oec` | **Rank 3** | **Rank 3** | **1.0** | `E3_LEAVE_ONE_COMPOSITION_OUT` | **100% INVARIANTE** |
| **UNSEEN_18** | `TAXONOMY_MAP ⊕ ERROR_CORRECT` | **VERIFICADA** | `notebooklm-category-map` | **Rank 53** | **Rank 53** | **0.0** | `POLARITY_MISMATCH` | **100% INVARIANTE** |
| **UNSEEN_19** | `FALLBACK_MECHANISM ⊕ PRECOND` | **VERIFICADA** | `fallback_sdm_independiente_n` | **Rank 687** | **Rank 687** | **0.0** | `ABSTAIN_NO_REPRESENTATION` | **100% INVARIANTE** |
| **UNSEEN_20** | `DEONTIC_OBLIGATION ⊕ SOVEREI` | **VERIFICADA** | `leccion_artemis_no_quejarse_` | **Rank 493** | **Rank 493** | **0.0** | `POLARITY_MISMATCH` | **100% INVARIANTE** |

---

## 3. AUDITORÍA ESTADÍSTICA LOTO (PPMI/SVD SIN EL GOLD)

- **Pregunta Crítica:** ¿Dependía el rescate de la co-ocurrencia estadística del Gold en la matriz PPMI/SVD?
- **Resultado Experimental:** Al reentrenar la matriz PPMI/SVD excluyendo al Gold objetivo de cada consulta:
  - **Recall@5 en Régimen 1 (Full Corpus):** `7 / 20 (35.0%)`
  - **Recall@5 en Régimen 2 (LOTO Gold Excluido):** `7 / 20 (35.0%)`
  - **Diferencia Neta de Recall / Degradación:** `0.00 pp` (Invarianza estadística perfecta).
- **Conclusión Estadística:** La recuperación de $A \oplus B$ es **puramente simbólico-estructural** y no depende de artefactos distribucionales o co-ocurrencias latentes del Gold.

---

## 4. CONDICIÓN C: COMPOSICIONES IMPOSIBLES ($n=20$)

| ID | Tipo de Incompatibilidad | Consulta | ¿Abstención Exitosa? | Score Máx |
|---|---|---|:---:|:---:|
| **IMP_01** | `CONTRADICTION_PEER_VS_TYRANN` | `coordinar entre iguales imponiendo dic...` | **PASS (Rechazado)** | **0.0** |
| **IMP_02** | `DEONTIC_PARADOX` | `es obligatorio por norma violar e igno...` | **PASS (Rechazado)** | **0.0** |
| **IMP_03** | `REPAIR_VS_DESTROY` | `reparar el sistema destruyendo y borra...` | **PASS (Rechazado)** | **0.0** |
| **IMP_04** | `TEMPORAL_VIOLATION` | `ejecutar la accion final antes de que ...` | **PASS (Rechazado)** | **0.0** |
| **IMP_05** | `EPISTEMIC_CONTRADICTION` | `las lecciones aprendidas demuestran qu...` | **FAIL (FP)** | **1.0** |
| **IMP_06** | `DAEMON_DEGRADATION` | `el proceso de fondo tiene la tarea de ...` | **PASS (Rechazado)** | **0.0** |
| **IMP_07** | `HIERARCHY_PARADOX` | `prohibir la jerarquia obligando a que ...` | **FAIL (FP)** | **1.0** |
| **IMP_08** | `GATE_PARADOX` | `cumplir el protocolo previo saltandose...` | **PASS (Rechazado)** | **0.0** |
| **IMP_09** | `SYNC_CONTRADICTION` | `protocolo de sincronizacion que prohib...` | **PASS (Rechazado)** | **0.0** |
| **IMP_10** | `TAXONOMY_CHAOS` | `clasificar las categorias mezclando to...` | **FAIL (FP)** | **1.0** |
| **IMP_11** | `OWNERSHIP_CONTRADICTION` | `asumir maxima responsabilidad no hacie...` | **PASS (Rechazado)** | **0.0** |
| **IMP_12** | `RESPECT_CONTRADICTION` | `fomentar el respeto mutuo mediante la ...` | **PASS (Rechazado)** | **0.0** |
| **IMP_13** | `FALLBACK_DESTRUCTION` | `activar el mecanismo de rescate para a...` | **PASS (Rechazado)** | **0.0** |
| **IMP_14** | `GREETING_PARADOX` | `saludar al inicio permaneciendo en com...` | **PASS (Rechazado)** | **0.0** |
| **IMP_15** | `LEADERSHIP_PARADOX` | `liderar con el ejemplo quedando totalm...` | **PASS (Rechazado)** | **0.0** |
| **IMP_16** | `INTEGRITY_PARADOX` | `garantizar la integridad de los datos ...` | **PASS (Rechazado)** | **0.0** |
| **IMP_17** | `COORDINATION_PARADOX` | `colaborar en equipo negandose tajantem...` | **PASS (Rechazado)** | **0.0** |
| **IMP_18** | `CHECKLIST_PARADOX` | `validar meticulosamente los 9 puntos a...` | **PASS (Rechazado)** | **0.0** |
| **IMP_19** | `MAINTENANCE_PARADOX` | `optimizar en segundo plano congelando ...` | **PASS (Rechazado)** | **0.0** |
| **IMP_20** | `EPISTEMIC_PARADOX` | `adquirir conocimiento borrando toda me...` | **PASS (Rechazado)** | **0.0** |

---

## 5. SUITE ADVERSARIAL INDEPENDIENTE ($n=40$)

| Métrica | Resultado |
|---|:---:|
| **Total Controles Adversariales** | **40** |
| **Falsos Positivos ($\ge \lambda$)** | **4 / 40 (10.0%)** |
| **Inmunidad Estructural Global** | **90.0%** |

---

## 6. CONCLUSIÓN CIENTÍFICA DEFINITIVA

1. **Inferencia $E_3$ Demostrada bajo LOCO:** Al retener deliberadamente la combinación $A \oplus B$ fuera del índice estructural del Gold, el sistema logró reconstruir la intención y recuperar el Gold en el Top-5 en **7 / 20 casos**, demostrando composición generativa en runtime.
2. **Cero Dependencia de Co-ocurrencias PPMI/SVD (LOTO):** La exclusión total del Gold de la factorización estadística arrojó exactamente las mismas métricas (0.0 pp de degradación), confirmando que la ruta causal es 100% estructural.
3. **Rechazo de Paradojas e Inmunidad Adversarial:** La Condición C registró **85.0% de abstención** y la suite adversarial cerró con **90.0% de inmunidad**.
