# Experimento 14: la neurona asociativa que solo ORDENA el canal 2

- **Fecha:** 2026-11-25.
- **Rama:** `arena/da3df5df-memorybiorag`.
- **Estado:** medición y diseño. **No cambia el motor, ni la DB viva, ni el snapshot.** El script copia la DB a
  un directorio temporal y la borra al terminar. El snapshot sigue con sha256 `104dd2902aaf…`.
- **Viene de:** [experimento 11](../experimento_11_neurona_asociativa/README.md) (la neurona, cerrada, V2.15 y
  V2.20), [12](../experimento_12_neurona_en_el_motor/README.md) (peso al nacer: revertido) y
  [13](../experimento_13_enlaces_del_agente_y_ruido/README.md) (cortar al nacer o filtrar: baja el recall o deja
  recuerdos sin pistas).

---

## 0. En pocas líneas

- **El lugar:** el canal 2 (`asociaciones_enriquecidas`). Sale **por defecto en cada `recordar`**
  (`asociados=True`, `core/mcp_server/search.py`). Son las pistas que el agente usa para hilar
  (visión P7 y P11).
- **El verbo:** **ordenar**, no filtrar (Constitución, Pilar 12; regla de Dennys del 29-10). Se mantienen los
  mismos 5 lugares y los mismos filtros de hoy, y no se oculta nada. Los `manual` y `manual_v7` siempre van
  primero. Lo que cambia es **cuáles** automáticas ocupan los lugares que quedan.
- **La neurona:** la cerrada de hoy (`core/neurona_asociativa.py`, `asoc-1`, escala 0). No aprende nada de la
  memoria de la persona (decisión del 24-10).
- **Resultado en la DB viva (copia):**
  - mismos lugares (5853) y el mismo único recuerdo sin asociaciones;
  - las automáticas mostradas con fuerza ≥ .6 pasan del **20 % al 62 %**;
  - en el examen tapado, la neurona pone **60–62 %** de los enlaces manuales entre los 5 primeros. El peso de
    hoy pone el **2 %**. La guardia da lo mismo que el estudio.
- **El filtro** (ocultar las automáticas con fuerza < .50) deja a **55** recuerdos sin ninguna pista en la viva
  y a **91** en el snapshot. Choca con el Pilar 12 y **se descarta**.

## 1. Cómo es hoy el canal 2

`core/memory/synapses.py`, `obtener_asociaciones_enriquecidas`:

- trae los vecinos con `peso ≥ .50` y que estén activos;
- los ordena por una **escalera fija de tipos**: `manual` 0, `sinonimo_explicito` 1, `co_semantica` 2,
  `latente_confirmada` 3, `co_ocurrencia` 4, `co_nombre` 5, `legacy_csv` 6, `manual_v7` 7, `test` 8 y el
  resto (`pmi_hebbiano`, `dmn_synthesized`, `rafaga_rememb`…) 9;
- dentro de cada tipo, ordena por peso;
- muestra como máximo 2 `sinonimo_explicito` y 5 vecinos en total.

La escalera **no mira el par**: decide por la etiqueta del tipo, y el peso casi no distingue nada.

### Pesos con que nacen hoy las sinapsis (el «peso a mano», verificado en el código)

| Tipo | Dónde nace | Peso al nacer |
|---|---|---|
| `manual` | `core/memory/synapses.py` `vincular` | **0.5 fijo** |
| `sinonimo_explicito` | `core/sinapsis.py` `vincular_por_sinonimos` | **0.9 fijo**, por `LIKE '%término%'` y sin tope |
| `co_ocurrencia` (al guardar) | `core/sinapsis.py` `auto_vincular` | similitud del par |
| `co_nombre` | ídem | `0.7·solape_nombre + 0.3·peso` |
| `co_semantica` | ídem | `0.6·solape + 0.4·peso` |
| `pmi_hebbiano` | ídem | `0.75·pmi + 0.25·peso`, solo si ≥ .35 |
| `co_ocurrencia` (sesión) | `core/memory/consolidation.py` | `min(.9, .3 + .1·compartidos)` o .4; +.1 / +.05 por repetición |
| `rafaga_rememb` | `core/memory/rafaga.py` | 0.6 fijo |
| `dmn_synthesized` | `core/dmn_engine.py` | 0.30 (`BIORAG_DMN_SINTESIS_PESO`) |

