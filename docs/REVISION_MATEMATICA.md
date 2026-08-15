# Revisión matemática de MemoryBioRAG (v28.0)

Revisión hecha sobre el clon del repo en commit `364a770`, leyendo el código real
(`core/ppmi_vectorizer.py`, `core/ppmi_hybrid_search.py`, `core/memory_store.py`,
`core/sdm.py`, `core/pmi_semantico.py`, `core/inferencia_transitiva.py`,
`core/tematica.py`, `scripts/`), no sólo el README.

---

## 0. Veredicto corto

El proyecto es **serio y coherente**: PPMI + SVD truncado + retrofitting de Faruqui
sobre el grafo, PMI/NPMI aprendido, SDM binario tipo Kanerva, propagación multi-hop
con decaimiento, e inferencia transitiva con validación dual. Está bien elegido:
es exactamente la familia de métodos que funciona sin GPU en corpus pequeños
(cientos–miles de nodos), donde un embedding denso preentrenado es sobre-ingeniería.

Lo que **más te falta no es más biología, es estadística de decisión**:
1. la fusión de señales es una suma lineal de escalas incomparables con pesos a mano,
2. no hay calibración de probabilidad ni umbral de abstención derivado de datos,
3. el reporte de métricas no tiene intervalos de confianza ni tests pareados,
4. y hay 3–4 bugs matemáticos concretos, pequeños pero reales.

Abajo va todo con detalle, y te dejé dos módulos ejecutables:
`core/calibracion.py` y `scripts/evaluacion_estadistica.py`.

---

## 1. Bugs / inconsistencias matemáticas concretas

### 1.1 `varianza_explicada_top_k` siempre da 1.0 (bug real)

`core/ppmi_vectorizer.py`, `PPMISVD.entrenar`:

```python
U, S, Vt = np.linalg.svd(ppmi, full_matrices=False)
U = U[:, :dim_real]
S = S[:dim_real]          # <-- S ya quedó truncada aquí
...
var_total = (S**2).sum()               # suma de los top-k
var_expl  = (S[:dim_real]**2).sum() / var_total   # = 1.0 SIEMPRE
```

Verificado ejecutándolo: devuelve `varianza_explicada_top_k: 1.0` para dim=3 y
dim=10 sobre el mismo corpus. La métrica no informa nada. Fix:

```python
U_full, S_full, _ = np.linalg.svd(ppmi, full_matrices=False)
var_total = float((S_full**2).sum())
U, S = U_full[:, :dim_real], S_full[:dim_real]
var_expl = float((S**2).sum() / (var_total + 1e-12))
```

Y con eso puedes por fin **elegir `dim=100` con criterio** en vez de por costumbre
(ver §2.1).

### 1.2 Los pesos del score híbrido suman 1.34, no 1

`_calcular_score_hibrido` (memory_store.py:3146):

```
0.25+0.14+0.08+0.08+0.10+0.10+0.10+0.08+0.04+0.02+0.20 = 1.19
```
más `PPMI_VECTOR_WEIGHT = 0.15` fuera del `base_weight` → **1.34**.
Y luego `min(1.0, score)`. Consecuencia matemática: el score satura por arriba.
Todo candidato con evidencia media-alta se clipea a 1.0 y **el ranking pierde
resolución justo en el head**, que es donde importan R@1 y MRR. Además el
`base_weight = 1 - jsd_weight` sólo re-normaliza JSD, no el resto, así que el
comentario "sum to 1.0 when jsd_weight=0" es falso.

Esto también explica por qué GABA "no hace nada" en tu propia ablación
(`scripts/ablacion_resultado.json`: baseline 95.57 == sin GABA 95.57): el gate
`top_score >= 0.80` se dispara casi siempre por la saturación, y atenuar ×0.60 a
los que ya están por debajo de 0.7·top rara vez cambia el orden.

### 1.3 Pisos duros que destruyen el orden (`max(0.95, score)`)

