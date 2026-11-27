# Paso 3: protocolo de la batería de agujas de la neurona sináptica (solo documento, para revisión)

> **Estado:** propuesta. **No se ha medido nada.** Pedido por Dennys el 26-11: «antes de medir nada, entrégame solo
> el documento del protocolo del Paso 3».
> **Límites vigentes:**
> - no se tocan `core/`, `tests/`, la DB viva, snapshots, UD PUD ni la QA oficial;
> - CPU local, `numpy` puro, sin APIs externas;
> - E3 sigue abierta; no se avanza a E4.
>
> **Para quien llega sin contexto:**
> - La neurona sináptica ordenará el **canal 2**, los vecinos que el grafo de sinapsis le da a un recuerdo A. Nunca
>   borra ni oculta ninguno (Pilar 12).
> - Para ordenar necesita **agujas**: rasgos del par (A, vecino B) que digan si el enlace une recuerdos de verdad
>   relacionados (tema o puente) o es accidental.
> - El Paso 3 decide **qué agujas pueden entrar**, midiendo cada una por separado y con criterios fijados antes. El
>   Paso 4 entrena la neurona con las que entren.

## 1. Reglas de entrada (PLAN §5, sin cambios)

Una aguja entra solo si cumple las cinco:
1. **Sin idioma:** sin listas de palabras, sin `\w{4,}`, sin stemmer. Se compara por unidades Unicode (NFKC +
   casefold; bigramas en escrituras sin espacios).
2. **Invariante:** F(D, q) = F(D ∪ I0, q), con I0 sin relación con D.
3. **Sin bucle:** no lee el grafo que juzga. Si lo lee, como el tipo, tiene que superar al piso (C3.5).
4. **Costo fijo** por par.
5. **Aporte propio:** añade algo que el piso (el orden a mano de hoy) no tenga ya.

## 2. Inventario de agujas candidatas

| id | aguja | definición operativa | fuente | notas |
|---|---|---|---|---|
| **S** | estructura declarada compartida | Jaccard de dimensiones `|D_A ∩ D_B| / |D_A ∪ D_B|`, separado por eje (temáticos: dominio, entidad, intención, cualia; de tono: cualidad, emoción), **excluyendo `auto_generada = 1`**; más el número de `sustantivos_clave` compartidos por igualdad exacta normalizada | lo declara el agente | E1: AUC 0,822 en los 4 idiomas (mundo espejo; ver §4 sobre el riesgo de autoría) |
| **S_idf** | S pesada por rareza | cada dimensión compartida pesa por un IDF **congelado** (`db/hebbian_clusters.json`), nunca recalculado sobre la base | referencia fija | por medir |
| **X** | cobertura cruzada | fracción de los `sustantivos_clave` de A que aparecen como subcadena Unicode en el texto de B, y al revés. Se informan `min` (reciprocidad) y `max`, y por separado el campo donde coincide (concepto, sustantivos, contenido) | texto + declaración | piloto: AUC 0,62–0,65; S + X = 0,85 |
| **B** | bridges | flag: algún bridge de B coincide (por unidades Unicode) con el texto o con los bridges de A; `weight` del bridge que coincide; ángulo que coincide | `concept_hub_bridges` | solo si el mundo tiene bridges **escritos a ciegas** (§4) |
| **K** | competencia dentro del nodo | puesto de B entre los vecinos de A según S y X (rasgos invariantes), normalizado por el número de vecinos | local al nodo | solo sobre rasgos invariantes |
| **G_ciego** | engrama ciego | `|TopK_ciego(A) ∩ TopK_ciego(B)|`, buscando en la **copia limpia** (sin sinapsis), con `log1p` | buscador | hereda la invariancia del buscador; ver §6 |
| **R** | resonancia | ¿la pista de B, buscada en la copia limpia, devuelve A en el top-k? | buscador | solo de referencia frente a G_ciego; ciego a CJK si se usa la búsqueda vieja |
| **T1** | tipo de la arista | one-hot del tipo de nacimiento | regla de nacimiento | **entra por decisión del 26-11**, con invariancia medida por tipo (§5.2) |
| **T2** | prioridad ordinal | `manual` = 0 … `pmi_hebbiano` = 9 (`core/memory/synapses.py` L493–504; `co_ocurrencia` = 4, `co_nombre` = 5) | tabla del piso | va con T1 |
| **L1-local** | latente local | ¿existe un camino A→X→B de 2 saltos **solo por aristas del agente** (`manual`, `vincular_con`)? Sin PMI ni tope por nodo; se recalcula para el par | grafo del agente | la tabla `sinapsis_latentes` tal cual queda fuera (§3) |
| Cat | categoría compartida | igualdad de categoría | agente | débil (11 categorías); se informa, no se espera que entre sola |

