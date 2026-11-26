# H2/4b, ciclo 2: propuesta del siguiente protocolo (2026-11-26, rev. 2). SOLO DOCUMENTO, nada implementado

Rev. 2: incorpora las decisiones de la segunda revisión del 26-11, que llegaron vía Dennys. Cambios: K2 rehecho (§1);
el residual del buscador, diagnosticado leyendo el código y con una propuesta de medición estática (§1b); el control
de aristas (§3.3); y el inventario de señales ampliado y verificado (§5.4).

[V] = verificado leyendo el código o en los JSON ya medidos. [D] = deducción o propuesta, sin medir.

## 0. Alcance y salvaguardas
- **Autorizado:** aceptar como diagnóstico sintético los resultados de `../h2_medicion/RESULTADOS.md` (`d7bc5dc`) y
  preparar este documento. Es solo escritura: no autoriza medir ni implementar.
- **Sin cambios** en H2, 4b, el filtro, el motor, el ranking ni los tests. No se usó la DB viva, ni snapshots, ni datos
  privados, ni UD PUD, ni la QA oficial. E3 sigue abierto y no se avanza a E4.
- El residual del buscador (1–7 % del top-5 cambia con el estado de D idéntico, §2.5 de los resultados) queda como
  **«cambio residual no atribuido»**. No se abre un ciclo: el §1b lo diagnostica leyendo el código y propone cómo
  medirlo de forma estática. No se ejecutó nada nuevo.
- La revisión trabajó con la DB de Dennys en modo solo lectura («20 latentes en la UI», columnas reales). Yo no la abrí
  y no uso esas cifras. Todo lo marcado [V] aquí está verificado en el código del repo.

## 1. Ajustes aceptados al protocolo v2 (se aplicarán en la próxima medición)
Decisiones de la revisión: K2 se rehace (mi primera versión filtraba las consultas vacías, y eso podía esconder
justamente las pérdidas de cobertura); la atribución y M3′ se aceptan tal como los propuse. La mención a «K8» de la
primera revisión queda sin efecto: K8 no cambia.

| id | v2 | ciclo 2 | por qué |
|---|---|---|---|
| K2′ (rev. 2) | M1, M2 y M3 no peores que en T | **Conjunto fijo de consultas, sin filtrar.** Se informan por separado: **(i) cobertura**, consultas cuyo top-k (restringido a D) está vacío en D∪I y no en D, que cuentan como pérdida de recall; **(ii) orden**, los cambios de orden (M1/M2) en las consultas con lista en los dos mundos, siempre con su denominador; **(iii) recall del recuerdo de origen**. Ninguna de las tres puede ser peor que en T | en T los top-5 quedaban vacíos y «vacío = vacío» inflaba M1 y M2; filtrar escondería la pérdida |
| Atribución′ | un cambio es de H2/4b si no aparece en −H2 −4b | además: **si el estado de D es idéntico en D y D∪I (estado e importancia), el cambio se cuenta como del buscador**, aunque la regla de conjuntos diga otra cosa | en −H2 a 1000 la regla atribuía 1/4/1 cambios con D idéntico, por la interacción del buscador con importancias distintas |
| M3′ | consultas con palabras del tema | **más un conjunto de consultas que contienen la entidad puente** del recuerdo de origen | ninguna inserción legítima por puente llegó al top-5; esa parte de M3 no se pudo evaluar |
| Residual | — | se informa siempre en una línea propia, «cambio del sistema no atribuido», y **nunca** se presenta como invariancia del sistema | pedido de la revisión |
| Vacuo | — | todo criterio que se cumpla sin nada que pueda fallar se marca «vacuo» y no cuenta como evidencia | diario a 3000: ningún recuerdo de D activo |

## 1b. Residual del buscador: diagnóstico leyendo el código y medición estática propuesta
**Qué está medido [V]:** en −H2 −4b, con el estado de D idéntico (estado e importancia), cambia el top-5 de 5, 36 y 26
consultas de 480 a 1000, y de 8, 11 y 11 a 3000. Todas son consultas latinas.