```python
if match_exacto:      score = max(0.95, score)
elif sinonimos_ratio >= 0.95: score = max(0.70 + 0.10*ppmi, score)
```
Un `max` con constante es una función no monótona respecto a la evidencia: dos
nodos con match exacto quedan **empatados en 0.95** y el desempate lo decide el
orden de `sort` (estable → orden de la query SQL). Eso es ranking arbitrario.
Lo correcto es un *bonus aditivo en el espacio de logits* (ver §3), que preserva
el orden interno del grupo.

### 1.4 SDM: la "distancia" no es Hamming y el radio no filtra nada

`buscar_sdm`:
```python
dist = int((1.0 - sim) * SDM_BITS)   # sim = Jaccard ponderado
if dist <= radio_max:                # radio_max = 400 de 2048
```
Eso exige `sim >= 1 - 400/2048 = 0.805` de **Jaccard**. Con la densidad real de
bits del segmento de contenido (512 bits, ≤50 tokens × 4 proyecciones → ~0.32 de
densidad, calculado con `1-(1-1/m)^{kn}`), el Jaccard entre dos documentos casi
idénticos raramente pasa de 0.5. O sea: **el radio o no filtra nada o lo filtra
todo**, según el segmento, y encima está mezclando la métrica de Kanerva
(Hamming, que sí tiene una teoría de radio crítico ≈ 451 bits para 2048) con
Jaccard ponderado, que **no** es una distancia y no tiene esa teoría detrás.
Además `similitud_sdm` recorre bit a bit en Python: 2048 iteraciones × N nodos
por consulta, cuando `int.bit_count()` sobre máscaras por segmento te da lo mismo
~100× más rápido (ver §4.2).

### 1.5 `score_candidato` recalcula el vector de la query por candidato

`memory_store.py:4646` llama a `score_candidato(...)` **dentro del bucle de
candidatos**, y `score_candidato` hace `idx.vector_query(q_toks)` en cada llamada.
Es O(N·|q|) en vez de O(|q| + N·d). Sacarlo del bucle es una línea y te ahorra el
grueso de la latencia de la señal #13.

### 1.6 Mezcla de niveles en la matriz PPMI

Construyes PPMI sobre `tf = log1p(count)` normalizado a probabilidad conjunta.
Aplicar PPMI sobre frecuencias ya comprimidas logarítmicamente **no es el PPMI de
Levy & Goldberg** (que asume conteos crudos); el `α=0.75` de suavizado de contexto
está pensado para la distribución empírica de conteos. No está "mal" (es una
heurística razonable), pero deja de tener la equivalencia SVD(PPMI) ≈ SGNS que
justifica todo el enfoque. Vale la pena medir A/B `tf=count` vs `tf=log1p(count)`.

---

## 2. Lo que le falta matemáticamente (por orden de retorno esperado)

### 2.1 Elegir `dim` y `λ` por evidencia, no por default

`dim=100`, `retrofit_lam=0.2`, `iters=5`, `alpha=0.75`, `k_shift=1.0`,
`DECAY=0.4`, `ALPHA=5.0/BETA=1.0/GAMMA=1.0`: **ninguna de estas constantes está
justificada en el repo**. Con el bug 1.1 arreglado tienes el scree plot gratis;
además, para un corpus de ~900 nodos, `dim=100` sobre una matriz V×D con D≈900
es casi seguro sobre-parametrizado (el codo suele estar en 30–60).

Herramienta correcta y barata: **barrido de dim ∈ {25,50,75,100,150}** midiendo
R@5 por categoría con holdout, y quedarte con el menor dim dentro de 1 s.e. del
mejor (regla "one standard error", evita sobreajustar al benchmark).

### 2.2 Fusión por rango en vez de suma de escalas incomparables

Tus 13 señales viven en escalas distintas: BM25 normalizado con `x/(x+3)`
(saturación arbitraria), Jaccard ∈[0,1], coseno PPMI ∈[-1,1] recortado, PMI sin
acotar, `pred_score` como fracción de tokens... Sumarlas con pesos fijos supone
que 0.1 de coseno "vale lo mismo" que 0.1 de BM25 normalizado. No es cierto y
cambia con el corpus.

Dos alternativas, ambas implementadas en `core/calibracion.py`:

