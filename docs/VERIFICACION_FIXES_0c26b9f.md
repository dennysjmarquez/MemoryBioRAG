# Verificación del commit `0c26b9f` — los dos bugs están corregidos

**Fecha:** 2026-08-15
**Rama:** `origin/fix-by-fix-measurement`, commit `0c26b9f`
**Método:** lectura del código + ejecución de la función real con las tres versiones
históricas.

---

## 1. Los dos bugs están corregidos ✅

### Fix 1.3 — rama de sinónimos

El `max(logit, target_logit)` se sustituyó por un bono aditivo real:

```python
bonus = target_logit
score = 1.0 / (1.0 + math.exp(-(logit + bonus)))
```

Ejecutando la función tal como está en `0c26b9f`:

| entrada | salida |
|---|---|
| 0.20 | 0.3684 |
| 0.40 | 0.6087 |
| 0.60 | 0.7778 |
| 0.65 | 0.8125 |
| 0.69 | 0.8385 |

**5 de 5 salidas distintas, orden preservado**, y un score base de 0.5 aterriza
exactamente en el target 0.7000. Correcto.

### Fix 1.2 — suma derivada del dict

```python
_base_weights = {"bm25": 0.25, ..., "pred": 0.20}
_base_sum = sum(_base_weights.values())  # 1.19
total_base = _base_sum + PPMI_VECTOR_WEIGHT
```

El `1.19` literal desapareció. Verificado: el dict suma exactamente 1.19.

---

## 2. El fix 1.2 está a medias (duplicación residual)

El dict se usa **solo para calcular la suma**. La fórmula de abajo sigue con los
números literales:

```python
_base_weights = {"bm25": 0.25, ...}   # fuente A
...
0.25 * bm25_norm +                     # fuente B — literal
0.14 * dim_score +                     # literal
```

Son **dos listas separadas de los mismos once números**. Se pasó de una constante
mágica a once pares que hay que mantener sincronizados a mano. Si alguien cambia
`0.20 * pred_score` en la fórmula y olvida el dict, la normalización vuelve a estar
mal en silencio — que es el bug 1.2 original.

Blindaje completo: usar el dict en la fórmula (`_base_weights['bm25'] * bm25_norm`),
o un `assert` que compare ambas fuentes.

**Mitigación:** el TEST 3 del archivo que dejo abajo detecta esta desincronización
de forma funcional, sin mirar el código. Con ese test en verde, la duplicación deja
de ser peligrosa aunque siga siendo fea.

---

## 3. Lo que falta: los tests de regresión

El reporte dice "16/16 tests pasan". Verifiqué en `test_memory.py`: **no hay ninguna
comprobación de `sinonimos_ratio`, `_base_sum` ni `total_base`**. Los tests de
regresión no se añadieron.

Eso importa porque **los 16/16 estaban en verde con ambos bugs presentes**. La suite
no puede detectarlos: comprueba mecánica (LTP, sueño, SDM), no propiedades del
scoring.

He escrito `scripts/test_regresion_scoring.py` con cuatro tests de **propiedades**
(no de valores concretos, así que no se rompen si alguien recalibra un peso a
conciencia):

1. la rama de sinónimos preserva el orden interno
2. `match_exacto` preserva el orden interno
3. la normalización es coherente con los pesos reales de la fórmula
4. cada señal individual es monótona

### Validación del propio test (esto es lo importante)

Un test que solo pasa no demuestra nada. Lo corrí contra las tres versiones:

| versión | TEST 1 (sinónimos) | TEST 2 (match_exacto) |
|---|---|---|
| `master` (baseline, `max(0.95,·)`) | **FALLO** — 6 entradas → 1 salida | **FALLO** — todas 0.9500 |
| `573fd49` (fix 1.3 con `max`) | **FALLO** — 6 entradas → 1 salida | OK |
| `0c26b9f` (corregido) | **OK** — 6 salidas distintas | **OK** |

El test detecta los bugs donde existen y pasa donde están corregidos. Eso es lo que
lo hace útil como red de seguridad.

Ejecución: `python3 scripts/test_regresion_scoring.py` (sin argumentos, no necesita
DB, devuelve código 1 si falla — sirve para CI).

---

## 4. Una afirmación que reaparece y no es consistente

El reporte cierra con:

> *"El umbral óptimo en live DB es 0.78 (net=40 con ratio 881:32)"*

Eso mezcla dos mediciones incompatibles:

- **`net=40`** salió de la corrida con `limite_casos=120`, que usó ~51 positivos
  contra 32 negativos (ratio ~1.6:1).
- **`ratio 881:32`** es el ratio real del benchmark (~28:1).

Recalculado con el ratio real:

| umbral | Recall | FP | net real |
|---|---|---|---|
| **0.25** | 100% | 100% | **849** |
| 0.70 | 88% | 34% | 764 |
| 0.78 | 78% | 0% | **687** |

Con 881:32, el óptimo de `TP − FP` es **0.25**, no 0.78. Juntar el `net` de la
medición sesgada con el ratio de la corregida produce un número que no sale de
ningún cálculo consistente.

Y sigue pendiente lo que bloquea todo esto: **rehacer el barrido con el script
corregido y verificar que la curva sale monótona** (la tabla anterior tenía una fila
imposible en 0.80, donde FP y recall subían a la vez al subir el umbral).

Recordatorio de fondo: ni 0.25 ni 0.78 son "el óptimo". El ratio 881:32 es un
artefacto del diseño del benchmark, no la carga real. Hasta medir el ratio de
producción en `log_busquedas`, cualquier umbral es una preferencia disfrazada de
resultado.

---

## 5. `eventos_refuerzo` sigue sin commitear

0 ocurrencias en `core/memory_store.py` en las tres ramas del remoto
(`master`, `baseline-measurement`, `fix-by-fix-measurement`). El parche existe solo
en el entorno local del agente. Conviene commitearlo antes de que se pierda.

---

## Resumen

| Ítem | Estado |
|---|---|
| Fix 1.3 rama sinónimos | ✅ corregido y verificado ejecutando |
| Fix 1.2 suma derivada del dict | ✅ corregido (con duplicación residual, mitigada por el TEST 3) |
| Fixes 1.1, 1.4, 1.5 | ✅ correctos |
| Tests de regresión | ❌ faltaban — añadidos y validados contra las 3 versiones |
| `eventos_refuerzo` commiteado | ❌ pendiente |
| Barrido rehecho / monotonía verificada | ❌ pendiente — bloquea la decisión del umbral |
| "óptimo 0.78" | ⚠️ mezcla dos mediciones incompatibles |
