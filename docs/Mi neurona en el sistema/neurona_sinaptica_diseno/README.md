# Neurona sináptica (NS-1): diseño propuesto para reemplazar a la hormiguita

**Fecha:** 2026-11-25 · **Rama:** `arena/da3df5df-memorybiorag` · **Estado:** solo diseño. **No hay
nada implementado**; cada fase necesita el OK de Dennys.

**El pedido de Dennys:** que las sinapsis «se creen de verdad, como tiene que ser». Una neurona que haga
lo que ningún algoritmo simple haría, sin APIs externas, para que la hormiguita (Gemini) deje de podar.
- **Piso:** las ecuaciones base de hoy.
- **Techo:** «no más de un 20 %», para que aprenda y no memorice.
- **Alimentación:** todo lo que sirva.

Etiquetas: **[VERIFICADO]** = leído en el código o medido; **[HIPÓTESIS]** = sin medir;
**[DECISIÓN]** = la tiene que tomar Dennys.

---

## 1. Respuestas a las tres preguntas de Claude Web

### 1.1 ¿El experimento 12 probó pesos por debajo de 0.5?
**No [VERIFICADO].** En `experimento_12_neurona_en_el_motor/README.md` §1, la fórmula es
`peso = 0.5 + 0.5·fuerza`, siempre entre 0.5 y 1.0. Se eligió así a propósito, para que nada quedara por
debajo del filtro de 0.5 del canal 2.
- Ese experimento sí repesó **todas** las 13 114 sinapsis automáticas dentro de ese rango. La QA salió
  idéntica caso por caso (R@5 100 %, R@1 91,89 %, MRR .950).
- La razón medida: **la QA casi no ve el peso**. La expansión por el grafo actúa en 8 de 921 consultas.
- El grafo sí mejoró:
  - AUC del peso, sí contra no, en el examen de Dennys: de .628 a .738;
  - enlaces manuales entre los 6 vecinos principales: de 86 a 142;
  - un recuerdo nuevo desplaza a sus vecinos en 101 de 430 casos, contra 400 de 430 hoy.
- **El rango 0.05–0.2 nunca se probó.** Claude Web tiene razón en esto.

### 1.2 ¿Qué pasó en el experimento 13?
Allí se probó **cortar** (no crear) los pares que la neurona juzgaba débiles. Resultados sobre 875
búsquedas:

| Escenario | Enlaces automáticos | R@5 | R@1 | Fallos |
|---|---|---|---|---|
| Hoy | 13 114 | 100 % | 91,89 % | 0 |
| Hormiguita apagada (vuelve todo lo podado) | 15 864 | 100 % | **92,00 %** | 0 |
| Cortar con fuerza < .40 | 10 261 | 99,89 % | 91,77 % | 1 |
| Cortar con fuerza < .50 | 3 847 | 99,66 % | 91,77 % | 3 |
| Cortar con fuerza < .60 | 1 684 | 99,43 % | 91,66 % | 5 |
| Sin ningún enlace automático | 0 | 99,43 % | 91,77 % | 5 |

- **Conclusión de entonces:** el «ruido» sí sirve para buscar (sin él se pierden 5 búsquedas), y
  **cualquier corte al nacer baja el recall**.
- **Dato extra:** apagar la hormiguita *mejoró* la QA, y de 11 cortes suyos que Dennys juzgó, 4 eran
  enlaces buenos.
- **Sobre pesos bajos:** no hay ningún dato directo; solo cortar o no cortar.

### 1.3 Qué haría hoy un peso de 0.05–0.2 (leído en el código)
Antes de medir conviene saber qué hace cada consumidor del peso. **Un peso bajo no es neutro: en casi
todos los consumidores equivale a cortar.**

