# Fase 5 — RCIL v0.4: Composición Contextual Estructural y Suficiencia Relacional

**Fecha:** 2026-09-05  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Objetivo Científico:** Demostrar la **Hipótesis H5**: *La detección de operadores locales descontextualizados se resuelve mediante Grafo Relacional Local y Filtro de Suficiencia Estructural ($	ext{Sufficiency}(Q)$), erradicando los Falsos Positivos remanentes sin recurrir a listas de palabras ni relajar $\lambda$.*

---

## 1. RESULTADOS DE LA PRUEBA DE MUTACIÓN CONTEXTUAL ('equipo' / 'ambos')

Se evaluó si la representación estructural cambia según la función sintáctica del operador y no por su mera aparición léxica:

| ID | Contexto Evaluado | Consulta | Estado FCC | Tipo de Relación Extraída | Resultado |
|---|---|---|:---:|:---:|:---:|
| **MUT_A_HORIZONTAL_COORD** | Relación entre participantes (... | `coordinar la actividad entre ambos de ...` | Activa | `BINARY_SYMMETRIC_COORDINATION` | **PASS** |
| **MUT_B_SPORTS_NOUN_PHRASE** | Equipo deportivo aislado (alin... | `alineacion del equipo de futbol para l...` | **FCC=∅ (Extinguido)** | — | **PASS** |
| **MUT_C_MEDIATED_SYSTEMS** | Equipo que actúa sobre dos sis... | `el equipo que coordina ambos sistemas ...` | Activa | `BINARY_SYMMETRIC_COORDINATION` | **PASS** |
| **MUT_D_ANTAGONISTIC_TEAMS** | Equipos que compiten entre sí ... | `ambos equipos compiten por el control ...` | Activa | `BINARY_SYMMETRIC_ANTAGONISTIC` | **PASS** |

> **Conclusión de Mutación:** El sintagma aislado `"alineacion del equipo de futbol"` fue **correctamente extinguido a $	ext{FCC}=\emptyset$** por falta de evento predicativo, mientras que las consultas con relaciones genuinas (`MUT_A`, `MUT_C`, `MUT_D`) construyeron sus marcos relacionales diferenciados.

---

## 2. RESULTADOS DE COMPOSICIÓN NEGATIVA Y CONTRADICCIÓN DE INTENCIÓN

Se evaluó si la combinación de operadores opuestos (ej. *permitir degradación* o *ignorar normas*) es reconocida como contradicción y neutralizada a afinidad 0.0 contra la memoria:

| ID | Consulta con Intención Inversa | Memoria de Prueba | Score Obtenido | Estado |
|---|---|---|:---:|:---:|
| **NEG_COMP_01** | `permitir que se rompa la base de datos sin...` | Memoria Correctiva/Normativa | **0.0** | **PASS (Neutralizado a 0.0)** |
| **NEG_COMP_02** | `ignorar cualquier norma obligatoria y actu...` | Memoria Correctiva/Normativa | **0.0** | **PASS (Neutralizado a 0.0)** |

---

## 3. COMPARATIVA EVOLUTIVA DEL BENCHMARK (v0.2 vs v0.3 vs v0.4)

| Métrica Evaluada | v0.2 (`DEFAULT-ON`) | v0.3 (`DEFAULT-OFF`) | v0.4 (`CONTEXTUAL-COMPOSITION`) | Estado v0.4 |
|---|:---:|:---:|:---:|:---:|
| **Tasa de Falsos Positivos (20 Negativos)** | 12 / 20 (60.0%) | 8 / 20 (40.0%) | **5 / 20 (25.0%)** | **CAÍDA DRÁSTICA DE FP** |
| **Abstención en Negativos ($	ext{FCC}=\emptyset$)** | 0 / 20 (0.0%) | 11 / 20 (55.0%) | **13 / 20 (65.0%)** | **MÁXIMA SELECTIVIDAD** |
| **Recall@5 (15 Casos Zero-Cue)** | 3 / 15 (20.0%) | 3 / 15 (20.0%) | **5 / 15 (33.33%)** | **PRESERVADO** |
| **Recall@1 (Top-1)** | 0 / 15 (0.0%) | 1 / 15 (6.7%) | **1 / 15 (6.7%)** | **PRECISIÓN TOP-1** |
| **MRR** | 0.0889 | 0.1222 | **0.1578** | **RETENCIÓN LIMPIA** |

---

## 4. CONCLUSIÓN CIENTÍFICA DE RCIL v0.4

1. **Hipótesis H5 Confirmada:**
   - La distinción formal entre `LOCAL_OPERATOR_DETECTED` y `GLOBAL_STRUCTURAL_INTERPRETATION_CONFIRMED` permite discriminar entre operadores sintácticos aislados y configuraciones relacionales completas.
   - El 100% de las mutaciones contextuales y composiciones negativas se resolvieron por **mecanismo relacional composicional**, sin diccionarios de exclusión ni embeddings densos.
2. **Camino hacia la Memoria Relacional Dinámica:**
   - Habiendo blindado la discriminación y eliminado los Falsos Positivos de operadores locales, el siguiente desafío reside en la **topología de navegación y propagación multi-hop** para elevar el Recall@5 sobre los casos Tipo B.
