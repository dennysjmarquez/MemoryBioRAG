# Plan Word2Vec Adaptado — Puente Distribucional Condicional (HDC)

**Estado:** PROPUESTO 2026-08-06 — borrador v0.1 para revisión del auditor técnico (Claude) y aprobación de negocio (Dennys). Nada se ejecuta sobre producción: todo el experimento corre sobre snapshot aislado (protocolo establecido).

**Autor:** Athena-OEC
**Versión:** 0.1

---

## 1. Contexto — ¿Por qué este experimento?

**Veredicto de Tejedora Fase 2 (2026-08-06):** tejer sinapsis estructurales dio **+0.000pp** sobre los 921 casos. El recall de BioRAG NO mejora agregando cableado al grafo — **el cuello de botella es el matching léxico/semántico, no la red** (plan_tejedora L153-172).

**Lo que ya existe (verificado en código):**
- `core/pmi_semantico.py` — NPMI token-level con stems (Church & Hanks 1990). En producción como `pmi_hebbiano` (~1.8k sinapsis) al INGERIR nodos, y como `score_pmi_nodo` (peso 0.15) en query-time.
- `core/sdm.py` — SDM v2: vectores binarios 2048 bits con multi-proyección por hash (`_activar_proyecciones`, sdm.py:125). Sustrato HDC ya operativo.
- `score_pmi_nodo` hace completación de patrón: por cada token del query toma el mejor NPMI contra los tokens del candidato.

**El agujero:** cuando `NPMI(query_token, candidate_token) = 0` (vocabulario que nunca co-ocurrió en el corpus), el patrón de completación da 0 — no hay nada que puentee las palabras. Eso explica una parte de los **35 fallos top-5 de por_tema+sinonimo del pool de 921 casos (21 por_tema + 14 sinonimo, re-verificados en Fase 0 sobre `experimento_rr_pool.json` y `tejedora_baseline.json`)**. El conteo original "40 (23+17)" era de una medición previa sin remedición; la regla es remedir siempre.

**La idea:** aplicar el PRINCIPIO de word2vec — *hipótesis distribucional: "lo similar aparece en contextos similares"* — para puentear tokens con NPMI=0, expresado en el sustrato HDC/SDM que BioRAG ya tiene. NO embeddings, NO gensim, NO LLM.

**Lo que NO hace este experimento:**
- NO es word2vec literal (corpus ~377 nodos activos = matriz demasiado ruidosa; V1 PPMI+SVD descartado por eso)
- NO es una señal global (JSD -1.53pp, content_ratio -1.54pp, tematico_score inerte — lección documentada 4 veces en BioRAG)
- NO usa LLM en ningún punto (la paráfrasis LLM existente queda intacta e independiente)
- NO toca producción (experimento aislado, flag OFF por defecto, snapshot)

---

## 2. La Meta

> **Rescatar los 35 fallos top-5 de por_tema+sinonimo del pool de 921 casos (21 por_tema + 14 sinonimo, re-verificados en Fase 0) sin regresar ninguno de los 846 aciertos de esas categorías ni de las otras, usando un puente condicional de vocabulario basado en vectores de contexto HDC — el principio de word2vec sin LLM, sin embeddings y sin dependencias nuevas.**

Sub-metas:
1. Completar a query-time lo que `pmi_hebbiano` ya hace en ingestión: aprendizaje de equivalencias de vocabulario automático.
2. Dejar la paráfrasis LLM como refuerzo opcional, no como muleta del recall.
3. Dejar medido si el techo de recall depende de co-ocurrencia (estadística) o de contexto (distribucional) — el veredicto científico del experimento.

> **NOTA Fase 0 (2026-08-06):** la meta original decía "40 fallos (23 por_tema + 17 sinonimo)". La remedición sobre el pool congelado (`experimento_rr_pool.json`, 921 casos, seed 20260804) y el baseline oficial de Tejedora (`tejedora_baseline.json`) da **35 fallos reales: 21 por_tema (44/65) + 14 sinonimo (47/61)**. Los 5 restantes del conteo previo probablemente venían de una medición sobre DB en estado distinto. Los umbrales de la tabla 3 se recalibran proporcionalmente.

---

## 3. Métricas de Éxito y Fracaso

| Métrica | Umbral | Significado |
|---|---|---|
| **Éxito** | ≥ 18 de 35 fallos rescatados (≈50% del pool de fallos reales; delta R@5 global ≥ +2.0pp) | La hipótesis distribucional PUENTEA el agujero |
| **Neutro** | 9-17 fallos rescatados | Señal existe pero débil; no concluyente |
| **Fracaso** | < 9 rescatados | La co-ocurrencia no basta; el principio no se adapta al corpus |