## 3. Excluidas de antemano (con la razón)

| excluida | razón |
|---|---|
| `peso_sinaptico` y `estado` del **vecino** | los cambian H2, 4b y LTD, que con T **no son invariantes** (ciclo 2). Se reconsidera solo si el sueño cambia (ticket de invariancia del sueño) |
| valor NPMI de `pmi_hebbiano`, `pmi_score` de latentes, regla `co_nombre`, cualquier derivación con `stemmer_es` | estadística global, o atados al latín/español |
| Δt, `ultimo_uso`, dopamina | tiempo y uso (U0, norma 4) |
| `sinapsis_cuarentena` | la decide la hormiguita (LLM externo, reloj de pared); la hormiguita no es verdad |
| PPMI, LSA, SDM, ADN | regla del 25-11; además F-B (`h2_ciclo2/HALLAZGOS_DEL_MOTOR_K8.md`) |
| grado, `asociaciones` CSV, `grupos_semanticos`, SRL, `lexico_aprendido`, `hub_id`, `dmn_*`, valencia | bucle, idioma, uso o falta de procedencia (PLAN §5–§6; propuesta del ciclo 2, §5.4) |
| dimensiones `auto_generada = 1` | nacen del grafo de sinapsis: bucle (PLAN §6) |

**Punto a confirmar:** T1 contiene la **categoría** `pmi_hebbiano` (que exista una arista de ese tipo), no su valor
NPMI. Si el indicador «tipo = `pmi_hebbiano`» no es invariante (§5.2), no entra; como mucho, una versión recalculada
localmente.

## 4. Mundos y verdad: dos capas, porque una sola no basta

**El riesgo principal (PLAN §9):** si quien escribe los textos o las declaraciones conoce los pares, cualquier aguja
textual mide al autor, no la relación. Ya pasó en el exp. 16 (AUC 1,000 falso). El mundo sintético del laboratorio
H2 tiene el mismo defecto: cada tema tiene su vocabulario propio, así que X y S lo separarían por construcción.

### Capa L, de limpieza (autorizable ya: sintética)
- **Mundo:** `h2_medicion/mundo_sintetico.py` con las ampliaciones del ciclo 2 (sinónimos sintéticos, consultas
  puente), más:
  - nombres con palabras inventadas, para que pueda nacer `co_nombre`;
  - aristas del agente sintéticas, para L1-local;
  - recuerdos inmunes (laguna del ciclo 2).
- **Tamaño y semillas:** 7, 11 y 23 · \|D\| = 800 y 2400 · D, D∪I0 y D∪I1 · los 4 escritos (lat_a, lat_b, han, jpn).
- **Mide:** invariancia, bucle, costo, que la aguja no sea constante por escritura, y su distribución por tipo de
  arista.
- **No mide valor.** Las AUC de esta capa se informan marcadas «con filtración léxica por construcción» y **no cuentan
  para admitir** ninguna aguja.

### Capa V, de valor (necesita autorización de Dennys)
- **Corpus:** públicos y reales, del orden de varios miles de recuerdos en es, en, zh y ja, con documentos y párrafos
  (PLAN §9.0c). Candidatos: treebanks de UD distintos de PUD (GSD zh/ja, AnCora o GSD es, GUM o EWT en). **La lista
  exacta y sus licencias se fijan antes de medir; UD PUD sigue fuera.**
- **Verdad:**
  - positivo = los dos recuerdos son del mismo documento (o de documentos enlazados por una entidad común poco
    frecuente, que hace de puente);
  - negativo = documentos distintos.
  - Se informan aparte los **negativos duros** (comparten unidades de superficie pero no documento), que son los que la
    neurona tiene que bajar.
- **Población evaluada:** sobre todo los pares que **ya tienen una arista** en el motor, porque eso es lo que ordena el
  canal 2. Como dato secundario, pares al azar.
- **Partición:** por documento, en 3 vías: Estudio, Validación y **Guardia sellada del 20 %** (hash del recuerdo B).
  **El Paso 3 no toca la guardia.**
- **Declaraciones a ciegas** (dimensiones, `sustantivos_clave`, 5 bridges), porque los corpus públicos no las traen:
  - el escritor ve **un recuerdo cada vez**, en orden barajado, sin id de documento ni vecinos, y sigue el contrato de
    `aprender`;
  - nunca ve la verdad. No puedo ser yo, porque conozco el corpus y los pares. Propuesta: el agente local de Dennys en
    una sesión aislada, que es lo más parecido al uso real.
  - **Escritor mecánico de control:** una regla local por recuerdo, sin listas (las unidades más repetidas dentro del
    propio texto). Separa lo que aporta el conocimiento del agente de la simple coincidencia de superficie.