| Consumidor del peso | Regla en el código | Con peso 0.05–0.2 |
|---|---|---|
| Canal 2 (lo que ve el agente) | `peso_min=0.50` (`core/memory/synapses.py` L462) | **Invisible.** Igual que cortar |
| Expansión por el grafo (ranking) | Ventana de las últimas 512 aristas, ordenadas por peso, **top 6**; `score = 0.6·padre + 0.2·peso` (L337–406) | Entra solo si el recuerdo tiene menos de 6 vecinos más fuertes |
| Inferencia transitiva (latentes) | `WHERE peso >= 0.25` (`core/inferencia_transitiva.py` L125) | **Excluida** |
| Comunidades (LPA) | `peso >= 0.1` (`core/auto_clustering.py` L36) | Excluida si es < 0.1 |
| Recorrido de la hormiguita | `peso >= 0.1` (`core/dmn_reflexion.py` L381) | Excluida si es < 0.1 |
| Poda del sueño | `DELETE … peso < 0.05` | Borrada en cuanto baje de 0.05 |

**[HIPÓTESIS] Lo que yo esperaría del experimento:**
- en el ranking, un resultado entre «hoy» y «cortar < .40»;
- en el canal 2, la desaparición de los pares débiles, igual que el filtro que **Dennys rechazó el
  25-11** (porque deja 55 recuerdos sin asociaciones).

**Consecuencia de diseño importante.** «Nacer bajito» solo es compatible con la regla «el canal 2 ordena,
nunca oculta» si **antes** el canal 2 deja de usar el umbral absoluto de 0.5 y pasa a ordenar (la neurona
del experimento 14). El experimento 15 (S1) ya mostró el mismo acoplamiento: bajar pesos le roba lugares
al canal 2.

---

## 2. Qué cuenta como «uso» (A5): respuesta, como hipótesis

Se adopta la definición propuesta, **como hipótesis documentada, sin implementar**:

> Una sinapsis se *usa* cuando el proceso de recuperación la **recorre y por ella activa o incorpora un
> recuerdo candidato** en el resultado. En el código, eso es la expansión por el grafo (L337–406) y la
> evocación en cadena (`_evocacion_por_cadena`). Es un evento interno del algoritmo. **No significa que
> el agente leyó o usó ese recuerdo.**

- **No cuenta como uso** aparecer en el canal 2.
- **No se registran** consultas, respuestas, identidad del agente ni qué enlaces aparecieron en cada
  interacción.
- **No se agrega** telemetría, ni olvido, ni refuerzo por uso, hasta que Dennys elija una opción.

**Un dato que hay que poner sobre la mesa [VERIFICADO]:** el sistema **ya guarda hoy** una señal por
sinapsis, la columna `sinapsis.ultimo_uso`. La escriben:
- `buscar_vecinos` (`core/sinapsis.py` L404–409), que marca **todas** las sinapsis del recuerdo
  consultado, no la recorrida;
- `buscar_recuerdo_microsegundos` y `buscar_recuerdo_profundo` (`core/memory/search.py` L3030 y L3154);
- el refuerzo de ráfaga y el de feedback.

Es decir, ya existe un registro por enlace, pero impreciso. La decisión no es solo «agregar o no
agregar»: también es qué hacer con lo que ya existe.

### Opciones para decidir [DECISIÓN]

| Opción | Qué se guarda por sinapsis | Qué permite | Qué no permite |
|---|---|---|---|
| **U0. Nada** | Nada nuevo; `ultimo_uso` se deja como está o se deja de escribir | La neurona usa solo evidencia estática, la convergencia de reglas y los rechazos | Madurar ni olvidar por uso. El sistema **no puede afirmar** que conoce el uso de cada enlace |
| **U1. Marca de tiempo** | `ultimo_recorrido` (un número, sin consulta ni agente). Se sobrescribe, no hay historial | Olvido por desuso ajustado («no recorrida en X sueños») | Distinguir 1 recorrido de 100 |
| **U2. Traza que se apaga** | Un número entre 0 y 1 que sube al recorrerla y decae en cada sueño (traza de elegibilidad) | Tres factores reales: etiqueta, captura y consolidación | — (sigue sin guardar consultas, pero es memoria por enlace) |
| **U3. Solo por recuerdo** | Contador por recuerdo, nunca por sinapsis | Una homeostasis aproximada | Saber qué enlace concreto sirvió |

**Mi recomendación técnica:** U2, porque es la que hace posible el ciclo de vida biológico. Si se elige
U0, la neurona igual sirve, pero solo para nacer y renacer; el sistema no debe aparentar que madura por
uso.

