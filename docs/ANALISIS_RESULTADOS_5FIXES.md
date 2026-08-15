# Análisis de los resultados de los 5 fixes

**Fecha:** 2026-08-15
**Veredicto:** el benchmark se corrió (bien), pero **ninguna de las mejoras es
estadísticamente distinguible de cero**, y hay un efecto adverso enorme que se
descartó sin probarlo.
**Recomendación:** no seguir con RRF. Resolver primero la ambigüedad del fix 1.2.

---

## 1. Lo que hizo bien

Corrió `evaluar_qa.py` con baseline explícito (`5a306fa`) y validación dual
snapshot + live. Eso es exactamente lo que faltaba. El reporte es honesto: publica
el R@1 que baja y el FP de 80% en lugar de esconderlos.

## 2. Las mejoras son de 1 y 2 casos

Traducidos los porcentajes a casos sobre los 881 de retrieval:

| Métrica | Antes | Después | En casos | McNemar (mejor escenario) |
|---|---|---|---|---|
| R@5 snapshot | 96.14% | 96.25% | 847 → 848 (**+1**) | p = 1.00 |
| R@5 live | 96.14% | 96.37% | 847 → 849 (**+2**) | p = 0.50 |
| R@1 snapshot | 88.76% | 88.76% | 782 → 782 (**0**) | — |
| R@1 live | 88.76% | 88.65% | 782 → 781 (**−1**) | p = 1.00 |
| MRR | 0.916 | 0.917 | +0.001 | — |

Los valores de p son del **escenario más favorable posible** (asumiendo que todos
los discordantes van a favor). Ninguno se acerca a 0.05.

Del análisis de potencia que ya está en `scripts/evaluacion_estadistica.py`: con
881 casos hacen falta ~782 casos pareados para detectar +2pp con potencia 80%.
Estos deltas son de +0.11pp y +0.23pp — **un orden de magnitud por debajo del
umbral de detección del benchmark**.

Y el FP de 25% → 17.5% son 10 → 7 casos sobre 40 negativos. McNemar: **p = 0.25**.
Wilson: 25% → [14.2, 40.2], 17.5% → [8.8, 32.0]. Los intervalos se solapan casi
por completo.

> Conclusión de esta sección: los 5 fixes son **neutros en calidad de recuperación**
> hasta donde este benchmark puede medir. Eso no los invalida — 1.1 (correctitud),
> 1.4 (métrica coherente) y 1.5 (latencia) valen por sí mismos. Pero la frase
> *"Fix 1.2 es el driver principal: +0.11pp R@5, −7.5pp FP"* atribuye causalidad a
> ruido de 1 y 3 casos respectivamente.

## 3. El FP de 80% en live: se descartó sin probarlo

Este es el problema serio del reporte.

| Efecto | Magnitud | Significancia |
|---|---|---|
| Mejora R@5 celebrada | +2 casos / 881 (+0.23pp) | p = 0.50 |
| **Daño FP en live** | **+22 casos / 40 (+55pp)** | **p = 0.00000048** |

El efecto adverso es **10× más grande y ~5000× más significativo** que la mejora
que se está celebrando. Se explicó como *"daemon activo contaminando consultas
negativas (esperado)"* y se marcó con asterisco.

Dos problemas con esa explicación:

**a) El intervalo del daemon no es el que dice.** `graph_maintenance_daemon.py:64`:
`INTERVALO_HORAS = float(os.environ.get("BIORAG_DAEMON_INTERVALO_HORAS", "1"))`.
El default es **1 hora**, no 0.5. El docstring de la línea 24 dice 6. Los tres
números no coinciden — y ninguno se verificó contra el proceso realmente en marcha.

**b) Es una hipótesis, no una medición.** Nadie apagó el daemon y volvió a correr.
Eso es una línea de comando. Hasta que se haga, "el daemon lo contamina" y "el fix
1.2 rompe la discriminación en corpus grandes" son **igual de compatibles con los
datos**.

## 4. La causa alternativa que nadie descartó: el FP se mide con umbral fijo

`scripts/evaluar_qa.py:106`:

```python
# Noise threshold: if any result has score >= 0.25, it's considered a false positive
```

El umbral es **fijo en 0.25** y absoluto, no relativo.

Ahora, qué hace el fix 1.2: los pesos sumaban 1.34 y ahora se renormalizan a 1.0.
Es decir, **todos los scores se multiplican por ≈ 1/1.34 = 0.746**.

