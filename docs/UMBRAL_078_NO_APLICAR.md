# El umbral 0.78: tres problemas antes de aplicarlo

**Fecha:** 2026-08-15
**Estado:** el barrido fue el paso correcto. Pero la tabla tiene una imposibilidad
matemática, el `net` se calculó sobre una muestra sesgada, y el criterio de
optimización asume algo que no es cierto.
**Recomendación:** no aplicar 0.78. Rehacer el barrido con el script corregido.

---

## 1. La tabla viola la monotonía (hay un error de medición)

Al **subir** un umbral, tanto el FP como el recall solo pueden **bajar o quedarse
igual** — menos resultados cruzan un listón más alto. Es monotonía matemática, no
una cuestión de datos.

En la tabla reportada:

| umbral | FP% | Recall% | |
|---|---|---|---|
| 0.78 | 0.0 | 78 | |
| **0.80** | **9.4** | **82** | ← FP sube +9.4pp **y** recall sube +4pp al subir el umbral |
| 0.85 | 0.0 | 78 | |

**Ambas cosas son imposibles simultáneamente con el resto de la tabla.** El FP no
puede pasar de 0% a 9.4% subiendo el corte, y el recall no puede subir de 78% a 82%.

Eso significa que hay un error en cómo se generó la fila (¿corridas distintas?
¿DB cambiando bajo los pies? ¿el daemon reactivado?). **Y si una fila está mal, el
"óptimo 0.78" que sale de la fila contigua no es fiable.**

Es reproducible: volver a correr el barrido debería dar una curva monótona. Si no
la da, el problema está en la medición, no en el umbral.

## 2. El `net = 40` se calculó sobre ~51 positivos, no sobre 881

Reconstruyendo: con `FP=0` y `recall=78%`, `net = n_pos × 0.78 = 40` implica
`n_pos ≈ 51`.

El benchmark tiene **881 positivos**. Si el `net` usara todos, en el óptimo daría
~687, no 40.

**La causa es un defecto de mi script**, y lo asumo: `_scores_top1()` tenía
`limite_casos = 120` por defecto. Eso truncaba los positivos a los primeros 120
casos del jsonl (mayoritariamente `literal`) mientras los ~32-40 negativos entraban
**completos**.

Resultado: el ratio positivos:negativos pasó de **~22:1** (el real) a **~1.6:1**.
Truncar la clase mayoritaria y no la minoritaria sesga el punto de operación hacia
la precisión.

**Ya está corregido:** el default ahora es sin límite, y si alguien pasa un límite
el script avisa de que sesga el ratio.

## 3. El criterio "maximizar TP − FP" asume que un FP cuesta lo mismo que un FN

Ese criterio solo es correcto si (a) ambos errores cuestan igual y (b) la muestra
refleja el ratio real de consultas con y sin respuesta. Aquí no se cumple ninguna.

Con el ratio real del benchmark (881 positivos : 32 negativos):

| umbral | FP% | Recall% | TP | FP | **net real** |
|---|---|---|---|---|---|
| **0.25** | 100 | 100 | 881 | 32 | **849** ★ |
| 0.60 | 65.6 | 96 | 846 | 21 | 825 |
| 0.70 | 34.4 | 88 | 775 | 11 | 764 |
| 0.78 | 0 | 78 | 687 | 0 | **687** |

**Con el ratio real, el óptimo de "TP − FP" es el umbral MÁS BAJO (0.25), no 0.78.**
Cada punto de recall vale 22 veces más que un punto de FP, porque hay 22 veces más
positivos.

El "óptimo 0.78" es un artefacto de haber medido con ~1.6:1 en vez de ~22:1.

## 4. Lo que el barrido corregido muestra

Añadí al script un barrido que reporta el neto bajo **varios costes relativos**, en
vez de asumir uno. Con distribuciones simuladas de AUC≈0.89 (parecido al 0.914 real):

```
coste_fp=1/1   (FP y FN cuestan igual)              -> umbral 0.75
coste_fp=1/5   (1 FP evitado vale 5 aciertos)       -> umbral 0.55
coste_fp=1/22  (ratio real del benchmark)           -> umbral 0.45
```

*(simulación, no medición — sirve para mostrar la sensibilidad)*

**El óptimo se mueve de 0.45 a 0.75 según lo que asumas.** Eso significa que **no
existe un umbral "natural"** que los datos revelen por sí solos. Es una decisión de
producto: ¿cuánto peor es inventarse una respuesta que decir "no sé" cuando sí lo
sabías?

Esa pregunta no la responde el benchmark. La responde el uso real — y la tabla
`log_busquedas` tiene el histórico para estimarla.

---

## 5. Lo que sigue siendo cierto y valioso

- **AUC = 0.914** es un resultado sólido: hay separación de sobra.
- **Escenario A confirmado**: el problema es el corte, no las señales.
- **RRF descartado como solución al FP**: correcto y bien argumentado.
- **El umbral 0.25 es demasiado bajo para el corpus vivo**: cierto, y sigue siendo
  el hallazgo principal de toda esta línea.

Nada de eso cambia. Lo que cambia es que **0.78 no es el número**.

## 6. Orden recomendado

| # | Acción | Por qué |
|---|---|---|
| 1 | Rehacer el barrido con el script corregido (sin `limite_casos`) | La curva actual tiene una fila imposible y un ratio sesgado |
| 2 | Verificar que la curva sale monótona | Si no, el problema es la medición, no el umbral |
| 3 | Medir el ratio real en `log_busquedas` | Convierte la elección de coste en fundamentada |
| 4 | Elegir el umbral con el coste explícito y documentado | Que quede escrito *por qué* ese número |
| 5 | Aplicar con benchmark antes/después | Un cambio, una medición |

## 7. Nota de método sobre mis propios errores en esta línea

Dos de los tres problemas de este reporte los causé yo:

- el `FP=6.2%` tautológico venía de que mi script calibraba y medía sobre los
  mismos negativos (corregido: ahora parte en calibración/validación);
- el `net=40` sesgado venía del `limite_casos=120` por defecto (corregido: sin
  límite, con aviso si se usa).

Ambos son el mismo tipo de fallo: un default cómodo para probar rápido que se
convierte en un sesgo silencioso cuando alguien confía en el número. Es exactamente
lo que la regla del proyecto llama "resultado que parece válido pero no lo es".
