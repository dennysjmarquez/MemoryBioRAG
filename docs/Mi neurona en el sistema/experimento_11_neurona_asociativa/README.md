# Experimento 11 — La neurona asociativa "de nacimiento"

> **Pedido de Dennys:** *"Ármate la neurona que usa el ser humano cuando va a guardar información y
> enlazar información… lo más parecido o exactamente igual."* Que decida si dos recuerdos **de
> verdad** tienen que ver, que venga **ya calibrada de fábrica** (como nacemos con neuronas listas),
> que **no** se entrene con la memoria de la persona y que funcione en **cualquier** memoria.
>
> **Estado:** experimento. **No se cambió ni una línea del motor. No se tocó ninguna DB real.** La
> memoria de Dennys se leyó desde una **copia** del snapshot, solo lectura.

---

## 0. En pocas líneas

| Pregunta | Respuesta corta |
|---|---|
| ¿Se pudo armar? | Sí. 10 agujas universales + piso a mano + una corrección chiquita de fábrica. Solo numpy. |
| ¿Funciona en una memoria que nunca vio? | Sí. Se entrenó con 2 memorias y se examinó en la 3ª (x3). AUC **.878 / .903 / .981**. |
| ¿Y en la memoria real de Dennys (español, técnica, nunca vista)? | Ordena los enlaces que puso una persona **por encima** de los mecánicos: AUC **.859**. El peso que el motor usa hoy da **.271** (los pone **por debajo**). |
| ¿Qué tanto ayuda en la práctica? | Si cada recuerdo se queda con sus **10** socios más fuertes, se queda con el **41 %** de las conexiones de hoy y conserva el **83 %** de las humanas. Con el peso de hoy, en el mismo cupo, solo el **26 %** de las humanas. |
| ¿La parte que "aprende" ayuda? | Casi nada todavía. Lo que viaja de una memoria a otra es el **instinto** (el piso a mano). Lo digo claro en la sección 6. |
| ¿El umbral fijo sirve en cualquier memoria? | **No.** En la memoria de Dennys marcaría "no" al 94 % de lo que hay. Por eso la decisión final es por **competencia** (cada recuerdo se queda con sus mejores socios), no por un número fijo. |
| ¿Es perfecta? | **Todavía no.** Hay enlaces humanos que no puede ver porque al motor le faltan capas (el **momento** en que se guardó, sobre todo). Sección 9. |
| ¿Ya está en el motor? | **No.** Este experimento solo prueba la neurona. Cablearla y pasar el QA es el paso siguiente, con tu permiso. |

---

## 1. Qué hace un humano cuando guarda y enlaza (y qué copiamos)

Cuando guardas algo nuevo, el **hipocampo** decide con qué recuerdos viejos se une. A grandes rasgos:

| Parte del cerebro | Qué hace | En esta neurona |
|---|---|---|
| **Corteza entorrinal** | Entrega al hipocampo un resumen de lo que estás viviendo | Las **agujas** (sección 2): cada par de recuerdos se describe con 10 números |
| **Giro dentado** | Separa lo parecido pero distinto. Le da peso a lo **raro**: un detalle raro compartido dice mucho, uno común no dice nada | Agujas `rareza_max`, `rareza_media`, `pistas_raras` |
| **CA3** | Completa patrones: si dos cosas tienen los mismos "vecinos", se asocian | Agujas `vecinos`, `cobertura` (y el grafo del motor, que ya existe) |
| **CA1 + inhibición lateral** | Compara y decide. Solo los mejores socios ganan (k-ganadores) | Aguja `mutuo` y la regla de **competencia** (sección 7) |
| **Homeostasis (escalado sináptico)** | Una neurona que se dispara con todo pierde fuerza | Aguja `hub` (recuerdo que se parece a todo = poco fiable) |
| **Nacer con circuitos listos** | No aprendemos de cero a reconocer qué se parece: venimos calibrados | **Pesos de fábrica** congelados (`pesos_fabrica.json`) |
| **El momento / episodio** | Lo que vives junto se une aunque no se parezca | **FALTA en el motor** (sección 9) |

---

## 2. Las agujas (la entrada de la neurona)

