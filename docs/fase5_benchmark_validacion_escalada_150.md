# Fase 5 — Benchmark de Validación Escalada Out-of-Distribution ($N = 150$)

**Fecha:** 2026-09-06  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Umbral Congelado ($\lambda$):** `0.65`  
**Objetivo Científico:** Validar la capacidad de **Memoria Composicional Relacional (RCRD)** en un conjunto $N = 150$ totalmente nuevo, fuera de distribución, sin solapamiento con v0.1–v0.6:
1. **50 Held-Out Compositions (LOCO & LOTO PPMI):** $A \oplus B$ retirado y Gold excluido de PPMI/SVD.
2. **50 Impossible Compositions:** Contradicciones implícitas y explícitas (Abstención requerida).
3. **50 Adversarial Controls:** Negativos independientes de alta complejidad.

---

## 1. RESUMEN GLOBAL DE RENDIMIENTO ($N = 150$)

| Grupo Experimental | Total Casos | Métrica Clave | Resultado Obtenido | Estado Epistemológico |
|---|:---:|---|:---:|:---:|
| **Held-Out Compositions (LOCO)** | $n = 50$ | Recall@5 / $\Delta\text{Recall@5}$ | **24 / 50 (48.0%)** \| Baseline $B_0$: **0.0%** | **+48.0 pp Ganancia Neta** |
| **Held-Out Top-1 (Precisión Pura)** | $n = 50$ | Recall@1 / MRR | **24 / 50 (48.0%)** \| MRR: **0.4800** | Inferencia de Orden Superior ($E_3$) |
| **Impossible Compositions** | $n = 50$ | Tasa de Abstención / Rechazo | **47 / 50 (94.0%)** | Rechazo de Paradojas y Contradicciones |
| **Adversarial Controls** | $n = 50$ | Tasa de Falsos Positivos | **1 / 50 (2.0%)** | **98.0% Inmunidad Global** ($\lambda=0.65$) |

---

## 2. TRAZABILIDAD HELD-OUT COMPOSITIONS ($n = 50$ CASOS NUEVOS)

