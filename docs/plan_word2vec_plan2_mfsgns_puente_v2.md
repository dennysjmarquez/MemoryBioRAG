# Plan 2 — Puente Distribucional MF-SGNS (v2) sobre sustrato simbólico

**Estado:** PROPUESTO 2026-08-08 — borrador v0.2 para revisión del auditor técnico (Claude) y aprobación de negocio (Dennys). Nada se ejecuta sobre producción: todo el experimento corre sobre snapshot aislado (protocolo establecido).

**Autor:** Athena-OEC
**Versión:** 0.1
**Sucede al plan:** `plan_word2vec_adaptado_puente_condicional.md` (v0.2, Fases 1-2 ejecutadas y REFUTADAS)

---

## 1. Contexto — Qué se aprendió y por qué este Plan 2

### 1.1 Veredicto del Plan 1 (sweep HDC Fase 2, refutado)

**`word2vec_sweep_resultado.json` (2026-08-07 01:26):** 81 configs (ventana W0/W1/W0+W1 × top_k 5/10/20 × peso 0.1/0.15/0.2 × umbral None/0.5/0.6) sobre mitad A del holdout (457 casos, pipeline real `buscar_por_frase(limite=100)` sobre snapshot `word2vec_pre_fase0_20260806_235239.db`). **0/81 configs cumplen rescate con regresión ≤1 por categoría.**

Mejor config (W0, top_k=5, peso=0.1): rescata **3**, regresiona **15** (delta global **−2.75pp**; por_tema 84.38→59.38 con 10 regresiones; sinonimo 76.67→73.33). El boost aditivo `score + peso·bridge` a **todos** los candidatos fuera de top-5 con `score_pmi_nodo==0` mueve el pool completo y destruye aciertos.

### 1.2 Diagnóstico de discriminación — la bifurcación real del problema

**`word2vec_discriminacion.json` (2026-08-07 09:34):** para cada uno de los 35 fallos, se ordenó el pool por cada señal y se midió el rank del expected.

| Señal | por_tema (21) | sinonimo (14) |
|---|---|---|
| bridge HDC W0 — expected en rank 1 | **14/21** | 0/14 |
| bridge HDC W0 — expected en rank ≤5 | **18/21** | 0/14 |
| bridge HDC W1 / W0+W1 (idéntico a W0) | 14/21 · 18/21 | 0/14 |
| `sinonimo_dirigido` — expected en rank ≤5 | 0/21 | 0/14 |

**Conclusión bifurcada (la raíz, no el síntoma):**
1. **por_tema:** la señal HDC **ya discrimina** al expected (rank 1 en 14/21). El fracaso del sweep es del **mecanismo de aplicación** (boost global aditivo), no de la señal. Fix = re-rank selectivo con margen, no boost universal.
2. **sinonimo:** ninguna señal actual (HDC ni sinapsis dirigida) separa al expected. Los sinonimos léxicos puros (`perfil`→`dennys-identidad-profunda`, `dimensiones`→`cuando_usar_dimensiones_biorag`) tienen co-ocurrencia directa nula y contexto HDC sin solape. La señal de co-ocurrencia **binaria** no alcanza → aquí la hipótesis distribucional necesita la variante **ponderada** (Firth sobre magnitudes, no sobre presencias).

> Nota de fidelidad: W1 y W0+W1 dieron resultados idénticos a W0 en el diagnóstico, indicando que los vecinos sinápticos 1-hop no aportan señal adicional con Hamming binario. Se eliminan del barrido.

---

## 2. La Meta (transformada por Dennys, 2026-08-08)

> **Que BioRAG entienda por significado y no por palabra exacta, sin usar embeddings de punto flotante — materializando la hipótesis distribucional de Firth ("you shall know a word by the company it keeps") sobre el sustrato simbólico (co-ocurrencia real, pesos enteros, sin vectores aprendidos).**

