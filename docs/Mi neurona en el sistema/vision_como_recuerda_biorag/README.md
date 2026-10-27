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