- **RRF (Reciprocal Rank Fusion)**, `score = Σ_s w_s / (k + rank_s)`, k≈60.
  Invariante a monotonías de cada señal, es el estándar en IR híbrido y no
  requiere entrenamiento. Ya lo tienes tanteado en
  `scripts/experimento_rrf_921.py`, pero no está en producción ni evaluado con
  test pareado.
- **Fusión logística aprendida** (learning-to-rank ligero): regresión logística
  sobre las señales z-normalizadas por query, entrenada con tus 921 casos con
  holdout estratificado. Son 13 parámetros: no hay riesgo serio de sobreajuste
  con ~900 queries, y **te da los pesos que hoy pones a mano**, con sus errores
  estándar (así ves cuáles señales son estadísticamente indistinguibles de 0 —
  sospecho que `asoc_norm`=0.02 y `temporal`=0.04 lo son).

### 2.3 Calibración de probabilidad + abstención con garantía (lo que más te falta)

Tu FP rate es 25% sobre 40 negativos (IC de Wilson 95%: **14.2%–40.2%**, o sea
no sabes casi nada de ese número, §2.4). Y el "filtro de honestidad epistémica"
decide con umbrales fijos sobre un score no calibrado.

Lo correcto: convertir el score en **probabilidad calibrada** de que el top-1 sea
correcto (Platt/isotónica sobre el score del top-1 + el gap top1−top2), y luego
usar **predicción conforme** para fijar el umbral de abstención con garantía
distribución-libre: eligiendo el umbral en el cuantil ⌈(n+1)(1−α)⌉/n de los
scores de los negativos de calibración, obtienes FP ≤ α **con cobertura
garantizada en muestras futuras i.i.d.**, no un número medido en 40 casos.
Eso convierte "no sé" en una decisión con teoría detrás en vez de un heurístico.
Implementado en `core/calibracion.py` (`UmbralConforme`, `CalibradorPlatt`).

Señales de entrada que ya tienes y sirven mucho para esto: `gap = s1 − s2`,
entropía normalizada del top-k, y la cobertura QCR. El gap es históricamente el
mejor predictor de acierto en el top-1.

### 2.4 Estadística del benchmark: intervalos y tests pareados

Hoy el README compara puntos porcentuales sin ninguna medida de incertidumbre.
Números que calculé con tus propios tamaños de muestra:

| Métrica reportada | n | IC 95% (Wilson) |
|---|---|---|
| GLOBAL R@5 96.14% | 881 | 94.7 – 97.2 |
| `por_tema` 86.15% | 65 | **75.7 – 92.5** |
| `sinonimo` 83.61% | 61 | **72.4 – 90.8** |
| `cruce_idioma` 87.5% | 8 | **52.9 – 97.8** |
| FP 25% | 40 | **14.2 – 40.2** |
| FP 7.5% | 40 | 2.6 – 19.9 |

Conclusiones incómodas pero importantes:
- La mejora de FP 25%→7.5% **sí** es significativa si es pareada (McNemar exacto
  con 7 discordantes: p≈0.016), pero **no** lo es leída como dos proporciones
  independientes (los IC se solapan). Reporta siempre el test pareado, es más
  potente y es el correcto aquí.
- `+0.57pp` de R@1 global (v26.1→v26.2) son ~5 casos de 881: McNemar exacto
  p≈0.06 en el mejor caso (todos los discordantes a favor). **No es evidencia.**
  Está bien mantener el cambio, pero no como "mejora demostrada".
- `cruce_idioma` con n=8 no debería aparecer como porcentaje en una tabla.

### 2.5 El benchmark está desbalanceado y el "GLOBAL" engaña

487 de 881 casos (55%) son `literal`, la categoría trivial que da ~100%. Por eso
el GLOBAL R@5 de 96% se mueve poco pase lo que pase (mira tu ablación: quitar
PPMI mueve el global de 95.57 a 95.46, pero `por_tema` cae 17 puntos al quitar
jaccard). **Reporta macro-promedio por categoría** además del micro:
con tus números de snapshot el macro da **77.6%**, no 96%; con los de producción,
94.1%. Esa es la métrica que refleja de verdad la capacidad semántica, y la que
va a moverse cuando mejores `sinonimo`/`por_tema`.

### 2.6 Multiplicidad: estás haciendo muchos experimentos sobre el mismo test set