Con estas reglas, un enlace hecho a mano por el agente (0.5) queda **por debajo** de casi cualquier automática.
Por eso, en el examen tapado, el peso de hoy no encuentra los manuales (§3).

## 2. Las tres variantes medidas

Las tres usan los mismos filtros (`peso ≥ .50`, vecino activo, 5 lugares, máximo 2 `sinonimo_explicito`).

| Variante | Qué hace |
|---|---|
| `hoy` | la escalera de §1 |
| `filtro_050` | oculta las automáticas con fuerza < .50 y aplica la escalera al resto (propuesta externa) |
| `ordena` | `manual`/`manual_v7` primero; el resto por la fuerza de la neurona, **incluidos los `sinonimo_explicito`**, con su tope de 2 |

## 3. Resultados

Salidas completas: `resultados/viva_20261125.json` y `resultados/snapshot.json`. Solo contienen totales,
ningún nombre ni texto de recuerdos.

### 3.1 Lo que ve el agente

| | Viva: hoy | Viva: filtro | **Viva: ordena** | Snapshot: hoy | Snapshot: filtro | **Snapshot: ordena** |
|---|---|---|---|---|---|---|
| Lugares mostrados | 5853 | 5220 | **5853** | 3173 | 2587 | **3173** |
| Recuerdos sin ninguna asociación | 1 | **55** | **1** | 10 | **91** | **10** |
| Recuerdos cuya lista cambia | — | 1116 | 1255 | — | 703 | 710 |
| Fuerza mediana de las automáticas | .444 | .604 | **.705** | .452 | .594 | **.619** |
| Automáticas con fuerza ≥ .6 | 20 % | 51 % | **62 %** | 20 % | 49 % | **53 %** |

Viva: 1380 recuerdos con vecinos; mediana de 35 vecinos, p90 de 97 y máximo de 759. Snapshot: 839 recuerdos;
23, 71 y 258.

**Estimación de pistas útiles (con margen ancho).** En la hoja de 100 pares que Dennys marcó a mano
(experimento 11, V2.18), en las sinapsis existentes era relacionado el 93 % de las que tenían fuerza ≥ .6 y el
36 % de las que tenían menos. Aplicando esas proporciones a la viva: hoy ≈ **47 %** de las pistas automáticas
mostradas serían relacionadas, y con `ordena` ≈ **72 %**. Es una estimación: la hoja tiene 100 pares y se hizo
sobre el snapshot.

### 3.2 Examen tapado (enlaces del agente como respuesta correcta, sin feedback)

Se le quita la etiqueta `manual` a todas las sinapsis de cada recuerdo que tenga al menos un manual y más de 5
vecinos. Se cuenta cuántos manuales caen entre los 5 primeros (como máximo 5 por recuerdo). La guardia es el
20 % por `sha256(nombre)[:8] % 5 == 0`, como en la primera neurona. La neurona no aprende, así que la guardia
sirve de control de que no hay sobreajuste por construcción.

| Base | Grupo | Recuerdos | Manuales posibles | Peso de hoy | Escalera por tipo | **Neurona** |
|---|---|---|---|---|---|---|
| Viva | estudio | 570 | 1687 | 2,5 % | 2,1 % | **60,2 %** |
| Viva | guardia | 139 | 386 | 2,1 % | 1,6 % | **62,4 %** |
| Snapshot | estudio | 225 | 561 | 4,3 % | 7,0 % | **61,7 %** |
| Snapshot | guardia | 52 | 133 | 3,8 % | 8,3 % | **60,2 %** |

### 3.3 Costo

- Construir el estado: 0,5 s (snapshot) y 1,2 s (viva).
- Juzgar un par: unos **0,4 ms**.
- Un recuerdo con 759 vecinos costaría unos 0,3 s si se juzgaran todos. **Para el canal 2 hace falta un tope
  fijo** de vecinos juzgados por recuerdo, para que el tiempo sea constante (§4).

## 4. Diseño propuesto (no implementado)

**Piso:**
- `manual`/`manual_v7` siempre primero, en su orden de hoy;
- los mismos filtros y el mismo número de lugares que hoy: nunca se muestran menos pistas;
- si la neurona falla, está apagada o no tiene estado, el canal 2 queda **byte a byte como hoy**.

