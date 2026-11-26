# La segunda neurona estrella: la neurona sináptica (plan guía)

**Fecha:** 2026-11-25. **Estado:** plan de trabajo. **No hay código en el motor.**
**Pedido del usuario:** que la neurona que juzga las sinapsis del grafo sea «estrella de lujo», igual o más
blindada que la de re-ranqueo (`core/memory/neurona.py`), «no de juguete, de verdad», y con una mirada amplia
sobre las agujas, sin encerrarse en una sola idea.

Etiquetas: **[V]** verificado leyendo el código o midiendo; **[D]** deducido, es una interpretación.

---

## 1. Para quien llega sin contexto

- BioRAG guarda recuerdos y los une con **sinapsis**: el grafo. Cuando una búsqueda encuentra un recuerdo, sus
  vecinos sinápticos llegan con él (el «canal 2»). Esos vecinos traen palabras que ayudan a recordar.
- Las sinapsis automáticas aciertan poco: un **11–18 %** en el experimento 16. Se busca una neurona que aprenda a
  distinguir las buenas de las malas.
- La primera neurona del motor (re-ranqueo) es el modelo a seguir. Este documento explica qué la hace fuerte, qué
  de eso se puede trasladar a las sinapsis y en qué orden.

## 2. Qué hace fuerte a la primera neurona [V] (`neurona.py` L1–100, L598–906)

1. **La respuesta correcta le sale gratis.** Cuando un recuerdo se consolida, se hace preguntas a sí mismo
   («tapar y adivinar»). La respuesta correcta es él mismo. No necesita etiquetas humanas, telemetría ni al
   agente.
2. **Piso:** con la corrección en cero, el motor es idéntico al de siempre. Ninguna categoría del examen puede
   quedar por debajo de los pesos a mano, ni en R@1 ni en MRR ni en R@5.
3. **Guardia del 20 %** por hash del nombre: esos recuerdos nunca se estudian y solo sirven para juzgar.
4. **Campeón y retador:** el retador asciende solo si mejora sin empeorar la guardia y sin quitarle al campeón más
   de `tol_campeon` casos en ninguna categoría.
5. **Detector de memorización:** si el estudio mejora y la guardia no (brecha > 5 %), se reinicia y no asciende.
6. **Margen «primero no dañar»:** solo cambia el orden donde está segura. Es el menor margen con el que no pierde
   ningún caso de guardia.
7. **Solo ordena** (Pilar 12): mismos nodos, mismos números.
8. **Capas:** silencio por hilo, candado, cortacircuitos (3 fallos → pausa), pesos sanos con vuelta atrás,
   huella del motor, estado estricto, memoria acotada, tiempo fijo por ciclo y apagado total
   (`BIORAG_NEURONA=0`).

**Lo esencial es el punto 1.** Todo lo demás se apoya en tener una verdad gratuita contra la que medir.

## 3. La idea central para la neurona sináptica [D]

**No preguntarle «¿A y B están relacionados?».** En una base de usuario nadie sabe la respuesta: las decisiones
de Dennys prohíben usar `manual` y `desvincular` como etiquetas, prohíben la telemetría y dicen que la hormiguita
no es verdad.

**Preguntarle lo que sí tiene respuesta gratis: el examen de rescate.**
1. En el sueño, el recuerdo B se hace sus preguntas, como en la neurona 1.
2. La búsqueda **sin sinapsis** (repaso ciego) no encuentra a B, pero encuentra a A.
3. A tiene vecinos sinápticos. La pregunta del examen es **¿en qué puesto queda B entre los vecinos de A?** La
   respuesta correcta es B: se sabe porque la pregunta salió de B.
4. La neurona aprende a **ordenar los vecinos del canal 2** para que el recuerdo buscado quede arriba. Es el
   mismo tipo de examen que el de la neurona 1 (un ranking con respuesta conocida), así que **el molde completo
   se traslada tal cual**: piso, guardia, campeón/retador, margen y capas.
5. Ve **solo rasgos del par (A, vecino)**, nunca de la consulta. Así lo que aprende es un juicio sobre la sinapsis,
   no sobre la búsqueda. Ese mismo puntaje sirve después, en **modo sombra**, como evidencia del sueño para
   consolidar o atenuar sinapsis `a_prueba` (E3).

Por eso **U no debe ser una entrada de la neurona: U es su examen.** En E1, U dio 0,50 porque las pistas eran tan
literales que la búsqueda directa nunca fallaba: no hubo casos de examen.

## 4. Verificación del dictamen del otro asesor

