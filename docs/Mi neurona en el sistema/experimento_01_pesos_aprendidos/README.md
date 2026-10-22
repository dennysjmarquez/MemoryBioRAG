# Experimento 01: ¿la neurona de BioRAG puede aprender sus pesos?

- **Fecha:** 2026-10-22.
- **Rama:** `arena/720a0807-memorybiorag`.
- **Estado:** experimento offline. **No modifica el motor, la DB ni el snapshot.**
- **Origen:** los dos videos de esta carpeta (`1--dddd.invento1-/`, `2--dddd.invento2-/`), que cuentan el camino de la neurona de 1943 al transformer, y la pregunta de Dennys: ¿pueden las señales de BioRAG funcionar como neuronas que aprenden?

---

## 1. La idea en una línea

`_calcular_score_hibrido` (`core/memory/scoring.py:295`) **ya es una neurona**. Recibe unas 17 entradas (bm25, dim, concepto, sinónimos, hub, pred, ppmi…), las multiplica por pesos, las suma y aplica no linealidades en espacio logit (bonos de coincidencia exacta y de sinónimos). Lo único que le falta es lo que le faltaba a McCulloch-Pitts en 1943: **los pesos se ponen a mano** (.25, .14, .20…). Este experimento mide si pueden aprenderse de los datos.

| Video | En BioRAG |
|---|---|
| "0,8 × peso 0,5" y luego la suma ponderada | La suma de `scoring.py:337–360` |
| Sesgo + curva = neurona | Los bonos en logit (`match_exacto` +2.94, `sinónimos ≥ .95`) |
| Perceptrón: `w ← w + η(y − ŷ)x` | Modelo **P** y corrección **R1** |
| El XOR que ninguna recta separa | La señal `hub` (ver §4.1) |
| Retropropagación: red 2-2-1 de 9 pesos | Modelo **R2** (capa oculta de 6 neuronas) |
| Atención: la consulta decide a quién mirar | Modelo **R3** (compuerta por consulta) |
| "Corrida propia · numpy · **semilla fija**" | `PYTHONHASHSEED=1` (ver §5) |

---

## 2. Método

**Paso 1: exportación** (`exportar_senales.py`).
- Para los 921 casos de `scripts/casos_qa_baseline_v1.jsonl` se guarda, por cada candidato del pool, exactamente lo que recibió `_calcular_score_hibrido` y el score que devolvió.
- Resultado: **875 casos evaluables y 228 432 candidatos**. Se excluyen los 40 negativos y las 3 consultas con etiqueta contradictoria, igual que `evaluar_qa.py`.
- **Control de fidelidad:** la exportación reproduce el QA oficial al decimal (R@1 **91.89**, R@5 **100**), así que los datos son los del motor real.

**Paso 2: entrenamiento** (`entrenar_neurona.py`, solo numpy). Hay cinco modelos, y todos ordenan el pool completo de cada consulta:

| Modelo | Qué es |
|---|---|
| **M0** | Los pesos manuales de hoy: el score que devuelve el motor. |
| **P** | Perceptrón puro: regresión softmax lineal sobre las 17 señales, desde cero. Es la propuesta de "una logística con 14 features". |
| **R1** | `logit(M0) + w·x`. **Arranca exactamente en M0** (w = 0) y aprende una corrección lineal. |
| **R2** | `logit(M0) + v·tanh(Wx + b)`. Corrección con una capa oculta de 6 neuronas (unos 110 pesos). |
| **R3** | `logit(M0) + Σ xᵢ·(wᵢ + Aᵢ·q)`. La consulta *q* modula el peso de cada señal: es una atención mínima sobre señales. |

En R3, *q* se compone de: número de tokens, mejor coincidencia en el nombre, si hay coincidencia exacta, si se activó un hub y el mejor BM25 del pool.

**Entrenamiento y validación:**
- Pérdida: entropía cruzada softmax sobre el pool (*listwise*).
- Optimizador: Adam, 400 pasos, η = .03, L2 = 1e-3. **Los hiperparámetros se fijaron antes de mirar los resultados.**
- Validación: **5 folds agrupados por nodo esperado.** Los casos literal, typo y variante de un mismo nodo nunca están a la vez en entrenamiento y en prueba.
- Todo se repitió con **3 particiones distintas** (semillas 7, 11 y 23).
- Todas las cifras son **de prueba**, sobre casos que el modelo no vio.

---

## 3. Resultados

Salidas completas en `resultados/particion_{7,11,23}.txt`. Los rangos se comparan **antes del post-proceso** del motor (ver la limitación 1 en §6).

