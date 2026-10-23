# Experimento 03: las ideas de la conversación, medidas

- **Fecha:** 2026-10-22.
- **Rama:** `arena/720a0807-memorybiorag`.
- **Estado:** experimento offline. **No modifica el motor, la DB ni el snapshot.**
- **Origen:** una conversación de Dennys con otra IA sobre cómo hacer que la neurona aprenda, y la respuesta de esa IA al [experimento 02](../experimento_02_examen_sellado/README.md).
- **Viene de:** [experimento 01](../experimento_01_pesos_aprendidos/README.md), del que usa las mismas señales y los mismos datos.

Todas las variantes parten **exactamente de los pesos a mano de hoy**. Se repitieron con **3 semillas** (7, 11 y 23), que cambian la partición, el orden de las consultas y el azar. Solo se dan por buenos los resultados que se repiten en las tres.

> **Nota:** aquí se evalúan 872 consultas, en vez de 875, porque se excluyen 3 con un solo candidato en el pool. Por eso los pesos a mano dan 90.14, no 90.17.

---

## 1. Cómo reparte la neurona "el negativo" entre las agujas

Es la pregunta de Dennys: *"¿cómo saber cuánto negativo le vas a quitar a cada una de las agujas?"*. El algoritmo es la **regla de la cadena** (retropropagación, video 2). Para una capa se reduce a una cuenta:

> **culpa de una aguja = Σ sobre los candidatos de (objetivo − probabilidad) × valor de esa aguja en el candidato**
>
> **peso nuevo = peso + tasa × culpa**

Ejemplo con dos candidatos y dos agujas:

| | BM25 | Hub | Probabilidad que le da la neurona | Objetivo | Error (objetivo − prob.) |
|---|---|---|---|---|---|
| A (correcto) | .9 | .1 | .3 | 1 | **+.7** |
| B (impostor) | .2 | .8 | .7 | 0 | **−.7** |

- Culpa de BM25 = (+.7 × .9) + (−.7 × .2) = **+.49**. Esta aguja apuntaba al correcto, así que **se sube**.
- Culpa de Hub = (+.7 × .1) + (−.7 × .8) = **−.49**. Esta aguja apuntaba al impostor, así que **se baja**.

Cada aguja recibe culpa **en proporción a cuánto empujó al candidato equivocado**. Con capa oculta, la misma cuenta se repite hacia atrás, capa por capa. En el código es `entrenar_neurona.py`, líneas 138 y 146-149. Hay un ejemplo real, el caso 0739, en [LA_NEURONA_EXPLICADA.md §4](../experimento_01_pesos_aprendidos/LA_NEURONA_EXPLICADA.md).

**Condición imprescindible:** para calcular el error hay que saber **cuál era el correcto**. Toda esta sección depende de eso, y las secciones siguientes lo comprueban.

---

## 2. Resultados

Formato de las columnas "gana / pierde 1.º (sale del top-5)": casos ganados en el 1.º puesto / casos que pierden el 1.º puesto (casos que salen del top-5), siempre frente a los pesos a mano. Las salidas completas están en `resultados/ideas_{7,11,23}.txt` y `.json`.

### I1. Re-ranqueo en vivo de 3-4 vueltas con respaldo, sin conocer la respuesta

Antes de entregar, el motor mueve las agujas para subir una "nota" que se pone a sí mismo y entrega su mejor intento.

| Nota que se pone el motor | Vueltas | R@1 (7 / 11 / 23) | Gana / pierde 1.º (sale del top-5) |
|---|---|---|---|
| Pesos a mano (hoy) | — | 90.14 | — |
| Coincidencia de señales del top-5 | 4 | 88.88 / 88.53 / 88.07 | +1–4 / −13 a −19 (16–19) |
| Margen de confianza | 4 | 87.50 / 87.39 / 87.50 | +14–18 / −37 a −42 (53–59) |
| Coincidencia de señales del top-5 | 50 | 84.40 / 83.72 / 83.14 | +4–13 / −63 a −66 (44–50) |
| **Oráculo: conoce la respuesta** | 4 | 94.84 / 94.72 / 94.50 | +38–41 / **−0** (0) |
| **Oráculo: conoce la respuesta** | 50 | **99.43 / 99.54 / 99.43** | +81–82 / **−0** (0) |