**¿Es IDF/BM25 global? En el uso normal del motor, no [V].** El buscador ya tiene un diseño estable al crecimiento:
- `core/memory/schema.py` L801–858: la primera vez que se abre una base con filas se fija
  `search_baseline_rowid = MAX(rowid)`, que se guarda en la tabla `data`; lo mismo con `search_baseline_sinapsis_rowid`
  para las aristas;
- `core/memory/growth_stable_fts.py` L61–: índices FTS **inmutables** (trigram y unicode61) para esa cohorte;
- `core/memory/search.py` L441–458: BM25 de FTS5 con pesos 5/1/2/4 **sobre ese índice congelado**; L1916–1928:
  normalización min-max solo con la cohorte. Los recuerdos posteriores reciben un score local que depende solo de la
  consulta y del recuerdo.
En una base real, por tanto, N, df y avgdl de los recuerdos viejos no cambian cuando llegan recuerdos nuevos.

**Pero el laboratorio lo esquivó sin querer.** Lectura de `../h2_medicion/laboratorio_h2.py` [V], con la consecuencia
marcada [D]:
- `hijo_construir` abre el motor sobre una base **vacía** (L172, `c16.abrir`), y con la tabla vacía no se guarda
  ningún corte (`schema.py` L833–835);
- D e I se insertan en el mismo proceso, sin reabrir;
- `hijo_medir` (L249–250) abre un motor nuevo sobre la copia, y **es entonces** cuando se fija el corte, con el
  `MAX(rowid)` de todo D∪I.
- **Hipótesis H-R1 [D]:** en los mundos D∪I la cohorte congelada **incluye a I**, así que N y avgdl (y df, en I1)
  son distintos que en el mundo D. Eso mueve el BM25 de los recuerdos de D y con él el orden. Si se confirma, el
  residual es un **artefacto del protocolo** (I quedó dentro de la cohorte de referencia), no una propiedad del motor
  en el uso normal. No explica por sí sola por qué solo cambian las consultas latinas; eso también se mide.