Una aguja es un número de 0 a 1 sobre un **par** de recuerdos (A, B). Son **universales**: no miran
*qué* palabras hay, sino *cómo* se relacionan los dos recuerdos **dentro de su propia memoria**. Por
eso sirven en cualquier idioma y tema. Todo sale de los textos, nada viene de afuera
(`agujas.py`).

| Aguja | Qué pregunta |
|---|---|
| `parecido` | ¿Se parecen sus palabras? (coseno tf-idf) |
| `semantica` | ¿Se parecen en significado, aunque usen otras palabras? (LSA de 100 dimensiones) |
| `rareza_max` | ¿Cuál es la pista compartida más rara? |
| `rareza_media` | ¿Qué tan raras son, en promedio, las pistas compartidas? |
| `pistas_raras` | ¿Cuántas pistas raras distintas comparten? |
| `cobertura` | ¿Qué parte de lo importante del más corto está en el otro? |
| `mutuo` | ¿A está entre los más cercanos de B **y** B entre los de A? |
| `vecinos` | ¿Tienen los mismos vecinos cercanos? |
| `hub` | ¿Alguno de los dos se parece "a todo"? (resta) |
| `una_sola` | ¿Se tocan por **una sola** palabra? (resta; tu regla) |

Se probó una 11ª aguja, `corto` (¿alguno es muy corto?). No separa nada (AUC ~.50) y se sacó.

Detalles universales: sin lista de palabras vacías de ningún idioma. Una palabra que sale en más del
15 % de los recuerdos se trata como "relleno" **en esa memoria**. La raíz de una palabra son sus
primeras 7 letras (`busqueda`/`busquedas` → `busqued`).

---

## 3. Las memorias de fábrica (donde "nace" la neurona)

Para calibrar hace falta saber la verdad: qué pares **sí** tienen que ver. Usé tres memorias públicas
muy distintas entre sí, cada una con una verdad conocida (`corpus.py`):

| Memoria | Qué es | "Sí tienen que ver" cuando… | Recuerdos | Pares | Sí |
|---|---|---|---|---|---|
| **noticias** | Reuters (inglés) | tratan el mismo tema | 2,000 | 43,574 | 28.4 % |
| **diccionario** | WordNet (inglés) | WordNet los une directo (es-un, parte-de, opuesto…) | 2,000 | 40,225 | 2.9 % |
| **relatos** | Brown (inglés), trozos de 150 palabras | son trozos del **mismo** texto | 1,200 | 27,195 | 5.8 % |

Los pares no son al azar: son los que un motor mecánico **propondría** (comparten raíz o son vecinos
cercanos), hasta 30 por recuerdo. Así la neurona se entrena justo en la decisión difícil que va a
tener que tomar en el motor.

Los casos dudosos (por ejemplo, dos palabras de WordNet a 2 pasos) no se usan ni para entrenar ni
para medir.

---

## 4. Banco de calibración: qué separa cada aguja

AUC = probabilidad de que un par que **sí** tiene que ver saque más puntaje que uno que **no**.
0.5 es azar y 1.0 es perfecto. (`resultados/banco_calibracion.json`)

| Aguja | noticias | diccionario | relatos |
|---|---|---|---|
| parecido | .859 | .922 | .961 |
| semantica | .900 | .698 | .968 |
| rareza_max | .720 | .881 | .891 |
| rareza_media | .675 | .819 | .808 |
| pistas_raras | .612 | .829 | .905 |
| cobertura | .811 | .809 | .910 |
| mutuo | .850 | .926 | .969 |
| vecinos | .838 | .594 | .920 |
| hub | .512 | .436 | .452 |
| una_sola | .369 | .323 | .400 |

Lectura simple: ninguna aguja sola gana en las tres. `semantica` es la mejor en noticias pero floja
en el diccionario. `rareza_max` es al revés. Por eso hace falta **juntarlas**.

---

## 5. El piso a mano (el instinto)

Como manda el molde de BioRAG, primero una fórmula a mano con pesos redondos:

```
z = -5 + 3·mutuo + 3·parecido + 2·rareza_max + 2·semantica + 1·vecinos + 1·pistas_raras − 1·una_sola − 1·hub
fuerza = 1 / (1 + e^-z)        (de 0 a 1)
```

| Memoria | AUC del piso |
|---|---|
| noticias | .866 |
| diccionario | .906 |
| relatos | .981 |