> **Calibración (2026-08-06):** la tabla original (≥20/40, neutro 10-19, fracaso <10) se definió sobre el conteo previo de 40 fallos. Con los 35 reales de Fase 0, se recalibró proporcionalmente (50% de rescate = 18/35). **Pendiente de confirmación literal del auditor/Dennys** — la proporción (¿50% o fija en 20?) no fue decidida explícitamente (regla: todo criterio necesita proveniencia aprobada).

**Restricciones (no negociables):**
- Ninguna categoría pierde >1 caso (por_tema / sinonimo)
- Sin regresión en R@1 (protect-r0)
- Latencia no aumenta >5ms
- Los 881 aciertos actuales permanecen estables (misma query → mismo top-1)

**Gate de no-arranque (Fase 1b):** si los vectores de contexto HDC no separan los pares de sinónimos CONOCIDOS de pares aleatorios (sinapsis `sinonimo_explicito` — 4694 en la medición de Fase 0 2026-08-06, remedir antes de usar + columna `sinonimos`), la señal no porta información → hipótesis refutada de antemano → se detiene el experimento sin gastar el sweep.

---

## 4. Parámetros del Experimento

### 4.1 El corazón del "word2vec adaptado": contexto por término

Cada término `T` del corpus recibe un **vector binario HDC de contexto** = superposición (activación multi-proyección, hash md5 con seeds, reusando `_activar_proyecciones` de sdm.py:125) de los tokens con los que co-ocurre.

Ventana de co-ocurrencia (a barrer):
- **W0 — Nodo completo:** mismo criterio que `pmi_semantico` (VENTANA_NODO=0). Contexto léxico.
- **W1 — Nodo + vecinos sinápticos (1-hop):** el contexto se define por la RED, no solo por el texto. Contexto estructural-distribucional.
- **W0+W1 — Combinado.**

Similitud distribucional `S_dist(Ta, Tb) = similitud_sdm` (Hamming) entre sus vectores de contexto. Es *count-based word2vec en espacio HDC*: dos palabras son intercambiables si aparecen rodeadas de las mismas palabras/nodos.

Filtros de corpus: stems (reusar `stemmer_es`), stopwords fuera, frecuencia mínima 3 (mismo criterio que `pmi_semantico`).

### 4.2 Trigger condicional (la lección JSD aplicada)

El puente SOLO se activa donde las señales específicas fallan:

1. `score_pmi_nodo == 0` — ningún par query↔candidato tiene NPMI > 0 (el agujero exacto)
2. El candidato NO está en top-5 — solo afecta candidatos que no llegaron (no reordena aciertos)

Nunca es una señal global. Nunca se agrega al score de un candidato que ya está en top-5. Con eso se esquiva la homogeneización que mató a JSD (señal distribucional global → empata queries genéricas).

### 4.3 Parámetros a barrer (Fase 2)

| Parámetro | Valores |
|---|---|
| Ventana de contexto | W0, W1, W0+W1 |
| Top-K puentes por token de query | 5, 10, 20 |
| Peso del puente (reemplaza NPMI en el fallback) | 0.10, 0.15, 0.20 |
| Umbral de similitud HDC para aceptar puente | top-K relativo (sin umbral), ≥0.50, ≥0.60 |
| **Total combinaciones** | 3 × 3 × 3 × 3 = **81 configs** |

Barrido sobre mitad A del holdout (8 workers, mismo esquema que `tejedora_sweep.py`). Criterio de selección: mayor rescate sin regresión >1 caso por categoría.

### 4.4 Anti-canibalización (lección de backfill_predicados)

Antes de integrar, verificar en Fase 4 que el puente NO duplica una señal existente de la misma familia con datos incompletos. Evidencia esperada: el puente cubre `NPMI=0`, zona que `pmi_hebbiano`, `co_semantica` y el jaccard de re-ranking NO alcanzan (todos operan sobre co-ocurrencia/existencia léxica > 0) → familia COMPLEMENTARIA, no superpuesta.

---

## 5. Protocolo — Fases 0-8

### Fase 0: Preparación (30 min)
1. **Snapshot de la DB actual** (protocolo establecido; remedir el conteo de nodos activos en el momento — nunca confiar en conteos de snapshots viejos)
2. **Holdout split 50/50** con seed fija `20260804`, reusando `experimento_faseB_holdout.py` + `experimento_rr_pool.json` (921 casos)
3. **Baseline:** R@5 / R@1 / MRR + enumeración de los 40 fallos por categoría → `scripts/word2vec_baseline.json`