Meta operativa del experimento:
> **Rescatar ≥18 de los 35 fallos top-5 (21 por_tema + 14 sinonimo, re-verificados en Fase 0) sin regresar ninguno de los aciertos, usando un puente de re-rank con la loss ponderada de MF-SGNS (`w·c = PMI − log k`, sigmoide ponderada por co-ocurrencia real `N_ij`) — sin LLM, sin embeddings de punto flotante persistidos, sin dependencias nuevas.**

---

## 3. Por qué MF-SGNS y no el HDC binario del Plan 1

El HDC del Plan 1 comprime el contexto a bits (Hamming binario): la **magnitud** de la co-ocurrencia se pierde — un par que co-ocurre 1 vez vale lo mismo que uno que co-ocurre 50 veces. Para sinonimos léxicos puros, esa señal binaria es indistinguible del ruido (0/14).

MF-SGNS (Matrix Factorization of Skip-Gram Negative Sampling) resuelve exactamente ese defecto:
- La loss correcta de SGNS (Kenyon-Dean Part 2, 2021) es una **matrix factorization con loss logística ponderada por conteos reales**:
  `L(i,j) = N_ij·log σ(w_i·c_j) + (k·N_i·N_j/N)·log σ(−w_i·c_j)`
- En el óptimo, el producto interno de equilibrio es `w·c = PMI(i,j) − log k`.
- La señal de un par es un **escalar continuo ponderado por `N_ij`** (frecuencia real de co-ocurrencia en el corpus), no un jaccard binario.
- `σ(x) = 1/(1+e^{−x})` es la función de activación logística (float interno de cálculo, no representación persistente — igual que el PMI actual).

**Materialización simbólica (sin embeddings):** no se entrena ni se persiste ningún vector. El puente se computa a query-time usando la matriz de co-ocurrencia real del snapshot (ya la construye `core/pmi_semantico.py::_construir_corpus` → `co_freq`, `doc_freq`, `total`). El score entre query y candidato:

```
score_sgns(Q, C) = promedio sobre q ∈ tokens(Q) de max_{c ∈ tokens(C)} N_qc · σ(PMI(q,c) − log k)
```

- `PMI(q,c) = log(N·N_qc / (N_q·N_c))`
- pares con `N_qc = 0` → `PMI = −∞` → `σ = 0` (sin evidencia directa, no penaliza)
- `k` = negativos muestreados (hiperparámetro a barrer: 1, 5, 10, 15)

Es count-based distributional semantics (HAL, Lund & Burgess 1996) con la loss logística de SGNS — el antepasado directo de word2vec, en sustrato simbólico, computado al vuelo. Es **complementario** al NPMI existente: el puente solo cubre los pares donde `score_pmi_nodo == 0`.

---

## 4. Las dos correcciones (cada una para su bifurcación)

### 4.1 Fix del mecanismo — por_tema (18/21 ya son rescatables por señal)

En vez de `score + peso·bridge` aplicado a **todo** el pool fuera de top-5 (que reordena el mundo y regresiona 15), el re-rank selectivo:

1. Se computa el `score_sgns(Q,C)` para **todos** los candidatos del pool.
2. Los top-5 base quedan **intocados** salvo promoción calificada.
3. Un candidato fuera de top-5 **solo se promueve** si `score_sgns` supera al 5º candidato actual **con margen** (`score_sgns_cand > score_sgns_top5 + margen`), y el desplazado no es el expected de otro caso del pool.
4. El margen es parámetro a barrer (`margen ∈ {0.02, 0.05, 0.10}`).

Esto esquiva la homogeneización que mató al sweep (reglas vividas: `tematico_score_senal_constante_pool_inerte`, `principio_señales_distribucionales_vs_especificas`).

### 4.2 Fix de la señal — sinonimo (14)