**Nota de honestidad:** estos pesos los elegí mirando las **tres** memorias de fábrica. Para tener el
número limpio, repetí la elección sin mirar la memoria examinada (rejilla de 72 combinaciones,
elegida con 2 y examinada en la 3ª; `variantes.py` → `resultados/variantes.json`):

| Memoria examinada | Piso elegido sin mirarla | Piso del archivo (mirándola) |
|---|---|---|
| noticias | **.841** | .866 |
| diccionario | **.867** | .906 |
| relatos | **.982** | .981 |

La memoria de Dennys **nunca** se miró para elegir nada. Sus números (sección 8) están limpios.

---

## 6. La corrección de fábrica (lo que "aprende") y lo que descubrí

Encima del piso va una red chiquita (10 agujas → 6 neuronas → 1 número) que **suma** al piso, acotada
a ±TECHO. Se entrena **una sola vez, en la fábrica**, y queda fija. En la memoria de la persona no
aprende nada: solo decide (`neurona_asociativa.py`).

Para que aprenda y no memorice:

- 20 % de los recuerdos son **guardia** y nunca se estudian.
- Se guarda la versión que mejor le va a la guardia.
- Cada memoria pesa lo mismo.
- 3 semillas.

**Examen "nunca vista"** (entrena con 2 memorias, examina en la 3ª). AUC:

| Techo de la corrección | noticias | diccionario | relatos |
|---|---|---|---|
| (sin corrección: solo piso) | .866 | .906 | .981 |
| ±3 (primera versión) | .866 | **.867** ❌ | .975 ❌ |
| **±1 (la que quedó)** | **.878** | .903 | .981 |
| ±1 con más freno | .866 | .905 | .981 |
| ±0.5 con más freno | .866 | .906 | .981 |

**Lo que descubrí, dicho claro:**

- Con techo ±3, la corrección aprendía cosas de las memorias de fábrica que **no viajan**: en el
  diccionario empeoraba el piso (.906 → .867). La bajé a **±1**.
- Con ±1 gana un poco en noticias (+.012), pierde un pelo en el diccionario (−.003) y empata en
  relatos. En la memoria de Dennys empata con el piso (.859 = .859).
- O sea: **lo que viaja de una memoria a otra es el instinto (el piso a mano)**. La corrección hoy
  aporta casi nada. Se queda porque es el marco para cuando haya más memorias de fábrica (más
  idiomas, más tipos); con techo ±1 no puede hacer daño grande.

---

## 7. La decisión: umbral vs competencia

La neurona da una **fuerza** de 0 a 1. Probé dos formas de convertirla en "sí/no".

**a) Umbral fijo** (≥ .80 conectar, .50–.80 débil, < .50 no). En las memorias de fábrica nunca vistas
funciona razonable:

| Memoria | Precisión "conectar" | Recall "conectar" | Conecta el |
|---|---|---|---|
| noticias | .80 | .32 | 11.6 % |
| diccionario | .31 | .52 | 5.0 % |
| relatos | .79 | .81 | 6.0 % |

Pero **en la memoria de Dennys el umbral no calza**: marcaría "no" al 94 % de las conexiones que
existen, incluida la mitad (51 %) de las que puso una persona. Cada memoria tiene su propia escala (textos
largos y técnicos, mucho vocabulario compartido). Es la misma lección de la historia de BioRAG: **un
número absoluto no viaja** (pasó con los cortes absolutos del ranking).

**b) Competencia** (como las neuronas de verdad: cada una se queda con sus K entradas más fuertes).
Cada recuerdo conserva sus **K socios de mayor fuerza**, más todo lo que pase de .80. Nunca deja a un
recuerdo solo y no depende de la escala de la memoria.

Memorias de fábrica nunca vistas, K = 10:

| Memoria | Se queda con | Conserva de lo verdadero | Precisión (antes → después) |
|---|---|---|---|
| noticias | 29 % | **61 %** | .28 → .59 (x2.1) |
| diccionario | 30 % | **88 %** | .03 → .09 (x3.0) |
| relatos | 26 % | **97 %** | .06 → .22 (x3.8) |

**La regla que queda es competencia.** El umbral solo sirve para el estado: lo que pasa de .80 llega
como "activa"; lo demás que gana la competencia llega "a prueba".

---

## 8. El examen real: la memoria de Dennys (nunca vista)

