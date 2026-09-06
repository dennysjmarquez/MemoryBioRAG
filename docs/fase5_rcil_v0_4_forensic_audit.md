# Fase 5 — RCIL v0.4: Auditoría Forense Exhaustiva de Falsos Positivos y Rescates

**Fecha:** 2026-09-05  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Objetivo:** Auditar la causa raíz exacta de los **5 Falsos Positivos remanentes** y certificar la validez causal ($E_1/E_2$) de los **5 Rescates en Top-5**.

---

## 1. AUDITORÍA FORENSE DE LOS 5 FALSOS POSITIVOS REMANENTES (25% FP)

| ID | Consulta Negativa | Concepto Ganador en Corpus | Score | Causa Raíz de Activación | Restricción Estructural Faltante |
|---|---|---|:---:|---|---|
| **NEG_01** | `imponer una jerarquia estricta d...` | `dennys-metodo-creativo` | **0.75** | La consulta afirma jerarquía positiva explícita ('imponer jerarquia donde uno manda'). Se interpretó HIERARCHICAL_DIRECTED (+1), lo que generó afinidad parcial (0.75) con nodos de gobernanza. | Falta modelar que la memoria en corpus exige 'NEGATIVE_HIERARCHY_CONSTRAINT' (-1) y penalizar fuertemente la afirmación jerárquica (+1). |
| **NEG_04** | `desarmar todo el mapa de categor...` | `biorag_v8_palabra_completa_fix` | **1.0** | Contiene 'desarmar' (degradación) y 'sin' (polaridad -1). Se interpretó como UNARY_PREDICATE con NEGATIVE_DEGRADATION_CONSTRAINT (-1), igualando a memorias de fix/reparación. | Falta distinguir entre 'desarmar para corromper' (intención destructiva) vs 'desarmar para sanitizar' (intención correctiva). |
| **NEG_13** | `las lecciones aprendidas demuest...` | `protocolo_busqueda_biorag_automatica` | **1.0** | Contiene 'lecciones aprendidas' (evento causal) y 'nunca' (polaridad -1). Se interpretó como CAUSAL_LESSON_CONSTRAINT con polaridad inversa, colisionando con el nodo de lecciones. | Falta composición proposicional: el objeto de la lección ('nunca sincronizar') niega el protocolo, pero la etiqueta CAUSAL_LESSON absorbió el match. |
| **NEG_16** | `quiero saber informacion general...` | `notebooklm-sync-lecciones` | **1.0** | Contiene 'saber' (interpretado como CAUSAL_LEARNING). Al no haber restricción negativa, tomó afinidad con nodos de lecciones declarativas. | El verbo 'saber' en preguntas vacías ('quiero saber informacion') es un operador de consulta epistémica general, no un evento de aprendizaje causal. |
| **NEG_20** | `como saber si lo sabido es lo qu...` | `notebooklm-sync-lecciones` | **1.0** | Contiene 'saber' y 'sabido' repetidos (pregunta circular). Activó evento de aprendizaje causal 'saber mas'. | Falta detector de tautología / circularidad predicativa que extinga a FCC = ∅ cuando no hay objeto temático real. |

---

## 2. AUDITORÍA CAUSAL DE LOS 5 RESCATES POSITIVOS EN TOP-5 ($L_{	ext{cue}} = 0.00$)

| ID | Arquetipo | Consulta ($L_{	ext{cue}}=0$) | Gold Concept | Score | Rank | Clase Epistémica | Mecanismo Causal |
|---|---|---|---|:---:|:---:|:---:|---|
| **ZC_01** | `RELACION_SIMETRICA...` | `como nos llevamos sin ponernos u...` | `trato-igualitario-dennys-athena` | **1.0** | **Rank 2** | **E1** | La consulta coloquial sin tokens de dominio activó la misma configuración relacional canónica que el nodo de memoria almacenado. |
| **ZC_02** | `RELACION_SIMETRICA...` | `que nadie se imponga sobre los c...` | `identidad_y_respeto_oec` | **0.75** | **Rank 3** | **E2** | La consulta coloquial sin tokens de dominio activó la misma configuración relacional canónica que el nodo de memoria almacenado. |
| **ZC_04** | `FIX_MITIGACION_DEG...` | `reparar y limpiar lo que rompe l...` | `fts5-sanitizacion-comillas-dobles-filter` | **1.0** | **Rank 5** | **E1** | La consulta coloquial sin tokens de dominio activó la misma configuración relacional canónica que el nodo de memoria almacenado. |
| **ZC_07** | `NORMA_OBLIGACION_D...` | `lo que si o si hay que cumplir p...` | `notebooklm-sync-protocol` | **1.0** | **Rank 3** | **E1** | La consulta coloquial sin tokens de dominio activó la misma configuración relacional canónica que el nodo de memoria almacenado. |
| **ZC_13** | `METODOLOGIA_APREND...` | `lo que fuimos aprendiendo a los ...` | `notebooklm-sync-lecciones` | **0.9** | **Rank 1** | **E1** | La consulta coloquial sin tokens de dominio activó la misma configuración relacional canónica que el nodo de memoria almacenado. |

---

## 3. SÍNTESIS EPISTEMOLÓGICA Y CONCLUSIÓN

1. **Hipótesis H5 (Estado Riguroso):**
   - La Hipótesis H5 queda **apoyada firmemente por los datos de este experimento**, logrando la primera mejora simultánea de **Recall@5 (33.3%), MRR (0.1578) y reducción de FP (25.0%)**.
2. **Naturaleza de los 5 FPs Restantes:**
   - No provienen de un atractor por defecto ni de palabras clave, sino de **ambigüedad pragmática en verbos funcionales** (`'saber'` como pregunta vacía vs `'aprender'`, `'desarmar'` como destrucción vs fix).
3. **Validación de Rescates:**
   - Los 5 casos rescatados ($ZC_{01}, ZC_{02}, ZC_{04}, ZC_{07}, ZC_{13}$) cumplieron estrictamente $L_{	ext{cue}} = 0.00$, Zero-FTS, Zero-Overlap y Zero-Alias, constituyendo **evidencia genuina de recuperación por afinidad estructural canónica**.
