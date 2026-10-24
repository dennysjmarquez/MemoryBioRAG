# Experimento 04: la neurona que aprende sola y entra al motor real

- **Fecha:** 2026-10-22.
- **Rama:** `arena/720a0807-memorybiorag`.
- **Estado:** experimento aislado. **No modifica el motor, la DB ni el snapshot.** El snapshot se abre en modo solo lectura y el QA trabaja sobre su copia temporal de siempre.
- **Viene de:** experimentos [01](../experimento_01_pesos_aprendidos/README.md), [02](../experimento_02_examen_sellado/README.md) y [03](../experimento_03_ideas_conversacion/README.md).

## 0. La idea (de Dennys) y la pieza que faltaba

> Antes de devolver resultados, la neurona se re-entrena en "lo que falló". Solo se aceptan pesos nuevos si no bajan del **piso** (los pesos a mano de hoy) y no memorizan (**techo**). Sin feedback, sin registros, sin trabajo extra del agente. Debe funcionar en una DB vacía de un tercero.

El experimento 03 demostró que para aprender hay que saber **cuál era el correcto**, y en una búsqueda real nadie lo dice.

**La pieza que faltaba es el autoexamen ("tapar y adivinar").** Cada recuerdo de la DB genera sus propias preguntas, con el mismo generador del QA: variante, sinónimo, typo, pregunta natural, por tema y cruce de idioma. Como sale del propio recuerdo, **la respuesta se conoce**. Si el recuerdo no sale #1 en su propia pregunta, eso es "lo que falló".

Esto lo puede hacer cualquier DB, de cualquier tercero, sin que nadie etiquete nada.

## 1. Qué se hizo, paso a paso

| Paso | Archivo | Qué hace |
|---|---|---|
| 1 | `generar_examen.py` | Genera el examen. 866 recuerdos dan **4149 preguntas** (semilla 2026, sin dormidos, sin literales). Se descartan las preguntas idénticas a alguna del QA y las que repiten el nombre del nodo. |
| 2 | `exportar_pools.py` | Pasa cada pregunta por el **motor real** y guarda qué vio cada aguja de cada candidato. Corre en 2 partes en paralelo, unos 25 min. Salida en `datos/`, ignorado por git porque pesa 65 MB. |
| 3 | `autoaprendizaje.py` | Entrena la corrección sobre los pesos base solo con el examen. El QA solo pone la nota y la neurona nunca ve sus respuestas. Modo **A "sueño"**: offline, de una vez. Modo **B "en vivo"**: por búsqueda, antes de responder. |
| 4 | `qa_con_neurona.py` + `correr_qa_motor.sh` | Mete la neurona **dentro del motor real** (en memoria, sin tocar archivos) y corre el `scripts/evaluar_qa.py` **oficial**, completo, de punta a punta. |
| 5 | `comparar_casos.py`, `regla_margen.py`, `reglas_en_qa.py` | Comparan caso a caso, prueban reglas de seguridad y aplican al QA las reglas elegidas con el examen, sin re-correr el motor. |

**Piso y techo en el entrenamiento:**

- **Piso:** ninguna categoría del examen puede tener menos aciertos #1 que los pesos base.
- **Techo:** el 20 % de los recuerdos queda de **guardia**. La neurona nunca estudia sus preguntas, y se elige el punto donde la guardia deja de mejorar (parada temprana).
- **Partición:** el corte estudio/guardia es por nodo, para que no se filtren respuestas.
- **Semillas:** 3 particiones distintas (7, 11 y 23). Solo cuenta lo que se repite en las tres.

## 2. Resultado principal: QA oficial, motor real, de punta a punta

**Cómo entra la neurona al motor (modo `top5`):**

- La neurona **solo reordena la lista final** que entrega el motor, con los mismos 5 nodos. Los scores de hoy se reasignan en el nuevo orden.
- Con los pesos de hoy, el R@5 de punta a punta ya es 100 %, así que **todos** los fallos de R@1 tienen la respuesta dentro del top-5. Reordenar ahí captura todo lo ganable.
- Por construcción, **el R@5 no puede bajar** y **ningún umbral absoluto cambia** (GABA .80, abstención .6212, FP de negativos), porque los números siguen siendo los mismos.

Salida literal de `evaluar_qa.py` (921 casos, `PYTHONHASHSEED=1`). Los archivos están en `resultados/qa_motor_*.txt`.