Es español, técnico y de otro dominio. La neurona **nunca** la vio: ni para entrenar ni para elegir
pesos. Se leyó desde una copia del snapshot (851 recuerdos activos, 13,342 conexiones directas entre
ellos).

**La verdad que hay:** las **381** conexiones `manual` las unió una persona (o el agente) **a
propósito**. Son la mejor señal de "sí tienen que ver" que existe en la DB. Del resto no se sabe la
verdad: no son basura, solo no están verificadas.

### 8.1 ¿Quién pone primero lo humano? (`resultados/examen_dennys.json`)

| Quién ordena las conexiones | AUC manual vs resto |
|---|---|
| El peso que usa el motor hoy | **.271** (pone lo humano **por debajo**: `sinonimo_explicito`, el tipo más común, pesa .88 de media y los manuales .50) |
| Piso a mano | **.859** |
| Neurona de fábrica | **.859** |

### 8.2 Competencia en la memoria de Dennys

Para comparar justo, el mismo cupo por recuerdo y dos órdenes distintos:

| K por recuerdo | Se queda con | Humanas conservadas (orden neurona) | Humanas conservadas (orden peso de hoy) |
|---|---|---|---|
| 5 | 22 % | **67 %** | 10 % |
| 10 | 41 % | **83 %** | 26 % |
| 20 | 67 % | **94 %** | 49 % |

Con K = 10, qué parte se queda de cada tipo:

| Tipo | Hay | Se queda |
|---|---|---|
| manual | 381 | **82.9 %** |
| sinonimo_explicito | 5,728 | 48.1 % |
| co_nombre | 1,491 | 44.1 % |
| dmn_synthesized | 56 | 37.5 % |
| co_semantica | 1,147 | 33.1 % |
| latente_confirmada | 120 | 32.5 % |
| co_ocurrencia | 2,080 | 29.8 % |
| pmi_hebbiano | 2,317 | 27.7 % |

Esto coincide con la medición D del experimento 10, hecha por otro camino: `manual` era el tipo más
útil y `pmi`/`latente` los menos útiles.

### 8.3 El recuerdo de tu captura del Neuro-Visor

`leccion_discrepancia_busquedas_vocabulario_no_estocasticidad`: 129 conexiones con recuerdos
activos, 4 de ellas humanas.

| Puesto (de 129) | Con | Tipo | Fuerza | ¿Se queda (K = 10)? |
|---|---|---|---|---|
| 1 | teoría_nodos_sinapsis | co_ocurrencia | .99 | sí (conectar) |
| 2 | que_es_nodo_biorag_definicion | **manual** | .58 | sí |
| 3 | fts5-sanitizacion-comillas-dobles-filter | sinonimo_explicito | .40 | sí |
| 4 | leccion_experimento_predicados_vocabulario_normalizado | sinonimo_explicito | .36 | sí |
| 11 | leccion_bbusqueda_bilingue_nodos_tecnicos | **manual** | .12 | sí |
| 63 | athena_leccion_grep_patron_bug_antes_de_cerrar_fix | **manual** | .03 | no |
| 68 | evaluacion_ideas_evolucion_20260805_interferencia_agujeros_permutacion | **manual** | .03 | no |

Se quedarían 56 de 129 (todas pasan a "a prueba" o "activa", nada se borra). Las dos humanas que
pierde son la pista de lo que falta (sección 9): se unieron por **lo que estaba pasando ese día**, no
porque el texto se parezca.

---

## 9. Lo que la neurona todavía NO ve (capas que le faltan al motor)

| Falta | Por qué importa | Qué habría que agregar |
|---|---|---|
| **Momento / episodio** | El cerebro une lo que vives junto. Las 2 humanas perdidas en 8.3 son de ese tipo. En la memoria "relatos" la verdad era justamente "mismo texto", y ahí la neurona lo logra por el texto; en la memoria de Dennys hace falta el **cuándo** | Guardar de forma confiable la sesión/fecha de cada recuerdo y una aguja "se guardaron en el mismo episodio" |
| **Dimensiones (dims)** | El agente ya manda dims al guardar; hoy no entran como aguja | Aguja "comparten dimensión" (necesita medir cuántos recuerdos tienen dims) |
| **Predicados** | "A causa B" no es lo mismo que "A se parece a B" | Capa de predicados (ya listada en el exp 10) |
| **Contradicción** | Dos recuerdos que dicen lo opuesto se parecen mucho en texto | Capa de contradicción |
| **Utilidad** | Si una conexión ayudó a encontrar algo | Ya existe la medición D; falta convertirla en aguja **sin** pedirle trabajo al agente |

