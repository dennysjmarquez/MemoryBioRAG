# Alerta: el umbral calibrado está mal aplicado — revertir o corregir hoy

**Fecha:** 2026-08-16
**Commit:** `de9e062` — *"feat(core): apply conformal calibrated threshold to search results"*
**Severidad:** alta. Está en `master` y degrada la búsqueda en producción.
**Acción:** revertir `de9e062`, o aplicar el fix de una línea de §4.

---

## 1. Lo que se hizo bien

La conexión que faltaba **sí se hizo**. Antes el umbral conforme estaba construido y
sin enchufar; ahora `buscar_por_frase` lo usa. Eso era correcto y necesario.

El problema es **dónde** se aplica.

## 2. El bug

`core/memory_store.py:5511-5513`:

```python
if self._umbral_conforme:
    pagina_resultados = [r for r in pagina_resultados if self._debe_responder(r[4])]
    total = len(pagina_resultados)
```

Esto aplica el umbral a **cada uno de los 5 resultados** de la página.

Pero el umbral se calibró sobre el **top-1**. En `calibrar_umbral_conforme`:

```python
scores_neg.append(resultados[0][0][4])   # <- índice [0] = primer resultado
```

**Se calibró con top-1 y se aplica a toda la lista.** Son dos cosas distintas.

### Por qué eso destruye R@5

En una lista ordenada los scores decrecen:

```
top-5:      [0.95, 0.78, 0.64, 0.55, 0.48]
umbral:     0.60
sobreviven: [0.95, 0.78, 0.64]   -> 3 de 5
```

Si la respuesta correcta está en posición 3, 4 o 5 —que es **exactamente lo que R@5
mide y R@1 no**— el filtro la borra.

Y eso explica la firma del daño reportado:

| métrica | antes | ahora | caída |
|---|---|---|---|
| R@1 | 88.8% | 70.9% | −18 pp |
| **R@5** | **96.0%** | **73.4%** | **−22 pp** |

**R@5 cae más que R@1.** Un filtro de abstención correcto no puede hacer eso: decide
*si responder*, no *cuántos resultados mostrar*.

## 3. El balance es catastrófico

Con los números del propio reporte (live DB):

| | R@5 | FP | aciertos | FP evitados |
|---|---|---|---|---|
| antes | 96.0% | 17.5% | 846 | 33 |
| ahora | 74.0% | 2.5% | 652 | 39 |

```
respuestas correctas perdidas : 194
falsos positivos evitados     :   6
ratio                         : 32 a 1 EN CONTRA
```

**Se sacrificaron ~194 respuestas buenas para evitar 6 malas.**

El reporte lo presenta como *"expected precision-recall tradeoff"*. No lo es. Un
trade-off razonable sería 2:1 o 4:1. Un 32:1 es un bug, no un compromiso.

Y el análisis de coste que se hizo hace dos días concluía que el punto de equilibrio
estaba en `C_fp/C_fn > 1.09`. Con 32:1, ese umbral queda pulverizado: **habría que
creer que una alucinación es 32 veces peor que un silencio** para justificarlo.

## 4. El fix (una línea)

El umbral debe decidir **si la consulta tiene respuesta**, mirando el top-1. Si la
tiene, la lista se devuelve entera:

```python
# Umbral calibrado: decide SI responder (abstención), no CUÁNTOS resultados mostrar.
#
# POR QUÉ SOLO EL TOP-1: el umbral se calibra sobre el score del primer
# resultado de consultas negativas (calibrar_umbral_conforme usa
# resultados[0][0][4]). Aplicarlo a cada elemento de la lista es un error de
# escala: los scores decrecen por construcción, así que corta la cola y destruye
# R@5 (medido: 96.0% -> 73.4%) sin que eso aporte nada a la garantía FP.
if self._umbral_conforme and pagina_resultados:
    if not self._debe_responder(pagina_resultados[0][4]):
        pagina_resultados = []      # abstención: no hay evidencia suficiente
    total = len(pagina_resultados)
```

Con esto:
- si el mejor candidato no supera el umbral → **abstención completa** (que es el
  objetivo: no inventar);
- si lo supera → la lista sale intacta y **R@5 no se toca**.

## 5. Y una decisión que sigue pendiente

Incluso con el fix, hay que decidir **si activar la abstención por defecto**. Lo que
ya sabemos:

- los negativos con los que se calibró son **sintéticos** (los reales de tipo B aún
  no se han acumulado);
- el ratio real de producción es ~8:1 positivos:negativos;
- el punto de equilibrio calculado era `C_fp/C_fn > 1.09`.

Mi recomendación: **`BIORAG_CALIBRACION_ACTIVA=0` por defecto** hasta tener negativos
reales. El mecanismo queda listo y conectado, pero no altera producción hasta que la
calibración se base en datos reales. Eso es exactamente lo que se hizo con Signal #14
(ADN) y fue la decisión correcta entonces.

## 6. Además: el README volvió a adelantarse

El commit `4f1e99e` dice *"clarify FP 80% status and calibrated threshold state"*.
Conviene revisar que el README no afirme ahora que el FP bajó a 0-2.5%, porque ese
número viene acompañado de una pérdida de 22 puntos de recall que lo invalida como
logro.

El FP no bajó porque el sistema discrimine mejor. Bajó porque **está respondiendo
mucho menos**. Un sistema que se calla siempre tiene FP = 0%.

---

## Resumen

| | |
|---|---|
| Conectar el umbral | **correcto y necesario** |
| Aplicarlo a cada resultado | **bug** — calibrado en top-1, aplicado a la lista |
| Coste medido | 194 aciertos perdidos por 6 FP evitados (32:1) |
| Fix | 4 líneas: evaluar solo `pagina_resultados[0]` |
| Recomendación | revertir `de9e062` o aplicar el fix + dejar OFF por defecto |

Es la octava vez en esta sesión que aparece un problema de conexión: no que la pieza
esté mal construida, sino que esté enchufada en el sitio equivocado.
