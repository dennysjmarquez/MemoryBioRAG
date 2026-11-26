# H2/4b, ciclo 2: propuesta del siguiente protocolo (2026-11-26). SOLO DOCUMENTO, nada implementado

[V] = verificado leyendo el código o en los JSON ya medidos. [D] = deducción o propuesta, sin medir.

## 0. Alcance y salvaguardas
- **Autorizado:** aceptar como diagnóstico sintético los resultados de `../h2_medicion/RESULTADOS.md` (`d7bc5dc`) y
  preparar este documento. Es solo escritura: no autoriza medir ni implementar.
- **Sin cambios** en H2, 4b, el filtro, el motor, el ranking ni los tests. No se usó la DB viva, ni snapshots, ni datos
  privados, ni UD PUD, ni la QA oficial. E3 sigue abierto y no se avanza a E4.
- El residual del buscador (1–7 % del top-5 cambia con el estado de D idéntico, §2.5 de los resultados) queda como
  **«no atribuido»** hasta un ciclo aparte, que necesitaría autorización propia.

## 1. Ajustes aceptados al protocolo v2 (se aplicarán en la próxima medición)
La revisión habló de «ajustes de K2 y K8». Lo que propuse fue K2, la atribución y M3; K8 no tenía ningún ajuste. Los
recojo tal como los propuse; si la revisión quería otro cambio en K8, hace falta precisarlo.

| id | v2 | ciclo 2 | por qué |
|---|---|---|---|
| K2′ | M1, M2 y M3 no peores que en T | M1 y M2 **solo sobre consultas con top-k no vacío en los dos mundos**, más una guardia: el recall del recuerdo de origen en D∪I no baja frente a D | en T los top-5 quedaban vacíos y «vacío = vacío» inflaba M1 y M2 |
| Atribución′ | un cambio es de H2/4b si no aparece en −H2 −4b | además: **si el estado de D es idéntico en D y D∪I (estado e importancia), el cambio se cuenta como del buscador**, aunque la regla de conjuntos diga otra cosa | en −H2 a 1000 la regla atribuía 1/4/1 cambios con D idéntico, por la interacción del buscador con importancias distintas |
| M3′ | consultas con palabras del tema | **más un conjunto de consultas que contienen la entidad puente** del recuerdo de origen | ninguna inserción legítima por puente llegó al top-5; esa parte de M3 no se pudo evaluar |
| Residual | — | se informa siempre en una línea propia, «cambio del sistema no atribuido», y **nunca** se presenta como invariancia del sistema | pedido de la revisión |
| Vacuo | — | todo criterio que se cumpla sin nada que pueda fallar se marca «vacuo» y no cuenta como evidencia | diario a 3000: ningún recuerdo de D activo |

## 2. Qué dejó claro el diagnóstico y qué no [V]
- **Con sueños seguidos, H2 rompe la invariancia por su puesto relativo:** al añadir I0, sin ningún carácter en común,
  duerme a todo D que seguía activo (101→0, 97→0).
- **4b solo actúa cuando la media ronda 0,70.** Entonces I la hace cruzar el umbral, y la importancia de todo D cambia:
  en el mundo de 3000 sin H2, 5 ciclos y suma |Δ| = 155,6.
- **Sin H2 suben las accidentales, pero también los puentes, y los dos vienen sobre todo de `pmi_hebbiano`.** En D∪I′,
  comprimido, en el mundo de 3000 (`pmi_hebbiano_por_verdad` en los JSON):

  | semilla | T: tema / puente / accidental | −H2: tema / puente / accidental | puentes de −H2 que son `pmi_hebbiano` |
  |---|---|---|---|
  | 7 | 50 / 0 / 289 | 49 / 42 / 533 | 42 de 44 |
  | 11 | 16 / 0 / 444 | 14 / 44 / 934 | 44 de 46 |
  | 23 | 7 / 10 / 320 | 5 / 66 / 531 | 66 de 70 |

  Lectura [D]: cortar `pmi_hebbiano` al nacer quitaría casi todos los puentes válidos. Además, «cortar al nacer baja el
  recall» ya está en los callejones sin salida. **El problema de las accidentales es de orden en el canal 2, no de
  existencia de las aristas.** Ese orden es justo el trabajo de la neurona asociativa, que ordena sin borrar.