| Modelo | R@1 | MRR | Gana / pierde R@1 vs M0 | Sale del top-5 |
|---|---|---|---|---|
| M0, manual (hoy) | 90.17 | .936 | — | — |
| P, perceptrón puro | 92.34 – 92.57 | .950 – .951 | +35–38 / **−16 a −19** | 8 – 10 |
| R1, manual + lineal | 92.69 – 93.14 | .953 – .955 | +36–38 / −12 a −14 | 8 – 9 |
| **R2, manual + capa oculta** | **93.94 – 94.51** | **.960 – .964** | +41–44 / **−6 a −8** | 9 – 10 |
| R3, manual + compuerta | 93.26 – 93.71 | .956 – .958 | +39–40 / −9 a −12 | 9 – 10 |
| R2 atenuado (λ = .25) | 93.60 – 94.51 | — | +34–41 / **−2 a −4** | 6 – 7 |

**R@1 por categoría** (partición 7):

| | cruce | dormido | literal | por_tema | pregunta | sinónimo | typo | variante |
|---|---|---|---|---|---|---|---|---|
| M0 | 50.00 | 100.00 | 99.59 | 63.08 | 95.38 | 56.36 | 73.85 | 81.54 |
| R2 | **75.00** | 100.00 | 99.59 | **72.31** | 96.92 | **63.64** | **95.38** | **90.77** |

**Lo que aprendió R1 sobre cada señal** (corrección media en logit; positivo significa que el peso manual la subestima):

| Señal | Corrección | Lectura |
|---|---|---|
| `asoc` | −1.19 | Sobrevalorada. Premia nodos populares, no relevantes. |
| `temático` | −1.13 | Sobrevalorada. |
| `pred` | −0.75 | Sobrevalorada. El código ya advierte de su canibalización en `search.py:1709`. |
| `hub` | −0.12 | Sobrevalorada como peso fijo (ver §4.1). |
| `bm25` | +4.02 | La más subestimada. |
| `concepto` | +2.71 | Subestimada. |
| `ppmi` | +2.67 | Subestimada. |
| `campo` | +2.26 | Subestimada. |
| `match_exacto` | +1.81 | Subestimada. |

---

## 4. Lo que significa

### 4.1 La lección del XOR se cumple en BioRAG

- La señal `hub` **rescata paráfrasis** en la suite Concept Hub de `scripts/run_qa_suite.sh` (pasa de 0/5 a 5/5).
- En el QA **se equivoca 12 de 17 veces** cuando decide el primer puesto.

"Hub sirve cuando no hay coincidencia literal y estorba cuando sí la hay" es una interacción entre señales: ninguna recta (ningún peso fijo) la separa. Por eso el perceptrón puro **P** es el que más casos pierde (16–19), y la capa oculta **R2**, igual que la red 2-2-1 del video, es la mejor y la que menos pierde.

### 4.2 La neurona confirma el diagnóstico hecho leyendo el código

Sin que nadie se lo indicara, el modelo bajó el peso de `asoc`, `temático`, `pred` y `hub`, y subió el de `bm25`, `concepto`, `ppmi`, `campo` y `match_exacto`. Coincide con la auditoría señal por señal hecha sobre las trazas.

### 4.3 La regla "el recall jamás baja" todavía no se cumple

Ningún modelo llega a cero casos perdidos. El mejor equilibrio, R2 atenuado, pierde entre 2 y 4 en R@1. Las pérdidas **se repiten en las tres particiones**, casi todas de `por_tema`:

| Caso | Categoría | Rango con R2 (particiones 7 / 11 / 23) |
|---|---|---|
| 0504 | por_tema | 2 / 2 / 2 |
| 0596 | por_tema | 6 / 3 / 7 |
| 0640 | por_tema | 2 / 3 / 2 |
| 0688 | por_tema | 3 / 3 / 3 |
| 0842 | por_tema | 2 / 2 / 2 |

Que se repitan indica una causa concreta, no ruido. Hay que estudiarlos uno por uno antes de integrar nada.

---

## 5. Requisito previo: determinismo

Hoy el motor **no da el mismo resultado en todos los procesos**:
- `core/memory/search.py:724` construye `nodos_cache` como un `set`;
- `core/similitud_conceptual.py:130` toma los 10 primeros en orden de hash.

Con semillas distintas cambian los scores de 41 casos, y el caso **0513** entra o sale del top-5. La corrida de Dennys del 2026-10-22 lo muestra: R@5 99.89, R@1 91.66, frente a 100 y 91.89 con `PYTHONHASHSEED=1`.