**Veredicto: sin la respuesta, siempre empeora; y cuantas más vueltas, peor.** La "nota" que se pone el motor se calcula con **las mismas agujas** que está moviendo, así que es circular: mide cuánto se cree a sí mismo, no si acertó.

La fila del oráculo enseña qué pieza falta. **Si supiera la respuesta, llegaría a 99.5 %.** El problema nunca fue el algoritmo de ajuste: es que **en vivo nadie le dice cuál era la correcta**.

### I2. Pesos campeones persistentes ("si mejoró, queda fijo; si no, no se guarda")

| Variante | R@1 (7 / 11 / 23) | Gana / pierde 1.º (sale del top-5) |
|---|---|---|
| Sin respuesta: se guarda si mejora la coincidencia de señales | 80.39 / 80.16 / 76.61 | +9–13 / **−96 a −131** |
| Sin respuesta: se guarda si mejora el margen | 93.23 / 91.97 / **89.79** | +37–41 / −14 a **−44** |
| **Con feedback después de entregar y repetición de experiencias** (últimas 300), evaluación en línea | 92.09 / 93.00 / 90.94 | +30–34 / −8 a −23 |
| Los mismos pesos finales aplicados a todo | 93.58 / 93.58 / 92.55 | +39–43 / −10 a −18 |

**Veredicto:**

- **Sin respuesta, es inestable o desastroso.** La variante del margen parecía buena en la semilla 7 (+41), pero en la 23 pierde 44 casos. **Depende de en qué orden lleguen las preguntas, así que no es fiable.**
- **Con feedback real, que es la versión correcta de la idea, sí aprende**: llega a ~92.5–93.6 de R@1 con los pesos finales. Pero aun con la compuerta de repetición ("solo se guarda si no baja ninguno de los últimos casos vistos"), **bajan 8–23 casos**. Los que bajan son casos fuera de esa memoria y casos nuevos.

### I3. "Empate técnico": si la neurona deja casi empatados al 1.º y al 2.º, se entrega el orden de los pesos a mano

| ε | Consultas delegadas | Gana / pierde 1.º (sale del top-5) en las semillas 7 / 11 / 23 |
|---|---|---|
| Sin empate técnico (R2) | 0 | +41/−8 (8) · +40/−6 (10) · +40/−7 (8) |
| 0.2 | ~20 | +39/−4 (7) · +39/−5 (7) · +37/−5 (8) |
| 0.5 | ~35 | +35/−2 (5) · +36/−4 (7) · +35/−5 (6) |

**Veredicto: ayuda, de forma modesta pero consistente en las tres semillas.** Quita 2–6 pérdidas a cambio de 4–6 ganancias. **Es una buena idea de la otra IA** y vale la pena incluirla en la integración. Como el ε se eligió viendo esta tabla, debe confirmarse de punta a punta.

### I4. Pesos por tipo de consulta (una neurona por perfil)

Los perfiles son tres: nombre exacto en el 1.º puesto (600 consultas), consulta corta (56) y consulta larga (216).

| | Semilla 7 | Semilla 11 | Semilla 23 |
|---|---|---|---|
| Una sola R2 | +41 / −8 (8) | +40 / −6 (10) | +40 / −7 (8) |
| Una R2 por perfil | +42 / −8 (6) | +41 / −10 (11) | +43 / −13 (7) |

**Veredicto: no mejora; en dos semillas pierde más.** La razón es que **la capa oculta de R2 ya hace esto por dentro**: combina agujas según el contexto de la consulta, y es el "XOR" del experimento 01. Partir los datos en perfiles solo deja menos ejemplos para cada neurona.

### I5. "Ganancia neta, siempre que los casos que bajan sigan en el top-5"

- De los casos que R2 baja del 1.º puesto (6–8), **5–7 siguen en el top-5**. Solo el **0596** sale en las tres semillas.
- Pero además hay **6–10 casos que estaban en los puestos 2-5 y salen del top-5**.

**Veredicto: hoy la regla no se cumple tal cual.** Para cumplirla habría que proteger también el top-5, o confiar en que el post-proceso del motor los rescate. Eso solo se sabe midiendo de punta a punta.

---

