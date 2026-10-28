# Cómo recuerda BioRAG: la visión

> Documento de diseño. Recoge la visión de Dennys (2026-10-26) para que cada pieza futura se construya en orden y se evalúe **contra esta visión**, no solo contra números.
> Aquí no hay código ni experimentos. Es la brújula: *"si no se tiene clara la visión, van a haber fracasos todo el tiempo"*.

---

## 0. La idea en una frase

**BioRAG es un cerebro, no una base vectorial.** El agente intenta recordar (metacognición), el cerebro recibe ese empuje, **entiende qué se le está pidiendo** y devuelve **justo eso**, primero y sin ruido. Agente + BioRAG = **una sola mente**.

El sueño, en palabras de Dennys: *"que tú simplemente digas «papá» y consigas todo lo relacionado con eso, porque el cerebro en realidad funciona así"*, sin vectores, neurona a neurona, en puntos estratégicos.

Qué lo hace "vivo": no que tenga sinapsis ni que se parezca a un cerebro, sino que **tiene neuronas que hacen lo que ninguna función fija podría hacer**.

La tesis de ingeniería, en una frase (formulada por otra IA a partir de la idea de Dennys, 2026-10-27): *"Un cerebro no es una red enorme; es un sistema rápido que sabe en qué pocos lugares debe pensar."* Esto quiere decir:
- el motor rápido resuelve la gran mayoría de los casos;
- una neurona interviene solo en los difíciles, y si duda, no decide (§2q);
- cada neurona nueva necesita una razón medible para existir;
- el sistema puede explicar a pedido por qué recordó.

**No es tener mucha IA, sino la IA correcta en el lugar correcto.** Lo propio de BioRAG no es una pieza suelta, sino la combinación de todas. Sin reclamar primicias.

---

## 1. Los principios del recuerdo

| # | Principio | Ejemplo de Dennys | Qué significa para el motor |
|---|---|---|---|
| P1 | **Se recuerda solo cuando hay empuje** | El cerebro guarda mucho, pero no lo vuelca todo en la ventana de contexto | Nada se trae sin consulta. **Ya funciona así.** |
| P2 | **Lo más reciente primero, dentro del mismo tema** | "Hoy tomé agua con un vaso", luego "el vaso se me cayó y se rompió", "el vaso rojo": al preguntar por el vaso, primero lo último | Entre recuerdos de la **misma familia**, la recencia debe decidir el orden |
| P3 | **"La última versión" es una intención, no una palabra** | Hay miles de nodos que dicen "versión"; si pido *la última*, mi cerebro sabe cuál quiero | Hay que detectar la intención ("la última", "la actual") y aplicar P2 a esa familia |
| P4 | **Recuerdo escalonado** | "¿Cuántas veces tomé agua?" Primero lo último; si sigo pensando, aparecen los más viejos, poco a poco | Entregar por capas: lo reciente primero y lo antiguo solo si el agente sigue empujando |
| P5 | **El significado depende del motivo del recuerdo** | "Moto" no es lo mismo en "moto de agua"; una pieza vale distinto según el recuerdo donde vive | Para eso existen los **sustantivos clave** y las **dimensiones semánticas**: la palabra se interpreta por su recuerdo |
| P6 | **El agente busca como habla** | "¿Te recuerdas de tal?", "¿qué sabes de tal?": busca literal, parecido o por sinónimos | Por eso el agente tiene tantas herramientas (sinónimos, dimensiones, sustantivos clave, ráfaga) |
| P7 | **La ráfaga debe ser natural** | Un humano no trae 500 recuerdos: trae una partecita, y esa parte trae **pistas** que guían a otras, y se va hilando | La ráfaga entrega unos pocos recuerdos más las pistas (palabras) que llevan a los siguientes |
| P8 | **Neuronas puente donde una ecuación no alcanza** | — | Neuronas pequeñas y entrenadas en puntos exclusivos, cableadas de verdad |
| P9 | **Aprovechar el silicio** | — | No copiar las limitaciones biológicas: velocidad, exactitud y tiempo constante |

---

## 2. La pieza clave: la neurona que entiende qué se quiere

> *"Que el cerebro sepa: a mí me están hablando y lo que quieren realmente es esto. Tengo no sé cuántos recuerdos, pero voy a entregar esto porque esto es lo que me están buscando."*