| score antes | score después |
|---|---|
| 0.95 | 0.709 |
| 0.60 | 0.448 |
| 0.40 | 0.298 |
| 0.30 | 0.224 |

Un umbral de 0.25 después del fix equivale a un umbral de **0.335** antes. **La
regla de medición cambió de significado en medio del experimento.**

Consecuencia directa: la "mejora" de FP 25% → 17.5% en snapshot puede ser
**puramente un artefacto del reescalado**. Bajar todos los scores hace que menos
crucen 0.25 — eso no es mejor separación señal/ruido, es mover la portería.

Y esto encaja mejor con los datos que la explicación del daemon:
- si de verdad hubiera mejor discriminación, el R@1 no bajaría en live
- el FP subiendo a 80% en un corpus más grande es lo que esperarías si la escala
  de scores se desplazó y el umbral fijo quedó descalibrado

**Ojo:** yo tampoco he probado esto. Es una hipótesis alternativa con el mismo
estatus que la del daemon. La diferencia es que ambas son comprobables y ninguna
se comprobó.

## 5. La prueba que resuelve las dos ambigüedades

Dos corridas, ~40 minutos:

### Prueba A — apagar el daemon
```bash
pkill -f graph_maintenance_daemon    # verificar antes con: ps aux | grep daemon
BIORAG_PATH=<copia_live> python3 scripts/evaluar_qa.py > /tmp/live_sin_daemon.txt
```
- Si FP vuelve a ~25%: la explicación del daemon era correcta. Cerrado.
- Si FP sigue en ~80%: **el fix 1.2 rompió la discriminación** y hay que revertirlo
  o recalibrar el umbral.

### Prueba B — umbral de FP equivalente
Correr el snapshot post-fix con el umbral escalado, para comparar peras con peras:
```bash
# umbral equivalente = 0.25 * (1/1.34) = 0.187
BIORAG_FP_THRESHOLD=0.187 python3 scripts/evaluar_qa.py
```
(requiere parametrizar el 0.25 hardcodeado de la línea 106 — cambio de una línea)

- Si con umbral 0.187 el FP vuelve a ~25%: la mejora era artefacto de escala.
- Si se mantiene en ~17.5%: la mejora es real y el fix 1.2 sí discrimina mejor.

**Recomendación permanente:** parametrizar ese umbral y documentar que cualquier
cambio de escala en el scoring invalida la comparabilidad histórica del FP. Es una
trampa que va a volver a morder.

## 6. Sobre "el R@1 baja 1 caso, aceptable"

Un caso de 881 es ruido, sí. Pero el patrón conjunto —R@1 baja, FP se dispara— es
consistente con "los scores se movieron de escala", que es justo lo que el fix 1.2
hace por diseño. Vale la pena mirarlo como síntoma, no como caso aislado.

## 7. El diagnóstico del UmbralConforme es correcto

> *"Calibración en escala de probabilidad vs umbral conforme en escala de score
> crudo. Requiere rehacer en escala de score crudo."*

Exacto, y coincide con lo que verifiqué: el máximo que Platt puede emitir con
`a=3.55, b=−1.11` es 0.9198, por debajo del umbral 0.9633. Ya añadí la guarda en
`core/calibracion.py`: `calibrar()` acepta ahora los positivos y grita
`*** UMBRAL DEGENERADO ***` cuando el umbral los supera a todos, en vez de
abstenerse en silencio.

Nota para cuando lo rehaga: con n=40 negativos, α=0.05 exige el cuantil
`ceil(41·0.95)=39` de 40 — el penúltimo, el estadístico más inestable de la
muestra. Con ese tamaño conviene α ≥ 0.10, o conseguir más negativos (son consultas
que no deben devolver nada: baratas de generar).

---

## Qué responder al agente

1. **Reconocer**: corrió el benchmark con baseline y validación dual. Eso es lo que
   faltaba y lo hizo bien.
2. **Corregir el marco**: los deltas son de 1-3 casos, todos con p > 0.25. La
   conclusión correcta es *"los 5 fixes son neutros en recuperación medible; valen
   por correctitud, no por métrica"*.
3. **Escalar la prioridad del FP 80%**: es el efecto más grande del experimento y
   está sin diagnosticar. No es una nota al pie.
4. **Correr las pruebas A y B** antes de cualquier otra cosa.
5. **No empezar RRF** hasta saber si el fix 1.2 mejora o rompe la discriminación.
   RRF cambia la escala de scores por completo, así que encima del 1.2 sin resolver
   haría el problema irrecuperable.