Ninguna de estas se agregó todavía: cada una es un cambio al motor y va con su propio permiso y su QA.

---

## 10. Cómo se enchufa en el motor (plan, no hecho)

- **El motor sigue buscando candidatos como hoy.** La neurona solo reemplaza la **regla fija** de los
  puntos donde nace una sinapsis: `auto_vincular`, `vincular_por_sinonimos`, consolidación, ráfaga,
  aprendizaje léxico, sueño de vacíos, DMN e inferencia transitiva. Esos puntos están listados en el
  exp 10.
- **El peso que nace** deja de ser una regla fija por tipo (hoy `sinonimo_explicito` nace con .90 y una manual con .50) y pasa a ser la
  **fuerza** de la neurona. Lo que el agente une a mano no se toca.
- **Estados, nunca borrar:** propuesta → a prueba → activa → consolidada → debilitada → cuarentena.
- **Velocidad:** las agujas usan estadísticas de la memoria (idf, vecinos) que se pueden mantener al
  día cuando entra un recuerdo. La decisión por par es una fórmula de 10 números. La competencia
  ordena como mucho unas decenas de candidatos por recuerdo.
- **Agente y MCP iguales.** No se pide nada nuevo al agente.
- **Hormiguita (Gemini):** la neurona hace su trabajo sin IA externa. Se apaga solo cuando el QA lo
  permita.
- **Antes de cablear:** QA en la copia del snapshot. La tabla de QA es el piso: si un número baja, no
  entra. Ojo: cortar conexiones mecánicas puede bajar el recall aunque sean "menos humanas" (medición
  D: las `sinonimo_explicito` siguen siendo 3 veces mejores que el azar). Por eso el primer cableado
  sería **re-pesar sin cortar** y el corte por competencia vendría después, medido.

---

## 11. Honestidad (lo que este experimento NO prueba)

- Las conexiones que la neurona deja fuera **no** son basura demostrada. La única verdad en la DB son
  las 381 humanas.
- Las memorias de fábrica son en inglés y la de Dennys en español. Que ordene bien en las dos es
  buena señal de que es universal, pero son 4 memorias, no 400.
- El piso del archivo se eligió mirando las 3 memorias de fábrica (números limpios en la sección 5).
- No se midió todavía el efecto en la búsqueda (QA). Hasta que eso pase, **no** digo que mejora el
  sistema; digo que **ordena las conexiones mucho mejor que el peso de hoy**.
- **No es perfecta:** le falta el episodio y las otras capas de la sección 9.

---

## 12. Cómo repetirlo

Hace falta: numpy y nltk (las del motor), los corpus `reuters`, `wordnet` y `brown` de NLTK en
`/tmp/e11/nltk_data`, y una **copia** del snapshot en `/tmp/e11/dennys.db` (nunca la DB real).

```bash
cd "docs/Mi neurona en el sistema/experimento_11_neurona_asociativa"
python fabrica.py      # ~2-4 min: banco, examen nunca vista, fábrica final, examen Dennys
python variantes.py    # ~3 min: piso sin mirar + tamaños de techo
```

| Archivo | Qué es |
|---|---|
| `agujas.py` | Las 10 (+1) agujas universales y la búsqueda de candidatos |
| `corpus.py` | Las memorias con su verdad |
| `neurona_asociativa.py` | Piso, corrección, umbrales, competencia, guardar/cargar |
| `fabrica.py` | Todo el experimento |
| `variantes.py` | Las comprobaciones de honestidad (secciones 5 y 6) |
| `pesos_fabrica.json` | Los pesos de nacimiento (congelados) |
| `resultados/*.json` | Todos los números de este README |

---

## 13. Próximo paso (con tu permiso)

1. Cablear la neurona en **una copia** del motor, primero solo **re-pesando** las sinapsis que nacen
   (sin cortar nada).
2. Medir el QA antes y después en la copia del snapshot. Si algo baja, no entra.
3. Después, medir el corte por competencia (K = 10 / 20).
4. Más adelante: la capa de **episodio** (la que más falta le hace).