- **Costo:** sin H2 el sueño cuesta ~2× porque procesa ~5× más activos. No está medido cuánto cuesta por recuerdo activo.
- **No se sabe:** qué pasa con uso real (U0 lo excluye); el porqué del residual del buscador; el comportamiento en CJK
  de las consultas de frase (limitación conocida del canal 1).

## 3. Diseños candidatos para el ciclo 2 (cada uno sería un cambio aislado; ninguno se implementa sin OK)
H2 y 4b siguen siendo controles/hipótesis a evaluar, ni intocables ni retirables sin evidencia.

### 3.1 H2-local: inhibición lateral por vecindad, no global [D]
- **Idea:** la inhibición lateral del cerebro es **local**: una neurona compite con sus vecinas, no con toda la corteza.
  Cada recuerdo compite solo con su vecindad en el grafo, es decir, con los recuerdos unidos a él por aristas.
- **Regla propuesta, sin parámetros nuevos de escala:** para cada recuerdo activo r se calcula la energía de su vecindad
  N(r) ∪ {r}, solo con activos. Si supera `0,8 · |N(r) ∪ {r}|`, se duerme el más débil de esa vecindad (desempate por
  acceso más antiguo), con las mismas exclusiones de inmunes que hoy.
- **Por qué podría servir:** un I sin aristas hacia D no entra en ninguna vecindad de D, así que por construcción no
  cambia nada en D (S1). Un I′ con aristas reales sí compite, y eso es legítimo (puentes y temas).
- **Las decisiones se toman todas sobre la foto anterior** al bloque y se aplican juntas. Así, el orden en que se
  recorren las vecindades no cambia el resultado.
- **Riesgos:**
  - las aristas accidentales meten en la competencia a recuerdos sin relación; hay que medirlo con la verdad de K4;
  - en sueños seguidos casi todas las importancias están cerca de 1,0, así que la condición se cumpliría en casi todas
    las vecindades y podría dormir a un miembro de cada tema por ciclo. Hay que medir cuánto duerme dentro de cada tema;
  - el costo depende del grado medio (≈ 3 en el laboratorio), así que es lineal.

### 3.2 4b-propio: escalado por recuerdo, sin media global [D]
- **Regla propuesta:** cada recuerdo activo no inmune con importancia > 0,70 se multiplica por 0,98 (redondeo a 2
  decimales, como hoy). La decisión depende solo de su propio valor.
- **Por qué:** elimina por construcción los cruces del umbral que provoca I (el fallo medido a 3000). Conserva la
  intención homeostática: lo muy fuerte baja.
- **Riesgo:** es un decaimiento extra para los recuerdos nuevos (1,0 → 0,98 → …). Hay que medir el efecto en el recall y
  en el sueño por peso propio (K6), en los dos relojes.

### 3.3 Las accidentales del canal 2: se ordenan, no se cortan
No se propone ningún cambio en el nacimiento. Si H2-local deja más aristas accidentales que T, la respuesta prevista
es la neurona asociativa (Paso 3), que **ordena** el canal 2 sobre el piso, con los manuales primero, sin borrar.
Mientras no exista, el ciclo 2 solo mide cuánto empeora el canal 2 visible (K5″).

## 4. Brazos y criterios del ciclo 2 (laboratorio sintético, mismo generador y mismas salvaguardas)
- **Brazos:**
  - **T** y **−H2 −4b**, como referencias;
  - **H2-local** (con 4b de hoy);
  - **4b-propio** (con H2 de hoy);
  - **H2-local + 4b-propio**.
  Todos solo en copias del código del sueño dentro del proceso hijo, como en la medición anterior.