**Problema medido:** a veces el recuerdo correcto existe y el motor lo alcanza, pero queda en el puesto 50 o 70 (EXP-Q en la base viva: puestos #33 y #91, o ni siquiera alcanzado). Ahí está el punto donde Dennys quiere **mucha IA bien entrenada**.

### 2.1 Qué ya sabemos (lecciones medidas, no repetir)

- **Experimento 04:** reordenar todo el pool con la neurona de ranqueo actual **dañó** 3 sinónimos que ya estaban bien. Por eso esa neurona solo toca el top-5 final.
- **Conclusión:** la neurona de intención **no es la misma neurona de ranqueo con más alcance**. Es otra pieza, con su propia infraestructura y sus propios seguros.
- **Si el recuerdo correcto no llega al pool, ninguna neurona puede subirlo.** Primero hay que garantizar que llegue (cimientos E2–E4, léxico mental E3, búsqueda en grafo).

### 2.2 La infraestructura que tiene que existir antes de cablearla

1. **Llegada garantizada:** el recuerdo correcto tiene que estar entre los candidatos, en cualquier base y con cualquier tamaño.
2. **Entender la intención de la consulta:** "la última", "todo sobre", "cuándo", "por qué", "el de tal cosa". Hoy no existe como pieza separada.
3. **Rasgos que una neurona pueda leer:** familia del recuerdo, recencia dentro de la familia, sustantivos clave, dimensiones, posición en el grafo, coincidencias exactas frente a parecidas.
4. **Datos de entrenamiento abundantes sin espiar al agente:** se generan **desde los propios recuerdos** (cada recuerdo produce preguntas cuya respuesta es él mismo: por sus alias, sustantivos clave, dimensiones y paráfrasis), más los casos QA. Pueden ser **millones de ejemplos**. Se respeta la regla de no registrar el uso del agente.
5. **Entrenamiento pesado, ejecución ligera:** los millones de datos se usan **al entrenar**; la neurona que corre en el motor sigue siendo pequeña, de tiempo constante y explicable.

### 2.3 Los seguros (como la primera neurona, o más)

- **Piso:** el ranking a mano sigue siendo la base. La neurona **suma** sobre él hasta un techo y nunca lo reemplaza ("el ranking no se toca").
- **Techo y guardia:** límite de cuánto puede mover; se apaga sola si se sale de lo seguro.
- **Examen sellado:** se evalúa con preguntas que nunca vio.
- **Compuerta QA:** **nunca baja el recall**; la tabla de Dennys es el suelo. En cualquier base: snapshot, viva y bases nuevas.
- **Desde una base vacía:** funciona sin depender de un tamaño concreto.
- **Explicable:** cada subida al primer puesto se puede justificar.
- **Probar sobre copias:** nunca sobre una base real.

---

## 2b. La neurona de razonamiento: la brújula (Dennys, 2026-10-26)

> *"El ser humano tiene algo que razona, porque entiende qué le quieren pedir. El cerebro lo hace con sinapsis, química y electricidad; nosotros tenemos que traducir eso al plano en el que estamos."*

**Equivalente biológico:** la **corteza prefrontal**. No guarda los recuerdos; mantiene **el objetivo** ("qué me están pidiendo") y desde arriba **inclina** al hipocampo para que gane el recuerdo que sirve. Esa es la función que hay que traducir.

**Qué haría en BioRAG:** antes de buscar, convierte el texto del agente en una **intención estructurada**:

| Pieza de la intención | Ejemplo |
|---|---|
| **Qué** (tema o familia) | "versión de BioRAG", "el vaso" |
| **Cómo** (tipo de pedido) | la última · todas · cuándo · por qué · cómo se hace · lo contrario |
| **Alcance** | uno solo · unos pocos · seguir hilando (P4, P7) |

El motor usa esa intención para decidir qué subir al primer puesto. La neurona de intención de §2 es la que **ejecuta** ese plan sobre los candidatos.

### Tres caminos para conseguirla

| Camino | Ventaja | Riesgo |
|---|---|---|
| **A. Traerla entrenada de internet** (un modelo de lenguaje pequeño en español) | Ya "entiende" idioma | Es una red pesada frente a la regla "nada pesado"; no sabe nada de BioRAG; depende de terceros (licencia, tamaño) |
| **B. Construirla desde cero** | Es nuestra, pequeña y explicable | Necesita muchísimos ejemplos para entender lenguaje |
| **C. Destilación: una IA grande enseña, una neurona pequeña aprende** | La IA grande genera y etiqueta **millones** de pedidos fuera de línea; la neurona pequeña aprende a imitarla y corre dentro del cerebro en tiempo constante | Hay que diseñar bien qué aprende y examinarla con preguntas que nunca vio |

**Recomendación del auditor:** el camino **C**, porque traduce la "química" de un modelo grande a nuestro plano (pequeño, rápido, con seguros) sin meter una red pesada en el motor. El camino A puede servir **solo como maestro** de C, no dentro del motor.

**Requisitos:** los mismos seguros de §2.3. Además:
- si la neurona no está segura de la intención, **no decide**: el motor sigue con el ranking a mano;
- la decisión final entre A, B y C es de Dennys, cuando lleguemos (después de E4).

---

## 2c. Cómo evita el cerebro que lleguen 500 recuerdos (y qué copiamos)

Pregunta de Dennys: *"¿qué sistema hay detrás que evita que, al recordar, compitan 100, 200 o 500 recuerdos parecidos? Yo siempre traigo el mismo recuerdo porque tiene características que otros no tienen."*

La intuición es correcta. La neurociencia lo explica con cinco mecanismos que trabajan juntos:

| Mecanismo (cerebro) | Qué hace | Equivalente en BioRAG | Estado |
|---|---|---|---|
| **Separación de patrones** (giro dentado del hipocampo) | Guarda experiencias parecidas con códigos **distintos y escasos**: pocas neuronas por recuerdo | Concepto único, sustantivos clave, dimensiones | Existe; los enlaces por alias que unen todo (45 %) **van en contra** de esto |
| **La pista con más rasgos diferenciadores gana** (diagnosticidad de la pista) | Pesa lo que distingue, no lo que comparten todos | Rareza de las palabras de la consulta | Parcial |
| **Sobrecarga de pista** (efecto abanico) | Una pista unida a muchos recuerdos se debilita sola: "biorag" no sirve para elegir entre 200 | Hoy "biorag" tiene 170 dueños en el snapshot y 203 en la viva | Por medir y corregir (E4) |
| **El contexto es parte del recuerdo** (especificidad de codificación, Tulving) | Se recuerda mejor cuando la pista trae el mismo contexto con que se guardó | Dimensiones, motivo del recuerdo (P5) | Existe |
| **Competencia con inhibición** (corteza prefrontal) | El ganador **apaga** a los rivales parecidos (olvido inducido por recuperación) | Ranking + abstención; neurona de razonamiento (§2b) | Parcial |
| **Recencia y frecuencia** (ACT-R) | Lo usado hace poco o muchas veces está más disponible | ACT-R ya existe en el olvido, pero casi no ordena (P2) | Por hacer (vigencia) |
| **Recuerdo por pasos** | No llegan 500: llega uno, trae pistas y se va hilando (memoria de trabajo limitada) | Recuerdo escalonado y ráfaga natural (P4, P7) | Por hacer |

**¿Y si dos recuerdos tienen las mismas características?** También pasa en el humano. Por ejemplo, "¿dónde dejé el carro hoy y dónde ayer?". El desempate lo dan el **tiempo** (el más reciente) y el **contexto**. Cuando ni eso alcanza, el humano confunde o mezcla. Por eso la vigencia y el contexto son piezas obligatorias, no adornos.

**Lección para el diseño:** el cerebro no evita la competencia teniendo "infinitas" características. La evita **guardando separado** lo parecido, **debilitando** las pistas comunes, **usando el contexto y el tiempo** y **dejando que un ganador apague** a los demás.

---

## 2d. La clave según Dennys: saber que lo buscado COINCIDE con el recuerdo (para después)

> *"Un mismo recuerdo puede tener las mismas señales de hacer match, pero ¿qué lo separa? No es tanto separarlo, sino **cómo saber que lo que se quiere buscar coincide con el recuerdo**. Ahí es donde está la clave. Lo tenemos que emular, sintetizar eso a nuestro sistema. Si lo logramos, tendríamos esto resuelto."*
> **Estado:** anotado para conversarlo y hacerlo **después** del trabajo actual (E2–E4). No se mezcla con lo que se está haciendo.

**Diagnóstico de Dennys:** el sistema léxico no es malo; **no se ha podido calibrar como tiene que ser**. El cerebro también trabaja con señales, pero sabe **cuál coincide de verdad**.

### Los cuatro mecanismos que hay que sintetizar

(Explicación traída por Dennys de otra IA, contrastada con §2c.)

| # | Mecanismo del cerebro | Qué hace | Traducción posible a BioRAG |
|---|---|---|---|
| 1 | **Separación de patrones** | Lo casi idéntico se guarda en neuronas distintas, como un código de barras: un solo dígito distinto lo hace otra cosa | Al guardar: **cada recuerdo con su firma única** (lo que lo distingue de sus vecinos), no solo sus palabras |
| 2 | **Compleción de patrones** | Con una fracción de la pista se enciende **el recuerdo completo** | Al buscar: **medir el encaje del patrón completo** (cuánto de la pista explica el recuerdo y cuánto del recuerdo explica la pista), no sumar coincidencias sueltas |
| 3 | **Inhibición lateral** ("el rey de la colina") | El recuerdo que mejor encaja **apaga** a sus vecinos parecidos | El ganador claro **baja a sus rivales parecidos**; si no hay ganador claro, se dice (abstención o desempate por tiempo y contexto) |
| 4 | **Olvido inducido por recuperación** | Tras elegir A sobre B, el cerebro debilita a B para el futuro | **Con cuidado:** choca con las reglas "sin feedback" y "sin registrar el uso del agente". Solo se haría como **consolidación al dormir** sobre la propia base, nunca espiando al agente, y con el OK de Dennys |

### La pregunta que hay que responder con pruebas

Hoy el motor suma señales (palabras, sinónimos, dimensiones, grafo) y gana quien suma más. El cerebro no suma: **verifica el encaje**. La pregunta para el trabajo futuro:

> **¿Cómo sabe el motor que la consulta coincide con ESTE recuerdo y no con su vecino que comparte las mismas señales?**

Candidatos a estudiar, en orden:
1. **Firma diferenciadora por recuerdo** (lo que solo él tiene frente a sus vecinos más cercanos), calculada al guardar o al dormir.
2. **Encaje en las dos direcciones** (pista → recuerdo y recuerdo → pista), con penalización por lo que la consulta pide y el recuerdo **no** tiene.
3. **Inhibición entre vecinos** en el top final: si dos candidatos se parecen mucho, gana el que tiene la firma que la consulta menciona.
4. Una neurona que **aprenda a verificar el encaje** (la "neurona de razonamiento" de §2b, con los seguros de §2.3).

**Mismas reglas de siempre:** QA primero; cada cambio aislado; nunca bajar el recall; igual en cualquier base; experimentos sobre copias.

---

## 2e. Si el cerebro fuera un buscador: los tres pasos (para después)

> Idea de Dennys (2026-10-27): *"hay que emular esto: buscar, agregar lo que nos faltaría o usar lo que tenemos para sintetizarlo"*. Se guarda como idea para después de E2–E4.

Explicación traída por Dennys de otra IA. Ante una consulta, el cerebro hace en milisegundos:

1. **Filtra por contexto, no por palabra suelta.** La prefrontal agrega un "filtro invisible": dónde estás, cómo te sientes y la conversación reciente. Por eso "banco" ya sabe si es para sentarse o para el dinero.
2. **Activa todo en paralelo y pondera.** Cada rasgo compartido suma, y el recuerdo con más encaje recibe una "descarga masiva".
3. **Inhibe el ruido.** Apenas el ganador toma la delantera, apaga a los competidores que compartían las mismas palabras.

No lee archivo por archivo: el contexto reduce las opciones y el ganador aplasta a los demás antes de llegar a la conciencia.

### Qué tenemos, qué falta y con qué se sintetiza

| Paso del cerebro | Qué ya tiene BioRAG | Qué falta | Cómo sintetizarlo (a estudiar) |
|---|---|---|---|
| **1a. Contexto que trae el que pregunta** | El agente envía dimensiones y sustantivos clave (P5, P6) | Medir cuánto pesan de verdad al ordenar | Que la intención (§2b) los use como filtro, no solo como suma |
| **1b. Contexto de la conversación reciente** | Existe `corto_plazo` (lo recién guardado, antes de dormir) | Un "foco" de la sesión que incline la búsqueda hacia el tema en curso (por verificar en el código si algo así ya existe) | Foco **solo en memoria y solo durante la sesión**, sin registrar el uso del agente (regla de Dennys). Si guardar algo choca con esa regla, se consulta antes |
| **2. Activación en paralelo y ponderación** | **Existe:** la fórmula de 14 señales y el grafo de sinapsis | La "descarga masiva": hoy el ganador gana por poco y no se amplifica | Amplificar la diferencia cuando un candidato encaja claramente mejor (sin tocar los pesos a mano: se suma encima, con piso y techo) |
| **3. Inhibición del ruido** | Parcial: la abstención ("saber que no sabe", FP 0/40) | El ganador no apaga a sus vecinos parecidos | Inhibición entre vecinos en el top final (§2d, punto 3), con desempate por tiempo y contexto |
| **Consulta ambigua** | La abstención | Decir *por qué* es ambigua y entre qué opciones | Devolver las opciones distintas (no 500 parecidas) para que el agente pregunte o elija |

**Relación con lo anterior:** el paso 2 es lo que hoy hace el motor. Los pasos 1 y 3 son lo que nos falta para que funcione como un cerebro. La verificación del encaje (§2d) es lo que une los tres.

---

## 2f. Cuando dos recuerdos comparten TODAS las palabras: coordenadas, no etiquetas (para después)

> Dennys (2026-10-27): *"Yo ya había intentado resolver esto con los sustantivos clave. Pero puede pasar que dos recuerdos tengan los mismos sinónimos, sustantivos clave y palabras clave. ¿Cómo se soluciona?"*
> *"De aquí saldrá la clave de nuestro problema. Hay que experimentar lo que más posibilidades tenga."*
> **Estado:** guardado para experimentar **después** de E2–E4.

### Lo que explicó la otra IA (resumen fiel)

1. **El cerebro no busca por palabras, sino por coordenadas.** Al guardar, el hipocampo crea una **firma multidimensional**: las palabras más **cuándo** pasó, el **estado interno** (hambre, ritmo, qué pensabas justo antes) y el **contexto**. Dos recuerdos con "mamá, comida, cocina" quedan en sitios distintos del mapa.
2. **Geometría.** Dos recuerdos pueden compartir algunos ejes (las palabras) y separarse mucho en otros (contexto, orden, emoción).
3. **El orden de disparo (código de fase).** "Guardar las llaves en la mesa al llegar" y "buscarlas en la mesa al salir" tienen los mismos sustantivos. Los separa **el orden de los hechos** y el ritmo cerebral (ondas theta y gamma).
4. **Conclusión de la otra IA:** cuando las palabras empatan, desempatan **el tiempo, el estado del momento y el orden de los hechos**.

**Nota del auditor:**
- La idea central (codificación relacional y contexto temporal) es ciencia establecida.
- La imagen de "vectores en un espacio tridimensional" es una simplificación.
- El papel exacto del código de fase al desempatar recuerdos sigue en investigación.
- Para BioRAG no hacen falta vectores: las **coordenadas pueden ser simbólicas**.

### Traducción a BioRAG: las coordenadas que ya tenemos y las que faltan

| Coordenada del cerebro | Qué hay hoy en BioRAG | Estado medido |
|---|---|---|
| **Qué** (palabras, sustantivos clave, sinónimos) | Sí: es casi todo lo que usa el ranking | Es justo la coordenada que empata |
| **Cuándo** (firma de tiempo) | `creado_en`, `ultimo_uso`, familias de versiones | Existe, pero casi no ordena: recencia 0,04 (P2, vigencia) |
| **Relación: quién hizo qué a qué** (el verbo separa "guardar" de "buscar") | Tabla `predicados` (sujeto, acción, objeto, contexto) y señal nº 12 | **Parcial:** en el snapshot hay 187 predicados en **102 de 866** recuerdos (12 %). La señal compara palabras sueltas, **no los papeles** (sujeto, acción, objeto) |
| **Contexto y motivo** (para qué se guardó) | Dimensiones semánticas | Existe; por medir cuánto separa |
| **Orden de los hechos** (antes y después) | Por verificar en el código si hay enlaces "antes/después" entre episodios | Desconocido |
| **Estado interno** (qué se estaba pensando) | El proyecto o la sesión en curso (ver §2e, foco de la conversación) | No existe |

**Regla que se deduce:** si dos recuerdos coinciden en **todas** las coordenadas (qué, cuándo, relación, contexto), no son dos recuerdos: es **el mismo** repetido, o **una versión nueva** del mismo. Eso no lo arregla el buscador, sino la consolidación (fusionar) o la vigencia (quedarse con el último).

### Experimentos, ordenados por posibilidad de éxito

1. **Coordenada "cuándo":** desempatar por tiempo dentro de la misma familia (vigencia). Ya hay un fallo medido: v32.3 frente a v35.0.
2. **Coordenada "relación":** medir si comparar sujeto, acción y objeto (no palabras sueltas) separa casos que hoy empatan. Antes hay que ampliar la cobertura de predicados del 12 % (con cuidado: el backfill de 2026-08-04 ya demostró que puede canibalizar el re-ranking jaccard).
3. **Firma diferenciadora** (§2d): lo que solo tiene ese recuerdo frente a sus vecinos.
4. **Orden de los hechos:** solo si se confirma que existe o que se puede construir sin registrar el uso del agente.

Mismas reglas: QA primero, un cambio cada vez, nunca bajar el recall, igual en cualquier base, experimentos sobre copias.

---

## 2g. Caso real: "la última versión" (Dennys, 2026-10-27)

> *"Debemos conseguirle la lógica a todo e implementar un sistema adecuado, bien sea que exista o adaptando lo que tenemos, para solucionar esto de una buena vez. El truco está entre lo que manda obligatoriamente el agente en el MCP y el motor."*

### La prueba (consulta real por MCP sobre la base viva)

El agente llamó a `biorag_recordar` así:
- `query="biorag version ultima orden nodos externos"`;
- `rafaga_palabras` con 11 palabras;
- 4 paráfrasis (reglas, protocolo, patrón exitoso, preferencias de Dennys);
- `sustantivos_clave=biorag,version,nodos,orden`;
- `forzar_rafaga=true`.

| # | Recuerdo devuelto | Score | ¿Es el vigente? |
|---:|---|---:|---|
| 1 | `version_actual_biorag_v34_0_20261024` (v34.0) | 0.5398 | no |
| 2 | `version_actual_biorag_v32_4_20261007` (v32.4) | 0.4671 | no |
| 3 | `version_actual_biorag_v32_3_20261003` (v32.3) | 0.4645 | no |
| **4** | **`version_actual_biorag` (v35.0)** | 0.4614 | **SÍ: el que se quería** |
| 5 | `version_actual_biorag_v26_3_20260811` (v26.3) | 0.4181 | no |

El agente "supo" la respuesta correcta (v35.0) porque leyó el contenido, pero **el cerebro no la entregó primero**.

### Por qué falla: tres capas (análisis del auditor)

**1. Los datos no dicen cuál está vigente.**
- El diseño es actualizar el nodo canónico `version_actual_biorag` en su sitio. Está documentado en el recuerdo `decision_diseno_actualizar_nodo_canonico_no_reordenar_por_recencia`.
- Las versiones archivadas **conservan "actual" en su nombre** (`version_actual_biorag_v34_0...`), así que compiten como si fueran actuales.
- **No existe una fecha de "última actualización"**: la tabla `largo_plazo` solo tiene `creado_en` y `ultimo_acceso`. Verificado en el snapshot: el canónico es **el más viejo** de su familia (creado 2026-07-04), mientras los archivados son posteriores.
- **Consecuencia comprobada en el código:** `ordenar_por="recencia"` ordena por `creado_en` (`core/memory/search.py:2121`), así que pondría el canónico **el último**. El diseño "actualizar en su sitio" y la recencia por creación se contradicen.

**2. El motor trata "última" como una palabra más.**
- "Última", "actual" y "vigente" no se interpretan como **intención** (P3).
- La recencia pesa 0,04.
- Ya estaba medido en §6 del mapa (v32.3 en el #1 y v35.0 en el #4): es el mismo fallo.

**3. El contrato agente → MCP no tiene un canal para la intención.**
- El agente no puede decir "quiero el vigente". Solo puede añadir palabras.
- Lo que añadió fue ruido (*orden, nodos externos*, paráfrasis de reglas y preferencias). Medido en E2: **una sola palabra que no aplica baja el recuerdo correcto del 1º al 4º.**

### Solución propuesta (por capas, para decidir con Dennys después de E2b)

| Capa | Qué | Quién lo hace | Riesgo |
|---|---|---|---|
| **A. Datos: vigencia explícita** | Una fecha de **última actualización del contenido** y una relación **"reemplazado por"** desde cada versión archivada hacia el canónico, creadas al guardar (sin borrar nada) | El motor, al ejecutar `aprender` | Bajo (solo añade). Requiere cambiar el esquema → OK de Dennys |
| **B. Contrato MCP: el agente declara la intención** | Un modo `ordenar_por="vigente"` (o un parámetro de intención temporal). El prompt enseña: *"la última / la actual / la vigente" → vigente* | El agente (metacognición: él ya sabe lo que pide el usuario) | Muy bajo. Es determinista y no toca el ranking a mano: reordena la familia ya encontrada |
| **C. El cerebro lo entiende solo (respaldo)** | Si el agente no lo declara: primero una lista cerrada de palabras de intención (piso a mano); después, la **neurona de vigencia** (§6.2 del mapa) aprende la familia en el tiempo | El motor | Medio. Va con los seguros de §2.3 |
| **D. Ruido en la consulta** | Que las palabras que no aplican no tumben al correcto | El motor (resultado de E2b) | Se decide con los datos de E2b |

**Orden recomendado:** **A + B primero**: dan el resultado correcto de forma determinista y en cualquier base. Luego **C**, para que el cerebro lo entienda aunque el agente no lo diga. **D** sale de E2b.

**Prueba de aceptación:** esta misma llamada debe devolver `version_actual_biorag` en el **#1**, tanto en el snapshot como en la viva, sin que baje ninguna cifra de la QA. Antes de construir nada, se mide sobre una copia de la viva qué devuelven hoy `ordenar_por="recencia"` y la consulta sin ruido. Eso confirma o descarta la capa 1.

### Propuesta externa evaluada: tres parches (2026-10-27)
Otra IA acertó en el diagnóstico (semejanza conceptual frente a relevancia de intención), pero propuso tres parches. El auditor los rechaza tal como vienen, porque son reglas para este caso y no sirven para cualquier base:

| Parche propuesto | Por qué no así | La versión general que sí |
|---|---|---|
| **"Veto atómico":** si la pregunta trae "última / versión / actual / orden", bajar los términos "históricos" | Lista fija de palabras y "histórico" sin definir. En otra base u otro idioma no sirve | Los síntomas de la pregunta entran como señales que la capa 2 aprende (§2l, §2n) |
| **Decaimiento ×0,65** a los nodos con fecha en el nombre (`_20261024`) | Depende de cómo se nombró el recuerdo: el canónico gana solo porque no tiene fecha en el nombre. Y hundiría a v34 cuando la pregunta es "¿qué se hizo en la v34?" | Fecha de modificación real (C1) + familia (§2j), aplicada **solo** si se pide "la última" |
| **`is_canonical` con piso fijo** | Etiqueta a mano y empujón fijo: rompe "el ranking no se toca" y no escala | Contención de identidad (§2j) + estado "vigente" escrito al guardar (§2n) |

**Dos causas medidas que esa propuesta no ve:**
1. **C8, el temático:** el canónico no recibe esa señal por su coincidencia de alias, y v34 sí. Es la misma señal que se investiga en **E2d** (siempre da 1,0). Arreglarla de raíz puede ayudar a este caso sin ningún parche.
2. **El ruido en la consulta:** el agente escribió "biorag version ultima **orden nodos externos**". Tres de esas palabras no hablan de la versión. E2b midió que cada palabra de más puede tumbar al recuerdo bueno. Es parte de "una sola mente": el agente debería separar la pregunta de la versión de la pregunta del orden.

---

## 2h. Investigación a fondo: ¿qué separa dos recuerdos que comparten todo? (2026-10-27)

### Lo que pidió Dennys (resumen fiel)

- *"Tienes un nodo y otro que comparte las mismas palabras, todo igualito. ¿Qué lo diferencia?"* Esto no pasa solo con las versiones: pasa con dos, tres o más recuerdos que compiten porque tienen las mismas palabras. Dennys lo intentó con los sustantivos clave, pero también pueden coincidir.
- **Cómo descarta un humano:** *"los otros recuerdos hablan de lo que busco, mencionan lo que busco, pero tienen otras cosas que no tienen que ver"*. Gana **"el que más simple tiene que ver con lo que estoy buscando"**; los demás son complementarios.
  - Ejemplo de la playa: viaje + playa + "la pasé muy rico" descarta los viajes a la playa sin esa vivencia. Si hubo cinco viajes buenos, desempata **el último que se guardó**.
- **El taller:** *"¿cuál fue la última vez que clavé clavos?"* Las actividades se solapan; debe salir la última **guardada**, no la última **a la que se accedió**.
- *"Lo último que traes a la mente se empodera, y es verdad"* (Dennys lo emuló así), *"pero en este caso falla, porque no fue lo último que se guardó"*.
- *"Si guardaste un nodo que habla de la versión pero trata de otra cosa, aparecería por encima del canónico. Ahí falta algo y no lo deduzco."*
- **Instrucción:** *"No hacerlo a la ligera. Si lo haces a la ligera, conseguirás los primeros que te salgan."*

### 1. La prueba reproducida sobre la base viva (dump del 2026-10-26, copia)

Llamada idéntica a la del agente (`biorag_recordar`, mismos parámetros) sobre una copia de la viva. **Se reproduce exactamente**: v34.0 0.5398, v32.4 0.4671, v32.3 0.4645, `version_actual_biorag` 0.4614 (puesto 4), v26.3 0.4181.

Variantes medidas (cada una sobre una copia nueva):

| Llamada | Puesto del canónico `version_actual_biorag` | Qué sale el #1 |
|---|---:|---|
| La real (ruido + ráfaga + paráfrasis) | **4** | v34.0 |
| La real con `dias=30` | **4** | v34.0 (la ventana no lo saca) |
| La real con `ordenar_por="recencia"` | **4** | v34.0; con ráfaga **el orden no cambió a fechas** (observado) |
| `"biorag version ultima"` (limpia) | **2** | `ultima_version_biorag`, **un nodo viejo que dice v32.3** |
| Limpia con `ordenar_por="recencia"` | fuera del top 6 | v34.0, y luego recuerdos **ajenos pero recientes** (linkedin, recetas…) |
| `"version actual biorag"` | **1** (score 1.0) | el canónico |

**La última fila explica el diseño original:** el recuerdo `decision_diseno_actualizar_nodo_canonico_no_reordenar_por_recencia` (2026-08-11) dice que el canónico gana **por coincidencia exacta del nombre** (piso 0,95). Funciona si el agente escribe "versión **actual**". Si escribe "**última**", ya no.

### 2. Las causas encontradas (verificadas, no supuestas)

| # | Causa | Prueba |
|---|---|---|
| C1 | **Actualizar un recuerdo no deja fecha de "último guardado".** `actualizar` solo cambia `creado_en` si `sobrescribir=True`; la fusión al dormir solo toca `ultimo_acceso` | En la viva, el canónico ya dice **v35.0**, pero su `creado_en` es **2026-10-14**. Más viejo que v34.0 (2026-10-24) |
| C2 | **`ultimo_acceso` no significa "lo último que recordé".** Cada evocación lo pone también en **todos los vecinos** por sinapsis (`search.py:2529`) | Casi toda la familia de versiones tiene `ultimo_acceso` = 2026-10-25 18:55–18:56: el mismo minuto |
| C3 | **La señal de recencia de la fórmula está muerta.** `temporal` (peso 0,04) nunca se pasa: siempre vale 0 | Ninguna llamada a `_calcular_score_hibrido` le pasa `temporal` |
| C4 | **`ordenar_por="recencia"` ordena todo el conjunto, no la familia** | Trae recuerdos ajenos pero recientes por encima (tabla anterior). Es exactamente lo que temía Dennys |
| C5 | **Hueco léxico: "última" ≠ "actual"** | Con "actual" el canónico sale #1; con "última", #2 a #4 |
| C6 | **Tres recuerdos "generales" dicen ser el actual:** `version_actual_biorag` (v35), `ultima_version_biorag` (v32.3, viejo) y `biorag_version_11_0`. Además, los archivados conservan "actual" en el nombre | Al guardar nadie decidió "¿nuevo o actualización?" |
| C7 | **Los sustantivos clave del canónico no dicen qué es** | `version,biorag,protocolo,sustantivos`: **idénticos** a los de v33.0. No dicen "vigente" ni "actual" |
| C8 | **Ruido de la consulta + castigo oculto del temático** | El canónico tiene `sinonimos_ratio`=0,5, así que temático=0 (castigo de E2); v34 cobra temático 1,0 y dimensiones 0,83 frente a 0,53 |

**Conclusión honesta:** no hay una sola causa ni un solo truco. Son **tres capas** que fallan a la vez: lo que se **guarda** (C1, C2, C6, C7), lo que el agente **pide** (C5, C8) y cómo el motor **elige** (C3, C4).

### 3. Prueba de la idea "gana el más simple" (exceso de rasgos)

Dennys propone que gana el que menos "cosas que no tienen que ver" tiene. Se midió sobre esta familia el **exceso**: rasgos de identidad del recuerdo (nombre + sustantivos clave) que la consulta no pide.

| Recuerdo | Exceso | Creado |
|---|---:|---|
| `biorag_version_11_0` | **0,00** | 07-04 (v11, viejísimo) |
| `ultima_version_biorag` | **0,00** | 10-04 (dice v32.3) |
| `version_actual_biorag_v26_3` | 0,50 | 08-11 |
| `version_actual_biorag` (el correcto) | 0,60 | 10-14 |
| `..._v34_0` | 0,67 | 10-24 |

**Resultado:** la idea es buena para **descartar lo que trata de otra cosa** (la comparativa con TencentDB y la decisión de diseño quedan al fondo). Pero **sola no basta**: los recuerdos "más simples" son generales **y viejos**. Hace falta el segundo paso de Dennys, **desempatar por el último guardado**, y para eso falta la fecha (C1).

### 4. Qué dice la ciencia (fuentes)

| Hallazgo | Fuente | Qué copiamos |
|---|---|---|
| No importa cuánto coincide la pista, sino su **valor diagnóstico**: cuánto especifica **solo** al objetivo frente a los competidores | Nairne 2002; Goh & Lu 2011, *Memory & Cognition* ([link](https://link.springer.com/article/10.3758/s13421-011-0133-9)) | Puntuar **en relación con los rivales**, no en absoluto. Es la idea de Dennys del "exceso" |
| Recordar tiene dos fases: **recuperación controlada** (traer) y **selección posterior** (elegir entre los activados) | Badre & Wagner 2007, resumido en ([link](https://www.mindomax.com/proactive-interference-old-memories-never-die-they-attack)) | Un paso de **selección por meta** después de buscar |
| La recencia es **relativa al contexto actual**: lo reciente se parece más al contexto de ahora | Howard & Kahana 2002, TCM ([link](https://memory.psych.upenn.edu/files/pubs/HowaKaha02.pdf)) | Recencia **dentro de la familia del tema**, no en toda la base (C4) |
| Al recordar, la prefrontal **suprime los rasgos únicos de los competidores** | Wimber et al. 2015, *Nature Neuroscience* ([link](https://www.nature.com/articles/nn.3973)) | Inhibición de vecinos (§2d) |
| Con la tarea **"recuerda la asociación más reciente"**, el cerebro separa a los competidores en fases distintas del ritmo theta | Kerrén et al. 2022, *eLife* ([link](https://elifesciences.org/articles/80633)) | Elegir "lo más reciente" es un **proceso de control propio**, no un efecto secundario |
| Al guardar algo parecido a lo que ya existe: si la sorpresa es pequeña, **se actualiza** el recuerdo; si es grande, **se crea uno nuevo** | Teorías de estado latente ([link](https://pmc.ncbi.nlm.nih.gov/articles/PMC11259430/)); Sinclair & Barense ([link](https://learnmem.cshlp.org/content/25/8/369.full)) | **"¿Nuevo o actualización?" al guardar.** Es la raíz de C6 |

### 5. El sistema propuesto: "selección por meta" (general, no solo para versiones)

| Paso | Qué hace | Equivalente en el cerebro | Pieza |
|---|---|---|---|
| **0. Al guardar** | Decidir **nuevo o actualización**. Registrar la **fecha de última modificación del contenido** (columna nueva, solo añade). Las versiones viejas quedan unidas como **"estado anterior de"** el canónico, sin borrar nada | Actualización por error de predicción | Regla a mano + neurona que solo **propone** (§6.1 del mapa, punto 4) |
| **1. Traer** | La búsqueda de hoy (no cambia) | Recuperación controlada | Motor actual |
| **2. Agrupar en familias** | Juntar los candidatos que comparten la **identidad** de la consulta (nombre y sustantivos clave). Lo que solo la **menciona** en el texto no entra en la familia | Separación de patrones | Regla a mano |
| **3. Elegir por meta** | Si la meta es "la última / la actual / la vigente": dentro de la familia, gana **la modificación más reciente**. Si es "lo que más encaja": gana el de **mayor valor diagnóstico** (más coincidencia propia, menos exceso) | Selección prefrontal; recencia relativa al contexto | El agente declara la meta (parámetro MCP) o el motor la detecta (lista cerrada → neurona de intención §2b) |
| **4. Inhibir** | El ganador baja a sus casi duplicados | Supresión de competidores | §2d |

**Respuesta a "¿qué los separa?":**
- Las **palabras** solo dicen de qué **familia** es el recuerdo.
- **Dentro de la familia** separan tres cosas: la **meta** (qué se pide), el **valor diagnóstico** (lo que solo ese recuerdo tiene frente a los otros) y el **tiempo de guardado**, bien registrado.
- Y si dos recuerdos empatan en todo eso, el fallo está al guardar: o son el mismo, o uno es versión del otro.

**Dónde haría falta una neurona** (lo que una regla no alcanza):
1. Decidir si un texto libre pertenece a una familia aunque use otras palabras ("última" ≈ "actual" ≈ "vigente": léxico E3 + intención §2b).
2. Decidir al guardar si algo es nuevo o una actualización.

Lo demás son reglas a mano, rápidas y explicables.

### 6. Cómo se experimentaría (general, sin parches por caso)

1. **Suite de competencia generada desde cualquier base:** familias de 3 o más recuerdos que comparten identidad. Dos tipos de pregunta:
   - "**la última** de esta familia": lo correcto es la modificación más reciente;
   - "la familia + **un rasgo que solo tiene uno**": lo correcto es ese recuerdo.
   Mide R@1. Como se genera de la propia base, sirve igual en el snapshot, en la viva y en bases nuevas.
2. Medir **hoy** esa suite (línea base) en el snapshot y en la viva.
3. Probar **un paso cada vez**, en este orden: fecha de modificación (paso 0, solo datos) → familias + meta "última" (pasos 2 y 3) → valor diagnóstico → inhibición.
4. Cada paso: QA completa en las dos bases, sin bajar nada, sobre copias, con el OK de Dennys.

**Estado:** investigación terminada; **no se ha tocado código ni ninguna base**. Se retoma cuando el operario cierre la etapa actual (E2b), dentro de E4/E5.

---

## 2i. Idea de Dennys: el nodo principal siempre por encima de sus aristas (2026-10-27)

> *"Un nodo principal tiene aristas vinculadas a las demás cosas de ese nodo. Esas aristas nunca deberían aparecer por encima del nodo principal, ni al ordenar ni en la búsqueda. Siempre por debajo."*

**Datos de la viva (copia):**
- El canónico `version_actual_biorag` tiene **181 enlaces**, el mayor de su familia; v34 tiene 63, v32.3 tiene 24 y v32.4 tiene 28.
- Está unido por enlaces **manuales** a v34.0 (0,85 y 0,5), v32.4, v32.3, v32.2 y v26.4.
- En el top-10 de la búsqueda real hay 13 pares enlazados de 45 posibles.
- **Con esta regla, el canónico subiría al #1.**

**Opinión del auditor: idea prometedora. Es el paso 2–3 de §2h con un criterio concreto ("cabeza de familia"). Antes de construirla hay que resolver tres riesgos:**
1. **Las preguntas específicas.** En "¿qué se hizo en la v34?", la v34 debe ganar aunque esté enlazada al canónico. Excepción: si la consulta nombra algo que **solo** tiene la arista (por ejemplo, "v34"), la arista va primero. La regla aplica cuando se pide la familia en general.
2. **Quién es "principal".** No puede ser solo el número de enlaces:
   - ese número crece con la base;
   - el 45 % son enlaces de alias sin control;
   - en la viva hay un nodo con 629 enlaces que ni siquiera existe.
   Hay que definirlo de forma estable en cualquier base. Candidatos: que las aristas apunten a él con enlaces manuales o estructurales; que su nombre sea la raíz del de las otras; o que sea el más conectado **dentro de la familia encontrada**, no en toda la base.
3. **Los hubs genéricos.** Un nodo enorme ("biorag") no debe subir por encima de todo. Límites:
   - solo reordena dentro de los resultados ya encontrados (no trae nada de fuera);
   - solo si el principal también coincide con la identidad de la consulta.

**Lo que no resuelve sola:** `ultima_version_biorag` (que todavía dice v32.3) **no está enlazado** al canónico, así que seguiría compitiendo. Sigue haciendo falta limpiar al guardar (C6).

**Siguiente paso propuesto (con el OK de Dennys):** simulación de solo lectura, sin tocar el motor. Aplicar la regla sobre los resultados de la QA del snapshot y de la viva, y contar cuántos casos **ganan** y cuántos **pierden** el #1. Si pierde casos, ajustar los tres límites; si no pierde ninguno, pasa a experimento formal.

---

## 2j. La relación que ordena: contención de identidad + "bajar solo si se nombra lo que el hijo añade" (2026-10-27)

> Dennys: *"La clave está en el ordenamiento, en la relación que se usa para ordenar. Pero los otros nodos también son padres enlazados con otros; si digo que las aristas de un padre nunca pasan por encima, hay algo que no me cuadra."*

**Por qué no cuadra:** los enlaces del grafo son **simétricos**. Si A está unido a B, B está unido a A, así que todos son "padre" de todos. Con una relación simétrica se pueden formar grupos, pero **no se puede ordenar**. Para ordenar hace falta una relación con **dirección**: que diga quién está por encima de quién.

**La relación con dirección que ya existe en los datos: la contención de identidad.**
- A es padre de B si **toda la identidad de A está dentro de la de B**, y B añade algo más.
- Identidad = nombre y sustantivos clave.
- Ejemplo: `version_actual_biorag` ⊂ `version_actual_biorag_v34_0_…`. La v34 es "la versión actual de biorag" **más "v34"**.

Medido en la viva (solo lectura): `version_actual_biorag` y `ultima_version_biorag` resultan **padres** de v34, v33, v32.4, v32.3 y v26.3. Coincide con los enlaces manuales que había puesto el agente.

**La regla de orden (propuesta):**
1. Se parte de los recuerdos cuya identidad está **completa** en la consulta. Ese es el nivel que se pide.
2. **Se baja a un hijo solo si la consulta nombra lo que ese hijo añade** sobre su padre ("v34"). Si no lo nombra, los hijos van **debajo** del padre: es la idea de Dennys, pero relativa a la consulta.
3. Entre hermanos del mismo nivel, desempata **el último guardado** (fecha de modificación).

**Comprobación sobre los nodos reales:**

| Consulta | Nivel pedido | Resultado de la regla |
|---|---|---|
| `biorag version ultima orden nodos externos` (la real) | `version_actual_biorag` y `ultima_version_biorag` (hermanos) | Desempate por fecha → **`version_actual_biorag`** ✓ (hoy sale #4) |
| `biorag version ultima` | igual | **`version_actual_biorag`** ✓ (hoy sale #2) |
| `qué se hizo en la versión v34` | la consulta nombra "v34", lo que añade el hijo | Se baja → **v34** ✓ |

**Condiciones honestas (sin ellas falla):**
- **Puente léxico "última" ≈ "actual" ≈ "vigente"** (E3). En la prueba se puso a mano. Sin él, el único padre completo es `ultima_version_biorag`, que dice v32.3, y ganaría el viejo.
- **Sustantivos clave que digan la identidad de verdad.** Los del canónico (`protocolo, sustantivos`) no la dicen; en la prueba se usó solo el nombre.
- **Fecha de modificación real** para desempatar entre hermanos (C1). Aquí funcionó con `creado_en` por casualidad: el 10-14 es posterior al 10-04.
- Los números de versión deben normalizarse ("v34" = "34").

**Ventajas frente a "el principal arriba" por número de enlaces:**
- No depende del número de enlaces, ni de los alias sin control, ni del tamaño de la base.
- El nodo gigante "biorag" no sube por encima de todo: en cuanto la consulta nombra "version", que es lo que añaden sus hijos, se baja a ellos.

**Siguiente paso (con el OK de Dennys):** la simulación de solo lectura sobre la QA del snapshot y de la viva (ganan / pierden el #1), ahora con esta regla.

**Objeción de Dennys (2026-10-27):** *"Si caigo en un nodo y sus aristas no pueden estar por encima, pero lo que busco está en las aristas y no en ese nodo…"*

Respuesta: por eso la regla **no es fija**, sino relativa a la consulta.
- **Si la consulta nombra lo que la arista añade** ("v34", o "neurona" si está en sus sustantivos clave), se baja a esa arista y **va primero**.
- **Si no lo nombra**, el padre va primero y sus aristas **justo debajo** (puestos 2 a 5), no perdidas en el 50. Es el recuerdo escalonado (P4): primero lo general y enseguida el detalle.
- **Condición:** que cada recuerdo diga en sus sustantivos clave lo que lo distingue de su padre. Si no lo dice, nadie puede bajar a él, ni humano ni motor.

---

## 2k. Reentrenar la neurona de ranking para que ordene "por lo que se intenta averiguar" (2026-10-27)

> Dennys: *"El cerebro no necesita recuperar simplemente algo relacionado con el problema. Necesita recuperar el recuerdo que mejor encaja con lo que intentas averiguar en este momento. Ahí está el entrenamiento de la neurona."* (Idea contrastada con otra IA, que revisó el repositorio.)

### Lo que la neurona ve y aprende hoy (verificado en el código)

- **Entradas por candidato:** las 17 "agujas" de la fórmula (`core/memory/neurona.py:242`) más lo que pasa después (bono de convergencia, evidencia por campo, peso, origen, si el agente mandó sustantivos). **No ve la intención de la consulta ni la familia.** *(Corrección 2026-10-27: sí recibe una señal de tiempo, `episodio_score`, entre las 17 agujas. Lo que le falta es relacionar la intención temporal de la pregunta con el tiempo del candidato.)*
- **Una de sus 17 agujas está muerta:** el temático vale 1,0 en el 100 % de los candidatos que lo reciben (medido en E2). **La recencia no existe** (C3).
- **Examen:** cada pregunta sale de **un** recuerdo y su respuesta es ese mismo recuerdo (`neurona_examen.py:145`). **Nunca le enseña** "mismo tema, distinta intención": no hay competidores difíciles de la misma familia.
- **Alcance:** reordena el top-5 a top-10. En el caso de la versión, el correcto estaba en el #4, **dentro de su alcance**. No lo subió porque **no tenía con qué distinguirlo**.

### Opinión del auditor

**La idea es correcta y es el sitio adecuado: la misma neurona, no una tercera.** Pero el orden importa: una neurona solo aprende de lo que ve. **Si se reentrena sin darle señales nuevas, aprenderá lo mismo.** Hacen falta dos cosas, en este orden:

**1. Darle ojos: señales nuevas, a mano, simbólicas y de tiempo constante** (salen de §2h y §2j):

| Señal nueva | Qué le dice | De dónde sale |
|---|---|---|
| Nivel en la familia | ¿Es el padre o un hijo? ¿La consulta nombra lo que añade el hijo? | Contención de identidad (§2j) |
| Exceso | Cuánto de su identidad **no** pide la consulta | §2h punto 3 |
| Recencia dentro de la familia | ¿Es la última modificación de su familia? | Fecha de modificación (C1) |
| Intención temporal | ¿La consulta pide "la última / la actual / la vigente"? | Lista cerrada primero (E3 / §2b después) |
| **Estado epistémico** | ¿Es verificado, hipotético u obsoleto? | **Ya existe**: la dimensión `epistemia` (`directa_experiencial, verificada, inferida, reportada_externa, hipotetica, obsoleta`), que el agente pone al guardar |

La última fila es la respuesta al ejemplo *"¿qué solución **no funcionó**?"*. La diferencia entre "hipótesis", "probado y funcionó" y "probado y falló" **no se puede deducir de las palabras**. Tiene que quedar dicha **al guardar**, y BioRAG ya tiene dónde: las dimensiones. Habría que ver si hace falta añadir "resultado: funcionó / falló". Una neurona que lea el texto libre para deducirlo es el camino C de §2b (destilación), para más adelante.

**2. Enseñarle con exámenes nuevos, generados desde cualquier base** (es la "suite de competencia" de §2h §6):
- "**La última** de esta familia" → la modificación más reciente.
- "La familia **en general**" → el padre.
- "La familia + **lo que solo tiene un hijo**" → ese hijo.
- "La familia + **verificado / hipotético / obsoleto**" → el que tiene ese estado.

Cada pregunta trae a **sus hermanos como competidores difíciles**. Así aprende *por qué* en una pregunta gana el padre y en otra el hijo.

**Reglas que no cambian:**
- Piso a mano, techo y guardia.
- Examen sellado con preguntas nunca vistas.
- Constante en el tiempo y funcional desde una base vacía.
- Sin embeddings.
- Cambiar las entradas obliga a **subir la VERSION de la neurona** y a reentrenar: los pesos actuales no valen para entradas distintas.
- Se compara contra el campeón actual. Solo se promueve si gana en la suite nueva **y** no baja nada en la QA oficial (snapshot y viva).

**Límite honesto:** la neurona solo reordena lo que el motor ya trajo al top-5 / top-10. Si el correcto no llega (EXP-Q: puestos 33 y 91), primero hay que garantizar que llegue (E4).

**Orden propuesto (con el OK de Dennys, después de E2b):**
1. Auditar el vector de entrada actual y retirar las agujas muertas, medido en las dos bases.
2. Construir la suite de competencia y medir la línea base de hoy.
3. Añadir las señales una a una, como fórmula a mano primero.
4. Reentrenar la neurona encima con los exámenes nuevos.
5. Comparar contra el campeón.

---

## 2l. La "capa definitiva": segunda neurona de ranking condicionada por la consulta (Dennys, 2026-10-27)

> **El problema en una frase (Dennys, 2026-10-27):** el sistema confunde **semejanza conceptual** con **relevancia de intención**. La capa definitiva es la neurona que, **en la etapa final de ordenar**, mira los candidatos que llegaron, entiende qué se quiere averiguar y pone en el **top-1** el recuerdo adecuado. Necesita dos cosas: que el correcto **llegue** a los candidatos (motor, E4) y que los recuerdos tengan su **tipo escrito** (§2n). Si las pistas no alcanzan para elegir, lo dice (empate real) en vez de inventar un ganador.

> Dennys: *"Pasarle la query original como una aguja más, porque es la única forma de que aprenda: cuando le escriban algo, sabrá qué es lo que se está buscando."*
> *"El re-ranqueo actual déjalo, está bien. Lo que vamos a sumar es otra capa definitiva."*
> *"Más neuronas ocultas, más parámetros, entrenarla con miles de millones de preguntas. Las puedes generar tú misma usando el MCP: invocas `recordar` con los parámetros obligatorios, ves lo que devuelve el motor de verdad y lo vuelcas como entrenamiento. Con mi base, con cualquier otra base, con bases armadas de internet. Así sirve para cualquier base, porque aprende a identificar en la query los síntomas del recuerdo más certero."*
> *"¿Cómo lo han hecho los demás? Hay que investigarlo."*

**Corrección del auditor a §2k:** el entrenamiento actual **sí** pone rivales. La pérdida compara al correcto contra todo el pool que devuelve el motor. Lo que falta son rivales **elegidos a propósito**: mismo tema, distinta intención.

### Cómo lo hace la industria (fuentes)

| Pieza | Quién / dónde | Qué copiamos |
|---|---|---|
| **Ranking en cascada**: etapas sucesivas, cada una más precisa sobre menos candidatos | Wang, Lin & Metzler, SIGIR 2011 ([Google Research](https://research.google/pubs/a-cascade-ranking-model-for-efficient-ranked-retrieval/)) | La capa 1 (neurona actual) queda intacta. La **capa 2** solo actúa sobre el top-5/10 que deja la capa 1 |
| **La consulta entra como interacción, no como texto**: una matriz "término de la consulta × término del documento" con coincidencias exactas y su posición, que la red resume a tamaño fijo. **Modelo local, sin embeddings** | Microsoft, Mitra, Diaz & Craswell 2017, modelo *Duet* ([PDF](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/10/wwwfp0192-mitra.pdf)) | Encaja con la regla "sin embeddings": la query entra como coincidencias por término y por campo |
| **Datos sintéticos**: generar preguntas para cada documento, pasarlas por el **buscador real** y usar lo que devuelve como **competidores difíciles** | InPars / InPars-v2 ([arXiv](https://arxiv.org/abs/2301.01820)), Promptagator | Es exactamente la idea de Dennys: generar con `recordar` del MCP y entrenar con lo que el motor devuelve de verdad |

### Diseño propuesto

**1. Cómo entra la query (la "aguja" de Dennys, hecha para que una red la pueda leer).** Una cadena de texto no es un número; si se pasa tal cual, la red no aprende nada. Se convierte en dos bloques de tamaño fijo:
- **Interacción consulta × candidato:** por cada término de la consulta (hasta N huecos), qué tipo de coincidencia tiene en cada campo del recuerdo:
  - campos: nombre, sustantivos clave, sinónimos, contenido, dimensiones;
  - tipos: exacta, raíz, sinónimo o ninguna;
  - también dónde aparece.
  Esto cambia **por candidato**, y es lo que le permite decidir cuál encaja mejor.
- **Síntomas de la consulta** (iguales para todos los candidatos, pero se combinan con lo anterior en la capa oculta):
  - superlativo temporal ("la última", "la primera");
  - negación o resultado ("no funcionó", "falló");
  - causa ("por qué");
  - general frente a específico (¿nombra lo que añade un hijo?);
  - pide estado ("vigente", "obsoleto").
- **Más las señales de §2k:** nivel en la familia, exceso, recencia en la familia y epistemia.

**2. Tamaño.** Más grande que la actual, pero sigue siendo pequeña: unas 100–150 entradas, 32–64 ocultas, **unos 5.000–10.000 pesos**. Corre en microsegundos y en tiempo constante, así que respeta "nada pesado".

**3. Datos de entrenamiento (camino InPars, adaptado):**
- **Generador programático** a partir de los metadatos de cada base: familias, fechas de modificación, epistemia, lo que distingue a cada hijo, paráfrasis por plantilla y errores de tipeo.
  - Cada pregunta se pasa por `recordar` del MCP **con los parámetros obligatorios** (sustantivos clave incluidos), sobre **copias**. Es como se reprodujo hoy el caso de la versión: mismos parámetros, scores idénticos.
  - Se guarda lo que ve la capa 2, para que entrene y sirva con lo mismo (desfase 0, como la neurona actual).
- **Bases:** la viva (copia, nunca se sube), el snapshot y **bases sintéticas** construidas con texto público en español de licencia libre. Así aprende *síntomas* y no las manías de una sola base.
- **Cantidad:** no hacen falta miles de millones. Para unos 10.000 pesos bastan **cientos de miles a pocos millones** de ejemplos. Lo que importa es la **variedad** (intenciones, familias, bases), no la cifra.
- **Límite honesto:** el auditor puede escribir a mano cientos o algunos miles de preguntas naturales, que quedan para el **examen sellado**. No hay acceso a un LLM para generar millones de paráfrasis de calidad; para eso está el generador programático.
- **Etiquetas solo donde son fiables:** "la última" se saca de la fecha; "el padre" de la contención; "el obsoleto" de la epistemia. **"Funcionó / falló" solo si quedó dicho al guardar**: lo que no se puede etiquetar no se entrena.

**4. Seguros de la capa 2 (los de siempre, más uno):**
- piso = el orden de la capa 1; techo; guardia; examen sellado;
- funciona desde una base vacía, sin embeddings;
- QA oficial sin bajar nada (snapshot y viva);
- **nuevo:** se evalúa en **bases que nunca vio al entrenar**. Esa es la prueba de que sirve "para cualquier base".

**5. Requisitos previos:**
- fecha de modificación (C1);
- suite de competencia (§2h §6) como línea base;
- y que el correcto **llegue** al top-10. Si llega en el 50, ninguna capa de ranking lo arregla (E4).

**Orden (con el OK de Dennys, después de E2b):**
1. Especificación de entradas y del generador.
2. Prueba en seco del generador sobre copias.
3. Línea base de la capa 1 en la suite.
4. Entrenar la capa 2.
5. Comparar con todos los seguros.

---

## 2m. Tres opiniones externas contrastadas + "el cableado de fábrica" (Dennys, 2026-10-27, para después)

Dennys trajo tres respuestas de otras IAs y pidió guardarlo para hacerlo después. Aquí está qué se adopta, qué no y por qué, contrastado con el código real.

**La frase que la capa 2 debe aprender (Dennys la marca como LA clave):**
> "El cerebro no necesita recuperar simplemente algo relacionado con el problema. Necesita recuperar el recuerdo que mejor encaja con lo que intentas averiguar en este momento."

Dicho en términos de ingeniería: la relevancia es una función de **(consulta, recuerdo)**, no del recuerdo solo. **La prueba que lo demuestra es el cambio de ganador:** con el MISMO grupo de candidatos, cuando preguntas distintas tienen **respuestas de referencia distintas** ("la última", "la primera", "la que falló", "la general"), el #1 debe ser el de cada una. Si dos preguntas tienen la misma respuesta correcta, el #1 no tiene por qué cambiar. *(Precisión aceptada de una revisión externa, 2026-10-27.)*

### Opinión 1: revisión del código (coincide con §2l)
- **Confirmado contra el código:**
  - 29 entradas y 6 ocultas;
  - la `frase` solo se usa en `_es_su_nombre()`;
  - el entrenamiento ya usa como rivales los candidatos del motor;
  - faltan los rivales **elegidos a propósito**: mismo tema, distinta intención.
- **Se adopta:**
  - auditar el vector de entrada completo antes de diseñar;
  - el campeón queda intacto mientras se prueba;
  - una batería de candidatos difíciles;
  - medir R@1, MRR, R@5 y FP en el snapshot y en una copia de la viva.
- **Se adopta y se subraya:** "verificada" no significa "funcionó"; una prueba también verifica un fallo. El resultado (funcionó/falló) tiene que quedar dicho al guardar para poder entrenarlo.

### Opinión 2: neurociencia (coincide con las fuentes de §2h)
- **Coincide con lo investigado:**
  - control de la búsqueda (PFC) + recuperación asociativa (hipocampo), en la línea de Badre y Wagner 2007;
  - lo que decide es lo que distingue al recuerdo de sus rivales, no solo el parecido (Nairne 2002; Goh y Lu 2011).
- **Dos ideas que se suman al plan:**
  1. **Separación de patrones al guardar.** Diferenciar los recuerdos parecidos en el momento de escribirlos (nuevo frente a actualización, qué añade cada hijo) es el paso 0 de §2h. Sin eso, la capa 2 no tiene con qué distinguirlos.
  2. **Verificar la ambigüedad.** Si la evidencia no alcanza para elegir, no se debe inventar un #1: se reconoce la ambigüedad y el agente sigue empujando con más pistas. Es el recuerdo por etapas (P3) y la "una sola mente" (P6). La capa 2 puede dar, además del orden, una señal de "empate real".
- **Rapidez no es exactitud:** lo primero que llega no siempre es lo correcto. Por eso se mide R@1 con preguntas de intención, no solo R@5.
- *Nota:* el trabajo de Nature Neuroscience de abril de 2026 que cita **no está verificado por el auditor**. No se usa como base.

### Opinión 3: atención y embeddings (genérica; solo sirve una parte)
- Describe cómo lo hacen los Transformers con vectores densos. **Choca con la regla de BioRAG:** sin embeddings y nada pesado.
- **Lo aprovechable, traducido a BioRAG:**
  - **Entrenamiento con tríos** (consulta, recuerdo correcto, recuerdo parecido pero incorrecto) y ajuste de pesos por el error: es exactamente la pérdida por pares con rivales difíciles de §2l.
  - **Correspondencia simbólica consulta↔candidato** (no se le llama "atención", porque no es ese mecanismo): cada término de la consulta se cruza con cada campo del candidato (nombre, sustantivos, sinónimos, texto) según el tipo de coincidencia. Es la matriz de interacción local de Duet (§2l), sin embeddings. Contar coincidencias no basta: un "no" en "la que no funcionó" cambia lo que se pide, y eso tiene que ser una señal propia.
  - Sus ejemplos ("la marcha del carro" frente a "marcha de protesta") son de **sentido de la palabra**. En BioRAG eso lo dan los sustantivos clave y las dimensiones (P4, moto frente a moto de agua), no un vector.
- **Se rechaza:**
  - embeddings densos (regla de Dennys);
  - aprender de clics o retroalimentación de uso (regla: nada de sistemas de feedback ni registro del uso del agente).

### El cableado de fábrica (la analogía de Dennys)
El cerebro nace con la infraestructura ya cableada y después solo se le mete información. En BioRAG:

| Cerebro | BioRAG |
|---|---|
| Cableado de nacimiento | El motor (SQLite + fórmula a mano): fijo, rápido y el mismo en cualquier base. |
| Instinto que viene de fábrica | La **capa 2 pre-entrenada** con miles de situaciones de muchas bases. Viaja **cerrada** en el repo, como la neurona asociativa, y funciona desde una base vacía. |
| Experiencia de vida | Los recuerdos de cada usuario: el contenido que llena el cableado. |
| Afinarse con la experiencia | Ajuste local opcional sobre su base, siempre con piso (capa 1), techo y examen sellado. |

Lo que viene de fábrica no es el contenido, sino **la habilidad de discernir**: leer los síntomas de la pregunta y elegir entre rivales parecidos. Por eso se entrena con muchas bases distintas y se examina en bases que nunca vio.

### La clave (respuesta a Dennys, 2026-10-27)

**1. La "pregunta" no es solo el texto: es todo lo que manda el agente.**
- `recordar` recibe query, paráfrasis, sustantivos clave, dimensiones, ráfaga, `ordenar_por` y `dias`/`desde`.
- El agente ya hace el trabajo de la corteza prefrontal: `prompt.py` le obliga a pensar qué busca antes de armar la query.
- Por eso la capa 2 debe leer **la pista completa**, no solo la frase. Es la "una sola mente" (P6): el agente decide la intención y la neurona la reconoce en los candidatos.

**2. Lo que decide no es lo que coincide, sino lo que distingue.**
- Si 5 candidatos comparten "biorag versión", esas palabras no ayudan a elegir y deben pesar casi cero.
- Lo que decide es la parte de la pista que **solo cumple uno de los rivales**: "última", "falló", "v34", la dimensión `intencion_aprender`...
- Es el valor diagnóstico relativo (Nairne 2002; Goh y Lu 2011, §2h). Por eso las entradas de la capa 2 deben ser **relativas al grupo de candidatos** (¿este cumple algo que los demás no?), no absolutas.
- Esto es lo que la neurona tiene que aprender a hacer: **mirar a los rivales para saber qué parte de la pregunta importa.**

**3. Búsquedas sin texto (verificado en `core/mcp_server/search.py`, líneas 181–182 y 325–345):**
- **Solo cronológica** (`dias`/`desde`, sin query ni dimensiones): es una consulta SQL ordenada por `creado_en`. La intención es "lo que pasó en ese tiempo" y ya está dicha; la capa 2 no debe tocarla.
- **Solo por dimensiones:** las dimensiones **son** la pista. Vale la misma regla: cruzar las dimensiones pedidas con las de cada candidato y pesar las que distinguen entre rivales.
- Dennys pidió no mezclar el diseño de la búsqueda por dimensiones con esto. Solo se anota que la capa 2 debe aceptar una pista sin texto. Antes de diseñar hay que verificar cómo corre hoy la neurona con `frase=""`.

**4. Correcciones aceptadas de la revisión externa:**
- la neurona actual sí ve tiempo (`episodio_score`), corregido en §2k;
- el cambio de ganador solo se exige cuando las respuestas de referencia son distintas;
- se habla de "correspondencia simbólica", no de "atención";
- **las etiquetas nunca salen del #1 del propio motor** (sería enseñarle sus errores). El MCP aporta los candidatos y las señales; la respuesta correcta sale de datos verificables (fecha, contención, epistemia, resultado dicho al guardar);
- epistemia (hipótesis/verificada/obsoleta) y resultado (funcionó/falló/no probado) son dos cosas distintas;
- pasar en bases reservadas demuestra que generaliza **a lo evaluado**, no a "cualquier base imaginable". Se dice así.

**Estado:** guardado para después. Va detrás de E2b → E3 → E4, como dice §2l. No se toca nada hasta el OK de Dennys.

---

## 2n. Con qué alimentar la neurona para que elija "lo que intentas averiguar" (investigación, 2026-10-27, para después)

Dennys: *"La clave es saber con qué la vamos a alimentar para que esto suceda."* El ejemplo de ChatGPT: cuatro recuerdos sobre el mismo problema:
- **A**: alguien te explicó una solución;
- **B**: otra solución para un problema parecido;
- **C**: aplicaste una solución y funcionó;
- **D**: una investigación con una explicación.

La pregunta: *"¿qué aprendimos la última vez y qué solución funcionó?"*. Es el mismo problema que el de "la última versión de BioRAG".

### La respuesta en una línea
**Se la alimenta con qué TIPO de recuerdo pide la pregunta, qué TIPO de recuerdo es cada candidato, y si ese tipo lo tiene solo él o también sus rivales.** El tema compartido no sirve para elegir; el tipo pedido sí.

### Qué dice la ciencia y qué hace la industria
| Fuente | Qué dice | Qué copiamos |
|---|---|---|
| **Orientación de recuperación** (Rugg y Wilding 2000, *Trends in Cognitive Sciences*) | Antes de recordar, el cerebro fija **qué tipo de información busca**, y la misma pista se procesa distinto según esa meta. | La pregunta se traduce primero a "qué tipo de recuerdo pido". |
| **Procesamiento apropiado para la transferencia** (Morris, Bransford y Franks 1977) | Se recuerda mejor cuando lo que se busca **coincide con cómo se guardó**. Ninguna forma de guardar es la mejor en abstracto. | El tipo se escribe **al guardar** y se pide **en el mismo vocabulario** al buscar. |
| **Tipo de respuesta esperado** en sistemas de pregunta-respuesta (Li y Roth 2002) | Clasifican la pregunta en tipos de respuesta para quedarse solo con los candidatos de ese tipo: 98,8 % en tipos gruesos y 95 % en finos, con 5.500 preguntas de entrenamiento. Moldovan 2002: cuando falla el tipo, los candidatos salen vacíos (28,2 %) o equivocados (8,2 %). | Es la pieza que falta: el "tipo pedido" filtra y ordena a los rivales que comparten tema. |

### Lo que BioRAG YA guarda (verificado en el snapshot, 866 recuerdos)
El agente ya escribe el tipo al guardar, en las dimensiones de `aprender`:

| Lo que pide la pregunta | Dónde está en BioRAG | Recuerdos en el snapshot |
|---|---|---|
| "alguien me explicó" (A) | `epistemia=reportada_externa`, `accion_comunicacion` | 5 · 35 |
| "lo apliqué / funcionó" (C) | `epistemia=directa_experiencial` / `verificada`; `intencion_solucionar` / `resolver` | 28 / 96 · 102 / 79 |
| "falló / no funcionó" | `accion_fallar` | 28 |
| "una investigación, una explicación" (D) | `epistemia=inferida` / `hipotetica`; `intencion_aprender` | 2 / 1 · 121 |
| "lo general" frente a "un caso" | `escala_abstraccion`: principio / patrón frente a instancia | 37 / 47 · 39 |
| "lo que aprendimos de un fallo" | categoría `Lesson` ("fallos resueltos, soluciones aplicadas") | 241 |
| "quién hizo qué a qué" | `predicados` (sujeto, acción, objeto) | 187 en 102 recuerdos |
| "la última vez" | `creado_en`; `coordenada_secuencia_relativa` | todos · 16 |
| otra solución del mismo problema (B) | lo que añade cada hijo (sustantivos, §2j) | — |

**El cuello de botella no es la neurona, son los datos.** La epistemia solo está en 132 de 866 recuerdos (15 %) y la escala en 128. Sin el tipo escrito, ninguna neurona puede saber cuál "funcionó". En la viva la cobertura está por medir.

### Prueba en la memoria real: el ejemplo A–D ya existe (snapshot, solo lectura, 2026-10-27)
Medido así: grupos de 4 a 12 recuerdos que comparten una palabra del nombre o de los alias; tipo = epistemia, `accion_fallar`, intención y escala.
- **470 grupos de tema; en 251 hay 3 o más tipos distintos.** El problema de ChatGPT no es teórico: está por toda la memoria.
- **El 48 % de los miembros no tiene ningún tipo escrito** (1.359 de 2.821). Es el techo actual de lo que una neurona puede aprender.
- **Ejemplo real, tema "determinista":**

| Recuerdo | Tipo guardado | Pregunta que lo pide |
|---|---|---|
| `vision_word2vec_adaptado_meta_dennys` | decisión, general, **me explicaron** | "¿qué nos propusieron?" (A) |
| `stemmer_no_determinista_entornos_nltk_vs_fallback_20260808` | **solución, verificada**, general | "¿qué solución funcionó?" (C) |
| `leccion_discrepancia_busquedas_vocabulario_no_estocasticidad` | **aprendizaje**, lo apliqué, verificada | "¿qué aprendimos?" |
| `puente_llm_sinonimos_veredicto_refutado_invariante_cero_llm` | **fallo**, decisión, verificada | "¿qué probamos que no funcionó?" |
| `biorag_v18_0_baseline_determinista` | solución, fallo | (mezcla: tipo ambiguo) |
| `artis_oec_dennys_solo` y otros dos | **sin tipo** | no se puede etiquetar |

Cada grupo así da varias preguntas de contraste con respuestas distintas, que es justo lo que pide §2l–§2o. Con una sola base salen cientos de grupos, y con más bases, miles.

### Ejemplo de entrenamiento n.º 1: el caso de la versión (propuesta externa contrastada, 2026-10-27)
Otra IA propuso usar el caso real (`version_actual_biorag` en el puesto 4) como primer ejemplo: registrar la llamada MCP real, los 10 candidatos y la respuesta verificada, y armar preguntas de contraste sobre el mismo grupo ("versión actual" → canónico; "primera neurona" → v34; "DimensionHub" → v32.4; "cambios de la 32.3" → v32.3). **Coincide con §2l–§2o y se adopta**, con cinco precisiones de quien conoce el sistema:

1. **Los nombres mienten, así que la neurona no debe verlos.** Los nodos viejos se llaman `version_actual_biorag_v34_0...` porque fueron "la actual" en su día. "version_actual" está en todos los nombres de la familia y no distingue a ninguno. Al entrenar, los conceptos se **anonimizan** (se renombran al azar en cada ejemplo), para que aprenda de señales y no de nombres.
2. **La pista se registra por partes:** consulta original, paráfrasis, ráfaga y sustantivos van separados (§2m, "la pista completa"). La consulta real llevaba ruido ("orden nodos externos"), así que se guardan **la real y una versión limpia**, cada una con la misma respuesta.
3. **La respuesta "versión actual" necesita la fecha de modificación (C1).** Hoy el canónico dice v35.0 en su contenido, pero su `creado_en` es del 14-10, anterior al de v34. Sin C1 y sin el estado "vigente", la etiqueta tendría que ponerse a mano, y eso no escala.
4. **Las preguntas de contraste no se escriben a mano:** salen solas de la **familia** (§2j). El padre responde "la actual o la general"; cada hijo responde "lo que solo él tiene", es decir su número de versión y lo que añade. Así se generan para cualquier familia de cualquier base.
5. **La fórmula `S_nuevo = S_actual + Δ(q, r)` ya es el molde de BioRAG:** piso (capa 1) más una corrección acotada con techo y guardia, igual que `neurona.py` (`_base` + `_correccion`). La capa 2 repite ese molde con la consulta dentro.

### Lo que entra a la capa 2 (tres bloques)
1. **Lo que pide la pista** (igual para todos los candidatos): los síntomas del texto ("la última", "la primera", "funcionó", "falló", "por qué", "en general"), las dimensiones que mandó el agente y `ordenar_por`. Todo se traduce **al mismo vocabulario de tipos que las dimensiones**, para que "lo que pide" y "lo que es" hablen el mismo idioma (Morris 1977).
2. **Lo que es cada candidato:** sus dimensiones de tipo (epistemia, acción, intención, escala), su categoría, su posición en el tiempo **dentro de su familia** (con fecha de modificación, C1), su nivel en la familia (§2j) y el resultado, si quedó dicho.
3. **La relación, medida contra los rivales:** por cada tipo pedido, ¿lo tiene este candidato? ¿cuántos rivales también lo tienen? Si lo tienen todos, no cuenta; si solo lo tiene uno, decide (valor diagnóstico, §2h). A eso se suma el puntaje de la capa 1 como piso.

### Cómo aprende (y de dónde salen las respuestas correctas)
- **Generador:** en una base, toma un grupo de rivales que comparten tema; elige un tipo que **solo uno** de ellos tiene; arma la pregunta con el tema más el síntoma de ese tipo (plantillas y variantes); y la respuesta correcta es el que tiene ese tipo.
- **Contraste:** el mismo grupo con otro tipo da otra respuesta correcta. Eso le enseña a cambiar de ganador según lo que se pide.
- La pregunta pasa por `recordar` del MCP, sobre una copia y con los parámetros obligatorios, para ver los candidatos reales. **La respuesta correcta sale del tipo guardado, nunca del #1 del motor.**
- **Pérdida** por pares o por lista (*learning to rank*). **Examen** en bases reservadas y con frases que no usó al entrenar.

### El caso de la versión visto así
- "¿Cuál es la última versión de BioRAG?": el tema "biorag versión" lo comparten todos y vale 0; el tipo pedido es "la última y vigente dentro de la familia".
- **Hallazgo honesto:** hoy el canónico tiene `creado_en` del 14-10 y v34 del 24-10, aunque el contenido del canónico ya dice v35.0. **Con estos datos, hasta una neurona perfecta elegiría v34 por fecha.** Primero hay que arreglar el dato: fecha de modificación (C1) y estado vigente. Después, la neurona aprende a usarlo.

### Qué hacer al guardar (sin trabajo extra para el agente)
`aprender` ya exige dimensiones. Basta con que, entre ellas, vayan la **epistemia** y el **resultado** (funcionó, falló o no probado) cuando se conozcan. Se propone para hablarlo después, sin tocar todavía `prompt.py`.

**Estado:** investigación guardada. Va después de E2b → E3 → E4 y con el OK de Dennys. El primer paso, cuando toque, es medir la cobertura de tipos en la viva (solo lectura, sobre una copia).

---

## 2o. Que la neurona aprenda a razonar "¿qué me están preguntando?" (Dennys, 2026-10-27, para después)

**Lo que pide Dennys, con sus palabras:**
- *"Tengo este paquete aquí. Ya lo ordené. Me están preguntando tal cosa. ¿Cuál es el recuerdo con el que me están preguntando?"*. No el más relacionado, sino **el que se pide**, porque puede haber otros recuerdos que también tienen que ver.
- *"Todo tiene señales. Las pistas son el entrenamiento; ella las deducirá con el descenso de gradiente."* Nuestro trabajo es darle pistas, no escribir todas las reglas a mano.
- **No es para su base:** tiene que aprender la habilidad de discernir, para cualquier base. Se puede crear una base nueva o usar una copia de la viva.
- **Una sola mente:** aunque el canónico no salga #1, si llega en los primeros 5 su información llega igual, y el agente también discierne.
- **Arquitectura hexagonal** (puertos y adaptadores), para no dañar nunca la lógica de negocio.

**La lectura científica (del auditor):**

1. **Sí: el gradiente encuentra las pistas, pero solo entre las que le llegan.** Una red aprende a pesar y combinar sus entradas; no puede inventar un dato que no recibe.
   - Si "la última" no entra como señal, o el recuerdo no tiene fecha de modificación, ningún entrenamiento lo arregla.
   - Por eso el diseño **no es escribir reglas**, sino **darle entradas completas y crudas**: cada palabra de la pista cruzada con cada campo del candidato, los tipos guardados (§2n), su lugar en la familia y en el tiempo, y cuántos rivales comparten cada cosa. **Que el gradiente decida qué importa.**
   - Menos reglas a mano y más entradas honestas. El piso (capa 1) sigue debajo por seguridad.

2. **"Razonar" aquí quiere decir comparar dentro del paquete.** La capa 2 no puntúa cada recuerdo solo: mira **el grupo entero de candidatos a la vez** y decide cuál es el pedido.
   - En ingeniería: entradas relativas al grupo (§2m, §2n) y pérdida por lista (*listwise*), que compara a todos los candidatos de una pregunta entre sí.
   - Sigue siendo pequeña y de tiempo constante: el grupo son 10 candidatos.

3. **Dos métricas, porque es una sola mente:**
   - **R@5 = lo que le llega al agente.** Si el correcto llega, el agente puede discernir; ese es el piso que nunca baja.
   - **R@1 = lo que la capa 2 debe ganar:** que el pedido quede primero, para que el agente no tenga que adivinar.

4. **Bases de entrenamiento:** una copia de la viva (nunca se sube), el snapshot y bases nuevas creadas para entrenar (§2l). El examen final se hace en bases que no vio.

5. **Arquitectura hexagonal, bien dicha:** las dependencias apuntan **hacia adentro**.
   - El núcleo (la lógica de negocio del motor) no sabe nada de las neuronas.
   - Cada neurona es un **adaptador** que se enchufa a un **puerto** que define el núcleo; hoy ese puerto es `neurona.reordenar(self, frase, pagina, v)` (`core/memory/neurona.py:538`), y "nunca lanza".
   - Se cambia o se apaga el adaptador sin tocar el núcleo, como ya pasa con `BIORAG_NEURONA=0`.
   - La capa 2 sería un adaptador más en el mismo puerto, detrás de la capa 1.

**Estado:** guardado. Va después de E2b → E3 → E4, junto con §2l–§2n, y con el OK de Dennys.

---

## 2p. Carta blanca después del motor, una neurona "muy buena" y un cerebro sin idioma (Dennys, 2026-10-27)

**Lo que decide Dennys:**
- Cuando el operador termine y el motor esté bien, el auditor tiene **carta blanca** para la capa definitiva, paso a paso.
- Tiene que ser una inteligencia **muy bien entrenada**, con los parámetros que haga falta, porque es una capa de raciocinio.
- La **neurona 2 (asociativa)** sigue sin cablear. Queda así por ahora y se conecta en la fase de neuronas.
- A la neurona se le entrega la **consulta original**: de ahí sale su percepción de qué se busca. Su trabajo es el **top-1**, y debajo lo relacionado con lo que se busca.
- *"La única forma de que no se logre es que no se conecte bien, que no le entren las agujas que tienen que entrarle o que no se entrene como tiene que ser."*
- **Es un cerebro: no puede estar casado con ningún idioma.** Lo usará cualquiera, también un chino o un coreano. **Toda pieza atada a un idioma está mal y hay que corregirla.**

### Cuántos parámetros (respuesta del auditor)
- No hay estándar, pero sí un método: **el tamaño lo decide la curva de validación.** Se empieza pequeño y se agranda (más unidades ocultas, más capas) **mientras mejore en bases que no vio**. Cuando deja de mejorar, más parámetros solo memorizan (sobreajuste).
- **Los parámetros siguen a los datos.** Regla práctica: muchos más ejemplos que pesos (orden de 10 a 1). Con cientos de miles de ejemplos, de 10.000 a 100.000 pesos es razonable. Si los datos crecen, la red puede crecer.
- "Muy buena" no significa "enorme": significa **entradas completas** (§2n, §2o) + **datos variados de muchas bases e idiomas** + **examen en bases nunca vistas**. Sigue corriendo en microsegundos.

### Auditoría de idioma del motor (medida, 2026-10-27, solo lectura)
| Pieza | Estado | Qué pasa con otros idiomas |
|---|---|---|
| `core/stemmer_es.py` | Snowball solo español e inglés | Ruso, coreano, chino, etc.: sin raíces, así que "versión/versiones" no se unen |
| `core/stopwords.py` | Listas fijas en español e inglés | En otros idiomas, las palabras vacías cuentan como contenido (más ruido, E2b) |
| `core/fallback_simbolico.py` (tokenizador `\w{2,}` + quitar tildes NFKD) | Pensado para escritura latina | **Chino:** sin espacios, "我的记忆系统" queda como **un solo token** y no hay coincidencia parcial. **Japonés:** quitar marcas une palabras distintas ("ガラス" vidrio y "カラス" cuervo dan el **mismo** token) y borra los kana sueltos. Coreano y ruso se tokenizan bien |
| `core/clasificador_wordnet.py` (OMW) | Multilingüe, pero muy disperso en español (ya medido) | Cobertura desigual por idioma |
| E3 propuesta con RLA-ES | Diccionario **solo en español** | **Choca con este principio:** E3 se rediseña |

### Qué cambia en el plan
1. **E3 deja de ser "diccionario español"** y pasa a ser **léxico independiente del idioma**:
   - el idioma entra como **puerto** con **adaptadores** (es/en hoy, cualquier otro enchufable, arquitectura hexagonal);
   - lo que no depende del idioma, primero: sinónimos aprendidos **del propio corpus** del usuario (coocurrencia/PPMI, ya existe en el motor), n-gramas de caracteres para escrituras sin espacios (estándar en búsqueda china y japonesa) y quitar tildes **solo** en escritura latina;
   - los diccionarios (RLA-ES u otros) quedan como adaptadores opcionales, nunca obligatorios.
2. **QA multilingüe mínima** antes de cambiar nada: casos sintéticos en chino, japonés, coreano, ruso e inglés sobre una base de prueba. Línea base primero, después cada cambio, con la regla de no bajar nada.
3. **La capa definitiva** se entrena con bases en varios idiomas, y sus "síntomas" (última, falló...) se aprenden de los datos, **nunca de listas de palabras**.

### ¿Si aprende en español, sabrá hacerlo en chino? (pregunta de Dennys, 2026-10-27)
**Depende de qué le entre.** Hay dos tipos de entradas:

| Tipo de entrada | Ejemplos | ¿Pasa a otro idioma? |
|---|---|---|
| **Neutras al idioma** | ¿esta palabra de la pista coincide exacta, por raíz o por sinónimo con el nombre, los alias o el texto? ¿cuántos rivales también la tienen? tipo guardado (epistemia, resultado), fecha dentro de la familia, nivel en la familia, dimensiones | **Sí.** No contienen palabras, solo relaciones. "La pista que solo cumple uno decide" vale igual en chino |
| **Palabras concretas** | "última", "falló", "por qué" | **No por sí solas.** Una red que solo vio "última" no conoce "最新" ni "latest" |

**Diseño que resuelve esto (una sola mente):** el agente es un modelo de lenguaje que ya entiende el idioma del usuario. Él traduce la intención a **parámetros neutros** que ya existen o se pueden añadir: dimensiones, `ordenar_por`, tipo pedido ("lo vigente", "lo que falló"). La neurona lee esos parámetros y las relaciones neutras, no palabras sueltas. Las palabras de la consulta entran solo como **coincidencias**, nunca como vocabulario aprendido.
- Así la neurona entrenada en español funciona en chino sin reentrenar, porque lo que aprendió son relaciones.
- Además se entrena y se examina con bases en varios idiomas (§2p) para comprobarlo, sin darlo por hecho.
- **Analogía honesta:** un humano bilingüe razona igual en los dos idiomas, pero no entiende una palabra china que nunca aprendió. El razonamiento se transfiere; el vocabulario no. Por eso el vocabulario lo pone el agente y el razonamiento la neurona.

**Datos (OK de Dennys):** se puede usar una copia de su memoria o bases construidas por el auditor con miles de recuerdos, donde la respuesta correcta se conoce porque se diseñó así: se arma la pista y se indica a qué recuerdo debe llegar. **Tamaño:** parámetros = pesos; más unidades ocultas dan más pesos; se agranda mientras mejore en bases no vistas (ver arriba).

**E3 aprobada por Dennys como "léxico independiente del idioma"** (no el diccionario solo en español).

**Estado:** guardado. La auditoría de idioma entra en la etapa del motor (antes de v36). La capa definitiva, después, con carta blanca.

### Pendiente: el mínimo de 2 letras y las palabras de una sola letra (Dennys, 2026-10-27, para después)

**El hueco (hallado al auditar B1 de la E3).** Los sustantivos clave del MCP exigen al menos 2 caracteres. En chino, japonés y coreano **un solo carácter ya es una palabra completa** (水 "agua", 本 "libro", 문 "puerta"). Por eso, en la QA multilingüe, 14 consultas (1 china, 9 japonesas, 4 coreanas) se siguen rechazando aunque B1 abra la puerta a otros alfabetos.

**Decisión de Dennys:** no se arregla en B1. Las 14 quedan rechazadas y visibles en la QA, marcadas como "pendiente del hueco 1".

> Dennys: *"Ya veremos qué hacer luego. El mínimo de letras existe para que no se busquen los conectores en español e inglés, como «mi», «la» y cosas así. Quizás otra neurona o algún método que sepa cuándo desactivar eso cuando se manda la query."*

**Ideas para cuando toque (sin decidir):**
- **Regla Unicode:** "mínimo 2 caracteres, o 1 carácter ancho" (`east_asian_width` W/F). Es simple y general, pero solo mira la forma de la letra, no si la palabra es un conector.
- **Conectores por estadística de la propia base, sin listas por idioma:** una palabra que aparece en casi todos los recuerdos es un conector ("la", "de", "の", "的"), en cualquier idioma; una rara es informativa, aunque tenga una sola letra (水). Es la idea clásica de la frecuencia inversa en documentos (IDF), que el motor ya usa en otras piezas. Respeta "un cerebro sin idioma" y además sustituiría con el tiempo las listas fijas de `core/stopwords.py` (español e inglés).
- **Neurona o método que decida** si una palabra corta es informativa según la consulta y la base: la idea de Dennys. Va con las neuronas (v37) si la estadística no basta.

---

## 2q. La neurona de razonamiento recibe la consulta y las agujas del motor (Dennys, 2026-10-27, para después)

> Dennys: *"Ya quiero probarla, pero hay que esperar a que el operario termine su parte. La idea es pasarle la query junto con la lista de resultados del motor (las demás agujas) para que ella evalúe, decida si la pregunta es relevante y suba el ítem correcto al top 1, considerando que después vendrá la neurona de re-ranking."*

**Qué cambia respecto a §2b y §2l:** la brújula (§2b) y la capa definitiva (§2l) pasan a ser **una sola neurona**: la de razonamiento. Ya no convierte el texto en intención **antes** de buscar; actúa **después**, sobre lo que el motor devolvió. Así no depende del idioma (§2p): lee coincidencias y relaciones, no palabras.

**Sus tres tareas:**

| Tarea | Qué significa | Con qué se entrena |
|---|---|---|
| **1. Evaluar** | Mira la consulta frente a cada aguja (interacción consulta × candidato de §2l, señales de §2k, tipo escrito de §2n) | Ejemplos consulta + ráfaga → recuerdo correcto (§2n, ejemplo n.º 1) |
| **2. Decidir si es relevante** | ¿Alguna aguja responde de verdad a lo que se pregunta? Si ninguna encaja, lo dice ("no tengo ese recuerdo") en vez de forzar un ganador | Los controles negativos de la QA (FP 0/40) y preguntas generadas sin respuesta en la base |
| **3. Subir el correcto al top-1** | Elige uno y deja los relacionados debajo | Pérdida por lista contra rivales difíciles de la misma familia (§2j, §2l) |

**Dónde va en la cadena (decisión pendiente de Dennys).** La neurona de ranking **ya existe** (capa 1, `neurona.reordenar`, entrenada). Hay dos órdenes posibles:

| Orden | Cómo funciona | Riesgo |
|---|---|---|
| **A. Motor → ranking → razonamiento** (recomendado por el auditor) | La de razonamiento ve el orden del ranking como una aguja más (su piso) y tiene la última palabra | Ninguno nuevo; es la cascada de §2l |
| **B. Motor → razonamiento → ranking** | La de razonamiento elige el top-1 y el ranking ordena solo del 2 en adelante | Si el ranking pudiera mover el top-1, desharía la decisión; hay que fijarlo. Además, la de razonamiento no ve lo que el ranking aprendió |

**Seguros:** los de §2.3 y §2l: piso = orden anterior, techo, guardia, examen sellado, bases que nunca vio, QA oficial sin bajar nada. Si duda, no decide.

**Cuándo:** después de que el operador cierre E3 y E4 y se publique v36.0. Es la primera neurona de v37.

**Opinión externa que trajo Dennys (2026-10-27), contrastada por el auditor.** Otra IA usa el caso de la versión (v34 0,5398 en el #1, el canónico v35 0,4614 en el #4) para describir una "neurona auditora" que mira los candidatos y pregunta *"¿cuál de estos es la verdad actual que se pide?"*.
- **Coincide** con §2g, §2l y §2q: la similitud no es lo mismo que la relevancia de intención, y el juicio va al final, sobre los candidatos del motor.
- **Matices del auditor:**
  - BioRAG no usa vectores ni coseno: el v34 ganó por coincidencias léxicas, dimensiones y la señal temática (causas C1–C8, §2h).
  - "Apagar lo histórico" solo vale cuando la pregunta pide el estado actual. Como regla fija es un callejón sin salida (§2j); tiene que depender de la consulta.
  - "Top 1 forzado" no: la neurona parte del orden recibido como piso y, si duda, no decide.
  - Para que sepa cuál es "el actual", el recuerdo tiene que tener su fecha de modificación (C1) y su identidad escrita (C7, §2n). Sin esos datos, ninguna neurona puede deducirlo.

---

## 2r. El mandato: resolver de verdad la competencia entre recuerdos (Dennys, 2026-10-27, para después)

> Dennys: *"Son como dos laterales, pero son el mismo problema, hay que resolverlo. Tienes que investigar incluso en internet, en papers, todo. Hacer algo de verdad de ingeniería: ingenioso, sublime, perfecto, delicado. Búscate cómo funciona el cerebro humano en realidad, y de esa parte del cerebro saca ideas para nosotros. Y si hace falta alimentarla con alguna aguja que no tenemos, se crea. Cuando te toque, investiga otra vez el proyecto entero y repasa sus archivos principales, porque cuando crece el contexto ciertas cosas se olvidan. Tenemos la fórmula, que es la neurona. ¿Cómo programamos la neurona? Ahí está el point."*

> **La frase guía (de ChatGPT, guardada por Dennys):** *"El cerebro no busca únicamente por el tema de la pregunta; también utiliza lo que necesitas obtener de ese recuerdo."*

> **Dennys, 2026-10-27:** *"Yo quiero confiar en tu criterio personal. No tenemos margen de perder: aquí tenemos que ganar. Para que esto crezca adonde tiene que crecer, tiene que haber una inteligencia por detrás. Hazlo como la primera vez: investigaciones aparte, lo más parecido al motor pero sin tocarlo, para que al cablear todo quede perfectamente igual. No me importa estar dos, cinco o diez días mientras entrenas esa neurona; tiene que quedar perfecta."*

**Compromiso del auditor:**
- Se construye con el mismo método de la neurona 1: investigación y entrenamiento **fuera del motor**, pero con **exactamente lo que el motor ve** (desfase 0), para que el cableado final sea idéntico a lo entrenado.
- Las decisiones de diseño son del auditor, con criterio propio y pruebas en la mano. Dennys aporta ideas y opiniones externas; el auditor las contrasta, como en §2s.
- Se entrena el tiempo que haga falta: no hay prisa, hay que acertar.

### Las dos caras del mismo problema (ya guardadas)
| Cara | Ejemplo | Dónde está |
|---|---|---|
| **Mismo tema, distinto TIPO de recuerdo** | ChatGPT: A (te lo explicaron), B (otra solución parecida), C (lo aplicaste y funcionó), D (una investigación). Pregunta: "¿qué solución funcionó la última vez?" | §2n |
| **Misma familia, distinto ESTADO o versión** | Caso de la versión: v34 en el #1 y el canónico v35 en el #4 | §2g, §2h, §2j, §2q |

En los dos, la pregunta trae **qué se busca** (tipo, estado, momento) y los candidatos comparten casi todas las palabras. La similitud no basta: hay que elegir por **encaje con la intención**.

### Protocolo del auditor cuando llegue el momento (después de v36.0)
1. **Releer el proyecto entero** antes de diseñar nada: motor (`core/memory/search.py`, `scoring.py`, `neurona.py`), MCP (`core/mcp_server/search.py`, `write.py`, `prompt.py`), esquema de la base, la guía `GUIA_CREAR_UNA_NEURONA.md`, el mapa `arquitectura_neuro_simbolica/README.md` y este documento completo.
2. **Investigar a fondo, con fuentes verificadas:**
   - **Cerebro:** control de la recuperación en la prefrontal (Badre y Wagner), supresión de competidores (Wimber 2015; Anderson), orientación de recuperación (Rugg y Wilding), separación y completado de patrones en el hipocampo, contexto temporal (Howard y Kahana), y el monitoreo posterior a la recuperación ("¿esto es lo que buscaba?").
   - **Ingeniería:** ranking en cascada, aprendizaje por lista con rivales difíciles, modelos de interacción sin embeddings (Duet), tipo de respuesta esperado (Li y Roth), predicción de si una consulta tiene respuesta (para decidir "no lo tengo") y datos sintéticos generados con el buscador real (InPars).
   - De cada fuente: qué dice, qué copiamos y qué no sirve en BioRAG (sin vectores, sin feedback).
3. **Inventario de agujas.** Qué entradas existen hoy, cuáles faltan y cuáles se crean. Candidatas conocidas: fecha de modificación (C1), identidad escrita del recuerdo (C7), tipo pedido frente a tipo del candidato (§2n), contención en la familia (§2j), exclusividad del tipo frente a los rivales. Si falta una, **se crea** en el guardado o en el motor, con su propia prueba y sin dañar la lógica de negocio (arquitectura hexagonal).
4. **Diseño** de la neurona de razonamiento (§2q): entradas, tamaño por curva de validación, pérdida por lista, decisión de relevancia y seguros.
5. **Examen sellado** con las dos caras del problema, en bases que nunca vio y en varios idiomas (§2p). La QA oficial no puede bajar.
6. **Comparación justa:** agente + BioRAG frente a agente + base vectorial, con las mismas preguntas. Es la prueba de la tesis de Dennys ("BioRAG es un cerebro, no una base vectorial").

### La visión de Dennys
> *"La base vectorial es obsoleta; nuestro sistema es mejor. Las bases vectoriales quedarán para recuperar documentos estáticos, pero para el resto no van a servir."*

**Lectura honesta del auditor:** las bases vectoriales son buenas para encontrar lo **parecido**. La apuesta de BioRAG es elegir lo **adecuado para la intención**, que es justo donde lo parecido falla (las dos caras de arriba). La comparación justa del paso 6 es la que lo demostrará con números.

---

## 2s. Opinión externa: siete "neuronas funcionales" para elegir el recuerdo pertinente (traída por Dennys, 2026-10-27, para después)

> Resumen de la propuesta de otra IA: *"La semejanza encuentra candidatos; intención + contexto + evidencia seleccionan el recuerdo que responde a la pregunta."* Propone siete módulos pequeños en cadena: **intención, separación, contexto episódico, evidencia, causa–acción–resultado (C-A-R), relevancia temporal y ambigüedad**. Su ejemplo es el de ChatGPT (§2n): ante "¿qué solución probamos y funcionó?" debe ganar C (aplicada y validada) aunque A (propuesta) tenga más palabras en común. También sitúa a BioRAG en la familia de los sistemas modulares (mezcla de expertos, RAG modular, reranker, neurosimbólico) y sugiere nombres defendibles: "neurona funcional", "micro-experto", "arquitectura cognitiva modular". Las fuentes que cita (Springer, PMC, arXiv) **no las verificó el auditor**.

### Qué tomamos (encaja con lo ya guardado)
| Idea | Dónde ya está o adónde va |
|---|---|
| Semejanza ≠ pertinencia | Problema central de §2l, §2q y §2r |
| **Ambigüedad con tres salidas: resuelto, competido, insuficiente** | **Se adopta como la salida de la neurona de razonamiento (§2q).** Formaliza el "empate real" de §2l y el "no lo tengo" de §2q. "Insuficiente" puede pedir una ráfaga (P4, P7) en vez de inventar un ganador |
| Evidencia: propuesta frente a probada frente a fallida | Ya se guarda al escribir: `epistemia` (`directa_experiencial`, `verificada`, `reportada_externa`) y `accion_fallar`, `intencion_solucionar` (§2n) |
| Tríada causa–acción–resultado | **Aguja nueva candidata** para el inventario de §2r paso 3. Hoy existe en parte: predicados SRL (`pred_score`) y dimensiones de intención/acción |
| Separación: "comparten casi todo salvo un detalle decisivo" | Es la contención con "lo que añade el hijo" (§2j) y la exclusividad del tipo frente a los rivales (§2n) |
| Relevancia temporal: versión, vigencia | §2g/§2h (C1 fecha de modificación, C5 última ≠ actual) |
| Nombres: "neurona funcional", "micro-experto" | Útiles para la documentación pública de v37; sin reclamar primicias |

### Matices del auditor (lo que NO tomamos tal cual)
1. **Una neurona de intención que lee la consulta ANTES de buscar ata el sistema al idioma.** Según §2p, la intención la traduce el agente (que ya es multilingüe) a parámetros neutros (sustantivos, dimensiones, tipo pedido). La neurona trabaja después, sobre relaciones.
2. **Listas de palabras marcadoras ("funcionó", "validado", "podría") = atadas al idioma.** Rompe la regla de Dennys. La evidencia se toma de lo que el agente escribe al guardar (`epistemia`, dimensiones), que es neutro.
3. **Pesos fijos a mano (0,30·resultado + 0,25·relación…) y un `score_final` que sustituye la fórmula:** no. El ranking actual es el piso y las neuronas suman encima con techo; los pesos se aprenden por gradiente con examen sellado (§2o).
4. **Siete neuronas en cadena:** cada una necesitaría sus propios datos, su prueba y sus seguros, y los errores se encadenan. Propuesta: **separación, contexto, evidencia, C-A-R y temporalidad entran primero como AGUJAS (entradas) de UNA neurona de razonamiento**. Una pasa a ser neurona propia solo si las pruebas demuestran que hace falta. Así se respeta "neuronas donde hagan falta" sin multiplicar piezas.
5. **Datos inexactos sobre BioRAG:**
   - "BM25 60 %, sináptico 25 %, riqueza 15 %" no es la fórmula del motor. La verificada es `_calcular_score_hibrido`, con unas 17 señales.
   - "Suite de 430 pruebas": 430 eran los tests unitarios de v35.0 (hoy más de 600). La QA oficial tiene 921 casos.
   - "BioRAG v36" con estas neuronas: v36 es el motor robusto; las neuronas van en v37.
6. **Ya existen piezas relacionadas que hay que revisar antes de crear otras:**
   - la inhibición lateral GABA, que atenúa a los competidores cuando el top-1 domina;
   - el umbral conforme de abstención, que en una base nueva no actúa (hallazgo de E3A, anotado para E4).

### Segunda respuesta de la otra IA y viabilidad (2026-10-27)
La otra IA aceptó las correcciones: tres errores suyos (fórmula inventada, cifras viejas, siete neuronas sin prueba) y el diseño de **una neurona de razonamiento con agujas** sobre el ranking como piso. Dice que es viable, y que el riesgo real son los datos de entrenamiento. Las tres salidas tienen nombre en la literatura: **clasificación con opción de rechazo** (Chow, 1970).

**Veredicto del auditor: viable.** Las dificultades reales, en orden:
1. **Agujas que hoy no existen:** fecha de modificación (C1), tríada causa–acción–resultado e identidad escrita (C7). Se crean (§2r paso 3).
2. **Que el correcto llegue a los candidatos** (E4). Si no llega, ninguna neurona lo arregla.
3. **Datos para las tres salidas, sin etiquetar a mano.** Idea del auditor: generarlas por construcción.
   - **Resuelto:** consulta con un único correcto conocido (§2n, ejemplo n.º 1).
   - **Competido:** los casos ambiguos que E1 apartó de la QA honesta (varios esperados válidos), más pares generados a propósito con dos respuestas igual de correctas.
   - **Insuficiente:** se toma un caso "resuelto" y, en una COPIA de la base, **se borra el recuerdo correcto**: la respuesta correcta pasa a ser "no lo tengo". Se suman los 40 controles negativos de la QA.
   - Así hay ejemplos de las tres clases en la proporción que se quiera, y la neurona no aprende a decir siempre "resuelto".

**Ajustes a lo que propuso:**
- **"Registrar qué aguja empujó cada decisión":** sí como explicación **a pedido**, en la QA y en diagnósticos. **No** como registro del uso del agente en producción (regla de Dennys: nada de logging del uso).
- **Separación temporal** (entrenar con lo viejo y examinar con lo nuevo): sí, pero la prueba principal sigue siendo **bases que nunca vio** (§2l).
- **"5–10 agujas":** son las nuevas. Se suman a las de §2l y §2k, unas 100–150 entradas en total.

**Tercera respuesta de la otra IA (2026-10-27): dos aportes que se adoptan.**
1. **"Insuficiente" se aprende por la razón, no por el hueco.** Riesgo: si la neurona solo ve que falta el nodo, puede aprender un atajo, como desconfiar de todo o detectar un artefacto de la copia. Solución del auditor, que se suma:
   - **Pares gemelos:** la misma consulta, en la misma base, con y sin el recuerdo correcto. Lo único que cambia es su presencia, así que no hay atajo posible.
   - **Insuficientes difíciles:** se borra el correcto pero se deja su hermano casi igual. Por ejemplo, se borra la versión actual y quedan las viejas. Ahí lo que debe aprender es que ninguna versión que queda es la actual.
   - Las agujas ya muestran el porqué: poca evidencia, falta la tríada causa–acción–resultado, rivales parecidos, versión incorrecta.
2. **Regla de aprobación: "que no se vuelva tímida".** La neurona solo se aprueba si:
   - el top-1 no baja frente al ranking actual;
   - **no convierte errores recuperables en "insuficiente"**: si el correcto está en la lista y tiene evidencia, debe elegirlo.

   Se mide aparte el **rechazo indebido** (dijo "insuficiente" teniendo el correcto con evidencia) con un tope fijado antes del examen. Se reporta la curva **cobertura frente a acierto** (cuántas veces decide y cuántas acierta cuando decide), la medida estándar de la predicción con rechazo.

**Cuarta aportación externa (traída por Dennys, 2026-10-27): dónde vive la neurona, de dónde sale la intención y cómo se entrena.**

| Propuesta | Decisión del auditor |
|---|---|
| **Neurona aparte del re-ranker**, con su propia señal de entrenamiento y la capacidad de abstenerse | **Se adopta.** Es el orden A de §2q: motor → ranking → razonamiento |
| **Salida = una decisión, no solo una lista**: recuperar / pedir contexto / abstenerse | **Se adopta, unida a las tres salidas.** "Competido" = **pedir contexto**: el MCP devuelve los candidatos en disputa y **lo que los distingue** (por ejemplo, "A es una propuesta, C se aplicó y funcionó"), y el agente decide o vuelve a preguntar. Es la "una sola mente": el cerebro no inventa, el agente completa |
| Intención en cascada: (1) la explícita del agente; (2) la deducida de verbos de la consulta ("funcionó", "propusimos"); (3) sin señal, no reordenar | **(1) y (3) se adoptan. (2) se rechaza:** leer verbos ata al idioma (§2p) |
| **Campo explícito `tipo_evidencia`** (hipótesis / procedimiento / resultado / explicación / preferencia / restricción) | **Primero se deriva de lo que ya existe** (`epistemia` y dimensiones de acción/intención, §2n). Exigir un campo nuevo al agente es trabajo extra (regla de Dennys). Solo si lo derivado no alcanza en la suite de competencia, se propone como **lista cerrada de valores neutros** (identificadores, no palabras de un idioma). Los recuerdos sin dimensiones (89 de 851 en el snapshot, 196 de 1.195 en la viva) son el hueco a medir |
| **Sondas contrastivas automáticas**: en un grupo que comparte sustantivos, la respuesta es el del tipo pedido y los demás son distractores | **Ya está en el plan** (generador de §2l, contrastes de la familia §2j, pares gemelos). Se adopta su formulación |
| Etiquetas desde el uso del agente o correcciones del usuario | **Se rechaza:** regla de Dennys, nada de feedback ni de registro del uso |
| **Regla de identidad**: si la consulta es el nombre literal del recuerdo y ya está en el #1, la neurona no lo mueve | **Se adopta como seguro** |
| Guardia por hash, piso si la confianza es baja, traza "por qué ganó C" | **Se adopta.** La traza solo a pedido, en la QA y en diagnósticos |
| Tres métricas: R@1, precisión de la abstención y utilidad de "pedir contexto" | **Se adopta, adaptada.** La utilidad de "pedir contexto" se mide **en simulación**, sin feedback: ¿el par en disputa contiene al correcto y la diferencia mostrada es la verdadera? Junto con el rechazo indebido ya fijado |

**Correcciones de datos:**
- La neurona asociativa **no se descartó por no mejorar la QA**: está construida y calibrada, y su conexión al motor está **pendiente** (escala 0).
- BioRAG ya no es "bilingüe" como objetivo: la meta es **independiente del idioma** (E3).
- El archivo `bio_problema_actual.md` que cita no está en el repositorio.

**Postura honesta que se adopta:** no declarar superioridad universal. Lo que se defiende es ganar **en su terreno**: memoria persistente de agentes, explicable, local, sin GPU y que sabe decir "no lo tengo". En la búsqueda semántica abierta sobre cualquier corpus no hace falta competir.

**Quinta aportación externa (2026-10-27): dos puntos que se adoptan.**
1. **¿Qué hace la neurona si no llega la intención del agente?** Hay tres opciones: abstenerse siempre, dejar el ranking intacto, o **deducir la ambigüedad del contraste entre los candidatos**. **Se adopta la tercera, como respaldo:**
   - Si los candidatos se reparten en tipos estructuralmente distintos (por ejemplo, uno con procedimiento y otro con resultado), la neurona sabe que **hay ambigüedad** sin leer la consulta.
   - Entonces devuelve "competido / pedir contexto" con la diferencia.
   - Es independiente del idioma y no sustituye la intención del agente: la cubre cuando no llega.
   - Si tampoco hay contraste claro, se deja el ranking intacto (piso).
2. **La prueba que decide si hace falta un campo nuevo.** Antes de escribir la neurona hay que comprobar si las dimensiones actuales separan "hipótesis", "procedimiento", "resultado" y "explicación". Es barato: se toman 20–30 grupos de recuerdos que comparten sustantivos clave pero difieren en tipo, y se mira si sus dimensiones los separan.
   - **Si los separan:** las sondas contrastivas tienen etiqueta sin pedir nada nuevo al agente.
   - **Si no:** el campo `tipo_evidencia` deja de ser trabajo extra y pasa a ser **estructural**. Se le propone a Dennys con la evidencia en la mano.
   - **Indicio previo (§2n):** en el snapshot ya hay 470 grupos de tema, y en 251 de ellos aparecen 3 o más tipos distintos según `epistemia` y las dimensiones de acción. Falta medir si esa separación alcanza.
   - **Es el primer paso medible del protocolo de §2r (paso 3).**

**Sexta aportación externa (2026-10-28): el mapa "learning to rank".** Dennys la trajo de otro asistente, como teoría, no como verdad ("la verdad de todo la decides tú"). El auditor la contrasta con lo ya guardado.

*Lo que dice, en corto:*
- Lo que buscamos existe y está estudiado: es un **reranker aprendido** (*learning to rank*).
- Hay dos ramas:
  - **sobre señales numéricas**, como la neurona 1 (29 → 6 → 1): RankNet (red) y LambdaMART (árboles de boosting, rápidos, interpretables y fuertes con señales tabulares);
  - **sobre texto** (*cross-encoders*), que leen consulta y documento juntos.
- La receta de entrenamiento que más rinde: cada ejemplo es un grupo (consulta, el correcto y varios negativos difíciles sacados del buscador de primera etapa), con pérdida *listwise* (softmax sobre el grupo).
- Lo más cercano a "entender la intención" son los **rerankers que siguen instrucciones**. Un método de 2026 fabrica pares donde, con otra instrucción, **el ganador y el negativo intercambian etiquetas**.
- Para tener muchos ejemplos: Promptagator e InPars generan consultas sintéticas y las filtran.
- Partir los datos **por consulta** y dejar una validación que el ajuste nunca toque.

*Qué se adopta y qué no:*

| Punto | Decisión | Por qué |
|---|---|---|
| La familia correcta es *learning to rank* sobre señales | **Adoptado** (ya era el camino) | La neurona 1 es eso. La capa 2 también lo será: señales neutras, sin texto. |
| **LambdaMART como línea base que la neurona debe batir** | **Adoptado**, solo en investigación | Rigor científico: si unos árboles estándar ganan a la red pequeña, la red no se justifica. Vive fuera del motor (como el entrenamiento de la neurona 1). Al motor solo entra lo que gane, y solo si cumple las reglas: tiempo constante, sin dependencias pesadas, piso y techo. |
| Pérdida *listwise* sobre el grupo (consulta + correcto + negativos difíciles) | **Adoptado** | Encaja con §2k: los negativos difíciles los fabrica el propio motor (los que quedan arriba sin ser el correcto). |
| Mezclar negativos difíciles con negativos fáciles de otras consultas | **Adoptado con medida** | Una fracción pequeña de fáciles; la proporción se decide con la validación, no a ojo. |
| **Pares que intercambian etiquetas al cambiar la intención** | **Adoptado: es la pieza más valiosa** | Son los "pares gemelos" de §2s, ahora del lado de la intención: mismos candidatos A–D, distinta intención ("¿qué funcionó?" frente a "¿qué descartamos?"), distinto ganador. Obligan a la neurona a mirar la intención y no solo el parecido. **Se fabrican por construcción, sin un LLM**, si la prueba de dimensiones (quinta aportación, punto 2) confirma que el tipo de cada recuerdo se puede leer. |
| La intención como canal aparte que pasa el agente | **Adoptado como parámetro neutro** | Ya estaba (cuarta aportación, parte 1). Pero va como **valor cerrado** (por ejemplo, solución que funcionó / propuesta / descartada / teoría), **nunca como texto libre**: el texto ataría la neurona a un idioma y exigiría un modelo de texto. |
| Aguja nueva que pide lo anterior | **Anotado** | Para que la intención sirva, cada candidato necesita su **tipo** como señal (derivado de `epistemia` y dimensiones, o `tipo_evidencia` si no alcanza). Se suma a las agujas de §2s: fecha C1, triada C-A-R, identidad escrita. |
| Consultas sintéticas con filtro de "la consulta recupera su documento" | **Adoptado con corrección** | Si exigimos que la consulta ya traiga su recuerdo en el top-1, solo quedan casos que el motor ya resuelve y no queda nada que aprender. El filtro correcto para la capa 2 es: **el objetivo está entre los candidatos** (lo que la capa 2 ve), aunque no esté primero. |
| Partir por consulta + validación intocable | **Adoptado y reforzado** | Además de partir por consulta, se deja **una base entera que nunca se ve** (hold-out por base, §2s), para probar el objetivo fijo: "el mismo resultado en cualquier base". |
| *Cross-encoders* que leen texto | **No adoptado** como arquitectura | Pesados, atados al idioma y sin tiempo constante. Solo se toma su receta de entrenamiento. |
| "Con ~921 casos el riesgo es el sobreajuste" | **Matiz** | Los datos no se limitan a la QA: se construyen (resuelto / competido / insuficiente, pares gemelos), miles si hace falta. El riesgo de sobreajuste sigue siendo real; por eso existe la validación intocable. |
| Rankers profundos con preentrenamiento que superan a los árboles con pocos datos etiquetados | **Anotado, sin decidir** | Es una hipótesis que solo se decide midiendo contra la línea base LambdaMART. |
| Citas de neurociencia de `bio_problema_actual.md` | **Sin verificar** | El propio asistente lo dice, y ese archivo no está en el repo. |

**Postura del auditor.** Nada de esto cambia el orden: primero el motor (E3–E4) y la publicación v36.0; después la capa 2 (v37), con este mapa como guía. La regla del inventor vale aquí: **nada es "imposible"**, solo **"todavía no medido"**. Cada idea se prueba contra la línea base y contra el piso del ranking actual.

---

## 3. El orden para llegar (paso a pasito)

| Etapa | Qué | Relación con la visión |
|---|---|---|
| E1 ✅ | QA honesta (cerrada 2026-10-26) | Medir de verdad, igual en cualquier base |
| E2 | Fallo `por_tema` 0848 | Cimientos del ranking |
| E3 | Léxico mental | P6: puentes de palabras (prolijo ↔ prolijidad) |
| E4 | Que el resultado no dependa de la base; arreglar el nacimiento de enlaces por alias | Llegada garantizada (§2.2.1); conexiones con criterio |
| E5 | Neuronas en puntos estratégicos | Por orden: asociativa (juez de enlaces), vigencia (P2, P3), "¿nuevo o actualización?" |
| Después (v37) | **Neurona de razonamiento** (§2b, §2l, §2q): recibe la consulta y las agujas del motor, decide si alguna es relevante y sube la correcta al top-1 | La brújula: entender qué se pide y subirlo al primer puesto |
| Después | Ráfaga natural con pistas (P7) y recuerdo escalonado (P4) | Recordar como un humano, con ventaja de silicio |

Detalle técnico de E5 (dónde hace falta criterio neuronal): `../arquitectura_neuro_simbolica/README.md`, §6.
Cómo entrenar cualquier neurona: `../GUIA_CREAR_UNA_NEURONA.md`.

---

## 4. Cómo se usa este documento

Antes de construir cualquier neurona o pieza nueva:

1. ¿Qué principio (P1–P9) cumple?
2. ¿Su infraestructura previa ya existe? (§2.2)
3. ¿Tiene todos los seguros? (§2.3)
4. ¿Mejora sin bajar nada, en cualquier base?

Si alguna respuesta es "no", todavía no toca.
