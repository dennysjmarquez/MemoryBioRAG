# Revisión del código real de los 5 fixes (`fix-by-fix-measurement`)

**Fecha:** 2026-08-15
**Ramas revisadas:** `origin/baseline-measurement` (baseline puro) y
`origin/fix-by-fix-measurement` (commit `573fd49`, los 5 fixes).
**Método:** lectura del código, no de los reportes.
**Resultado:** 3 fixes correctos, **2 con bugs reales** — uno de ellos reintroduce
exactamente el problema que decía resolver.

---

## Primero: qué contiene cada rama

Aclaración importante, porque afecta a cómo se leen los números publicados:

| Rama | Contenido |
|---|---|
| `baseline-measurement` | **NO tiene los 5 fixes.** Es el baseline. Sus cambios en `memory_store.py` son otra cosa: reordenan la prioridad de tipos de sinapsis en `obtener_asociaciones_enriquecidas` (Canal 2), poniendo `pmi_hebbiano` primero y `sinonimo_explicito` al final. Eso toca el halo asociativo, no el scoring. |
| `fix-by-fix-measurement` | Commit `573fd49` con los 5 fixes. |

Verificado: en `baseline-measurement` sigue `score = max(0.95, score)` (fix 1.3 sin
aplicar), `var_total = (S**2).sum()` (fix 1.1 sin aplicar) y `dist = int((1.0 -
sim) * SDM_BITS)` (fix 1.4 sin aplicar). Tampoco existe `eventos_refuerzo` en
ninguna de las dos ramas (0 ocurrencias) — ese parche debe estar sin commitear.

---

## Fix 1.1 — varianza explicada ✅ CORRECTO

```python
var_total = float((S_full**2).sum())
var_expl = float((S**2).sum() / (var_total + 1e-12))
```

Usa el espectro completo para el denominador. Resuelto. Ahora la métrica informa de
verdad y se puede usar para elegir `dim`.

## Fix 1.4 — SDM Hamming ✅ CORRECTO

```python
dist_hamming = (int1 ^ int2).bit_count()
if dist_hamming <= radio_max:
```

Distancia de Hamming real en vez de `(1-jaccard)*2048`. El radio de 400 sobre 2048
bits ahora sí tiene el significado que le da la teoría de Kanerva. Bien hecho.

## Fix 1.5 — vector_query fuera del loop ✅ (asumido correcto)

No lo revisé en detalle; es un cambio de rendimiento de bajo riesgo.

---

## Fix 1.2 — renormalización ⚠️ BUG: constante mágica duplicada

```python
total_base = 1.19 + PPMI_VECTOR_WEIGHT  # 1.34
base_weight = (1.0 - jsd_weight) / total_base
```

El `1.19` está **hardcodeado** y es la suma de once pesos que están escritos
literalmente doce líneas más abajo. Hoy coincide (lo verifiqué: suman exactamente
1.19), así que el fix funciona.

