# Plan 3 — El Eslabón Faltante: Coseno sobre SPPMI-shift (la señal que SGNS realmente factoriza)

**Estado:** PROPUESTO 2026-08-08 — borrador v1.0 para revisión del auditor técnico y aprobación de negocio (Dennys). Todo el experimento corre sobre snapshot aislado (`word2vec_pre_fase0_20260806_235239.db`), protocolo establecido. Nada toca producción.

**Autor:** Athena-OEC
**Versión:** 1.0
**Sucede al plan:** `plan_word2vec_plan2_mfsgns_puente_v2.md` (v0.2, Fase 1 ejecutada y REFUTADA)

---

## 0. Respuesta directa a la pregunta de negocio

> **¿Podemos alimentar la maquinaria de Word2vec con lo que BioRAG ya tiene, para traducir lenguaje humano a espacio geométrico sin embeddings de punto flotante?**

**SÍ, casi totalmente — y hay exactamente UN eslabón que nunca se probó.**

La matriz de co-ocurrencia real que Word2vec factoriza ya la construye BioRAG en producción:
`core/pmi_semantico.py::_construir_corpus()` → `co_freq` (pares co-ocurrentes), `doc_freq` (frecuencias), `total` (nodos). Esos tres contadores SON la entrada exacta de la matriz que SGNS aprende a factorizar (`M[i,j] = PMI(i,j) − log k`). El mapeo es directo:

| Parámetro Word2vec/SGNS | Equivalente en BioRAG | Estado |
|---|---|---|
| Corpus de entrenamiento | nodos `largo_plazo` activos (756 en snapshot) | ✅ ya existe |
| Tokenización | `_tokenizar()` con stems + stopwords | ✅ ya existe |
| Ventana (window size) | `VENTANA_NODO` (0 = nodo completo) | ✅ ya existe |
| min_count | `UMBRAL_FREQ_MINIMA` (3) | ✅ ya existe |
| Matriz de co-ocurrencia `#(w,c)` | `co_freq` (Counter de pares) | ✅ ya existe |
| Frecuencias `#(w)`, `#(c)` | `doc_freq` | ✅ ya existe |
| Total de pares `N` | `total` | ✅ ya existe |
| **`k` (negativos de la loss)** | hiperparámetro libre | ✅ barrible |
| **La señal de segundo orden (lo que SGNS factoriza)** | `SPPMI = max(PMI − log k, 0)` | ❌ **NUNCA probado como peso** |

**La conclusión honesta:** con lo que tenemos generamos el espacio geométrico — pero el último eslabón (usar el peso PMI-shift en el coseno de contexto, exactamente la matriz que Word2vec factoriza) **no se ha evaluado**. Los dos gates ya corridos usaron pesos que la propia teoría de Levy-Goldberg descarta.

---

## 1. La matemática verificada de Word2vec (fuente: PDF NIPS Levy & Goldberg 2014, leído completo)

### 1.1 Qué hace SGNS exactamente

Skip-Gram Negative Sampling aprende dos matrices de vectores (W = word vectors, C = context vectors) minimizando por SGD:

```
L(i,j) = N_ij · log σ(w_i·c_j) + k · N_i·N_j/N · log σ(−w_i·c_j)
```

donde `N_ij` = co-ocurrencia real del par, `N_i`/`N_j` = frecuencias, `N` = total de pares, `k` = negativos muestreados, `σ` = sigmoide.

**Teorema central (Levy & Goldberg 2014):** en el óptimo,

```
w_i · c_j = PMI(i,j) − log k
```

Es decir: **Word2vec está factorizando implícitamente la matriz shifted-PMI.** Todo el "significado geométrico" que aprende es una aproximación de baja dimensión de esa matriz.

### 1.2 La versión count-based exacta: SPPMI

Como SGNS solo factoriza `M[i,j] = PMI(i,j) − log k`, la versión simbólica equivalente (sin entrenar nada) es:

```
SPPMI_k(i,j) = max( PMI(i,j) − log k , 0 )
PMI(i,j) = log( N · N_ij / (N_i · N_j) )
```