**La regla «sin feedback del agente»:** U1 y U2 no usan feedback del agente; son eventos del
recuperador. Igual hace falta que Dennys diga si los permite.

---

## 3. El diseño: NS-1, neurona del ciclo de vida sináptico

### 3.1 Qué decide (y qué no)

| Decide | No decide nunca |
|---|---|
| Con qué peso nace un enlace automático: un peso **calibrado**, que significa probabilidad de que la relación sea real | Nada al recordar: no filtra, no oculta, no reordena el canal 1 (Pilar 12) |
| Si un par **rechazado antes** tiene evidencia nueva suficiente para volver a nacer (histéresis, no prohibición) | Nada sobre los enlaces `manual` o `manual_v7`: son intocables y además son su **mejor señal de aprendizaje** |
| En el sueño: si una sinapsis transitoria se consolida, se queda o va a cuarentena (reversible; nunca se borra un recuerdo) | Nada con APIs externas, red o GPU |

### 3.2 Por qué es «inteligencia» y no otra regla más
Lo que ningún algoritmo simple del sistema hace hoy:

1. **Combina señales débiles de forma no lineal.** «Comparten la palabra *protocolo*» es ruido en el
   nombre, pero es señal si además comparten dominio, un sustantivo clave declarado por el agente y una
   palabra rara. Hoy cada pasada decide sola, con un umbral fijo.
2. **Aprende cuánto confiar en cada regla según el contexto.** Por ejemplo, `co_semantica` con una sola
   palabra no es confiable, y `pmi_hebbiano` sí lo es en temas técnicos. También pesa que varias reglas
   independientes propongan el mismo par.
3. **Tiene memoria del par a lo largo del tiempo:** cuántas veces se propuso, en qué contextos, cuántas
   veces se rechazó y si alguien lo restauró. Un algoritmo de nacimiento ve un solo instante.
4. **Su peso significa algo.** Hoy la escala no es coherente:
   - `sinonimo_explicito` nace siempre en 0.9;
   - `co_semantica` llega a 1.0 con una sola palabra;
   - las pasadas 2–4 pesan según la importancia del destino.

   Con salida calibrada, 0.7 ≈ «70 % de probabilidad de que sea una relación real». El canal 2, la
   expansión, las latentes y la poda pasarían a hablar la misma escala.
5. **Se ajusta a la densidad del recuerdo.** En un hub con 241 vecinos, otro enlace débil vale menos
   que en un recuerdo con 3. Es la homeostasis que S1 quiso hacer a mano.

### 3.3 Arquitectura: piso + corrección + guardianes (Pilar 11)

```
x        = agujas del par (§3.4), calculadas en tiempo constante
piso     = la ecuación base de hoy para ese tipo (exactamente el peso a mano actual)
p        = σ( logit(piso_calibrado) + v·tanh(W·x + b) )      ← igual que la neurona de ranking
peso     = p                                                   (con techo de corrección, ver abajo)
estado   = "transitoria" si p < umbral_maduro, si no "madura"
```

- **Piso.** Si la neurona falla, se apaga o pierde contra el piso en el examen, el motor usa exactamente
  el peso de hoy.
- **Techo, lo que entiendo de «20 %» [DECISIÓN].** Lo entiendo como en la neurona de ranking: el
  **20 % de los datos queda como guardia** (`sha256(nombre)[:8] % 5 == 0`) y nunca se entrena con eso,
  para que aprenda y no memorice. Además propongo acotar la corrección: |logit(p) − logit(piso)| ≤ un
  máximo fijo, para que la neurona no pueda dar vuelta una decisión base de un salto. **Necesito que
  Dennys confirme si su 20 % era la guardia, el tope de la corrección o las dos cosas.**
- **Campeón.** Una versión nueva solo reemplaza a la anterior si gana en la guardia **y** en el examen
  sellado.
- **Examen sellado.** Los 100 pares que juzgó Dennys, más una hoja nueva de pares marcados a mano. No se
  entrena nunca con ellos.
