# Matriz completa: qué queda decidido y qué hacer ahora

**Fecha:** 2026-08-15
**Estado:** la matriz 2×2 está cerrada. Los 5 fixes quedan exonerados.
**Recomendación:** correr H-corpus antes que Test B, y **no** empezar por RRF.

---

## 1. Lo que la matriz zanja definitivamente

|  | SNAPSHOT | LIVE DB |
|---|---|---|
| **Baseline (5a306fa)** | 25% FP (10/40) | **80% FP (32/40)** |
| **Con 5 fixes** | 17.5% FP (7/40) | 80% FP (32/40) |

Medir `baseline@live` era la corrida que faltaba y ahora cierra la atribución:

- **El 80% es preexistente.** No lo causaron los fixes ni el daemon.
- **El fix 1.2 queda exonerado**, esta vez con evidencia real (antes era una
  hipótesis no descartada).
- Los fixes no empeoran nada en live: 80% → 80%, idéntico.

Esto está bien hecho y bien concluido. Es exactamente el experimento que faltaba.

## 2. El dato del propio reporte que decide el rumbo

Cruzando las métricas de **live DB**:

| Métrica en live | Valor |
|---|---|
| R@5 | **96.37%** — mejor que en snapshot (96.25%) |
| R@1 | 88.65% |
| MRR | 0.917 |
| FP | **80%** |

Traducido:

> Cuando **sí** hay respuesta, la encuentra el **96.37%** de las veces.
> Cuando **no** hay respuesta, "encuentra" algo el **80%** de las veces.

**El ranking funciona — y funciona mejor en live que en snapshot.** Lo que falla es
decidir *si responder*.

Eso descarta la causa nº1 que propone el reporte ("fusión lineal suma señales
incomparables"). Si la fusión estuviera rota, el R@5 se habría degradado. Subió.

Y por lo tanto descarta RRF como primer paso: **RRF mejora el orden de los
candidatos, y el orden ya es bueno.** No hay nada que arreglar ahí. Además RRF es
invariante a la magnitud, que es justo la información necesaria para abstenerse.

## 3. Test B ya no decide nada técnico

Con los fixes exonerados, Test B (snapshot post-fix @ 0.1866) responde una sola
pregunta: si la mejora 25% → 17.5% en snapshot fue real o artefacto de escala.

Esa diferencia son **3 casos de 40** (McNemar p = 0.25). Salga como salga, no es
concluyente y no cambia ninguna decisión.

**Vale la pena correrlo** — es una corrida, y cierra honestamente la narrativa del
"driver principal" en el changelog. Pero **no debe bloquear el trabajo real**, y
sobre todo no debe ir antes que H-corpus.

## 4. La pregunta que nadie ha medido todavía

El reporte dice que los negativos en live puntúan en **[0.3, 0.5]**, con umbral
0.25. Es decir: por encima del umbral, todos.

**Falta el otro lado de la distribución: ¿dónde puntúan los positivos en live?**

De eso dependen dos mundos distintos. Simulado con los negativos reportados:

| Escenario | AUC | Umbral conforme (α=0.10) | FP resultante | Recall preservado |
|---|---|---|---|---|
| **A)** positivos en [0.6, 0.9] | 1.000 | 0.465 | **7.5%** | **100%** |
| **B)** positivos en [0.35, 0.55] | 0.781 | 0.465 | 7.5% | **32.5%** |

> *(Estas cifras son de una simulación con los rangos reportados, no de una
> medición. Sirven para mostrar que los dos escenarios se distinguen nítidamente,
> no para afirmar cuál es el real.)*

- **Si estamos en A:** existe un hueco entre positivos y negativos. Un umbral
  calibrado en ~0.47 lleva el FP del 80% al 7.5% **sin perder un solo caso de
  recall**. El problema se resuelve con una constante bien elegida, no con
  arquitectura nueva.
- **Si estamos en B:** las distribuciones se solapan de verdad. Ningún umbral
  sirve (bajar el FP cuesta 2/3 del recall) y ahí sí hay que rehacer el scoring.

**Son dos diagnósticos opuestos con dos soluciones opuestas, y hoy no sabemos en
cuál estamos.** Elegir RRF ahora es apostar a B sin haberlo comprobado.

`scripts/test_h_corpus_umbral.py` lo mide directamente: calcula AUC entre positivos
y negativos, propone el umbral conforme y reporta cuánto recall sobrevive. Función
AUC verificada contra casos conocidos (separación perfecta → 1.0, solapamiento
total → 0.5, invertido → 0.0).

## 5. Orden recomendado

| # | Acción | Coste | Qué decide |
|---|---|---|---|
| 1 | **H-corpus en live** | 1 corrida | **A vs B: si el arreglo es calibrar o rehacer** |
| 2 | Test B en snapshot @ 0.1866 | 1 corrida | Cierra la narrativa del "driver principal" |
| 3 | Ampliar negativos a 200-300 | 1 tarde | Prerrequisito de cualquier calibración seria |
| 4 | Umbral conforme en escala de score crudo | 1 día | Ataca el FP con garantía |
| 5 | RRF / retrofitting | — | Solo si H-corpus dice B, y con benchmark antes/después |

**El paso 1 es el que importa.** Cambia el plan entero según el resultado.

## 6. Nota sobre el tamaño de muestra

`FP 80%` es 32/40. Wilson 95%: **[65.2, 89.5]**. La dirección es inequívoca, pero
el corpus de negativos son 40 casos — el 4.3% del benchmark.

Para calibrar con α=0.05, el método conforme exige el cuantil `ceil(41×0.95)=39`
de 40: el penúltimo valor, el estadístico más inestable de la muestra. Con n=40 el
α mínimo detectable es 1/41 ≈ 0.024.

Generar negativos es barato — son consultas que no deben devolver nada. **Subir a
200-300 antes de calibrar** convierte el umbral en algo defendible en vez de un
número atado a cuatro casos extremos.

## 7. Una corrección de redacción que sigue pendiente

La tabla de estado sigue diciendo *"Fix 1.2 — Driver principal: R@5 +0.11pp,
FP −7.5pp"*. Con la matriz completa, lo correcto es:

> Los 5 fixes son correctos. En snapshot mejoran el FP en 3 casos de 40
> (p = 0.25, no significativo) y el R@5 en 1 caso de 881 (p = 1.00). En live no
> cambian nada (80% → 80%). Su valor es de **correctitud** (1.1, 1.4), **latencia**
> (1.5) y **coherencia de escala** (1.2, 1.3) — no de métrica demostrable.

El 80% de FP en live era, y sigue siendo, el problema real. Ahora sabemos que no lo
causó nadie de este equipo — pero tampoco está resuelto.