| Afirmación | Veredicto | Evidencia |
|---|---|---|
| «Arena no entrenó ninguna neurona» | **Cierto, y era lo previsto.** E1 solo medía si las señales eran limpias; E3 está bloqueada por decisión aprobada | `PROTOCOLO_V3.md` §3 y §5 |
| U dio 0,50 porque las pistas eran del propio B | **Cierto en el síntoma** [V]: c1 eran 4 unidades seguidas del texto de B y la búsqueda directa encontró a B 129/132 veces en es/en. **Copiar `neurona_examen.py` no sirve:** está atado al español (`STOPWORDS`, `BILINGUAL_DICT` ES→EN, plantillas en español) | `neurona_examen.py` L1–60 |
| No correr E2 sacando U | **De acuerdo, por otra razón:** el E2 del v3 entrena un clasificador con etiquetas del mundo sintético, que no existen en una base de usuario. Hay que rehacerlo con el examen de rescate (v4) | §3 de este documento |
| El motor es ciego a palabras CJK de 2 caracteres | **Cierto** [V], medido en E1 | `RESULTADOS_E1.md` §5.1 |
| «Revisar el desempate de C1.1 para llegar a ≥ 271» | **No.** Ajustar el desempate para pasar el umbral es ajustar al examen. La diferencia viene del BM25, que depende del corpus. La solución de fondo son rasgos del par que no pasen por el buscador (§5) | `RESULTADOS_E1.md` §3 |
| Hub: «A y B comparten `hub_id`» | **Casi nunca ocurre** [V]: `aprender` crea un hub por recuerdo (`hub_{clave}`). Lo valioso son los **5 bridges** que escribe el agente | `write.py` L422–425 |
| `ctx_claims` como aguja | **No como aguja** [V]: solo se escribe al aprobar una corrección y genera su propia arista `sustituye`. Es una etiqueta explícita del agente, de la clase de `manual` | `contextual/service.py` L120–160 |
| SDM sin los bits de vecinos | **No aporta información nueva** [V]: es una bolsa de palabras con `stemmer_es`, que en CJK toma la frase entera como un token, más dimensiones y categoría (eso ya es S). Se rescata **pesar las dimensiones por rareza con el IDF congelado** de `db/hebbian_clusters.json` | `sdm.py` L30–60, L160–230 |
| `Δt` como aguja limpia | **Invariante sí, pero peligrosa** [V]: la cercanía temporal ya es una de las causas del nacimiento de sinapsis malas (B6: «consolidadas en el mismo sueño»). Puntuaría bien justo las sinapsis que hay que corregir. Además, en el mundo sintético todo nace en segundos, así que no se puede medir sin una línea de tiempo realista | `ALGORITMO_NACIMIENTO_SINAPSIS.md` B6; `episodes.py` |
| Cobertura cruzada entre campos | **Buena idea** [D]. Calculada directo sobre el par, sin buscador, es invariante por construcción y funciona en los 4 idiomas (piloto en §5) | piloto de este ciclo |
| Descartar `srl_extractor`, `stemmer_es`, `stopwords` y PPMI | **De acuerdo** | auditorías anteriores |

## 5. Inventario de agujas (barrido de `core/` y `core/memory/`)

Reglas para entrar: **sin idioma**, **invariante** (F(D,q) = F(D∪I,q)), **sin bucle** (no lee el grafo que juzga)
y **costo fijo**.