**Techo:**
- cerrada, escala 0: la corrección aprendida sigue apagada;
- la guardia del 20 % queda como examen permanente (§3.2).

**Guardianes:**
- `BIORAG_NEURONA_ASOCIATIVA=0` la apaga;
- `try/except` por recuerdo, con vuelta al orden de hoy;
- tope fijo de candidatos juzgados por recuerdo (por ejemplo, los 50 primeros por la escalera de hoy), para
  que el tiempo sea constante;
- el estado se construye en la consolidación o el sueño, **nunca dentro de `recordar`**. Hoy `estado()` crea
  tablas y tarda alrededor de 1 s si no hay caché.

**Qué no toca:**
- el ranking ni el canal 1, así que la QA oficial no puede cambiar;
- ninguna sinapsis: no borra, no cambia pesos, no crea;
- tampoco `sinapsis_latentes`.

**Pruebas que harían falta:**
- con el interruptor apagado, el canal 2 es idéntico;
- mismos lugares y mismos recuerdos con asociaciones;
- manuales primero;
- tope de 2 sinónimos;
- la neurona que falla vuelve a hoy;
- el tiempo está acotado con un recuerdo de 1000 vecinos;
- `recordar` no crea tablas.

**Medición de punta a punta:**
- QA oficial antes y después (debe dar idéntica);
- este examen tapado;
- «recuerdos sin asociaciones»;
- un ejercicio de intuición con un agente real (visión §2u).

## 5. Lo que este experimento NO prueba

- Los manuales son una verdad **parcial**: el agente no enlaza todo lo que tiene que ver. Un 60 % no quiere
  decir que el 40 % restante sea un error de la neurona.
- No mide si el agente **hila mejor** con estas pistas. Eso requiere el ejercicio con un agente real.
- La estimación de 47 % → 72 % viene de una hoja de 100 pares, con margen ancho.
- La medición en la viva usa una copia del 2026-11-25. El snapshot permite que cualquiera la repita.

## 6. Cómo repetirlo

```bash
PYTHONHASHSEED=1 python "docs/Mi neurona en el sistema/experimento_14_neurona_ordena_canal2/medir.py" \
    snapshots/qa_escape_qcr_20260811.db /tmp/exp14_snapshot.json
```

Tarda unos 15 s con el snapshot y unos 30 s con la viva. Lee la DB en modo solo lectura, trabaja sobre una
copia temporal y la borra.

## 7. Decisiones de Dennys

- **2026-11-25:** cerrada, que **solo ordena** el canal 2. Los `sinonimo_explicito` **también** los ordena la
  neurona, con el tope de dos por recuerdo, y los manuales siempre primero.
- **En esta etapa solo se documenta.** La implementación de §4 queda pendiente del OK de Dennys.
- **Pendiente:** la implementación de §4 y la «fábrica 2.0» (§8).

## 8. Para después: una neurona cerrada «lo mejor posible» (fábrica 2.0)

La corrección de fábrica quedó apagada (experimento 11, V2.6) porque, con **7 memorias**, lo que ayudaba a una
perjudicaba a otra. Con 7 mundos no se puede separar lo universal de lo propio de cada memoria. Más datos solo
sirven si son **muchos mundos distintos con una verdad del mismo tipo**: enlaces que una persona hizo a mano
entre notas.

**Fuentes candidatas.** Hay que revisar la licencia de cada una, y nada personal entra sin una licencia
abierta explícita.
- bóvedas públicas de notas personales con `[[enlaces]]` (Obsidian, Logseq, Foam, jardines digitales). Son lo
  más parecido a la memoria de un agente;
- enlaces internos de Wikipedia y Wikcionario en varios idiomas;
- preguntas «enlazadas» o «duplicadas» de StackExchange;
- grafos de importaciones en código.

**Reglas:**
- cientos de memorias;
- se deja una memoria fuera y se examina en ella;
- la nueva neurona entra como **retadora** solo si no empeora **ninguna** memoria (la peor manda);
- la memoria de Dennys (snapshot y viva) es el **examen sellado**: nunca se entrena con ella, y la marca a
  superar es el 60–62 % del examen tapado;
- si no gana, manda el piso de hoy.