**Otros dos contribuyentes posibles, leyendo el código [V], con su efecto marcado [D]:**
- **H-R2:** los vectores PPMI+SVD (señal #13, `PPMI_VECTOR_WEIGHT = 0.15` por defecto, `constants.py` L208) se
  recalculan sobre **todo** el corpus en el reindexado completo periódico del sueño (`consolidation.py` L772–790;
  `ppmi_vectorizer.py` L101 `np.linalg.svd`, L298). Con I dentro del corpus cambia la base del SVD, y con ella los
  vectores de D, `_ppmi_vq` y el campo potencial PPMI (`search.py` L2170–2177, `CAMPO_K = 64`).
- **H-R3:** el score latente (`search.py` L2193–2204, `MAX(peso_atenuado)` sobre `sinapsis_latentes`) se recalcula
  globalmente en cada sueño. Probablemente está vacío en el laboratorio, porque los caminos latentes solo pasan por
  aristas `manual`/`manual_v7`/`sinonimo_explicito`/`test` o `co_semantica`/`co_nombre` (`inferencia_transitiva.py`
  L139–146), y esas no nacen en el mundo sintético.

**Medición estática propuesta (no ejecutada; en el laboratorio sintético, con el brazo −H2 −4b y las mismas semillas):**
1. **R-E0, solo lectura de bases ya construidas:** comparar entre la base D y la D∪I el valor de
   `data.search_baseline_rowid`, el número de filas de `biorag_largo_plazo_fts_ref`, el hash de `nodos.vector` de los
   conceptos de D y el número de filas de `sinapsis_latentes`. No se busca nada ni se duerme.
2. **R-E1, factorial 2×2 sin cambiar el código:**
   - factor A: dónde se fija el corte. Puede ser **tras insertar D** (abrir y cerrar el motor una vez antes de I, que
     es como vive una base real) o en la medición, como hasta ahora;
   - factor B: `BIORAG_PPMI_WEIGHT` = 0,15 o 0, con una variable de entorno.
   Se mide el top-5 de las 480 consultas.
   **Predicción [D]:** si H-R1 es la causa, el residual cae a ~0 con «corte tras D».
3. **R-E2,** solo si R-E1 no lo cierra: descomponer las 9 señales del score en las consultas que cambian,
   instrumentando el buscador **solo en la copia del proceso hijo**.
4. **Consecuencia para el protocolo [D]:** si H-R1 se confirma, el protocolo del ciclo 2 fija el corte tras D. Es un
   cambio del laboratorio, no del motor. El (b) de la medición anterior se reinterpretaría. El (a) y los hallazgos de
   H2/4b no cambian, porque se basan en el estado de `largo_plazo`, no en el buscador.

**Resultado de R-E0/R-E1 (26-11; detalle en `../h2_medicion/RESULTADOS_RESIDUAL.md`) [V]:**
- **H-R1 refutada como causa principal:** con el corte fijado tras D, el residual sigue (19/28/20 y 7/7/28).
- **El residual vive en la familia PPMI:** con `BIORAG_PPMI_WEIGHT = 0` cae a 1/3/1 y 0/0/0 (con el corte tras D,
  0/1/0 y 0/0/0).
- El IDF global de `vector_query` (`n_docs`) existe, pero no explica las consultas que cambian.
- El componente exacto queda sin identificar; R-E2 se propone para cerrarlo y necesita OK.
- **Propuesta para el ciclo 2:** medir con PPMI 0,15 y 0 (control) y con el corte fijado tras D.

**R-E2 (26-11) lo cierra [V]:** el residual es la **Neurona 1**. En D asciende un campeón y en D∪I0 no, y eso
explica 35 de las 36 consultas. La que queda es BM25, por el corte. El PPMI la apagaba sin querer, porque cambia su
huella del motor. **Ajuste de control:**
- control con `BIORAG_NEURONA=0` en toda la corrida, en lugar de PPMI 0;
- corte fijado tras D;
- registro del estado de la neurona por mundo.
Detalle en `../h2_medicion/RESULTADOS_RESIDUAL.md` §7–§8.

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

### 3.3 Control de aristas: primero se mide, y el corte entra solo como brazo vigilado
La evidencia está en contra de cortar al nacer: casi todos los puentes válidos son `pmi_hebbiano` (§2), y «cortar al
nacer baja el recall» ya está en los callejones sin salida. Por eso el control de aristas tiene dos partes:
- **C-medida (siempre):** por recuerdo y por tipo se cuentan las aristas temáticas, puente, accidentales y ajenas, al
  nacer y tras cada sueño. Las accidentales se tratan en el canal 2 **ordenando, no borrando**: es el trabajo de la
  neurona asociativa del Paso 3, sobre el piso y con los manuales primero.
- **C-tope (brazo opcional, a decidir en la revisión) [D]:** un presupuesto por recuerdo de aristas automáticas al
  nacer, con el mismo número N para todos y nunca aplicado a los tipos del agente. Se queda con las N de mayor peso.
  Como el peso de `pmi_hebbiano` es NPMI **global**, el tope hereda esa falta de invariancia.
  **Predicción:** baja las accidentales, pero también los puentes. Falla K4 si los puentes caen por debajo de T.

## 4. Brazos y criterios del ciclo 2 (laboratorio sintético, mismo generador y mismas salvaguardas)
- **Brazos:**
  - **T** y **−H2 −4b**, como referencias;
  - **H2-local** (con 4b de hoy);
  - **4b-propio** (con H2 de hoy);
  - **H2-local + 4b-propio**;
  - **C-tope**, si la revisión lo aprueba (§3.3).
- **Corte de la cohorte del buscador fijado tras D** si R-E1 confirma H-R1 (§1b); si no, se mide igual que antes y el
  residual se informa aparte.
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

### 5.4 Inventario ampliado de señales candidatas (rev. 2, segunda revisión del 26-11, verificado en el código)
Reglas de entrada (PLAN §5): **sin idioma**, **invariante** (F(D,q) = F(D∪I,q)), **sin bucle** (no lee el grafo
que juzga) y **costo fijo**. Además rigen las reglas aprobadas: PPMI/LSA/SDM fuera de las entradas, nada de uso (U0),
la hormiguita no es verdad y ni `manual` ni ninguna declaración del agente es etiqueta. «Fuera» significa fuera como
entrada del Paso 3, no del motor.

| fuente / señal | qué es [V] | sin idioma | invariante | sin bucle | veredicto propuesto |
|---|---|---|---|---|---|
| **Tipo de la arista** (one-hot) y **prioridad ordinal** (manual = 0 … pmi = 9, `synapses.py` L492–503 y L515–527) | regla de nacimiento; el canal 2 ya ordena por él | sí | **depende del tipo**: no para `pmi_hebbiano` (NPMI global) ni para `co_ocurrencia` de sesión | lee el propio grafo; aceptable porque la neurona no escribe aristas, pero **tiene que superar al piso** | **entra (decisión del 26-11)**, con invariancia medida por tipo y la prueba de bucle del §5.2 |
| `sinapsis.peso` | lo fija el nacimiento y lo modifican LTP/LTD en el sueño | sí | no para `pmi_hebbiano` | igual que el tipo | entrada vigilada, junto con el tipo |
| **Latente L1:** ¿existe A→B? | `inferencia_transitiva.py` L85–: CTE de 2 saltos **solo** por aristas del agente o `co_semantica`/`co_nombre` (L139–146); se recalcula **entera** en cada sueño (`consolidation.py` L433–434; `DELETE` en L116); tope de 20 por nodo según el peso final (L222–235) | sí | **no por construcción**: el tope de 20 hace competir a las latentes entre sí y el filtro exige dimensión o PMI global; con I1 un camino A→X→B por X ∈ I es un puente legítimo | **lee el grafo que juzga** si el camino usa `co_semantica`/`co_nombre`; si usa solo aristas del agente, no (los manuales no se juzgan) | **candidata solo en una versión local recalculada:** camino de 2 saltos por aristas del agente, sin PMI ni tope; la tabla tal cual, no |
| Latente L2: `peso_atenuado` | `peso_max · (1 + 0,5·pmi + 0,1·dim) · madurez(pmi)` (L196–209) | sí | no (PMI global, tope) | — | **fuera:** contiene PMI (regla del 25-11) |
| Latente L3: `pmi_score` | `score_pmi_nodo` (NPMI global, `pmi_semantico.py` L246) | **no** (`stemmer_es`) | no | — | **fuera** (PPMI/PMI, 25-11) |
| Latente L4: `tiene_dim_comun` | JOIN de `largo_plazo_dimensiones` **sin filtrar `auto_generada`** (L64–69) | sí | sí | **no**: incluye dimensiones autogeneradas (bucle del PLAN §6) | **fuera tal cual**; lo útil ya está en S (Jaccard de dimensiones sin `auto_generada`) |
| **Bridges** (`concept_hub_bridges`) | ya figura en el PLAN §5 como aguja **B**; no es nueva. Hay **5 por hub, exactamente uno por ángulo**, validados (`concept_hub.py` L320–360); `weight` 1,0 por defecto; los escribe el agente con `aprender` | sí, si se compara por unidades Unicode | sí: se escriben al aprender y no dependen de I | sí: no los escribe ni la neurona ni el buscador | **candidata, como en el PLAN.** Señal útil: coincidencia de los bridges de B con el texto o los bridges de A, y **qué ángulo** coincide. El ángulo solo no informa (siempre están los 5) y `weight` es casi constante. Es una declaración del agente: entrada, nunca verdad. **No medible en el sintético** salvo con bridges escritos a ciegas (si los escribe quien conoce la verdad, se mide su autor) |
| ¿A y B comparten `hub_id`? | pertenencia al mismo hub | sí | sí | sí | fuera, como ya estaba (casi nunca ocurre) |
| **¿Estuvo en cuarentena?** (`sinapsis_cuarentena`) | la decide **la hormiguita** (`dmn_reflexion.py` L868–912; origen `ciclo_daemon`/`on_demand`/`gemini`); se purga a los 30 días **por reloj de pared** (trigger en `schema.py` L711–716); `_restaurar_cuarentena` devuelve aristas | sí | **no**: depende de un LLM externo y de la hora real | — | **fuera:** la hormiguita no es verdad, sin APIs externas, no reproducible; en el sintético siempre valdría 0 |
| `peso_sinaptico` y `estado` del vecino | los cambian H2, 4b y LTD | sí | **no** | — | **fuera** (de acuerdo con la revisión) |
| `exitos_dopamina` / `fallos_dopamina` | historial de uso | sí | no | — | **fuera** (U0) |
| `valencia_somatica` | 1,0 si la categoría es Principle/Protocol (`ingest.py` L58); la reescribe la hormiguita (`dmn_reflexion.py` L836) | sí | no (hormiguita) | — | **fuera** (la parte fiable equivale a la categoría) |
| Categoría compartida | la declara el agente | sí | sí | sí | como en el PLAN: débil (11 categorías); en el sintético siempre es «General» |
| `sustantivos_clave` | **los escribe el agente**, obligatorio al aprender (`mcp_server/prompt.py` L136); S y X los comparan por Unicode NFKC casefold, sin stemmer (PLAN §5) | **sí** como campo | sí | sí | **en conflicto, pido decisión (§6):** la revisión los excluye como «atados al español», pero lo que está atado al español es `stemmer_es`, no el campo. Excluir el campo **eliminaría S (AUC 0,822) y X (S + X = 0,85 en los 4 idiomas)**. Propuesta: excluir solo las derivaciones con stemmer |
| Predicados SRL | extractor en español | no | — | — | fuera, como ya estaba |
| ADN / SDM | firma SDM y cromosomas sobre PPMI/SVD; apagado por defecto (`memory_store.py` L193–195; PLAN L73, L97–98) | no | no | **no** | **fuera.** Corrección a la revisión: **no es S_idf.** S_idf es un IDF congelado de `db/hebbian_clusters.json` y sigue «por medir»; el «AUC ~0,65» corresponde a X, no al ADN |
| Hipótesis teleológicas | tabla `hipotesis_teleologicas` (no la verifiqué más allá del nombre) | — | — | — | fuera (de acuerdo: escasas) |
| `ultimo_uso` / Δt | uso o tiempo | sí | no fiable (U0) | — | fuera en esta etapa (de acuerdo) |
| G_ciego, S, S_idf, X, K, R | PLAN §5 y §9.0b | — | — | — | sin cambios; siguen siendo la batería base |

**Correcciones a lo reenviado:**
- «8 señales nuevas»: los bridges **ya estaban** en el PLAN (aguja B). La letra «B» del PLAN son los bridges, no
  «bigramas CJK».
- «Latentes: invariantes por construcción y sin bucle, por ser caché»: **no.** Se recalculan enteras en cada sueño
  sobre el grafo y el PMI globales, con tope por nodo. Ser una caché no evita el bucle: el bucle está en qué leen.
- «ADN = S_idf, AUC ~0,65»: no (ver la tabla).
- `latente_confirmada` no nace en ningún sitio de `core/`: solo aparece en la tabla de prioridades.

**Laguna del sintético [V]:** latentes, bridges, cuarentena, categoría y sinónimos están vacíos o son constantes en
el laboratorio actual. Para medir L1 local y los bridges hace falta un mundo con aristas del agente y bridges
**escritos a ciegas**. Queda para el diseño del Paso 3.

## 6. Decisiones que pido en la revisión
1. ¿Se aprueba este documento (rev. 2) como protocolo del ciclo 2? Brazos: T, −H2 −4b, H2-local, 4b-propio y los dos
   juntos; C-tope, opcional.
2. ¿Se aprueba R-E0/R-E1 (§1b) como la medición estática del residual, previa al ciclo 2? Es sintética, sin cambiar
   el código, y solo cambia cuándo se fija el corte y la variable `BIORAG_PPMI_WEIGHT`.
3. ¿Se aceptan K5″ (además de la fracción, que no baje el número de pares buenos visibles) y K7′ (costo por sueño y
   por recuerdo activo, con el umbral actual)?
4. **`sustantivos_clave`:** ¿se excluye el campo, con lo que caen S y X, o solo sus derivaciones con stemmer, que es
   lo que recomiendo?
5. ¿Se acepta el veredicto del §5.4: latentes solo en versión local por aristas del agente, bridges como aguja B ya
   prevista, y cuarentena fuera?
Nada se mide ni se implementa hasta el OK. E3 sigue abierto; no se avanza a E4.
