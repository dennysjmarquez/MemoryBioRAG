# Cómo recuerda BioRAG: la visión

> Documento de diseño. Recoge la visión de Dennys (2026-10-26) para que cada pieza futura se construya en orden y se evalúe **contra esta visión**, no solo contra números.
> Aquí no hay código ni experimentos. Es la brújula: *"si no se tiene clara la visión, van a haber fracasos todo el tiempo"*.

---

## 0. La idea en una frase

**BioRAG es un cerebro, no una base vectorial.** El agente intenta recordar (metacognición), el cerebro recibe ese empuje, **entiende qué se le está pidiendo** y devuelve **justo eso**, primero y sin ruido. Agente + BioRAG = **una sola mente**.

El sueño, en palabras de Dennys: *"que tú simplemente digas «papá» y consigas todo lo relacionado con eso, porque el cerebro en realidad funciona así"*, sin vectores, neurona a neurona, en puntos estratégicos.

Qué lo hace "vivo": no que tenga sinapsis ni que se parezca a un cerebro, sino que **tiene neuronas que hacen lo que ninguna función fija podría hacer**.

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

## 3. El orden para llegar (paso a pasito)

| Etapa | Qué | Relación con la visión |
|---|---|---|
| E1 ✅ | QA honesta (cerrada 2026-10-26) | Medir de verdad, igual en cualquier base |
| E2 | Fallo `por_tema` 0848 | Cimientos del ranking |
| E3 | Léxico mental | P6: puentes de palabras (prolijo ↔ prolijidad) |
| E4 | Que el resultado no dependa de la base; arreglar el nacimiento de enlaces por alias | Llegada garantizada (§2.2.1); conexiones con criterio |
| E5 | Neuronas en puntos estratégicos | Por orden: asociativa (juez de enlaces), vigencia (P2, P3), "¿nuevo o actualización?" |
| Después | **Neurona de razonamiento** (§2b) + **neurona de intención** (§2) | La brújula: entender qué se pide y subirlo al primer puesto |
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
