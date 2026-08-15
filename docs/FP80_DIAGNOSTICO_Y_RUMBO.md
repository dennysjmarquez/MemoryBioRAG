# FP 80%: falta una celda del experimento, y RRF no es la herramienta

**Fecha:** 2026-08-15
**Veredicto:** las dos pruebas se corrieron, pero una se aplicó al corpus equivocado
y falta la celda de control que permite atribuir el 80% a algo.
**Recomendación:** no proceder con RRF. Es ortogonal al problema que se quiere resolver.

---

## 1. Lo que quedó bien establecido

La Prueba A (daemon OFF → sigue 80%) **sí es concluyente**: el daemon no es la causa.
Eso cierra limpiamente una hipótesis y estuvo bien ejecutada.

## 2. La Prueba B se corrió sobre el corpus equivocado

**Qué debía probar B:** si la *mejora* de FP en **snapshot** (25% → 17.5%) era un
artefacto del reescalado del fix 1.2.

**Dónde debía correrse:** snapshot post-fix con umbral 0.1866.
- si vuelve a ~25% → la mejora era artefacto de escala
- si se mantiene en ~17.5% → la mejora es real

**Dónde se corrió:** live DB @ 0.1866 → 80%.

El problema es que **bajar un umbral solo puede subir o mantener el FP, nunca
bajarlo**: con un umbral más bajo, más resultados lo cruzan. Que `live @ 0.25` y
`live @ 0.1866` den ambos 80% era el resultado casi forzado. No informa nada sobre
el artefacto en snapshot, que es lo que B existía para medir.

La conclusión *"Fix 1.2 NO causó el FP"* no se sigue de ese experimento.

## 3. Falta la celda de control (esto es lo importante)

El diseño es una matriz 2×2 y solo hay tres celdas:

| | SNAPSHOT | LIVE DB |
|---|---|---|
| **Baseline (5a306fa)** | 25% | **NUNCA MEDIDO** |
| **Con 5 fixes** | 17.5% | 80% |

Entre "snapshot + baseline" (25%) y "live + fixes" (80%) cambian **dos cosas a la
vez**: el corpus y el código. Sin la celda faltante no hay atribución posible.

Los dos escenarios siguen igual de compatibles con los datos:

- **(a) baseline@live = 80%** → el 80% es una propiedad del corpus vivo. Los fixes
  son inocentes y el problema es preexistente. Se puede seguir adelante.
- **(b) baseline@live = 25%** → los fixes rompieron la discriminación al escalar
  el corpus. Habría que revertir, no construir encima.

**Es una sola corrida:** `git stash` + `evaluar_qa.py` sobre la copia live. Hasta
tenerla, "el fix 1.2 es inocente" es una hipótesis, no un resultado.

## 4. RRF no resuelve un problema de falsos positivos

Esta es la objeción de fondo a la decisión de proceder.

RRF calcula `score(d) = Σ_s w_s / (k + rank_s(d))`. Opera sobre **rangos**. Ante una
consulta negativa el sistema igual recupera candidatos y los ordena, así que el
top-1 recibe `1/(60+1)` **siempre**:

```
consulta CON respuesta correcta : 3 señales × 1/61 = 0.0492
consulta SIN respuesta correcta : 3 señales × 1/61 = 0.0492   ← idéntico
```

**RRF es invariante a la magnitud de la evidencia** — justamente la información que
hace falta para decidir abstenerse. Arregla el *orden entre candidatos*; el FP es
*decidir si responder*. Son ejes ortogonales.

Peor aún: RRF destruye la escala absoluta del score, con lo que el umbral de 0.25
deja de significar nada y habría que recalibrar todo desde cero — encima de un
cambio de escala (fix 1.2) que todavía no está diagnosticado.

El propio reporte lista como causa nº1 *"fusión lineal suma señales incomparables"*.
Eso es cierto y es un problema real de **ranking**, documentado en
`REVISION_MATEMATICA.md`. Pero no es la causa de un FP de 80%, y arreglarlo no
bajará el FP.

## 5. La hipótesis que los propios datos sugieren

El reporte contiene el dato decisivo y no lo explota:

> *"los scores de negativos en live DB son altos (0.3-0.5)"*, con umbral fijo 0.25.

Los negativos puntúan entre **20% y 100% por encima del umbral**. Eso no describe
una fusión mal ponderada: describe un **umbral absoluto que no escala con el
tamaño del corpus**.

**H-corpus:** el 0.25 se eligió para un corpus de ~800 nodos. La live DB es mayor;
más nodos ⇒ más colisiones léxicas ⇒ scores basales más altos para cualquier
consulta, incluidas las que no tienen respuesta. El umbral se queda corto por
construcción, sin que nada esté "roto".

Si H-corpus es cierta, ni RRF ni retrofitting cambian nada: el arreglo es que el
umbral **se derive de los datos** en vez de ser una constante.

Y eso es exactamente lo que hace la predicción conforme: el umbral se fija en el
cuantil de los negativos de calibración, se recalcula cuando el corpus cambia, y
trae garantía FP ≤ α. **No es "el paso 2 del plan": es el paso que ataca el problema
que se tiene delante.**

## 6. Nota sobre el tamaño de muestra

`FP 80%` es 32/40. Wilson 95%: **[65.2, 89.5]**. La dirección es clarísima (algo
está mal), pero el corpus de negativos es de 40 casos, el 4.3% del benchmark.

Para calibrar un umbral con α=0.05 hacen falta bastantes más: con n=40 el método
conforme exige el cuantil `ceil(41×0.95)=39` de 40, es decir el penúltimo valor —
el estadístico más inestable de la muestra. Generar negativos es barato (son
consultas que no deben devolver nada). **Subir a 200-300 negativos es prerrequisito
para cualquier trabajo serio de calibración.**

---

## Orden recomendado

| # | Acción | Esfuerzo | Por qué |
|---|---|---|---|
| 1 | **Medir baseline@live** | 1 corrida | Cierra la matriz 2×2. Sin esto no hay atribución. |
| 2 | **Prueba B bien hecha**: snapshot post-fix @ 0.1866 | 1 corrida | Dice si la mejora de FP fue artefacto |
| 3 | **Probar H-corpus**: distribución de scores de negativos, snapshot vs live | 1 script | Discrimina "umbral no escala" de "fusión rota" |
| 4 | **Ampliar negativos a 200-300** | 1 tarde | Prerrequisito de la calibración |
| 5 | **Umbral conforme** en escala de score crudo | 1 día | Ataca el FP con garantía |
| 6 | RRF / retrofitting | — | Ranking. Después, y con benchmark antes/después |

Los pasos 1-3 son tres corridas. Ninguna modifica código.

## 7. Sobre la tabla "Estado de los 5 Fixes"

Sigue diciendo *"Fix 1.2: driver principal, R@5 +0.11pp, FP −7.5pp"*. Con los
números en la mano: +0.11pp es **+1 caso de 881** (McNemar p=1.00) y −7.5pp es
**−3 casos de 40** (p=0.25). Ninguno es distinguible de cero.

La redacción honesta es: *"los 5 fixes son correctos y neutros en calidad medible;
1.1 y 1.4 aportan correctitud, 1.5 aporta latencia"*. Que sea neutro no le quita
valor a un fix de correctitud — pero llamarlo "driver principal" convierte ruido
en narrativa, y en dos meses nadie recordará que era 1 caso.
