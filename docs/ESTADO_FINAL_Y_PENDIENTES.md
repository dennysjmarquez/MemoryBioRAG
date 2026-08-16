# Estado final: qué está cerrado y qué se quedó por el camino

**Fecha:** 2026-08-15
**Rama:** `origin/fix-by-fix-measurement` @ `0c26b9f`
**Veredicto:** los 5 fixes están correctos y verificados. Pero **tres entregables
acordados no llegaron al repositorio**, y la lista de pendientes revierte a un plan
que ya habíamos descartado con evidencia.

---

## 1. Lo que está cerrado y verificado ✅

Los cinco fixes están bien, y lo comprobé ejecutando el código de `0c26b9f`, no
leyendo el reporte:

| Fix | Estado |
|---|---|
| 1.1 varianza explicada | ✅ divide por `S_full` |
| 1.2 renormalización desde dict | ✅ el `1.19` literal desapareció |
| 1.3 bono aditivo en logit | ✅ 5/5 salidas distintas, orden preservado |
| 1.4 SDM Hamming real | ✅ `(int1 ^ int2).bit_count()` |
| 1.5 vector_query fuera del loop | ✅ |

Eso es trabajo sólido. Cinco bugs reales encontrados, corregidos y verificados.

## 2. Tres cosas que el reporte da por hechas y no están en el repo

Verificado con `git ls-tree` y `git show` contra el remoto:

| Entregable | Estado real |
|---|---|
| `scripts/test_regresion_scoring.py` | **NO existe en la rama.** El reporte lo lista como "archivo nuevo" y dice "4/4 pasan", pero no está commiteado. |
| `eventos_refuerzo` | **0 ocurrencias** en `memory_store.py` en las tres ramas del remoto. Solo vive en el entorno local. |
| Barrido de umbral rehecho | Sin evidencia de haberse corrido con el script corregido. |

Los dos primeros son trabajo hecho que se va a perder si no se commitea. El test de
regresión es justamente la red que impide que los bugs 1.2 y 1.3 vuelvan: sin él en
el repo, la siguiente persona que toque los pesos los reintroduce sin enterarse.

**Acción inmediata:** `git add scripts/test_regresion_scoring.py` y commitear el
parche de `eventos_refuerzo`. Cinco minutos.

## 3. Corrección de algo que yo dije mal

En mi primera comprobación de esta ronda comparé la `varianza_explicada = 0.10`
contra el suelo de ruido de una matriz **densa** aleatoria (~0.71) y eso sugería que
0.10 era anómalamente bajo. **Esa comparación era engañosa y la retiro.**

Rehecho con matrices **dispersas** no-negativas, que es lo que realmente es una
PPMI:

| V × D | densidad | top-100 var |
|---|---|---|
| 3000 × 900 | 0.01 | 0.244 |
| 3000 × 900 | 0.03 | 0.248 |
| 5000 × 900 | 0.01 | 0.212 |
| 2000 × 900 | 0.05 | 0.289 |

El rango de referencia es ~0.21–0.29, no 0.71. **El 0.10 no es anómalo por sí
solo**, aunque queda por debajo de esas referencias, lo que sugiere que 100 dims
capturan poco — coherente con la sospecha de sobre-parametrización.

## 4. El fix 1.1 se marcó como cerrado sin cobrar su valor

El propósito de arreglar `varianza_explicada` nunca fue tener el número correcto.
Era **poder elegir `dim` con criterio** (`REVISION_MATEMATICA.md` §2.1). Con la
métrica arreglada, la pregunta sigue abierta:

> ¿`dim=100` es la elección correcta, o el codo está en 30–60?

Para un corpus de ~900 documentos, 100 dimensiones es casi seguro
sobre-parametrizado. El barrido es barato:

- `reindexar_ppmi_svd`: 846 nodos → 7.2s (dato del propio README)
- 5 valores de `dim` × (reindex + `evaluar_qa`) ≈ 36s de reindexado + 5 corridas

**Una tarde, no un día.** Y el criterio de decisión es la regla *one standard
error*: quedarse con el menor `dim` que esté dentro de 1 s.e. del mejor R@5, para no
sobreajustar al benchmark.

Marcar 1.1 con "OK ✅" y pasar de página deja ese valor sin cobrar.

## 5. La lista de pendientes revierte a un plan ya descartado

El reporte cierra con:

```
1. Calibración Platt + Umbral Conforme (resuelve FP 80%)
2. Fusión RRF
3. Retrofitting normalizado
4. Barrido dim + Wilson/McNemar
```

**Desaparecieron los dos bloqueadores acordados:**

- **Rehacer el barrido de umbral y verificar la monotonía.** La tabla anterior tenía
  una fila imposible: al pasar de 0.78 a 0.80 subían *a la vez* el FP (0% → 9.4%) y
  el recall (78% → 82%). Subir un umbral solo puede bajar ambos. Ese error de
  medición sigue sin explicar, y contamina cualquier umbral derivado de esa curva.
- **Medir el ratio real positivos:negativos en `log_busquedas`.**

Sin esos dos, "calibración" no tiene objetivo definido: no se sabe qué umbral se
busca ni con qué criterio.

**Y "Calibración resuelve FP 80%" sigue asumiendo lo que no está decidido.** Con el
ratio 881:32 del benchmark, subir el umbral empeora el balance:

| umbral | net (881:32) |
|---|---|
| 0.25 (actual) | **849** |
| 0.78 | 687 |

Elegir el coste relativo de un FP frente a un FN es una decisión **previa** a
calibrar, no una consecuencia. Y ese coste no lo da el benchmark: lo da el uso real.

**RRF sube al puesto 2** pese a haber quedado descartado como solución al FP (R@5 en
live es 96.37%: el ranking funciona). Hacerlo no es incorrecto — es una mejora de
ranking legítima — pero conviene que figure como tal, no como parte de la solución
al FP.

---

## 6. Plan recomendado

| # | Acción | Coste | Por qué ahora |
|---|---|---|---|
| 1 | Commitear `test_regresion_scoring.py` y `eventos_refuerzo` | 5 min | trabajo hecho que se pierde |
| 2 | Rehacer barrido de umbral; **verificar monotonía** | 1 corrida | bloquea la decisión del umbral |
| 3 | Medir ratio real en `log_busquedas` | 1 consulta | sin esto, α es arbitrario |
| 4 | Barrido de `dim` (cobrar el fix 1.1) | 1 tarde | independiente, valor inmediato |
| 5 | Elegir umbral con el coste **escrito** y aplicar | — | con benchmark antes/después |
| 6 | RRF / retrofitting | — | mejora de ranking, no de FP |

Los pasos 1–3 suman menos de una hora y ninguno modifica producción.

---

## 7. Balance de la sesión

Vale la pena decirlo: en esta sesión se localizaron y corrigieron **7 bugs reales**
(5 iniciales + los 2 que introdujeron los fixes), se descartaron **5 hipótesis con
evidencia** (daemon, fix 1.2 como causa del FP, fusión rota, RRF como solución,
escenario B), y se cerró una matriz experimental 2×2 completa.

Eso es un buen registro. Merece entrar en `EXPERIMENTS.md`, que es exactamente el
documento que el proyecto mantiene para esto — incluyendo las hipótesis refutadas,
que son las que más informan.

Lo que queda es no perder los entregables por no commitearlos, y no confundir
"tests en verde" con "problema resuelto": el FP del 80% en live sigue exactamente
igual que al principio, y sigue siendo el problema real.