Levy & Goldberg demuestran que SPPMI es la factorización **unweighted** de la misma matriz que SGNS factoriza **weighted**, y que para similitud de palabras SPPMI + coseno rinde a la par del SGNS entrenado. **SPPMI es Word2vec hecho simbólico — sin vectores aprendidos, sin punto flotante persistido, usando solo los conteos enteros que BioRAG ya tiene.**

### 1.3 La señal correcta de similitud (segundo orden)

"Una palabra se conoce por la compañía que mantiene" (Firth) se materializa como **coseno entre filas de la matriz de co-ocurrencia** — contexto compartido ponderado:

```
vector_contexto(t) = { u : SPPMI_k(t, u) }   para todo u
similitud(q, c)    = coseno( vector_contexto(q), vector_contexto(c) )
```

Esto NO es co-ocurrencia directa (que es nula para sinonimos léxicos puros). Es: *¿con quiénes se codea cada palabra, y qué tanto se parecen sus compañías?*

---

## 2. Estado real de la evidencia — qué se probó y qué NO

### 2.1 Gate v1 (`mf_sgns_gate.json`, 2026-08-08) — REFUTADO

`score_sgns = N_qc·σ(PMI − log k)` = **co-ocurrencia DIRECTA** query↔candidato.

| Señal | por_tema (21) top-5 | sinonimo (14) top-5 |
|---|---|---|
| P1 (sin peso) | 2 | 1 |
| P2 (peso N_qc) | 3 | 0 |
| P3 (pmi_nodo actual) | 2 | 0 |

**Veredicto:** FALLA ambos criterios. Pero esto era **esperable por diseño**: el gate v1 mide co-ocurrencia directa, que es nula por definición para "perfil"→"dennys-identidad-profunda". No es una refutación de la hipótesis distribucional — es la prueba de que la señal de primer orden no alcanza (el mismo script lo declara).

### 2.2 Gate v2 (`mf_sgns_gate_v2.json`, 2026-08-08) — INCOMPLETO, no refutado

`score_so = coseno( vector_contexto(q), vector_contexto(c) )` = señal de **segundo orden** (la correcta). PERO el archivo de resultado guardado corresponde a `--peso BIN` (vector de contexto binario de presencia).

| Peso usado | por_tema (21) top-5 | sinonimo (14) top-5 |
|---|---|---|
| BIN (binario de presencia) | 3 | 0 |

**El peso que la teoría exige — PMI-shift (`SPPMI_k`) — está implementado en el código** (`MF_SGNS_SO._peso_par` con `self.peso == 'PMI'`, línea 82-88) **pero no tiene un JSON de resultado reportado.** El último corrido sobrescribió el archivo con BIN.

**Esto es el eslabón faltante:** el coseno sobre filas de **SPPMI-shift** (el peso que Word2vec realmente aprende) es la ÚNICA señal de segundo orden que la teoría predice que funcionaría, y no se ha medido. La opción PMI del gate v2 usa `max(0, pmi)` = SPPMI con k=1; falta además barrer el shift `−log k` para k ∈ {5, 15}.

> Nota de rigor: el gate v2 con peso NQ (frecuencia cruda) también está disponible en código pero sin JSON reportado. Si se corrió, no quedó evidencia — bajo las reglas vividas de esta casa, **lo que no tiene artefacto de salida no está corrido.**

### 2.3 La pregunta que el auditor debe resolver (diseño, no descripción)

> **¿El coseno entre filas de SPPMI-shift (la matriz exacta que Word2vec factoriza) separa al nodo esperado del resto del pool en los 35 fallos?**

- Si **PASA** → la hipótesis distribucional se materializa por fin: Word2vec simbólico, count-based, sin embeddings. Se abre el sweep y el re-rank selectivo.
- Si **FALLA** → la refutación es epistemológicamente sólida: no quedará ningún peso teórico sin probar (directo-BIN-NQ-PMI-shift), y la conclusión honesta es que este corpus (756 nodos, ~30 tokens/nodo) no porta señal distribucional suficiente para sinonimos léxicos puros. Se cierra el experimento con evidencia completa, sin gastar el sweep.

---

## 3. La Meta (transformada por Dennys, 2026-08-08 — invariante)