- Señal MF-SGNS ponderada por `N_ij` (Sección 3), con la loss logística correcta.
- **Gate de no-arranque (Fase 1, obligatorio):** sobre los 14 fallos sinonimo, ¿`score_sgns` coloca al expected en top-5 del pool? Si 0/14 → la co-ocurrencia ponderada tampoco porta señal para sinonimos léxicos puros → **hipótesis refutada de antemano, no se gasta el sweep** (mismo criterio de parada que Tejedora y que Plan 1).
- Si el gate pasa (≥6/14), se barre `k` y `margen` sobre mitad A.

---

## 5. Métricas de Éxito y Fracaso

| Métrica | Umbral | Significado |
|---|---|---|
| **Éxito** | ≥ 18 de 35 fallos rescatados (delta R@5 global ≥ +2.0pp) | La hipótesis distribucional ponderada PUENTEA el agujero |
| **Neutro** | 9-17 rescatados | Señal existe pero débil; no concluyente |
| **Fracaso** | < 9 rescatados, o gate sinonimo 0/14 | Co-ocurrencia ponderada no basta |

**Restricciones (no negociables, heredadas del Plan 1):**
- Ninguna categoría pierde >1 caso (por_tema / sinonimo)
- Sin regresión en R@1 (protect-r0)
- Latencia no aumenta >5ms
- Los aciertos actuales permanecen estables (misma query → mismo top-1)
- **Gate de no-arranque sinonimo (Fase 1):** `score_sgns` debe separar al expected de pares aleatorios en los 14 sinonimo; si falla, se detiene el experimento antes del sweep.

---

## 6. Parámetros a barrer (Fase 2)

| Parámetro | Valores |
|---|---|
| `k` (negativos de la loss SGNS) | 1, 5, 10, 15 |
| `margen` de promoción (re-rank selectivo) | 0.02, 0.05, 0.10 |
| Ponderación | raw `N_qc·σ(PMI−log k)` vs `σ(PMI−log k)` sin peso vs NPMI escalado |
| **Total combinaciones** | 4 × 3 × 3 = **36 configs** |

Barrido sobre mitad A (457 casos). Criterio de selección: mayor rescate sin regresión >1 caso por categoría.

---

## 7. Protocolo — Fases 0-6

### Fase 0: Reuso (ya hecho en Plan 1)
- Snapshot `word2vec_pre_fase0_20260806_235239.db`, split 50/50 seed `20260804`, pool `experimento_rr_pool.json` (921 casos), baseline (R@5 global 94.67% en pool completo; 96.34% en mitad A). No se recrea.

### Fase 1: Gate de señal MF-SGNS (obligatorio, 1-2 h)
- `scripts/mf_sgns_gate.py` → para los 35 fallos: score_sgns de cada candidato del pool contra el query; métricas de discriminación (rank del expected, top1/top5, AUC vs pares aleatorios).
- **Criterios de no-arranque:** por_tema < 10/21 expected en top-5 por score_sgns, o sinonimo < 6/14 → refutación temprana.
- Salida: `scripts/mf_sgns_gate.json`

### Fase 2: Sweep de parámetros (2-4 h)
- 36 configs sobre mitad A, pipeline real `buscar_por_frase(limite=100)` (mismo esquema 8 workers que `word2vec_sweep.py`).
- Salida: `scripts/mf_sgns_sweep.json`

### Fase 3: Re-rank selectivo implementado + mitad B (1 h)
- Detrás de flag **`BIORAG_MFSGNS_RE_RANK_ENABLED` (default OFF)** — con flag OFF el comportamiento es idéntico (determinismo verificable).
- Evaluar mitad B (nunca vio el ajuste).

### Fase 4: Validación completa (1 h)
- 921 casos: R@5 / R@1 / MRR + por categoría. Latencia (>5ms = fail). Inspección manual de 20 puentes.

### Fase 5: Presentación al auditor técnico + decisión de negocio
- Plan + resultados + puentes de muestra con su score_sgns.
- Dennys decide (aprobador de negocio), el auditor valida contenido.

### Fase 6: Integración en producción (SOLO si Fase 5 aprueba)
- Flag ON + monitoreo en dashboard. La expansión de query por puente pasa a ser matemática, determinista y simbólica.