| Aguja | De dónde sale | ¿Sin idioma? | ¿Invariante? | ¿Sin bucle? | Estado |
|---|---|---|---|---|---|
| **S** — dimensiones y sustantivos clave compartidos | Lo declara el agente | Sí | Sí | **Solo si excluye `auto_generada = 1`** (ver §6) | AUC 0,822 en los 4 idiomas (E1) |
| **S_idf** — dimensiones pesadas por rareza | IDF **congelado** de `db/hebbian_clusters.json` | Sí | Sí (referencia fija) | Sí | Por medir |
| **X** — cobertura cruzada: sustantivos clave de A dentro del texto de B, y al revés | Subcadena Unicode NFKC casefold, sin buscador | Sí | Sí, por construcción | Sí | **Piloto exploratorio:** AUC 0,62–0,65; S + X = 0,85 en los 4 idiomas |
| **B** — bridges del agente (5 por recuerdo) cruzados con el texto y los bridges del otro | `concept_hub_bridges` | Sí, si se compara por Unicode | Sí | Sí | **No medible todavía:** el mundo sintético no tiene bridges, y si los escribo yo, mido mi autoría |
| **R** — resonancia en el repaso ciego | Buscador del motor | **No en CJK** hasta arreglar la búsqueda | ~98 % (BM25) | Sí, con la copia limpia A4 | 0,78–0,83 en es/en; 0,52–0,57 en zh/ja |
| **K** — competencia dentro del nodo (puesto del vecino entre los vecinos de A según S/X) | Local al nodo | Sí | Sí, si se calcula sobre rasgos invariantes | Sí | Por medir |
| **Δt** — distancia de creación | `creado_en` | Sí | Sí | Sí, pero repite la causa B6 | Solo con una línea de tiempo realista; como mucho, entrada vigilada |
| Categoría compartida | La declara el agente | Sí | Sí | Sí | Débil: solo hay 11 categorías |
| Tipo y peso a mano de la sinapsis | Regla de nacimiento | Sí | No (depende del corpus en B1/B6) | Es el propio grafo | **Es el piso**, no una entrada |
| Grado del nodo | Grafo | Sí | **No**: cambia cuando nacen sinapsis con I | No | Fuera |
| `grupos_semanticos` | Lexnames de WordNet | **No** (léxico inglés) | — | — | Fuera |
| Predicados SRL | Verbos en español | **No** | — | — | Fuera |
| PPMI, LSA y SDM con vecinos | Corpus completo + retrofit de sinapsis | No | No | No | Fuera |
| ADN conceptual | Clustering de la topología de sinapsis | — | — | **No** | Fuera (además, apagado por defecto) |
| `lexico_aprendido` | Episodios de uso del agente | Sí | — | Por revisar | Pendiente: no está en el laboratorio |

## 6. Dos vías de bucle nuevas que encontré en este barrido [V]

1. **`largo_plazo.asociaciones`** es una copia en CSV de los vecinos sinápticos (`sinapsis.py` L524–535). La
   búsqueda la cuenta (`search.py` L2282) y suma `0.02·min(1, asoc/20)` (`scoring.py` L342): un premio a los
   nodos con muchos enlaces. La copia limpia de E1 no la vaciaba. En E1 no influyó porque estaba vacía; en una
   base real sí.
2. **Dimensiones emergentes:** `auto_clustering.py` detecta comunidades **en el grafo de sinapsis** y las guarda
   como dimensiones del eje **`dominio`**, el mismo que usa el agente, con `auto_generada = 1`. Dos efectos:
   - **S tiene que excluirlas.** Si no, una sinapsis mala crea una comunidad, la comunidad crea una dimensión
     compartida y S dice «relacionados»: un bucle.
   - **El repaso las ve.** Inyectar una dimensión emergente falsa cambió 6 de los 276 pares en es y 5 en en.
3. Además, `largo_plazo_dimensiones` no guarda la procedencia. Las dimensiones que añade la reflexión de la DMN
   con un LLM externo (solo si hay claves de Gemini) no se distinguen de las del agente. **[D]** Haría falta
   guardar la procedencia: es un cambio en el motor, para su propio ciclo.

Ambas vías quedaron tapadas en el laboratorio con la enmienda A4 y el criterio C1.2c (`PROTOCOLO_V3.md` §0).

## 7. «Sin margen de error»: qué se puede garantizar de verdad [D]

Ninguna neurona, ni la primera, acierta siempre. Lo que la primera garantiza es **no hacer daño, por
construcción**. La sináptica puede garantizar lo mismo:
- **Nunca borra ni oculta** una sinapsis (Pilar 12). Solo ordena el canal 2, y en el sueño solo propone, en modo
  sombra.
- **Nunca toca** los enlaces `manual` ni los del agente; esos van siempre primero.
- **Piso:** en el examen nunca queda peor que el orden a mano, en ninguna categoría ni camino. En el laboratorio,
  tampoco en ningún idioma.
- **Margen:** solo cambia donde está segura y sin perder ningún caso de guardia.
- **Apagado total** con un interruptor, y vuelta automática al orden a mano si algo no cuadra.

Así, un error de la neurona no puede dejar el sistema peor que hoy. Eso es lo que sí se puede prometer.

## 8. El molde, pieza por pieza