`EXPERIMENTS.md` documenta ~10 hipótesis evaluadas sobre los mismos 921 casos.
Con α=0.05 y 10 comparaciones, la probabilidad de al menos un falso positivo es
40%. El holdout 50/50 con seed fija ayuda, pero se "quema" al reutilizarse.
Mínimo: corrección de Benjamini–Hochberg (FDR) sobre la tabla de experimentos, y
un **test set sellado** que sólo se toque para el release final.

### 2.7 Estimación de PMI: falta shrinkage

`core/pmi_semantico.py` filtra tokens con freq < 3 y usa NPMI crudo. El PMI de
pares raros tiene varianza enorme (el filtro por frecuencia marginal no lo
arregla, porque el problema está en el conteo *conjunto*). Dos mejoras estándar:
- **PMI con shrinkage / count-shift**: `PPMI_k = max(0, PMI − log k)` (ya tienes
  `k_shift` en el vectorizador, pero en `pmi_semantico` no) o suavizado
  bayesiano `(c_xy + β) / (c_x c_y / N + β)`.
- **Test de significancia del par**: log-likelihood ratio (Dunning 1993) en vez
  de PMI puro para decidir si crear la sinapsis `pmi_hebbiano`. Dunning está
  diseñado justo para eventos raros en corpus pequeños, que es tu caso exacto
  (900 nodos). Es un cambio de 20 líneas y debería limpiar bastante de las 2.725
  aristas `pmi_hebbiano`.

### 2.8 El retrofitting no está regularizado por grado ni tiene criterio de parada

```python
new_vecs[node] = (1-λ)*vectors[node] + λ * Σ w_ij v_j / Σ w_ij
```
Faruqui original usa `(α_i v̂_i + Σ β_ij v_j) / (α_i + Σ β_ij)` con `β_ij` típicamente
`= 1/deg(i)`. Tu versión promedia los vecinos con λ **constante**, así que un nodo
con 300 vecinos `sinonimo_explicito` (los tienes: 7.021 aristas de ese tipo) se
arrastra hacia el centroide de su hub tanto como un nodo con 2 vecinos de alta
calidad. Eso es **oversmoothing** — la misma patología que en GNNs profundas — y
es candidato número uno a explicar por qué `por_tema` se atasca: los vectores se
vuelven todos parecidos dentro de las islas.

Fixes concretos:
- λ efectivo por nodo: `λ_i = λ · deg(i)/(deg(i)+τ)` o directamente normalizar por
  grado como en el paper.
- Criterio de parada por cambio relativo (`‖V_t − V_{t-1}‖_F / ‖V_{t-1}‖_F < ε`)
  en vez de `iters=5` fijo.
- **Medir el oversmoothing**: energía de Dirichlet del grafo o simplemente la
  media de coseno intra-isla antes/después. Si sube mucho, estás borrando señal.
  Es exactamente el diagnóstico que le falta a tu hallazgo de las "105 islas".

### 2.9 Falta MMR / diversificación en el top-k

Tu Canal 2 (halo asociativo) y el top-5 sufren de redundancia: nodos casi
duplicados ocupan varios slots. **Maximal Marginal Relevance**
`argmax_d [ λ·sim(q,d) − (1−λ)·max_{d'∈S} sim(d,d') ]` es 15 líneas, usa el
coseno PPMI que ya tienes, y típicamente sube R@5 sin tocar R@1. Es el
complemento honesto de GABA (que hoy no hace nada medible).

### 2.10 Cosas del "manifiesto" que aún no están hechas matemáticamente

- **HDC**: `hdc_bind_bytes` (XOR) existe pero **no se usa en ningún sitio**
  (grepeé: sólo se define). El binding de Kanerva sin *unbinding* ni bundling
  (mayoría bit a bit) y sin *permutación* para roles no es HDC, es una función
  suelta. Si quieres HDC de verdad: role-filler binding `Σ_i ρ^i(r_i ⊗ f_i)`
  con cleanup memory. Y ahí sí el radio crítico de Hamming tiene sentido.