> **Que BioRAG entienda por significado y no por palabra exacta, sin usar embeddings de punto flotante — materializando la hipótesis distribucional de Firth sobre el sustrato simbólico (co-ocurrencia real, pesos enteros, sin vectores aprendidos).**

Meta operativa del experimento:
> **Probar el ÚNICO eslabón no medido del puente distribucional (coseno sobre SPPMI-shift) sobre los 35 fallos top-5 (21 por_tema + 14 sinonimo). Si el gate pasa (≥6/14 sinonimo y ≥10/21 por_tema en top-5), barrer `k` y `margen` y rescatar ≥18/35 sin regresar ningún acierto. Si falla, cerrar el experimento con refutación completa y evidencia.**

---

## 4. Por qué SPPMI-shift es diferente de lo que ya falló

| Señal probada | Qué mide | Por qué falló / es insuficiente |
|---|---|---|
| HDC binario (Plan 1) | Jaccard/Hamming de vecinos | Pierde magnitudes; sinonimos sin solape → 0/14 |
| Gate v1 (PMI directo) | `N_qc·σ(PMI−log k)` | Co-ocurrencia directa nula para sinonimos léxicos puros |
| Gate v2 BIN | coseno de contextos binarios | Presencia ≠ fuerza; ignora la frecuencia marginal |
| **SPPMI-shift (este plan)** | **coseno de contextos ponderados por `PMI − log k`** | **Normaliza por frecuencia marginal — la matriz que SGNS realmente factoriza** |

La diferencia esencial: BIN y NQ no descuentan la frecuencia marginal. Un token frecuente co-ocurre con todo "solo por ser frecuente" → su vector de contexto está contaminado. PMI-shift resta ese ruido de fondo exactamente como lo hace Word2vec (`w·c = PMI − log k`).

---

## 5. Métricas de Éxito y Fracaso (idénticas al Plan 2, ahora con el peso correcto)

| Métrica | Umbral | Significado |
|---|---|---|
| **Éxito** | ≥ 18 de 35 fallos rescatados (delta R@5 ≥ +2.0pp) | La hipótesis distribucional ponderada PUENTEA el agujero |
| **Neutro** | 9-17 rescatados | Señal existe pero débil; no concluyente |
| **Fracaso** | < 9 rescatados, o gate SPPMI-shift 0/14 sinonimo | Co-ocurrencia ponderada no basta en este corpus |

**Restricciones (no negociables):**
- Ninguna categoría pierde >1 caso
- Sin regresión en R@1 (protect-r0)
- Latencia no aumenta >5ms
- Aciertos actuales estables (misma query → mismo top-1)

---

## 6. Fases

### Fase 0: Reuso (ya hecho)
Snapshot `word2vec_pre_fase0_20260806_235239.db`, split 50/50 seed `20260804`, pool `experimento_rr_pool.json` (921 casos), baseline R@5 global 94.67%. No se recrea.

### Fase 1: Gate del eslabón — coseno sobre SPPMI-shift (obligatorio, <1 h)
Correr `mf_sgns_gate_v2.py` con el peso PMI ya implementado, más el shift `−log k`:

| Variante | Peso del vector de contexto |
|---|---|
| PMI (k=1) | `max(0, PMI)` = SPPMI_1 |
| PMI-shift k=5 | `max(0, PMI − log 5)` = SPPMI_5 |
| PMI-shift k=15 | `max(0, PMI − log 15)` = SPPMI_15 |

- **Criterios de no-arranque:** sinonimo < 6/14 o por_tema < 10/21 en top-5 con CUALQUIERA de las tres variantes → refutación temprana con evidencia completa.
- Salida: `scripts/mf_sgns_gate_v3.json` (nuevo nombre — no sobrescribir v2, se preserva la cadena de evidencia).

### Fase 2: Sweep de parámetros (solo si gate PASA)
- `k ∈ {1, 5, 10, 15}` × `margen ∈ {0.02, 0.05, 0.10}` × ponderación (raw vs σ) = 36 configs sobre mitad A (457 casos), pipeline real `buscar_por_frase(limite=100)`.

### Fase 3: Re-rank selectivo + mitad B
- Detrás de flag `BIORAG_MFSGNS_RE_RANK_ENABLED` (default OFF). Evaluar mitad B (nunca vio el ajuste).