| Neurona 1 (re-ranqueo) | Neurona sináptica |
|---|---|
| Examen: el recuerdo pregunta y la respuesta es él | **Examen de rescate:** B pregunta, la búsqueda ciega cae en A y la respuesta es B entre los vecinos de A |
| Entradas: 29 rasgos de (consulta, candidato) | Rasgos del **par** (A, vecino): S, S_idf, X, B, K y, donde sirva, R. Más el tipo y el peso a mano |
| Piso: los pesos a mano de `scoring.py` | El orden a mano del canal 2 de hoy (manuales primero, tope de 2 `sinonimo_explicito`) |
| Guardia del 20 % por hash del nombre | 20 % por hash del recuerdo **B** (el que pregunta) |
| Categorías del piso: tipos de pregunta × camino | Tipos de pista × tipo de sinapsis. En el laboratorio, además, × idioma |
| Campeón/retador con `tol_campeon` | Igual |
| Detector de memorización (brecha > 5 %) | Igual |
| Margen «primero no dañar» | Igual, por puesto en el canal 2 |
| Solo reordena la página | Solo reordena los vecinos; nunca quita ninguno |
| Capas: silencio, candado, cortacircuitos, pesos sanos, huella del motor, estado estricto, memoria y tiempo acotados | Las mismas. La huella también cubre las reglas de nacimiento (si cambian, empieza de cero) |
| `BIORAG_NEURONA=0` | `BIORAG_NEURONA_SINAPTICA=0` |
| Aprende al consolidar | Aprende en el sueño, sobre la copia limpia, con K recuerdos por ciclo (costo fijo) |

## 9. Orden de trabajo, con puertas

| Paso | Qué | ¿Toca el motor? | Puerta para pasar |
|---|---|---|---|
| 0 | Tapar las vías de bucle en el laboratorio (A4 + C1.2c) | No | C1.2c 276/276 en los 4 idiomas. **Hecho en este ciclo** (ver `RESULTADOS_E1.md` §8) |
| 1 | **«Ojos Unicode» en la búsqueda:** encontrar palabras CJK de 1–2 caracteres | **Sí** (canal 1) | QA completa sin bajar (R@5, R@1, MRR, FP 0/40) y suite en verde. **Hecho 2026-11-25** (ver `../ojos_unicode_busqueda/RESULTADOS.md`): 0/11 → 11/11 en top-1, todas las puertas idénticas. Pendiente de PR para Dennys |
| 2 | **Examen de rescate en el laboratorio:** pistas de dificultad graduada, sin listas de idioma (muestras dispersas de unidades Unicode, sin el nombre), con control de hubs | No | Suficientes casos por idioma; invariancia ≥ 98 %; rescates de hubs por debajo de un tope fijado antes. **Medido 2026-11-25** (`paso2_examen_rescate/RESULTADOS.md`): examen limpio y reproducible (P6), pero el mundo de 24 recuerdos no lo aloja (0–4 casos; los pocos casos eran basura y P5 los detectó). **Pasa 1 de 7** |
| 2b | **Examen de rescate v2 en un mundo grande real:** UD PUD (1000 frases paralelas, 397 documentos, es/en/zh/ja, CC BY-SA), filtro de pistas sin contenido sin listas, invariancia solo con I que no contienen la pista | No | Las mismas puertas P1–P6, fijadas antes. **Medido 2026-11-25** (`paso2b_examen_rescate_pud/RESULTADOS.md`): pasa 1/7. El filtro funciona; tres hallazgos del motor: H1 sin sinapsis en zh/ja (4 y 0), H2 la inhibición lateral duerme el 74 % y rompe la invariancia, H3 el rescate es raro por naturaleza. Propuesta: examen de orden para entrenar y rescate para validar |
| 3 | **Batería de agujas** (S, S_idf, X, B, K, R, Δt), cada una con AUC, invariancia y bucle por idioma | No | Se fija antes qué entra. Necesita un mundo más grande, **escrito a ciegas** (quien escribe los textos no conoce los pares) |
| 4 | **Protocolo v4 + E2:** la neurona con el molde completo, entrenada con el examen de rescate, en copias. Compara dos formas de entrenar con el mismo piso, la misma guardia del 20 % y los 4 idiomas (nota 9.1) | No | Gana al piso en la guardia sin bajar ninguna categoría ni idioma |
| 5 | E3: consolidación en el sueño, en modo sombra | No (sombra) | Solo tras pasar E1 y E2 |
| 6 | Llevarla al motor | Sí | PR; solo Dennys hace merge |

**El riesgo más grande del plan [D]:** el mundo de prueba. Si lo escribo yo, sabiendo qué pares son del mismo
tema, cualquier aguja textual puede medir mi forma de escribir y no la relación real. El exp. 16 ya tuvo una
filtración léxica así (AUC 1,000 falso). Para el paso 3 hace falta un mundo escrito a ciegas, o datos que Dennys
autorice.

### 9.0 Nota para el paso 3: soporte agrupado (engrama), idea del usuario y su agente (2026-11-25)

