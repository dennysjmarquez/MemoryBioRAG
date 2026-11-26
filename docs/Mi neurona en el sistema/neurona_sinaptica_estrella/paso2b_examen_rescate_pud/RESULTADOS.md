# Paso 2b: examen de rescate v2 en un mundo real (UD PUD) — resultados (2026-11-25)

Protocolo y puertas fijados antes de medir: `PROTOCOLO_V2.md`. Script: `examen_rescate_pud.py` (~11 min con 2 CPU).
Datos: `resultados/examen_pud.json`; diagnóstico posterior sin puerta: `resultados/diag_canal2_con_dormidos.json`.
Corpus: Universal Dependencies PUD (es, en, zh, ja), CC BY-SA 3.0, descargado al correr (sha256 en el JSON).
[V] = medido o leído en el código; [D] = deducido.

## 1. Veredicto en una línea
**Pasa 1 de 7 puertas (P6, limpieza).** El filtro de pistas sin contenido funciona sin listas, pero el examen casi no
tiene preguntas, y la causa principal **no es el examen: son tres comportamientos del motor** que este mundo real dejó
a la vista. No se cambió ningún umbral.

## 2. Puertas [V]
| puerta | es | en | zh | ja | |
|---|---|---|---|---|---|
| P1 casos ≥ 100, B ≥ 40, guardia ≥ 8 | 1 | 3 | 0 | 0 | ❌ |
| P2 top-5 ciego idéntico en pistas que ningún I contiene ≥ 98 % | 1376/1608 (85,6 %) | 1454/1661 (87,5 %) | 3971/4146 (95,8 %) | 1714/1919 (89,3 %) | ❌ |
| P2b, P3, P4, P5 | sin casos suficientes | | | | ❌ |
| P6 limpieza y reproducibilidad | ✅ | ✅ | ✅ | ✅ | ✅ |

## 3. El filtro de pistas sin contenido funciona [V]
Regla: cada unidad de la pista aparece en ≤ 10 recuerdos del mundo. Sin listas, las palabras vacías caen solas:
«de, la, en, el, que…» · «the, of, in, to, and…» · «一個, 他們, 年, 但是…» · «てい, した, った, して…». Las unidades de
contenido sobreviven en todos los idiomas, incluidos bigramas e ideogramas CJK sueltos. Pistas: es 7327 → 2421,
en 7324 → 2585, zh 7401 → 5931, ja 7441 → 3323.

## 4. Tres hallazgos del motor (lo importante de este ciclo)

### H1. El motor no crea sinapsis en chino ni en japonés [V]
Con 839 frases reales por idioma y sin estructura declarada por el agente, el grafo que crece solo tiene:
**es 643 filas, en 679, zh 4, ja 0.** El nacimiento automático de sinapsis (co-ocurrencia, PMI hebbiano) no ve las
palabras CJK, igual que la búsqueda antes del Paso 1. En E1 sí había sinapsis en zh/ja porque las daban las
dimensiones y los sustantivos clave declarados. **Consecuencia:** sin estructura declarada, en CJK no hay grafo que
juzgar, y la neurona sináptica no tendría nada que hacer ahí. Es un arreglo del motor para su propio ciclo
(«ojos Unicode» del nacimiento de sinapsis), con OK.

### H2. La inhibición lateral duerme el 74 % de los recuerdos y rompe la invariancia [V]
`consolidation.py` L524–562: si la suma de pesos activos supera `0,8 × activos`, duerme primero los de menor peso y
**más antiguos**, sin mirar el contenido. En un mundo sin uso, **622 de 839** recuerdos quedan dormidos, exactamente
igual en los 4 idiomas. Efectos medidos:
- **El canal 2 no muestra vecinos dormidos** (`l.estado = 'activo'`): un recuerdo dormido nunca puede ser
  rescatado, justo los olvidados, que son los que más lo necesitarían.