---

## 8. Archivos Involucrados

| Archivo | Rol |
|---|---|
| `scripts/mf_sgns_gate.py` | Fase 1: gate de señal (rank/AUC sobre 35 fallos) |
| `scripts/mf_sgns_sweep.py` | Fase 2: barrido 36 configs sobre mitad A |
| `scripts/word2vec_sweep.py` | Patrón de workers/evaluación (reusar) |
| `core/pmi_semantico.py` | `_construir_corpus` → `co_freq`, `doc_freq`, `total` (la matriz de co-ocurrencia real) |
| `core/similitud_conceptual.py` | Punto de inyección del re-rank (solo si integración aprobada) |
| `core/memory_store.py` | `buscar_por_frase` (L3079) — pipeline real del eval |
| `scripts/experimento_rr_pool.json` | Holdout 921 casos |
| `snapshots/word2vec_pre_fase0_20260806_235239.db` | Snapshot aislado |

---

## 9. Dependencias

- **Cero dependencias nuevas.** No numpy obligatorio (la pérdida logística se computa con `math.exp`). No gensim, no scipy, no LLM.
- El experimento usa floats de cálculo interno (PMI y sigmoide son operaciones escalares sobre conteos enteros) — igual que el NPMI actual en producción. **Ningún vector de punto flotante se persiste ni se aprende.**

---

## 10. Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| La co-ocurrencia ponderada tampoco separa sinonimos léxicos puros | Gate obligatorio Fase 1 antes del sweep; veredicto temprano sin gastar cómputo |
| Re-rank selectivo vuelve a homogeneizar | Margen de promoción + top-5 intocados + criterio estricto de regresión por categoría |
| Canibalización con NPMI/pmi_hebbiano | El puente solo cubre `score_pmi_nodo==0` → familia complementaria (verificar en Fase 4) |
| Latencia de computar co_ocurrencia a query-time | Caché de la matriz de co-ocurrencia (recálculo solo con crecimiento >10%, igual que pmi_semantico); score por pares precomputado para tokens frecuentes |
| Evaluación infiel a producción | Pipeline real `buscar_por_frase` sobre snapshot (lección de fidelidad, ya establecida en Plan 1) |

---

## 11. Referencias

- **`plan_word2vec_adaptado_puente_condicional.md`** (v0.2) — Plan 1: diseño, veredicto del auditor, Fases 0-1 ejecutadas
- **`word2vec_sweep_resultado.json`** — Fase 2 refutada: 0/81, mejor rescata 3 / regresiona 15, delta −2.75pp
- **`word2vec_discriminacion.json`** — bifurcación: por_tema señal existe (18/21 top-5), sinonimo no existe (0/14)
- **`word2vec_calibracion.json`** — gate de señal del Plan 1 (W1 AUC 0.709) que pasó pero no transfirió (lección: gate sobre pares conocidos ≠ señal de rescate sobre fallos reales)
- **`tematico_score_senal_constante_pool_inerte`** — toda señal nueva debe ser condicional (nodo BioRAG)
- **`principio_señales_distribucionales_vs_especificas`** — JSD −1.53pp: señales globales homogeneizan (nodo BioRAG)
- **Kenyon-Dean et al. (2021)** *"When Do You Need Billions of Words of Pretraining Data?"* Part 2 — SGNS = MF con loss logística ponderada; `w·c = PMI − log k`
- **Levy & Goldberg (2014)** *Neural Word Embedding as Implicit Matrix Factorization* — SGNS como factorización implícita de PMI shift
- **Lund & Burgess (1996)** HAL — co-ocurrencia ponderada como semántica distribucional count-based
- **`protocolo_avance_autonomo_validacion_auditor_externo`** — metodología de validación cruzada con auditor

---

*Documento generado por Athena-OEC. Borrador v0.1 — bifurcación del diagnóstico fundamentada en evidencia (sweep 81 configs + discriminación 35 fallos). Pendiente: revisión del auditor y aprobación de Dennys.*