Una neurona no puede aprender bien de señales que cambian en cada proceso. El autor del video también lo sabe: su XOR dice "semilla fija".

---

## 6. Limitaciones

1. **Comparación antes del post-proceso.** El post-proceso del motor (léxico, QCR, hub, convergencia de evidencia) sube M0 de 90.17 a 91.89 de R@1 y rescata el top-5 hasta 100 %. Algunos casos que aquí "salen del top-5" probablemente se rescaten. **El resultado de punta a punta solo se conoce integrando el modelo detrás de un flag y corriendo `evaluar_qa.py` completo.**
2. **Datos.** Son 875 casos y la mitad son literales. Las categorías donde hay margen suman unos 250. El agrupamiento por nodo evita memorizar nodos, pero no el estilo del dataset.
3. **Una sola semilla de hash** (1) en la exportación.
4. **Calibración.** Si cambian los pesos, cambia la escala del score: el umbral de abstención (.6212) habría que recalcularlo, y hoy no hay negativos útiles para hacerlo.
5. **Peso sináptico OFF.** Igual que en el QA. Producción usa peso ON.

---

## 7. Qué es original y qué no

Para presentarlo ante un auditor:

**Lo que no es nuevo.** Aprender a combinar señales de relevancia con pesos entrenados existe desde hace dos décadas y se llama *learning-to-rank*: RankNet (2005), LambdaMART y los rankers neuronales de los buscadores.

**Lo que sí es distintivo de BioRAG:**
- señales bioinspiradas (sinapsis, latentes, dormidos, dopamina) como entradas de la neurona;
- arranque exacto desde los pesos manuales, para que el primer día no cambie nada;
- una compuerta por consulta, explicable señal por señal;
- todo sin embeddings ni GPU, dentro de SQLite y numpy;
- la posibilidad de entrenarse **por corpus sin etiquetas humanas** (consultas sintéticas generadas de cada nodo) y de **seguir aprendiendo con el uso** mediante `feedback(util)` y el refuerzo dopaminérgico. Esto último aún no se ha hecho.

La afirmación defendible no es "la primera neurona para buscar información". Es "una memoria bioinspirada cuya neurona de ranking aprende de su propio corpus y de su uso, explicable y sin embeddings".

---

## 8. Próximos pasos propuestos (no ejecutados)

1. **Determinismo.** Orden estable en `search.py:724` y semilla fija en el gate, con QA antes y después.
2. **Estudiar los 5 casos de `por_tema`** que se pierden siempre.
3. **Integrar R2 atenuado detrás de un flag apagado** (`BIORAG_NEURONA=0`) y medir de punta a punta con `evaluar_qa.py` y el gate caso por caso.
4. **Negativos plausibles y recalibración** del umbral con el nuevo score.
5. **Aprendizaje en línea con `feedback(util)`:** el sistema aprende a buscar, no solo a recordar.

---

## 9. Reproducir

Desde la raíz del repo:

```bash
# 1) Exportar señales (~10 min; trabaja sobre una copia temporal del snapshot)
PYTHONHASHSEED=1 python "docs/Mi neurona en el sistema/experimento_01_pesos_aprendidos/exportar_senales.py"
#    -> datos/pools_semilla1.jsonl.gz (≈17 MB, fuera de git: ver .gitignore)

# 2) Entrenar y evaluar (~3 min por partición)
for s in 7 11 23; do
  python "docs/Mi neurona en el sistema/experimento_01_pesos_aprendidos/entrenar_neurona.py" --semilla-folds $s \
    > "docs/Mi neurona en el sistema/experimento_01_pesos_aprendidos/resultados/particion_$s.txt"
done
```

**Verificación hecha al publicar:**
- La exportación de prueba (`--limite 5`) es idéntica byte a byte a la exportación completa.
- Re-entrenar la partición 7 desde esta carpeta reproduce `resultados/particion_7.txt` exactamente.
- SHA-256 del snapshot antes y después: `104dd2902aaf24c3…`, sin cambios.

| Archivo | Contenido |
|---|---|
| `exportar_senales.py` | Paso 1: exporta las señales por candidato (solo lectura). |
| `entrenar_neurona.py` | Paso 2: modelos M0, P, R1, R2 y R3 con validación cruzada por nodo. |
| `resultados/particion_*.txt` | Salida completa de cada partición. |
| `resultados/rangos_particion_*.json` | Rango del esperado por caso y por modelo, para auditar caso por caso. |
| `datos/` | Exportación regenerable. No se versiona. |