- **Alternativa o complemento (decisión de Dennys):** una muestra de su propia memoria con enlaces `manual` ocultos
  como respuesta conocida, muestreada al azar. Hoy está prohibida (sin DB viva).

## 5. Criterios, fijados antes de medir

Por aguja, por escritura y por semilla. Son propuestas: se aprueban o se cambian **antes** de medir; después no se
mueven.

| id | criterio | umbral propuesto | capa |
|---|---|---|---|
| C3.1 | **Invariancia:** valor idéntico para cada par de D en D y en D∪I0 (y en D∪I1 para pares con los dos extremos en D) | agujas locales (S, S_idf, X, B, K, L1-local, Cat): **100 %**; las del buscador (G_ciego, R): **≥ 98 %**, con `BIORAG_NEURONA=0` y PPMI apagado en la copia; T1/T2: por tipo (§5.2) | L |
| C3.2 | **Bucle:** inyección de sinapsis falsas (C1.2b) y de dimensiones emergentes falsas + CSV `asociaciones` falso (C1.2c) | valores **idénticos 100 %** en las agujas que no deben leer el grafo; T1, T2 y L1-local van por C3.5 | L |
| C3.3 | **Sin idioma:** AUC (verdad: tema+puente frente a accidental+ajeno) | en **cada** idioma, AUC ≥ 0,60 con IC95 inferior > 0,50 (bootstrap por documento, 2000 remuestreos, semilla fija); diferencia máx − mín ≤ 0,10 | V |
| C3.4 | **Costo fijo** | tiempo por par constante entre \|D\| = 800 y 2400 (± 20 %), con K fijo por nodo | L |
| C3.5 | **Aporte sobre el piso** (listwise dentro de cada A) | MRR de los vecinos verdaderos en el canal 2 de A: piso + aguja > piso, con IC95 de la diferencia pareada > 0 **en cada idioma**, en Validación. La combinación es una regresión logística por nodo ajustada solo en Estudio | V |
| C3.6 | **Aporte único sobre el canal 1** (solo G_ciego y R) | AUC parcial de G_ciego controlando por R > 0 con IC95 > 0 | V |
| C3.7 | **Hubs** | correlación de Spearman entre la aguja y el grado de A ≤ 0,3 (el grado se mide, no se usa) | L y V |
| C3.8 | **Vacuo** | una aguja constante en un idioma o en un mundo se marca «no medible», nunca «cumplido» | L y V |

### 5.2 El tipo de arista (T1/T2)
- Invariancia **por tipo**: ¿cambia la existencia o el tipo de una arista entre dos recuerdos de D al añadir I0?
  - Los tipos con invariancia ≥ 98 % entran como indicador.
  - Los demás (se espera `pmi_hebbiano` y `co_ocurrencia` de sesión) no entran, o entran solo recalculados en local.
- Bucle: T1/T2 **son** el piso. Solo cuentan si la combinación con S, X y G_ciego supera al piso (C3.5) en preguntas
  donde el tipo no decide solo.
- Sin idioma: distribución de tipos por escritura. Un tipo que no puede nacer en CJK (`co_nombre`, `pmi_hebbiano`) se
  marca, porque sesgaría a la neurona por idioma (PLAN §9.3).

**Admisión:**
- **entra** la aguja que cumple C3.1–C3.5, C3.7 y C3.8 (y C3.6 si pasa por el buscador);
- **queda «limpia, sin valor demostrado»** la que cumple solo la capa L;
- **queda fuera**, en otro caso.

## 6. Condiciones técnicas descubiertas en los ciclos anteriores

- **Copia limpia para G_ciego y R** (PROTOCOLO_V3 §2, A4):
  - sin `sinapsis` ni `sinapsis_latentes`; `asociaciones` vacía; sin dimensiones `auto_generada = 1`;
  - `ignore_peso_sinaptico=True`;
  - **además, `BIORAG_NEURONA=0`**: la Neurona 1 cambia el top-k al añadir I (R-E2 y ciclo 2).
- **F-A y F-B** (`h2_ciclo2/HALLAZGOS_DEL_MOTOR_K8.md`): G_ciego y R se miden con el motor tal cual, con esos fallos
  anotados. Si se aprueban sus arreglos, se repiten.
- **K8 medido:** las corridas trazan las excepciones dentro del sueño y del buscador. Si aparece una excepción nueva,
  se informa.
- **Repaso con `profundidad="profundo"`** (A1): también se repasan los recuerdos dormidos.

## 7. Nota para el Paso 4: la invariancia de una neurona que aprende (decisión pendiente de Dennys)

- **El hecho:** la Neurona 1 no cambia el estado, pero su campeón aprendido de D∪I0 **reordena distinto** que el
  aprendido de D (residual de 32 frente a 6 en el ciclo 2).