## 3. Correcciones a la respuesta de la otra IA

| Lo que dijo | Lo que muestran los datos |
|---|---|
| El bajón a 88.02 % del experimento 02 viene de preguntas mal etiquetadas | No. Fue **memorización** por entrenar sin freno hasta 100 % (experimento 02, parte A). Las etiquetas débiles existen, pero son otro problema. |
| "Gana 40 casos a cambio de bajar sutilmente 2" | Sin freno: ~40 ganados por 6–8 que pierden el 1.º y 6–10 que salen del top-5. Con empate técnico ε = .5: ~35 por 2–5 y 5–7. |
| Un re-ranqueo en vivo que mide el "recall en vivo" | El recall necesita saber la respuesta correcta, y en vivo no se sabe. Medido: empeora siempre (I1). |
| Pesos campeones por tipo de consulta | Medido: no mejora (I4). La capa oculta ya lo hace. |
| LSTM, Transformers, BD vectorial, Redis | No aplican aquí. BioRAG ya es memoria externa. La neurona es un ordenador de 17 números por candidato, y SQLite basta. |

**Lo que tenía razón:**

- regularización y parada temprana (ya se usan, experimento 02);
- repetición de experiencias (I2: es la compuerta que más protege en el aprendizaje continuo);
- aumento de datos (es lo que hace `generar_casos_qa.py`);
- **empate técnico** (I3);
- **limpiar las preguntas débiles del QA**;
- la descripción de PPMI.

---

## 4. Conclusión: qué le dice a la neurona que se equivocó

Es la pregunta que Dennys hizo en su conversación, y es **la pieza central**. Los datos lo dejan claro:

1. **En vivo, sin respuesta, no hay nada fiable.** La neurona no puede autoevaluarse con sus propias agujas.
2. **Lo que sí sirve son señales que vienen de fuera de la neurona:**
   - **El QA** (921 preguntas generadas), para el entrenamiento inicial y como validador. Hay que limpiar las etiquetas débiles.
   - **`feedback(util)`** de los agentes, que ya existe en el MCP: es el "sí/no" real de cada búsqueda.
   - **El uso**: qué nodo terminó usando el agente después de buscar. Habría que medir si se puede registrar.
3. **"Guardar los pesos solo si mejoran" es correcto si el juez es el QA o el feedback**, no la nota propia. Es la compuerta de los experimentos 02 y 03, y conviene llevarla al motor con los pesos en una tabla de SQLite, versionados.

---

## 5. Ruta propuesta

Esta ruta es una propuesta para negociar con Dennys. Nada de esto está implementado.

1. **Determinismo** (`search.py:724`). Sin él no se puede verificar "nunca baja".
2. **Limpiar las etiquetas débiles del QA.** Empezar por 0516, 0634, 0596 y 0274, y por los 5 casos "por tema" recurrentes.
3. **Integrar R2 en el motor detrás de `BIORAG_NEURONA=0`**:
   - con λ y empate técnico;
   - con los pesos guardados en una tabla de SQLite, cada uno con su versión y su resultado de QA (los "pesos campeones" de Dennys);
   - medido **de punta a punta** con `evaluar_qa.py`, post-proceso incluido;
   - un juego de pesos nuevo **solo sustituye al campeón si el QA completo no baja**.
4. **Aprendizaje continuo con `feedback(util)`** y repetición de experiencias.
5. **Re-entrenar durante el sueño.** BioRAG ya tiene un ciclo de sueño y consolidación (`ciclo_sueno_consolidacion` en `core/memory/consolidation.py:285`, herramienta MCP `biorag_sueno`): ahí, y no en vivo, es donde la neurona podría re-entrenarse con lo aprendido en el día y pasar la compuerta antes de despertar.

---

## 6. Reproducir

```bash
cd "docs/Mi neurona en el sistema/experimento_03_ideas_conversacion"
for s in 7 11 23; do python medir_ideas.py --semilla-folds $s > resultados/ideas_$s.txt; done   # ~2 min c/u
```

Necesita `../experimento_01_pesos_aprendidos/datos/pools_semilla1.jsonl.gz`. Si no existe, se regenera con `PYTHONHASHSEED=1 python ../experimento_01_pesos_aprendidos/exportar_senales.py`.