- **Interruptor:** `BIORAG_NEURONA_SINAPTICA=0` vuelve todo al piso.
- **Modelo.** Pequeño (≈ 30 entradas → 8 ocultas → 1), solo con numpy, determinista con semilla. Tiene
  restricciones monótonas en las señales donde la dirección es obvia (por ejemplo, más palabras raras
  en común nunca baja la probabilidad), para que se pueda auditar. La salida se calibra (isotónica).
  Costo por par < 1 ms.

### 3.4 Con qué alimentarla: las agujas
Todas son locales al par y a su vecindario. **No se usa** el texto de consultas, la identidad del agente
ni el feedback.

| Grupo | Agujas |
|---|---|
| Léxicas | Jaccard-IDF; solapamiento de nombre y de sinónimos (con `min` **y** con `max`, para que la neurona vea el caso «una sola palabra»); largo de la palabra compartida más larga; «¿solo comparten palabras de ≤ 3 letras?» (en la memoria viva, 2530 de 4027 enlaces accidentales venían de eso); coincidencia por palabra completa o por pedazo (`LIKE`); rareza máxima y media de lo compartido; **cuántas reglas proponen el par** (de 1 a 4) |
| Semánticas | NPMI; coseno PPMI+SVD; LSA del experimento 11; similitud SDM; grupos WordNet compartidos; **dimensiones compartidas por eje** (13); **sustantivos clave compartidos** (los declara el agente: alta calidad); bridges o hub compartido; entidades SRL compartidas |
| Estructurales | Vecinos comunes; Adamic-Adar (castiga a los hubs); grado de cada extremo (log); importancia de cada extremo **como aguja, no como multiplicador**; misma categoría; misma comunidad |
| Episódicas | Distancia temporal de creación, con la guardia de 7 días del experimento 12; ¿nacieron en la misma sesión? |
| Historia del par | Veces propuesto; veces en cuarentena; veces desvinculado (hoy **no se registra**: §4, paso 2); veces restaurado por la alarma de la hormiguita; tiempo desde el último rechazo; si existe como latente y con qué madurez |
| Uso (solo con U1 o U2) | Traza de recorrido |

**Cuidado con las fugas de información:**
- Para un par `manual` usado como ejemplo positivo, las agujas estructurales se calculan **sin ese
  enlace**.
- La neurona **nunca ve el tipo `manual` como entrada**. En el experimento 14 hay que auditar justamente
  si la neurona aprendió a reconocer el tipo en vez de la relación.

### 3.5 Con qué datos se entrena

**Nivel fábrica (cerrado; viene con el sistema y funciona desde una DB vacía).**
- **Corpus sintético con estructura conocida:** temas, sinónimos reales, choques accidentales de
  palabras, hubs. Las etiquetas son verdad por construcción. El generador del experimento 15
  (`simular.py sintetica`) es la base.
- **Corpus públicos con licencia compatible**, para llegar a millones de pares. Por ejemplo, enlaces y
  categorías de Wikipedia (CC BY-SA) o WordNet. **[DECISIÓN] pendiente: fábrica 2.0 y licencias.**
- **El snapshot público (851 recuerdos):**
  - enlaces manuales → positivos;
  - pares de la cuarentena que restauró la alarma → positivos débiles;
  - pares en cuarentena no restaurados → negativos débiles, **solo si Dennys acepta usar las decisiones
    viejas de Gemini como datos (A3)**;
  - los 100 pares de Dennys → **solo examen, nunca entrenamiento**.

**Nivel local (opcional).** Hoy choca con la decisión del 24-10 de que la neurona asociativa sea
cerrada y no aprenda de la memoria del usuario. **[DECISIÓN]**
- Si se permite, aprende de los enlaces manuales del usuario y de sus `desvincular`, con la guardia
  del 20 % y el campeón contra el peso de fábrica.
- Si no se permite, la neurona es solo de fábrica y en cada memoria aporta su historia del par (que es
  dato, no aprendizaje).

### 3.6 Cómo vive una sinapsis con NS-1 (el ciclo biológico)

1. **Nace etiquetada.** La regla de siempre propone el par y NS-1 pone `p`. Si `p` es bajo, nace
   **transitoria**, como `hipotesis_sueno` hoy (0.08, con olvido). Si `p` es alto, nace madura.