- **Cualquier neurona que aprenda de la base de cada usuario hereda el problema.**
- Hay dos invariancias distintas, y conviene separarlas:

| | qué fija | ¿se puede garantizar? |
|---|---|---|
| **I-func** (funcional) | con los **mismos pesos**, el puntaje de un par de D es idéntico en D y en D∪I0 | sí, por construcción, si todas las entradas cumplen C3.1. Se exige al 100 % |
| **I-apr** (de aprendizaje) | los pesos aprendidos de D∪I0 ordenan los vecinos de D igual que los aprendidos de D | **no por construcción**, si se aprende de la base. Hay que medirla y acotarla |

- **Opciones para el Paso 4:**
  - **(a) Pesos congelados, entrenados solo con los corpus públicos de la capa V** (como el IDF congelado de S_idf).
    I-apr se cumple por construcción: los pesos no dependen de la base del usuario. Coste: no se adapta a cada
    usuario. **Lo recomiendo como base.**
  - **(b) Adaptación en el sueño** sobre la base del usuario, solo como retador del campeón congelado (a), con un tope
    de I-apr fijado antes. Por ejemplo, ≥ 98 % de los nodos de D conservan el orden relativo de sus vecinos de D tras
    reentrenar con I0.
    - Esto **no** es invariancia estricta. Es una tolerancia que Dennys tendría que aprobar como excepción explícita
      a la NORMA MÁXIMA, o rechazar.
- **Aparte, el canal 2 de A cambia sí o sí** si I0 trae una arista accidental hacia A: aparece un vecino nuevo, con o
  sin neurona.
  - Lo que se puede exigir es que el **orden relativo de los vecinos de D** no cambie (M2), y llamarlo así, **no**
    «invariancia del sistema».

## 8. Lo que pido decidir antes de medir

1. ¿Se aprueban las reglas, el inventario (§2), las exclusiones (§3) y los umbrales C3.1–C3.8?
2. **Capa V:** ¿qué corpus públicos (con sus licencias) y quién escribe las declaraciones a ciegas? ¿Se autoriza
   también una muestra de la memoria propia con `manual` ocultos?
3. Confirmar el punto de §3: T1 lleva la categoría `pmi_hebbiano`, no su valor.
4. **Paso 4:** ¿pesos congelados (a), o (a) + adaptación acotada (b)? ¿La NORMA MÁXIMA se aplica a I-func, a I-apr o a
   las dos?
5. ¿Se abren aparte los ciclos de arreglo de F-A y F-B? Tocan el ranking, así que van uno a uno, con QA.

Mientras no haya respuesta, solo se puede ejecutar la **capa L**, y únicamente con autorización.

## 9. Decisiones del 27-11 (Dennys, por medio de su agente local; con opiniones de Claude web y del auditor de Arena)

1. **Inventario, exclusiones y umbrales C3.1–C3.8: aprobados.**
   - Queda para una etapa posterior, con autorización explícita, una **prueba final sellada sobre datos reales** con
     enlaces `manual` ocultos. Claude web la pidió como examen final, no como entrenamiento.
   - Reserva de Claude web, que comparto: AUC ≥ 0,60 es un piso bajo. Lo que decide es C3.5.
2. **Capa V: aprobada, con condiciones:**
   - corpus públicos alcanzables desde el entorno, con la **licencia registrada por corpus**; UD PUD sigue fuera;
   - declaraciones a ciegas escritas por una **sesión aislada distinta** de la que diseñó el protocolo (un recuerdo
     cada vez, sin id de documento ni verdad), más el escritor mecánico de control.
3. **T1:** entra solo la categoría o prioridad de `pmi_hebbiano`, nunca su valor NPMI. Sujeta a C3.1 y C3.5.
4. **Paso 4:**
   - invariancia funcional (I-func) exigida al **100 %**;
   - **primero pesos congelados**, entrenados con corpus públicos;
   - una adaptación local acotada se evalúa después, solo como retador, contra la guardia sellada del 20 % y con la
     tolerancia de I-apr fijada antes.
   - Riesgo anotado por Claude web: los pesos de corpus públicos pueden no transferirse a la memoria real. Eso lo mide
     la prueba final sellada (punto 1).
5. **F-A y F-B:** no se abren ciclos en el motor ahora; quedan como tickets para después de cerrar la neurona, junto
   con la revisión de los `except OperationalError: pass`.
   - **F-A resultó ser código muerto** (`content_match_counts` no se lee): `h2_ciclo2/HALLAZGOS_DEL_MOTOR_K8.md`,
     corrección 1.
6. **Se autoriza ejecutar la capa L.** Resultados: `capa_L/RESULTADOS_CAPA_L.md`.