- **Mismos mundos:** semillas 7, 11 y 23; 1000 y 3000; comprimido y diario; I0 e I′; K8 desde DB vacía. Además:
  - el conjunto de consultas con la entidad puente (M3′);
  - sinónimos sintéticos en una parte de los recuerdos, para que nazcan `co_semantica` y `sinonimo_explicito`, que hoy
    no aparecen en el laboratorio porque `syn = ""` (§5.3).
- **Criterios:** K1–K9 del v2, con los ajustes del §1 y dos precisiones, para decidir en la revisión:
  - **K5″:** además de la fracción tema+puente del canal 2 visible, se exige que el **número** de pares buenos visibles no
    baje frente a T. En T la fracción era mayor, pero con 4–15× menos pares buenos.
  - **K7′:** se informa el costo por sueño y el costo por recuerdo activo. El umbral sigue siendo ≤ 1,2 × T por sueño,
    salvo que la revisión decida otra cosa.
- **Resultado esperado [D]:** H2-local + 4b-propio cumple K1, K3, K6 y K8 como −H2 −4b, y queda más cerca de T en K4 y
  K7. Si no ocurre, se informa así.

## 5. El tipo de sinapsis como aguja candidata del Paso 3 (no forma parte de este ciclo)
### 5.1 Inventario verificado de los nacimientos (`INSERT INTO sinapsis` en `core/`) [V]
| tipo | dónde nace | qué lo dispara (código) | ¿agnóstico al idioma? | ¿invariante a I? | ¿permitido como entrada? |
|---|---|---|---|---|---|
| `co_ocurrencia` | `core/sinapsis.py:187`; `core/memory/consolidation.py:129` y `:191` | solapamiento de tokens del contenido; ≥ 2 tokens comunes **en la misma sesión** (con cierre triádico); y pares en el mismo mensaje de `comunicaciones` | en parte (tokenizador) | **no**: la variante de sesión depende de con quién llega cada recuerdo | la de contenido, sí; la de sesión y la de mensajes, no (composición de lote / uso) |
| `co_nombre` | `core/sinapsis.py:240` | palabras del **nombre del concepto** con la regex `[a-zA-Záéíóúñ]{4,}`; no son los sustantivos clave | **no**: solo latino, ciego a CJK, del tipo `\w{4,}` | sí | no, mientras sea solo latino |
| `co_semantica` | `core/sinapsis.py:302` | solapamiento léxico en la columna **sinónimos** que escribe el agente; no es SVD ni PPMI | sí | sí | sí, a medir |
| `pmi_hebbiano` | `core/sinapsis.py:367` | NPMI **global** de la base (`pmi_semantico.pares_fuertes`, con caché) y `stemmer_es` | **no**: stemmer español | **no**: estadística global (como «DF sobre la DB») | no como señal directa; ver §5.2 |
| `sinonimo_explicito` | `core/sinapsis.py:504`; `core/lexical_learning.py:317` (`TIPO_SINAPSIS_LEXICO`) | el término coincide con el concepto o con los sinónimos de otro recuerdo | sí | sí | sí, a medir; ya tiene un tope de 2 en el piso |
| `manual` | `core/memory/synapses.py:180` | `vincular` / `vincular_con` del agente | — | — | no hace falta: los manuales son intocables y van primero; además «`manual` no es etiqueta» |
| `dmn_synthesized` | `core/dmn_engine.py:128` y `:339` | síntesis de la DMN, con tope; en el laboratorio nació una al **abrir** el motor | sí | **no** (elige entre activos) | no: está en la lista de no usar (familia DMN) |
| `hipotesis_sueno` | `core/sueno_vacios.py:280` (`SUENO_TIPO`) | hipótesis del sueño, con respaldo PPMI (`afinidad_semantica`) | sí | **no** | no: PPMI quedó fuera de las entradas (25-11) |
| `rafaga_rememb` | `core/memory/rafaga.py:333` | nace **de las consultas** del agente | — | — | no: es señal de uso (U0) |