2. **Captura (en el sueño, ventana de N sueños).** La transitoria se consolida si llega un tercer
   factor:
   - **convergencia:** otra regla u otro guardado vuelve a proponer el par en un contexto distinto;
   - **un evento fuerte cercano:** el agente vincula explícitamente uno de los extremos con un vecino
     del otro (etiquetado y captura de Frey y Morris);
   - **uso:** solo con U1 o U2.
3. **Sin captura, se apaga.** Baja hasta un umbral y pasa a **cuarentena**. Es reversible, no se borra.
4. **Memoria de rechazo con histéresis.** Un par que ya estuvo en cuarentena o se desvinculó solo
   renace si su `p` nuevo supera al `p` que tenía cuando se rechazó, más un margen. No es una
   prohibición: es exigir **evidencia nueva** (como la marca C1q, que no se reconstruye igual).
5. **Los manuales no pasan por nada de esto.**

---

## 4. Plan en fases (cada una medida en copias, con OK antes de la siguiente)

Costo de medición: cada QA oficial tarda unos 16 min; cada fase necesita al menos la QA antes y después,
y la suite completa.

| Fase | Qué | Criterio para pasar (fijado antes de medir) |
|---|---|---|
| **F0** | Decisiones de Dennys: A1 (invariancia), A2 (¿el Pilar 12 aplica al nacimiento?), A3 (decisiones de Gemini), A4 (`desvincular` permanente), A5 (U0–U3), techo del 20 %, nivel local sí o no | — |
| **F1** | Neurona del canal 2 que **ordena** (experimento 14, §4) y sale del umbral absoluto | Recall idéntico; huérfanos ≤ hoy; examen tapado mejor |
| **F2** | Arreglos de reglas sin neurona: (a) memoria de rechazo con registro de `desvincular`; (b) `vincular` deja los dos sentidos como manuales; (c) nada automático toca el peso de un manual | QA y suite idénticas; invariancia `F(D,q) = F(D∪I,q)` |
| **F3** | **El experimento que faltó (el de Claude Web):** pares sin relación con 0.15 y 0.05, contra el peso a mano; con el canal 2 actual **y** con el de F1 | Recall ≥ hoy; canal 2 sin pérdidas con F1; invariancia |
| **F4** | Armar el dataset de fábrica y entrenar NS-1 sin conexión | Gana al piso en la guardia y en el examen sellado; AUC > .738 (experimento 12) |
| **F5** | **Modo sombra** en una copia: NS-1 decide en paralelo durante N sueños simulados. Se registran solo las decisiones sobre sinapsis, sin consultas | Menos renacimientos, menos hubs, canal 2 mejor; recall idéntico |
| **F6** | Integración detrás de un interruptor, en un punto único de nacimiento (`decidir_nacimiento`) para las 4 pasadas, los sinónimos, la co-ocurrencia, el DMN y la ráfaga | QA, suite, invariancia y examen |

**La invariancia (A1) es un riesgo real de diseño.** Varias agujas usan estadísticas globales (idf, PMI)
que cambian cuando crece el corpus. Hay que congelarlas en fábrica o usar razones locales, y probarlo
con un corpus de referencia contra otro ampliado con recuerdos irrelevantes **antes** de aceptar.

## 5. Riesgos, sin adornos
- **Etiquetas escasas:** hoy hay unos 380 pares manuales en el snapshot y 100 pares juzgados. Por eso
  hace falta la fábrica con corpus sintéticos y públicos.
- **Las etiquetas de Gemini tienen ruido:** 4 de 11 cortes juzgados eran enlaces buenos.
- **La QA no ve los pesos** (experimento 12). Medir la mejora exige métricas de asociación: hoja de
  pares, examen tapado y calidad del canal 2. La QA solo protege que el recall no baje.
- **Si se elige U0, no hay maduración por uso.** NS-1 queda en nacer y renacer bien, que igual es el
  trabajo de la hormiguita.
- **Que NS-1 «reemplace a la hormiguita» se tiene que demostrar**, no suponer. En F5 se compara contra
  las 5446 decisiones históricas de la cuarentena, y en especial contra las 2201 que la propia alarma
  revirtió.