- **Cierre triádico (Granovetter)** aparece en el título del README; en el código
  hay `_vecinos_comunes`, pero no hay un coeficiente de clustering ni una
  predicción de enlace tipo Adamic–Adar `Σ_{z∈Γ(x)∩Γ(y)} 1/log|Γ(z)|`, que es la
  formalización estándar y barata de esa idea, y sería una señal nueva y
  ortogonal a las que ya tienes.

---

## 3. Propuesta priorizada (esfuerzo vs impacto)

| # | Cambio | Esfuerzo | Impacto esperado |
|---|---|---|---|
| 1 | Fix `varianza_explicada` + barrido de `dim` | 1 h | Elimina sobre-parametrización, base para todo lo demás |
| 2 | Reportar Wilson + McNemar + macro-promedio | 2 h | Deja de tomar decisiones sobre ruido |
| 3 | Sacar `vector_query` del bucle de candidatos | 10 min | Latencia de señal #13 ÷ N |
| 4 | Fusión RRF o logística en vez de suma con pesos a mano | 1 día | Es donde está el techo actual |
| 5 | Calibración + abstención conforme (FP con garantía) | 1 día | Convierte "honestidad epistémica" en teorema |
| 6 | Retrofit normalizado por grado + medir oversmoothing | 3 h | Sospecha principal del estancamiento de `por_tema` |
| 7 | Dunning LLR para crear aristas `pmi_hebbiano` | 2 h | Grafo más limpio → todo lo demás mejora |
| 8 | MMR en top-k y en el halo | 1 h | R@5 y calidad percibida del Canal 2 |
| 9 | Reemplazar pisos `max(0.95, ·)` por bonus en logit | 1 h | Recupera resolución de ranking en el head |
| 10 | HDC real (bundling + unbinding + cleanup) o quitarlo del README | — | Honestidad de la narrativa |

---

## 4. Lo que te dejé implementado

### 4.1 `core/calibracion.py`
Sin dependencias más allá de numpy. Contiene:
- `fusion_rrf(rankings, pesos, k=60)` — fusión por rango.
- `zscore_por_query(X)` — normalización intra-query (lo que le falta a tu suma).
- `FusionLogistica` — LTR ligero con L2, entrenamiento por descenso, `.pesos_` con
  errores estándar aproximados para ver qué señal es indistinguible de 0.
- `CalibradorPlatt` / `calibracion_isotonica` — score → probabilidad.
- `UmbralConforme` — umbral de abstención con FP ≤ α garantizado.
- `mmr(candidatos, sim_q, sim_dd, lam)` — diversificación.
- `dunning_llr(c_xy, c_x, c_y, N)` — test de asociación para crear sinapsis.
- `retrofit_normalizado(...)` — Faruqui con normalización por grado y parada por ε.
- `energia_dirichlet(V, adj)` — métrica de oversmoothing.

### 4.2 `scripts/evaluacion_estadistica.py`
Ejecutable directo sobre `scripts/casos_qa.jsonl` o sobre dos ficheros de
resultados. Da: Wilson por categoría, macro vs micro, McNemar exacto pareado,
bootstrap de la diferencia de MRR, y corrección BH para la tabla de experimentos.

Uso:
```bash
python3 scripts/evaluacion_estadistica.py --demo          # con los números del README
python3 scripts/evaluacion_estadistica.py --a run_a.jsonl --b run_b.jsonl
```

---

## 5. Lo que está bien y no tocaría

- La elección de PPMI+SVD+retrofit para este tamaño de corpus es la correcta.
- La validación dual de `inferencia_transitiva.py` (PMI alto **o** dim+PMI **o**
  dim+topología fuerte) es una regla de decisión sensata y bien documentada.
- El poda top-K por nodo como inhibición lateral es, matemáticamente, un
  degree-capping: correcto para evitar hubs.
- `EXPERIMENTS.md` con hipótesis refutadas es una práctica excelente y poco común.
- El determinismo verificado (4 corridas idénticas) es un activo real.
- Reconocer que el `84.62%` histórico era un snapshot parcial es honestidad
  científica que la mayoría de repos no tiene.

El proyecto no necesita más metáforas biológicas. Necesita que las señales que ya
tiene se combinen con una regla de decisión aprendida y se midan con
incertidumbre. Ahí está el próximo salto.