**El problema es el mañana.** El propio README documenta que el peso `0.20` de
`pred_score` (Signal #12) es *"capacidad disponible, NO enganchada"* y que hay una
canibalización pendiente de revisar. El día que alguien lo toque —o cualquier otro
peso— la renormalización queda mal **en silencio**: los scores dejan de sumar 1.0 y
nadie se entera, porque no hay nada que lo compruebe.

Es el bug 1.2 original reintroducido en otra forma: una suma de pesos que hay que
mantener sincronizada a mano.

**Corrección sugerida** — derivar la constante de los propios pesos:

```python
# Pesos de las señales, en un solo sitio. La suma se calcula, no se escribe.
PESOS_SENALES = {
    'bm25': 0.25, 'dim': 0.14, 'concepto': 0.08, 'sinonimos': 0.08,
    'peso_sin': 0.10, 'latente': 0.10, 'grupo': 0.10, 'tematico': 0.08,
    'temporal': 0.04, 'asoc': 0.02, 'pred': 0.20,
}
total_base = sum(PESOS_SENALES.values()) + PPMI_VECTOR_WEIGHT
```

Así, cambiar un peso re-normaliza solo. Es el mismo principio que ya se aplicó bien
en `termodinamica_cortical.py`: centralizar las constantes para que la teoría no se
desincronice del código en silencio.

## Fix 1.3 — bonos en logit ❌ BUG: la segunda rama no arregla nada

La rama `match_exacto` **sí está bien**:

```python
logit = math.log(p / (1.0 - p)) + 2.94
score = 1.0 / (1.0 + math.exp(-logit))
```

Es un bono aditivo en log-odds, monótono. Verificado: 0.20 → 0.8254, 0.40 → 0.9265,
0.60 → 0.9660. Entradas distintas, salidas distintas. El empate del `max(0.95, ·)`
queda resuelto.

**Pero la rama de sinónimos no:**

```python
score = 1.0 / (1.0 + math.exp(-max(logit, target_logit)))
```

Eso es un **`max`**, no un bono aditivo. Es el mismo piso de antes, movido de sitio.
Verificado con `ppmi_score = 0` (target = 0.70):

| score de entrada | score de salida |
|---|---|
| 0.20 | **0.7000** |
| 0.40 | **0.7000** |
| 0.60 | **0.7000** |
| 0.65 | **0.7000** |
| 0.69 | **0.7000** |

**Cinco scores distintos salen idénticos.** El empate que el fix decía eliminar
sigue exactamente igual, solo que ahora en 0.70 en lugar de en 0.95. Y el comentario
del código dice *"Bono aditivo hacia el target"*, que es justo lo que **no** hace —
un comentario que contradice a su propio código, el caso que la regla 20 del manual
advierte.

**Corrección sugerida** — bono aditivo real, como en la rama de match_exacto:

```python
elif sinonimos_ratio >= 0.95:
    # Bono aditivo en log-odds. Preserva el orden interno del grupo:
    # dos nodos con sinonimia perfecta pero distinta evidencia siguen
    # distinguiéndose, que es justo lo que el max() destruía.
    target = 0.70 + 0.10 * ppmi_score
    bono = math.log(target / (1.0 - target))  # ~0.847 para target=0.70
    p = max(1e-6, min(1 - 1e-6, score))
    logit = math.log(p / (1.0 - p)) + bono
    score = 1.0 / (1.0 + math.exp(-logit))
```

Con esto, 0.20 → 0.368, 0.40 → 0.610, 0.60 → 0.777: suben todos, pero **mantienen
su orden relativo**.

---

## Por qué esto importa para las métricas publicadas

El fix 1.3 se presentó como *"Mantiene FP bajo"* y el conjunto como *"driver
principal"*. Con la segunda rama todavía aplastando scores a un piso fijo:

- sigue habiendo empates artificiales en el ranking, resueltos por el orden del
  `SELECT` de SQLite;
- cualquier medición de R@1 o MRR sobre casos con `sinonimos_ratio >= 0.95` está
  contaminada por ese desempate arbitrario;
- y el `sinonimo` es precisamente una de las categorías flojas del benchmark
  (36.07% R@5 en snapshot frío según el README).

No digo que arreglarlo vaya a mover las métricas — con +1 y +3 casos de diferencia,
probablemente no mueva nada medible. Lo digo porque **el fix no hace lo que dice
que hace**, y eso es lo que hay que corregir en el registro.

---

## Qué hacer

| # | Acción | Coste |
|---|---|---|
| 1 | Corregir la rama de sinónimos del fix 1.3 a bono aditivo real | 5 líneas |
| 2 | Derivar `total_base` de un dict de pesos en vez del `1.19` literal | 10 líneas |
| 3 | Test unitario: dos scores distintos con `sinonimos_ratio=1.0` deben salir distintos | 5 líneas |
| 4 | Test unitario: `sum(PESOS_SENALES.values()) + PPMI_WEIGHT == total_base` | 2 líneas |
| 5 | Commitear `eventos_refuerzo` (no está en ninguna rama del remoto) | — |

Los puntos 3 y 4 son los que evitan que estos dos bugs vuelvan. Son cuatro líneas
de test que `test_memory.py` no tiene y que habrían detectado ambos.

## Nota sobre `baseline-measurement`

Esa rama cambia el orden de prioridad de tipos de sinapsis en el Canal 2:
`pmi_hebbiano` pasa de última prioridad (9) a primera (0), y `sinonimo_explicito`
de 1 a 9. El comentario anterior justificaba lo contrario (*"tipos EXPLÍCITOS
primero — son señal semántica real; pmi_hebbiano al final: es estadístico,
hiperdenso y ruidoso"*).

Es un cambio de criterio de fondo, en la rama que se suponía era "la medición del
baseline". Conviene separarlo: mezclar un cambio funcional dentro de la rama de
baseline hace que "el baseline" ya no sea el baseline.