Más hallazgos de la lectura:
- `latente_confirmada`, `legacy_csv`, `manual_v7` y `test` aparecen en la prioridad del piso
  (`core/memory/synapses.py` L492–503) pero **no tienen ningún nacimiento** en `core/`. Son de importaciones, del
  legado o de tests. `manual_v7` está en `TIPOS_SINAPSIS_AGENTE` (`core/memory/constants.py:362`).
- `core/dmn_reflexion.py:947` **restaura** aristas de la cuarentena con su tipo original (por defecto `pmi_hebbiano`).
  Es una restauración, no un nacimiento.
- **Correcciones al texto de la revisión:**
  - `co_nombre` no usa los sustantivos clave, sino las palabras del nombre, con una regex solo latina;
  - `co_semantica` no es SVD/PPMI, sino solapamiento de sinónimos;
  - el salto 643→1838 es el **total** de aristas en es; `pmi_hebbiano` pasó de 374 a 1576 en es y de 279 a 1845 en en.
- **El tipo ya está previsto como entrada:** el PLAN, L137, lista «el tipo y el peso a mano» entre las entradas de la
  neurona. Lo que falta es medirlo como aguja en la batería del Paso 3 (L160), y eso es lo que se propone.

### 5.2 Cómo se probaría (en el laboratorio sintético, cuando se autorice el Paso 3)
- **AUC por tipo frente a la verdad sintética:** indicador «tipo = X» y, aparte, el one-hot completo, frente a
  tema+puente contra accidental+ajeno. Por escritura, con las 3 semillas.
  - Lo ya medido sugiere que `pmi_hebbiano` es mayoritariamente accidental, pero también la fuente de casi todos los
    puentes (§2). Por eso el tipo solo no basta: hay que ver si, **combinado con rasgos del par** (S, X, G_ciego),
    separa el puente del accidente.
- **Invariancia:** ¿cambia el tipo o la existencia de una arista entre dos recuerdos de D al añadir I0? Se espera que
  sí para `pmi_hebbiano` (NPMI global) y para `co_ocurrencia` de sesión. Si cambia, ese tipo no entra como aguja, o
  entra solo una versión recalculada localmente, sin estadística global.
- **Bucle:** el piso ya ordena por tipo. La neurona tiene que mejorar **sobre el piso**: MRR del orden con la neurona
  frente al MRR del piso, en preguntas donde el tipo no decide solo. Si no, el tipo como entrada solo copia el piso.
- **Agnosticismo:** distribución de tipos por escritura. Un tipo que no puede nacer en CJK (`co_nombre`) sesga a la
  neurona por idioma.
- **Exclusiones previas,** por las reglas ya aprobadas: `rafaga_rememb` (uso), `hipotesis_sueno` (PPMI),
  `dmn_synthesized` (DMN), `manual` (intocable, no etiqueta).

### 5.3 Laguna del laboratorio actual [V]
El generador construye los recuerdos con `syn = ""`, así que en el laboratorio **no nacen** `co_semantica` ni
`sinonimo_explicito`, y `co_nombre` tampoco (nombres numéricos, a propósito). Para medir el tipo como aguja, el mundo
necesita sinónimos sintéticos y nombres con palabras, sin listas de ninguna lengua. Queda anotado para el Paso 3.

## 6. Decisiones que pido en la revisión
1. ¿Se aprueba este documento como protocolo del ciclo 2, con los brazos H2-local y 4b-propio, para medir en el
   laboratorio sintético?
2. ¿Se aceptan K5″ (número de pares buenos visibles además de la fracción) y K7′ (costo por sueño y por recuerdo
   activo, con el umbral actual)?
3. ¿Qué ajuste se quería en K8? No propuse ninguno.
4. ¿Se acepta que el tipo de sinapsis entre en la batería de agujas del Paso 3 con las pruebas del §5.2 y las
   exclusiones del §5.2? Es para más adelante, no para este ciclo.
Nada se mide ni se implementa hasta el OK. E3 sigue abierto; no se avanza a E4.