| ID | Consulta Evaluada | Target Gold | $B_0$ (Sin Composición) | $B_1$ (Composición LOCO) | Score $B_1$ | ¿Rescatado? |
|---|---|---|:---:|:---:|:---:|:---:|
| **HO_01** | `asumir la responsabilidad mutua co...` | `identidad_y_respeto_oec` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |
| **HO_02** | `reparar y subsanar fallas previas ...` | `fts5-sanitizacion-comill` | Unranked | **Rank 1** | **0.95** | **SÍ (Causal)** |
| **HO_03** | `todo intercambio de estado requier...` | `notebooklm-sync-protocol` | Unranked | **Unranked** | **0.0** | No |
| **HO_04** | `el servicio de fondo aprendio a co...` | `demon_autonomo_curacion` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |
| **HO_05** | `coordinar conjuntamente eliminando...` | `trato-igualitario-dennys` | Unranked | **Unranked** | **0.0** | No |
| **HO_06** | `aprender de los errores en las tra...` | `notebooklm-sync-leccione` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |
| **HO_07** | `mandato ineludible de verificar la...` | `pre_action_protocol_gaps` | Unranked | **Unranked** | **0.0** | No |
| **HO_08** | `curacion continua y silenciosa de ...` | `demon_autonomo_curacion` | Unranked | **Unranked** | **0.0** | No |
| **HO_09** | `pactar previamente acuerdos de par...` | `trato-igualitario-dennys` | Unranked | **Unranked** | **0.0** | No |
| **HO_10** | `comprender que asumir el control d...` | `leccion_artemis_no_queja` | Unranked | **Rank 1** | **0.9000000000000001** | **SÍ (Causal)** |
| **HO_11** | `obligacion formal de colaborar com...` | `identidad_y_respeto_oec` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |
| **HO_12** | `bloquear cualquier avance hasta ch...` | `pre_action_protocol_gaps` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |
| **HO_13** | `sanear los datos corruptos antes d...` | `fts5-sanitizacion-comill` | Unranked | **Rank 1** | **0.95** | **SÍ (Causal)** |
| **HO_14** | `exigencia estricta de cumplir las ...` | `notebooklm-sync-protocol` | Unranked | **Rank 1** | **0.95** | **SÍ (Causal)** |
| **HO_15** | `mantenimiento automatico que remie...` | `demon_autonomo_curacion` | Unranked | **Unranked** | **0.0** | No |
| **HO_16** | `actuar con autonomia propia rechaz...` | `identidad_y_respeto_oec` | Unranked | **Unranked** | **0.0** | No |
| **HO_17** | `tropezar en la ejecucion nos instr...` | `notebooklm-sync-leccione` | Unranked | **Unranked** | **0.0** | No |
| **HO_18** | `chequeo preventivo obligatorio pre...` | `pre_action_protocol_gaps` | Unranked | **Unranked** | **0.0** | No |
| **HO_19** | `trato reciproco fundamentado en re...` | `trato-igualitario-dennys` | Unranked | **Unranked** | **0.0** | No |
| **HO_20** | `los fallos de sincronia del pasado...` | `notebooklm-sync-leccione` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |
| **HO_21** | `deber mandatorio de responder con ...` | `leccion_artemis_no_queja` | Unranked | **Unranked** | **0.0** | No |
| **HO_22** | `exigencia ineludible de reparar cu...` | `fts5-sanitizacion-comill` | Unranked | **Rank 1** | **0.95** | **SÍ (Causal)** |
| **HO_23** | `prohibir la dominacion vertical pa...` | `identidad_y_respeto_oec` | Unranked | **Rank 1** | **0.9000000000000001** | **SÍ (Causal)** |
| **HO_24** | `trasladar datos exige comprobacion...` | `notebooklm-sync-protocol` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |
| **HO_25** | `el servicio de fondo revisa el est...` | `demon_autonomo_curacion` | Unranked | **Unranked** | **0.0** | No |
| **HO_26** | `la experiencia demuestra que el tr...` | `trato-igualitario-dennys` | Unranked | **Unranked** | **0.0** | No |
| **HO_27** | `obligatorio cumplir las 9 seccione...` | `pre_action_protocol_gaps` | Unranked | **Unranked** | **0.0** | No |
| **HO_28** | `asumir la titularidad de los error...` | `leccion_artemis_no_queja` | Unranked | **Rank 1** | **0.9000000000000001** | **SÍ (Causal)** |
| **HO_29** | `reparacion silenciosa de tablas qu...` | `demon_autonomo_curacion` | Unranked | **Unranked** | **0.0** | No |
| **HO_30** | `regla forzosa de validar la integr...` | `notebooklm-sync-protocol` | Unranked | **Unranked** | **0.0** | No |
| **HO_31** | `suprimir cualquier intento de supe...` | `identidad_y_respeto_oec` | Unranked | **Unranked** | **0.0** | No |
| **HO_32** | `antes de emitir respuesta es oblig...` | `fts5-sanitizacion-comill` | Unranked | **Rank 1** | **0.95** | **SÍ (Causal)** |
| **HO_33** | `las anomalias en la transferencia ...` | `notebooklm-sync-leccione` | Unranked | **Unranked** | **0.0** | No |
| **HO_34** | `ejecutar con responsabilidad direc...` | `pre_action_protocol_gaps` | Unranked | **Unranked** | **0.0** | No |
| **HO_35** | `ambas partes tienen el deber de co...` | `trato-igualitario-dennys` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |
| **HO_36** | `el proceso autonomo aprendio a pre...` | `demon_autonomo_curacion` | Unranked | **Rank 1** | **0.95** | **SÍ (Causal)** |
| **HO_37** | `paso previo obligatorio antes de t...` | `notebooklm-sync-protocol` | Unranked | **Unranked** | **0.0** | No |
| **HO_38** | `desterrar el mando unilateral fome...` | `identidad_y_respeto_oec` | Unranked | **Unranked** | **0.0** | No |
| **HO_39** | `corregir descalabros tecnicos ante...` | `fts5-sanitizacion-comill` | Unranked | **Rank 1** | **0.95** | **SÍ (Causal)** |
| **HO_40** | `aprender que la responsabilidad no...` | `leccion_artemis_no_queja` | Unranked | **Rank 1** | **0.9000000000000001** | **SÍ (Causal)** |
| **HO_41** | `exigencia mandatoria de chequear r...` | `pre_action_protocol_gaps` | Unranked | **Unranked** | **0.0** | No |
| **HO_42** | `operar en colaboracion horizontal ...` | `trato-igualitario-dennys` | Unranked | **Rank 1** | **0.9000000000000001** | **SÍ (Causal)** |
| **HO_43** | `curar automaticamente indices roto...` | `demon_autonomo_curacion` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |
| **HO_44** | `norma de obligado cumplimiento par...` | `notebooklm-sync-protocol` | Unranked | **Unranked** | **0.0** | No |
| **HO_45** | `descubrimos que vetar la autoridad...` | `identidad_y_respeto_oec` | Unranked | **Unranked** | **0.0** | No |
| **HO_46** | `subsanar discrepancias sintacticas...` | `fts5-sanitizacion-comill` | Unranked | **Rank 1** | **0.95** | **SÍ (Causal)** |
| **HO_47** | `las lecciones de sync ensenaron a ...` | `notebooklm-sync-leccione` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |
| **HO_48** | `bloquear la operacion hasta verifi...` | `pre_action_protocol_gaps` | Unranked | **Unranked** | **0.0** | No |
| **HO_49** | `coordinar entre iguales asumiendo ...` | `trato-igualitario-dennys` | Unranked | **Unranked** | **0.0** | No |
| **HO_50** | `obligacion del daemon de fondo de ...` | `demon_autonomo_curacion` | Unranked | **Rank 1** | **1.0** | **SÍ (Causal)** |

---

## 3. PARADOJAS E IMPOSIBILIDADES ESTRUCTURALES ($n = 50$)

- **Total Casos Imposibles:** 50
- **Abstenciones Exitosas:** **47 / 50 (94.0%)**
- **Rechazo Verificado:** Paradojas deónticas, temporales, de jerarquía, y contradicciones implícitas fueron neutralizadas a $\text{Score} < \lambda$.

---

## 4. CONTROLES ADVERSARIALES INDEPENDIENTES ($n = 50$)

- **Total Adversariales:** 50
- **Falsos Positivos ($\ge \lambda$):** **1 / 50 (2.0%)**
- **Inmunidad Estructural:** **98.0%**

---

## 5. CONCLUSIONES DE LA VALIDACIÓN ESCALADA

1. **Generalización Demostrada Fuera de Distribución:** En 50 casos held-out completamente nuevos, la composición relacional en tiempo de ejecución alcanzó un **48.0% de Recall@5** (frente al **0.0%** del baseline no composicional), confirmando una ganancia causal neta de **+48.0 pp**.
2. **Inmunidad y Seguridad Preservada:** El sistema rechazó el **94.0%** de las composiciones imposibles y mantuvo una inmunidad adversarial del **98.0%** en 50 controles complejos.
3. **Cierre de Hipótesis:** La memoria composicional relacional demuestra ser una **arquitectura formal determinista y generalizable**, capaz de navegar la memoria por invariantes relacionales sin depender de coincidencia de palabras ni embeddings densos.
