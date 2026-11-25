# Experimento 16, protocolo v2: un mundo más difícil y la pregunta «¿hace algo que un algoritmo fijo no logra?»

**Fecha:** 2026-11-25. **Se sube antes de medir los mundos v2** (semillas 1, 2, 3 y G).
**El protocolo v1 sigue vigente y se mide completo tal como se escribió.** La v2 se agrega aparte y no
reemplaza nada.

## Por qué hay una v2

Al depurar el código del análisis v1 sobre la semilla 1, se vio que el mundo v1 es demasiado fácil.
Fue antes del análisis oficial y sin cambiar ningún umbral de la v1, pero **sí sobre datos de un mundo
de la medición**; se declara aquí por transparencia.

Cada tema tiene palabras exclusivas, así que basta una fórmula fija («¿comparten una palabra rara?»)
para separar casi a la perfección lo relacionado de lo no relacionado: AUC 0,999 con
`top3_idf_compartidas` en la parte sellada de la semilla 1.

Por eso la v1 puede medir el piso y la invariancia, pero **no puede probar** que la neurona aporte
algo que una fórmula fija no logra. Y ese es el requisito central del usuario: cada neurona debe
cubrir una inteligencia que un algoritmo simple no alcanza.

## 1. Mundo v2 (`mundo.generar_v2`)

Igual que el v1 (temas, sesiones, hubs, palabras genéricas, siglas, variantes I e invariancia), con
cuatro cambios que imitan el lenguaje real:

| Rasgo | Cómo se genera |
|---|---|
| **Sinonimia** | Cada *concepto* tiene 1, 2 o 3 palabras distintas (50 %, 35 % y 15 %). Cada recuerdo elige una al azar, así que dos recuerdos del mismo subtema pueden hablar de lo mismo **sin compartir palabras** |
| **Polisemia** | 40 palabras pertenecen a **dos conceptos de temas distintos** (la misma palabra con dos significados). Generan coincidencias falsas |
| **Vocabulario transversal** | 80 conceptos compartidos. Cada tema usa 15 de ellos, y esos grupos se solapan entre temas |
| **Dimensiones y categorías ruidosas** | Solo 5 perfiles de dimensiones, compartidos por 4 temas cada uno, con un 35 % de ruido. La categoría coincide con la del tema solo el 60 % de las veces |

El sinónimo de un concepto presente en el recuerdo aparece en `syn`, como cuando un agente anota
sinónimos.

**Piloto (semilla 101, que no se usa en ninguna medición):** pares que comparten al menos una palabra
que no es conector, sin pasar por el motor.

| Señal | AUC |
|---|---|
| Mejor fórmula léxica fija (`max_idf_compartida`) | 0,913 |
| Jaccard de dimensiones | 0,867 |
| Combinador aprendido, solo con agujas léxicas | 0,965 |
| Coseno semántico (memoria semántica sin etiquetas) | 0,999 |

Se declara aquí, antes de medir, para que nadie pueda decir que el mundo se ajustó después.

## 2. La neurona v2

Tiene tres piezas. Cada una se reporta por separado (ablación).

1. **Memoria semántica sin etiquetas** (`neurona.Semantica`). Aprende el significado por el uso:
   - método PPMI + SVD, 48 dimensiones;
   - dos palabras rodeadas de las mismas palabras quedan cerca, aunque nunca aparezcan juntas, que es
     justo el caso de los sinónimos;
   - se calcula **una vez** sobre el texto (sin etiquetas) de los recuerdos del mundo D y se congela
     con un hash.
2. **Combinador aprendido** (red de 23 → 16 → 1). Usa las 20 agujas léxicas de la v1 y 3 agujas
   semánticas: coseno, coseno solo con palabras raras y alineación palabra a palabra. Aprende cuánto
   vale cada señal y cómo se combinan; por ejemplo, que coincidir solo en siglas o palabras genéricas
   es ruido.
3. **Calibración isotónica**, hecha sobre una parte del entrenamiento.

**Por qué no se filtra el examen.** La memoria semántica y el IDF de referencia son estadísticas **sin
etiquetas**, calculadas sobre el texto de D, incluido el de los temas sellados. Es lo mismo que haría el
sistema real con su propio corpus. **Las etiquetas** (qué está relacionado con qué) de los temas
sellados **nunca** se usan para entrenar, calibrar ni elegir nada.

**Invariancia por construcción.** La memoria semántica y el IDF quedan congelados con D. En las
variantes D∪I se usan los mismos, sin recalcular. Ninguna aguja depende de otros recuerdos, del grado,
del peso del piso, del tiempo ni del uso.

## 3. Construcción, partición y métricas

Iguales que en la v1: §2–§6 de `PROTOCOLO.md`.
- Variantes: D, D_rep, D_Ipuro, D_Ireal y D_orden para las semillas 1, 2 y 3.
- Mundo G de otra familia: `T = 35`, 5 subtemas, 25 % de palabras genéricas, semilla 11.
- Entrenamiento: pares no sellados de los tres mundos D. Calibración: pares que tocan un tema
  `t % 4 == 1`. Evaluación: pares sellados.

## 4. Criterios v2 (fijados antes de medir)

- **Criterios 1–8:** los de `PROTOCOLO.md` §8, con los mismos umbrales.
- **Criterio 9: hacer lo que una fórmula fija no logra.** Sobre los pares sellados de **cada** semilla y
  de G, el AUC de la neurona debe ser ≥ el de la **mejor** de estas fórmulas + 0,03:
  - B0: el piso, es decir, el peso del motor;
  - B1: Jaccard de contenido ponderado por IDF;
  - B2: suma del IDF de las 3 palabras compartidas más raras;
  - B3: Jaccard de dimensiones;
  - B5: `max_idf_compartida`.

  La «mejor» se elige **mirando la parte sellada**, lo que le da ventaja a las fórmulas. Así el
  criterio es más difícil para la neurona.

**Ablación (se reporta, no es criterio):**
- B4: coseno semántico solo, sin combinador;
- la neurona solo con agujas léxicas;
- la neurona completa.

Si casi toda la ganancia viene de la memoria semántica, se dirá así.