En el cerebro, los recuerdos se apoyan en grupos de sinapsis de una misma rama, no en una sinapsis suelta. Aguja
candidata **G** para la batería: ¿cuántos vecinos de A también apuntan hacia B (o comparten rasgos invariantes con
B)? Condiciones para entrar, como las demás: sin idioma, invariante y **sin bucle** (no puede contar el propio
enlace A–B ni leer el grafo que juzga sin la copia limpia; si usa el grafo, solo como entrada vigilada y medida
con la prueba de sinapsis falsas de C1.2b).

### 9.0b Complemento de auditoría del agente local para el paso 3 (2026-11-25)

Candidatas para la batería del paso 3, con las mismas reglas de entrada (sin idioma, invariante, sin bucle, costo
fijo). Lo verificado aquí se marca [V]; el resto queda como propuesta [D] hasta medirlo.
1. **G_ciego (engrama ciego):** `|TopK_ciego(A) ∩ TopK_ciego(B)|` en la copia sin sinapsis. Es la forma sin bucle de
   G: no lee `sinapsis`. Capta pares sin palabras comunes que caen cerca de los mismos recuerdos. Cuidado [D]: pasa
   por el buscador, así que hereda su invariancia (la del BM25: ~93–100 % según el idioma en el Paso 2) y hay que
   medirla con la NORMA MÁXIMA como R.
2. **S refinada:** Jaccard de dimensiones `|D_A ∩ D_B| / |D_A ∪ D_B|` (local al par, invariante) y separación por
   eje (temáticos: dominio, entidad, intención, cualia; de tono o forma: cualidad, emoción), siempre sin
   `auto_generada = 1`.
3. **X refinada:** separar la coincidencia en concepto, sustantivos clave y contenido (el motor los pesa 5, 4 y 1 [V],
   `evidence_convergence.py` L20–25) y medir la reciprocidad `min(X(A→B), X(B→A))` frente a `max`, para
   distinguir enlaces mutuos de hubs unilaterales.
4. **`lexico_aprendido` queda fuera** [V]: normaliza con `[^a-z0-9\s]` (`lexical_learning.py` L52, solo ASCII, no ve
   CJK) y guarda enseñanza explícita, de la clase de `manual`.

### 9.0c Exigencia de escala y variedad para los pasos 3 y 4 (usuario y asesor, 2026-11-25)

UD PUD (frases cortas, ~15 palabras) sirve para validar el examen (paso 2b), **no basta para entrenar ni evaluar la
neurona**. Los pasos 3 y 4 sumarán otros cuerpos reales y públicos, en los 4 idiomas, del orden de varios miles de
recuerdos: párrafos largos, textos enciclopédicos y técnicos, documentos variados. Todo en copias o en RAM, no
millones de filas en SQLite. Desde este entorno solo se alcanzan GitHub y PyPI; candidatos verificables: otros
treebanks de Universal Dependencies con documentos y párrafos (p. ej. GSD de Wikipedia en zh y ja, AnCora o GSD en es,
GUM o EWT en en). La elección se fija antes de medir, en su ciclo.
**En el motor**, como la neurona 1, el examen de rescate vivirá dentro del sueño, sobre los datos de cada usuario,
con piso, techo, guardia del 20 % y campeón/retador (pasos 5 y 6).

### 9.1 Nota para el paso 4: gradiente frente a neuroevolución (idea del usuario, 2026-11-25)

Viene del video de los 200 coches (se copian con mutaciones los que llegan más lejos) y de la sugerencia del
agente local. Se traduce a una prueba limpia, no se copia tal cual:

- **Dos retadores, mismo juez.** (a) El entrenamiento por gradiente del molde de `neurona.py`. (b) Una población
  pequeña de retadores en RAM con `numpy` (p. ej. 20–40 vectores de pesos) que muta y conserva a los mejores,
  optimizando directamente la métrica discreta del examen de rescate (rango de B en el canal 2 de A).
- **Mismo piso** (el orden a mano), **misma guardia sellada del 20 %**, los **4 idiomas** y un **tercer grupo
  sellado** para elegir al ganador: nunca se elige mirando la guardia.
- **Currículo de dificultad:** las generaciones empiezan con pistas fáciles del examen y suben de nivel en escalera;
  el piso es la regla de muerte (un retador que pierde contra el piso en cualquier idioma se descarta).
- **Solo en RAM y en copias:** nada contra SQLite, sin fase de choques en vivo, sin telemetría de uso (norma 4).
- **Idea a futuro, fuera de este plan:** mutaciones pequeñas alrededor del campeón de `neurona.py` cuando llegue a
  su techo. **No se toca la neurona 1** sin un ciclo y un OK propios.