### Fase 4: Validación completa
- 921 casos: R@5/R@1/MRR + por categoría. Latencia (>5ms = fail). Inspección manual de 20 puentes.

### Fase 5: Presentación al auditor + decisión de negocio
- Plan + resultados + puentes de muestra con su score SPPMI. Dennys decide, el auditor valida contenido.

### Fase 6: Integración en producción (SOLO si Fase 5 aprueba)
- Flag ON + monitoreo. Expansión de query matemática, determinista y simbólica.

---

## 7. Archivos Involucrados

| Archivo | Rol |
|---|---|
| `scripts/mf_sgns_gate_v2.py` | YA contiene el peso PMI (`_peso_par`, líneas 82-88); falta el shift `−log k` |
| `scripts/mf_sgns_gate_v3.py` | (nuevo) Gate SPPMI-shift con salida separada `mf_sgns_gate_v3.json` |
| `core/pmi_semantico.py` | `_construir_corpus` → `co_freq`, `doc_freq`, `total` (la matriz real) |
| `core/memory_store.py` | `buscar_por_frase` (L3079) — pipeline real del eval |
| `scripts/experimento_rr_pool.json` | Holdout 921 casos |
| `snapshots/word2vec_pre_fase0_20260806_235239.db` | Snapshot aislado |

---

## 8. Dependencias

- **Cero dependencias nuevas.** PMI, `−log k`, coseno y shift se computan con `math.*` sobre conteos enteros.
- `numpy 2.4.3` está disponible en el sistema (verificado) pero NO es obligatorio — el experimento completo se hace con `math` puro. (SVD solo se consideraría en una fase futura, si el negocio quisiera vectores densos — y eso YA sería embedding, fuera del alcance de la meta.)

---

## 9. Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| El gate v2 BIN ya falló y el eslabón PMI-shift podría correr la misma suerte | Es exactamente la pregunta; el costo es <1h y el veredicto es informativo en ambos sentidos (pasa → sweep; falla → refutación completa y cierre limpio del experimento) |
| Corpus de 756 nodos demasiado chico para señal distribucional | Es el riesgo real y honesto. PMI-shift es el último peso teóricamente correcto; si falla, el límite es del corpus, no de la implementación |
| Confundir "no probado" con "refutado" | Cadena de evidencia con salidas separadas (v1, v2, v3); el plan 3 documenta explícitamente que BIN no es la señal que la teoría exige |
| Latencia de coseno a query-time | Caché de matriz (recálculo con crecimiento >10%, patrón `pmi_semantico`); solo pares relevantes |

---

## 10. Referencias

- **`plan_word2vec_plan2_mfsgns_puente_v2.md`** — Plan 2: la bifurcación por_tema/sinonimo, el diseño del puente
- **`mf_sgns_gate.json`** — Gate v1: co-ocurrencia directa, REFUTADO (0-3/14 sinonimo, por diseño)
- **`mf_sgns_gate_v2.json`** — Gate v2: segundo orden con peso BIN, 0/14 sinonimo — INCOMPLETO (peso equivocado)
- **`word2vec_discriminacion.json`** — bifurcación: por_tema señal existe, sinonimo no
- **`word2vec_calibracion.json`** — lección: gate sobre pares conocidos ≠ señal de rescate sobre fallos reales
- **Levy & Goldberg (2014)** *Neural Word Embedding as Implicit Matrix Factorization* — `w·c = PMI − log k`; SPPMI como versión count-based; coseno sobre filas como similitud. **Fuente primaria leída completa (PDF NIPS).**
- **Kenyon-Dean et al. (2021)** Part 2 — SGNS = MF con loss logística ponderada
- **`principio_señales_distribucionales_vs_especificas`** — señales globales homogeneizan (nodo BioRAG)
- **`protocolo_avance_autonomo_validacion_auditor_externo`** — metodología de validación cruzada con auditor

---

*Documento generado por Athena-OEC. Borrador v1.0 — creado tras verificar la matemática de Word2vec contra el sistema real (mapeo completo, Sección 0) y auditar el estado de la evidencia (Sección 2). Pendiente: revisión del auditor y aprobación de Dennys. El gate SPPMI-shift es el ÚNICO eslabón de la teoría que nunca se midió.*