- **Añadir recuerdos duerme a otros:** con I, 177 recuerdos de D pasan a dormidos. **El 100 %** de los fallos de P2
  (232, 207, 175 y 205 pistas) toca un recuerdo que cambió de estado. Es una violación de la NORMA MÁXIMA
  F(D,q) = F(D∪I,q) causada por el sueño del motor, no por el examen.
- [D] En una base real, el uso sube los pesos y mantiene activos a los recuerdos consultados; el efecto será menor,
  pero el mecanismo es el mismo. Es una decisión de diseño de Dennys; aquí solo se informa.

### H3. Tensión propia del examen: una pista informativa encuentra a B directamente [V]
Con el filtro, B queda fuera del top-5 ciego solo en el 1,3–5,3 % de las pistas (es 106, en 137, zh 76, ja 101).
Una pieza rara del texto de B casi siempre lleva a B. El rescate por el canal 2 es raro por naturaleza.

## 5. Diagnóstico posterior (sin puerta): ¿y si el canal 2 mostrara a los dormidos? [V]
Reconstruyendo el orden a mano del canal 2 desde todas las aristas (peso ≥ 0,50) sin el filtro de estado:
| | es | en | zh | ja |
|---|---|---|---|---|
| casos | 10 | 11 | 0 | 0 |
| A y B del mismo documento en los casos | 50 % | 36 % | — | — |
| … en todas las aristas del grafo | 18 % | 22 % | — | — |
Aun así faltaría un orden de magnitud para P1. La señal es buena pero con muy pocos datos: en los casos, la relación
real aparece 2–3 veces más que en el grafo.

## 6. Otros datos [V]
- Precisión del grafo automático en texto real (aristas entre frases del mismo documento): **18 % en es, 22 % en en**,
  coherente con el 11–18 % del exp. 16.
- En es/en entran en el top-5 recuerdos I que no contienen las unidades exactas de la pista (156 y 128 pistas): el
  buscador es difuso (trigramas y raíces), así que «contener la pista» para el motor es más amplio que la
  comprobación por unidades. En zh/ja, 0.
- Construcción: 18–86 s por idioma. 85 de las 839 frases de D no tienen compañera de documento.

## 7. Qué propongo [D]
1. **El examen de rescate, tal como está definido, da muy poca señal con este motor.** Para la neurona, eso significa
   poco material por sueño. Dos rediseños posibles, cada uno con sus puertas fijadas antes de mirar cifras:
   - **Examen de orden** (como el «tapar y adivinar» de la neurona 1): toda pista de B que hace aparecer a un A con B
     entre sus vecinos es una pregunta válida («¿B queda arriba entre los vecinos de A?»), falle o no la búsqueda
     directa. Da muchas más preguntas sin perder la respuesta gratuita.
   - Mantener el rescate como examen de **validación** (pocas preguntas, pero las más valiosas) y el de orden como
     examen de **entrenamiento**.
2. **H1 es un requisito previo para los 4 idiomas:** sin sinapsis en CJK no hay nada que ordenar. Un ciclo del motor,
   como el Paso 1, con OK.
3. **H2 es una pregunta para Dennys:** ¿debe el canal 2 poder mostrar vecinos dormidos? ¿La inhibición lateral debe
   respetar la invariancia? No se toca sin su decisión.

## Corrección (2026-11-26, Paso 2c)
La frase de §4 H2 «El 100 % de los fallos de P2 toca un recuerdo que cambió de estado» está inflada: el conteo
trataba como cambio de estado a los recuerdos de I, que no existen en D. Clasificación correcta, en este mismo mundo
(`../paso2c_examen_orden_rescate/RESULTADOS.md` §4): en es/en, 156 y 128 fallos son recuerdos de I que el buscador
difuso considera coincidencia (no violan la NORMA MÁXIMA) y 53 son cambios de estado de D. En zh/ja los fallos sí
vienen de H2 (cambio de estado o reorden), y desaparecen al apagar la inhibición lateral. La conclusión sobre H2 se
mantiene: con la inhibición apagada, el orden relativo de D es invariante en el 99,0–100 % de las pistas.