### Fase 1: Vectorizador HDC + Gate de calibración (1-2 h)
- `scripts/word2vec_vectorizador.py` → construye los vectores de contexto por término (ambas ventanas) sobre el snapshot → `scripts/word2vec_vectores.json`
- `scripts/word2vec_calibracion.py` → gate de no-arranque: ¿la similitud HDC separa pares `sinonimo_explicito` conocidos de pares aleatorios? → `scripts/word2vec_calibracion.json`
- **Si el gate falla → veredicto temprano: hipótesis refutada, no se gasta el sweep** (mismo criterio de parada que Tejedora)

### Fase 2: Sweep de parámetros (2-4 h)
- 81 configs sobre mitad A, `buscar_por_frase` real (limite=5)
- Seleccionar mejor config por mayor rescate sin regresión

### Fase 3: Bridge implementado + evaluación mitad B (1 h)
- Implementación del fallback condicional detrás de flag **`BIORAG_W2V_BRIDGE_ENABLED` (default OFF)** — con flag OFF el comportamiento de producción es IDÉNTICO (verificable por determinismo)
- Evaluar mitad B (nunca vio el ajuste)

### Fase 4: Validación completa (1 h)
- 921 casos completos: R@5 / R@1 / MRR + por categoría
- Latencia (>5ms = fail) + inspección manual de 20 puentes de muestra
- Verificación de anti-canibalización (4.4)

### Fase 5: Presentación al auditor técnico + decisión de negocio
- Plan + resultados + puentes de muestra con su similitud HDC
- Dennys decide la inversión (aprobador de negocio), el auditor valida contenido

### Fase 6: Integración en producción (SOLO si Fase 5 aprueba)
- Flag ON + monitoreo en dashboard
- La expansión de query por puente pasa a ser matemática y determinista

### Fase 7: Documentación
- EXPERIMENTS.md, CHANGELOG.md, nodo BioRAG con dimensiones y sinónimos

### Fase 8: Commit
- Commit descriptivo, backup de DB post-experimento

---

## 6. Archivos Involucrados

| Archivo | Rol |
|---|---|
| `scripts/word2vec_vectorizador.py` | Fase 1: vectores de contexto HDC por término |
| `scripts/word2vec_calibracion.py` | Fase 1: gate de no-arranque (sinónimos conocidos vs random) |
| `scripts/word2vec_sweep.py` | Fase 2: barrido 81 configs (reusar patrón tejedora_sweep) |
| `scripts/word2vec_eval.py` | Fases 3-4: evaluación con bridge condicional |
| `core/sdm.py` | Reuso: `_activar_proyecciones` (multi-hash), `similitud_sdm` |
| `core/pmi_semantico.py` | Trigger condicional: `score_pmi_nodo` |
| `core/similitud_conceptual.py` | Punto de inyección del fallback (solo si integración aprobada) |
| `core/memory_store.py` | `buscar_por_frase` (L3079) — pipeline real del eval |
| `scripts/experimento_faseB_holdout.py` | Protocolo split 50/50 (reusar) |
| `scripts/experimento_rr_pool.json` | Holdout 921 casos |

---

## 7. Dependencias

- **numpy 2.4.3** (ya instalado; probablemente ni se necesita — HDC es operación de bits)
- **Cero dependencias nuevas.** No scipy, no gensim (V3 node2vec descartado por introducir dependencia externa).

---

## 8. Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| Homogeneización JSD-like (señal global empata genéricas) | Trigger condicional estricto: solo NPMI=0 y solo fuera de top-5 + gate de calibración |
| Evaluación infiel a producción | Pipeline real `buscar_por_frase` sobre snapshot (no replicación propia) — lección de fidelidad |
| Corpus chico (~377 nodos) → contexto escaso | Ventana W1 (grafo 1-hop) + freq≥3 + gate ANTES del sweep |
| Canibalización con señales existentes | Verificación de familia complementaria en Fase 4 (lección backfill_predicados) |
| Regresión de categorías | Umbral categórico (>1 caso = fail) + protect-r0 |
| Falso puente semántico | Inspección manual de 20 puentes + solo puentes que rescatan fallos concretos |

---

## 9. Referencias

- **plan_tejedora_agujeros_estructurales.md** — veredicto +0.000pp: el cuello de botella es matching, no cableado (L153-172)
- **principio_señales_distribucionales_vs_especificas** — JSD -1.53pp por_tema; toda señal candidata debe evaluarse contra queries genéricas
- **tematico_score_senal_constante_pool_inerte** — 22/23 fallos por_tema con jaccard > promedio top-5 → la señal nueva debe ser condicional
- **backfill_predicados_restaura_parcial_no_84_62_y_canibaliza_con_jaccard** — antes de añadir una señal de matching, verificar familia existente con datos incompletos
- **decision_word2vec_hdc_puente_condicional_v2** (nodo BioRAG) — decisión de estrategia: HDC primario, V1/V3 descartados, remedir siempre
- **protocolo_avance_autonomo_validacion_auditor_externo** — metodología de validación cruzada con auditor