| Categoría | Hoy (base) | Neurona A, semilla 7 | Neurona A, semilla 11 | Neurona A, semilla 23 | Neurona B (en vivo), semilla 7 |
|---|---|---|---|---|---|
| cruce_idioma | 62.50 | **87.50** | **87.50** | **87.50** | **75.00** |
| dormido | 100 | 100 | 100 | 100 | 100 |
| literal | 99.59 | 99.59 | 99.59 | 99.59 | 99.59 |
| por_tema | 63.08 | **84.62** | **83.08** | **83.08** | **81.54** |
| pregunta_natural | 93.85 | **96.92** | **96.92** | **96.92** | **96.92** |
| sinonimo | 56.36 | **63.64** | **63.64** | **63.64** | **61.82** |
| typo | 89.23 | **98.46** | **98.46** | **98.46** | **98.46** |
| variante_gramatical | 89.23 | **96.92** | **98.46** | **96.92** | **96.92** |
| **R@1 global** | **91.89** | **95.66** | **95.66** | **95.54** | **95.20** |
| R@5 global | 100 | 100 | 100 | 100 | 100 |
| MRR | .950 | .973 | .973 | .973 | .971 |
| FP negativos | 0 / 40 | 0 / 40 | 0 / 40 | 0 / 40 | 0 / 40 |
| ambiguo (cobertura) | 66.7 % | 66.7 % | 66.7 % | 66.7 % | 66.7 % |
| Gate | OK | OK | OK | OK | OK |

**En las cuatro corridas, ninguna categoría baja del piso y ningún caso sale del top-5.**

**Caso a caso** (`comparar_casos.py`):

| Corrida | Gana | Pierde | Casos perdidos |
|---|---|---|---|
| A, semilla 7 | 36 | 2 | 0274 (literal), 0593 (cruce) |
| A, semilla 23 | 35 | 2 | 0593 (cruce), 0873 (por_tema) |
| B, semilla 7 | 33 | 3 | 0593, 0596, 0842 |
| **A, semilla 7 + regla de identidad** | **36** | **1** | 0593 |

**Regla de identidad:** si escribes el nombre exacto de un recuerdo, ese recuerdo va primero. En los 96 casos en que el #1 de hoy se llama exactamente como la consulta (comparación sin distinguir mayúsculas), esa regla nunca contradice la etiqueta. Arregla 0274 sin costo.

**Tiempo:** el QA tarda 561–577 s con la neurona contra 620 s sin ella. El costo no es medible frente al ruido.

## 3. Lo que NO funcionó (y por qué importa)

1. **Sumar la corrección al score (modo `escala`):** el R@1 sube a 95.66, pero **3 sinónimos salen del top-5** (R@5 de sinónimo cae a 94.55). La neurona infla los scores: el 75–99 % de los top-1 pasan de .95, contra el 22 % de hoy. Ponerle un "ancla de escala" (castigar correcciones grandes) **no lo arregló**.
2. **Reordenar todo el pool antes del post-proceso (modo `orden`):** con la escala intacta, **los mismos 3 sinónimos siguen saliendo**. La causa era el orden, no la escala, así que mi primer diagnóstico estaba mal. Por eso la neurona solo toca el top-5 final.
3. **La neurona lineal (R1) casi nunca cumple el piso.** Mejora unas categorías a costa de otras. La de capa oculta (R2) sí, porque reparte pesos según el contexto.
4. **El modo en vivo es más lento de lo deseable.** La mediana es 0.1 ms, porque la mayoría de las búsquedas no dudan. Pero cuando duda: p95 de 360–460 ms y máximo de 1.5–2.5 s (R2), o p95 de unos 140 ms (R1). Aprender en cada búsqueda **es posible**, pero para producción conviene que el aprendizaje ocurra en segundo plano o al consolidar (modo A).
5. **Piso también en el top-5 del examen:** no cambió nada, porque el examen ya no perdía top-5.
6. **Margen ε (la neurona solo cambia el #1 si le saca más de ε):** elegido con la guardia del examen, ε = 2 deja 0 / 2 / 1 pérdidas en las semillas 7 / 11 / 23 y conserva unos 70 % de las ganancias. En el QA no ayuda: baja de +36 a +28 y la pérdida 0593 sigue.

## 4. Por qué no llega al 100 %

- **Sinónimo:** en 25 de los 61 casos, la palabra buscada es sinónimo registrado de **varios** recuerdos. Por ejemplo, "regla" lo es de 18 recuerdos y "arquitectura" de 11. El QA da por bueno solo uno, elegido al generar el caso. Medido antes del post-proceso, si se acepta cualquier dueño legítimo, la neurona pone a uno de ellos #1 en 46 de 61 casos (los pesos base, en 41). Con la cuenta estricta, solo el esperado, son 37 contra 32.
- **Por tema:** son 3 palabras sacadas al azar del contenido, y a menudo describen igual de bien a varios recuerdos.
- **0593 (cruce):** el post-proceso del motor (léxico aprendido / hub) había subido al correcto a .915. La neurona calcula su corrección **antes** de ese paso y no ve esa evidencia. **Siguiente paso:** "la neurona no contradice evidencia que no vio", es decir, no bajar un nodo que el post-proceso ascendió. Sale de un solo caso, así que debe validarse en otra DB antes de darlo por bueno.

## 5. Advertencias honestas

- El examen y el QA salen de la **misma familia de generador** (semillas distintas, preguntas idénticas excluidas). Es la mejor prueba disponible sin usuarios reales, pero no sustituye búsquedas humanas.
- Es **un solo snapshot** (866 recuerdos, en español, de un dominio). Falta probarlo en otra DB.
- El enganche usa trucos que solo valen para un experimento:
  - lee la variable `concepto` del marco que llama a la fórmula;
  - envuelve `buscar_por_frase`.
  En un PR serían 2 líneas explícitas: guardar la corrección al puntuar y reordenar el top-k al final.
- **21 de los 4008 puestos** de top-5 final (853 búsquedas con 2 o más resultados, semilla 7) no tenían corrección: esos nodos los añadió el post-proceso. Se les puso la media de los demás.
- El modo B "pesos al final" vio las **consultas** del QA (no sus respuestas) mientras aprendía. La cifra limpia del modo B es "respuesta en el momento", que se mide antes del post-proceso (93.83–94.17).
- El QA oficial de punta a punta usa `limite=5`. El camino MCP pide 30 y corta a 10, así que habría que decidir el k del reordenamiento.

## 6. Cifras antes del post-proceso (todas las semillas)

Este es el ranking "crudo" de la fórmula (el de los experimentos 01–03), donde los pesos base dan R@1 90.17. Están en `resultados/autoaprendizaje_<semilla>.txt`.

| Modelo | Semilla 7 | Semilla 11 | Semilla 23 |
|---|---|---|---|
| A sueño R2 | 95.31 (+49 / −4) | 95.20 (+50 / −6) | 95.31 (+49 / −4) |
| B en vivo R2, respuesta en el momento | 94.17 (+39 / −4) | 93.83 (+36 / −4) | 94.06 (+38 / −4) |
| B en vivo R2, pesos al final | 94.63 (+42 / −3) | 94.86 (+43 / −2) | 94.86 (+43 / −2) |
| Guardia del examen (A R2 frente a base) | 85.86 vs 69.73 | 85.52 vs 69.08 | 86.50 vs 69.88 |

Comparación con el experimento 01: aprendiendo **con las etiquetas del QA**, R2 llegaba a 93.94–94.51. **Aprendiendo sola con su autoexamen llega más alto**, porque el examen es casi 5 veces más grande.

## 7. Reproducir

```bash
cd /ruta/al/repo
PY=python3   # con numpy
E="docs/Mi neurona en el sistema/experimento_04_autoaprendizaje"
$PY "$E/generar_examen.py"
PYTHONHASHSEED=1 $PY "$E/exportar_pools.py" --casos "$E/datos/examen_autogenerado.jsonl" --parte 0 --partes 2 --salida "$E/datos/pools_examen_p0.jsonl.gz"
PYTHONHASHSEED=1 $PY "$E/exportar_pools.py" --casos "$E/datos/examen_autogenerado.jsonl" --parte 1 --partes 2 --salida "$E/datos/pools_examen_p1.jsonl.gz"
$PY "$E/autoaprendizaje.py" --semilla 7          # también 11 y 23; necesita los pools QA del exp01
PY=$PY bash "$E/correr_qa_motor.sh" base=base top5_A_R2_s7=resultados/pesos/A_R2_semilla7.npz
$PY "$E/comparar_casos.py" base top5_A_R2_s7
$PY "$E/reglas_en_qa.py" top5_A_R2_s7 0 1 2
```