---

## 11. Respuesta al dictamen del auditor (2026-08-06, verificación real contra código y DB)

**Veredicto del auditor:** plan técnicamente sólido y metodológicamente riguroso; 6 afirmaciones verificadas contra código (sdm.py:125, SDM_BITS=2048, PMI 0.15 en similitud_conceptual.py, buscar_por_frase memory_store.py:3079, pool/baseline/holdout, VENTANA_NODO env) y 5 de 6 referencias de memoria confirmadas. **Un punto serio: `decision_word2vec_hdc_puente_condicional_v2` no aparecía como nodo en largo_plazo al momento de la auditoría.**

**Resolución (Athena-OEC):** el nodo SÍ existía, pero estaba en **corto_plazo (id 794) — nunca consolidado** → por eso no era visible en largo_plazo (donde el auditor buscó) y estaba en riesgo de poda. La cita no era fabricada; era un respaldo temporal no fijado. **Acción correctiva: `biorag_consolidar()` ejecutado; verificado contra DB que los 3 nodos word2vec pasaron a largo_plazo activos (ids 1007-1009)**. La referencia ahora es a memoria consolidada y verificable.

**Nota sobre conteo sinonimo_explicito:** auditor reportó 4578; este plan midió 4694 en Fase 0 y 4722 post-consolidación. Diferencia por drift entre mediciones — consistente con la regla del proyecto (remedir siempre, no fijarse en conteos de un momento).

**Pendiente que el auditor NO decide (decisión de negocio, solo Dennys):** umbral de éxito — ¿proporcional 50% (≈18/35, calibrado en este plan) o fijo en 20? Ver Sección 3, tabla recalibrada.

---

## 10. Cronograma

| Fase | Tiempo estimado | Dependencias |
|---|---|---|
| Fase 0 | 30 min | Snapshot + split + baseline |
| Fase 1 | 1-2 h | Vectorizador + gate de calibración |
| Fase 2 | 2-4 h | 81 configs × mitad A |
| Fase 3 | 1 h | Bridge + mitad B |
| Fase 4 | 1 h | 921 completos + latencia + anti-canibalización |
| Fase 5 | — | Presentación al auditor + decisión Dennys |
| Fases 6-8 | 1-2 h | Solo si Fase 5 aprueba |
| **Total** | **6-9 h** | |

---

*Documento generado por Athena-OEC. Borrador v0.2 — dictamen del auditor integrado (Sección 11), punto de memoria resuelto por consolidación. Pendiente: decisión de negocio del umbral (Dennys) y aprobación de Fases 5-6.*
**Anexo 11.1 — Resolución del salto de nodos activos (377 → 433) reportado por el auditor (2026-08-07):**

El auditor detectó que los nodos activos pasaron de 377 a 433 (+56) entre su clon original (fe5f19e) y el commit actual (62e3c83), preguntando si la Hormiguita, un backfill o Tejedora generaron el salto. **Verificación directa contra las DBs de los 4 commits clave:**

| Commit | Activos | Dormidos | Total | max_id | Delta activos |
|---|---|---|---|---|---|
| fe5f19e (clon original) | 377 | 378 | 755 | 1004 | — |
| 94e6e65 (merge origin/master) | 402 | 353 | 755 | 1004 | +25 |
| a81e157 (docs word2vec) | 433 | 328 | 761 | 1010 | +31 |
| 62e3c83 (chore db, actual) | 433 | 328 | 761 | 1010 | 0 |

**Conclusión: NO son 56 nodos nuevos — el total creció solo +6 (755 → 761).**
- **+25** del merge 94e6e65: trajo estados de otra rama (mismos nodos, distinto estado activo/dormido). Cero creación de nodos.
- **+31** de a81e157: +6 nodos nuevos reales (ids 1005-1010: 2 de Tejedora merge, 4 del trabajo word2vec) + rebalanceo del ciclo de consolidación/sueño (reactivó 142, durmió 117, neto +25 en ese paso).
- **Hormiguita:** corrió (174 ciclos, 725 visitados) pero NO crea nodos — solo evalúa/poda sinapsis. No es causa.
- **Backfill:** ninguno en estos commits.
- El rebalanceo activo↔dormido es comportamiento normal del ciclo de sueño (refuerza lo nuevo, decae lo viejo).

**Veredicto final:** la DB tiene 6 nodos reales más que el clon original del auditor, no 56. Nada patológico. Autorizado Fase 0-2.

