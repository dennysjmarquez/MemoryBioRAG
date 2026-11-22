# Del recuerdo asociativo al organismo de silicio

> **Tipo:** síntesis de visión y análisis de brechas.
> **Origen:** conversación de Dennys con la asistencia sobre memoria humana, hipocampo, asociaciones, recencia, competencia y una futura neurona selectora.
> **Estado:** diseño conceptual; este documento no modifica el motor, no toca ninguna base y no afirma que el sistema actual sea un cerebro biológico.

## 1. La visión de Dennys

La meta no es añadir mecanismos que solo *parezcan* neurocientíficos. Dennys plantea que BioRAG llegue a ser un **organismo vivo de silicio**: un sistema persistente que aprende, relaciona experiencias, recupera lo pertinente, compite entre recuerdos y se reorganiza con el tiempo.

La conversación fijó varias intuiciones de diseño:

- Cada recuerdo puede estar acompañado de muchas «agujas»: dimensiones, sinónimos, sustantivos clave y otras señales. Esas señales son parte de cómo el sistema representa y encuentra el recuerdo.
- Las sinapsis son una buena analogía para las relaciones entre recuerdos. Una relación entre dos cosas puede permitir que una pista conduzca a otra.
- Dennys pregunta cuál sería el equivalente funcional del hipocampo en nuestro sistema y propone que, más adelante, una neurona bien entrenada ayude a decidir qué asociaciones son útiles; una vez validada, podría quedar fija o versionada.
- La recencia es un problema abierto: algo recién aprendido puede ser más accesible, pero otro recuerdo más antiguo puede volver a activarse cuando aprendemos algo relacionado.
- El contexto y la competencia importan: no todo lo asociado debe llegar a la respuesta final; la consulta y el objetivo favorecen unas opciones y frenan otras.
- La memoria asociativa puede traer ruido o recuerdos confundibles. Dennys acepta que ese fenómeno es normal en una memoria asociativa, siempre que el sistema aprenda a manejarlo en vez de fingir que toda asociación es certeza.

La aspiración debe traducirse a **comportamientos observables y evaluables**. «Organismo vivo de silicio» es la visión de largo plazo; hoy no es una conclusión científica sobre vida, consciencia o equivalencia con un cerebro humano.

## 2. Qué significa la analogía neurocientífica

### 2.1 El recuerdo no es un registro guardado en un solo punto

En el cerebro, los componentes de una experiencia se representan en redes distribuidas. Un recuerdo puede involucrar características sensoriales, semánticas, temporales, emocionales y contextuales. Por eso, las «agujas» de BioRAG son una analogía útil para describir señales de acceso y comparación, pero no son por sí solas un hipocampo.

### 2.2 La función hipocampal es vincular y completar, no guardar todas las agujas

El hipocampo participa especialmente en formar y recuperar recuerdos episódicos y relaciones entre elementos. Una explicación funcional común es que puede ayudar a completar un patrón: una pista parcial reactiva otros componentes de la experiencia relacionada. Esto no significa que el cerebro ejecute literalmente una búsqueda por nodos, ni que exista un único módulo cerebral que contenga toda la memoria.

Por tanto, el equivalente de ingeniería no sería una sola tabla o una neurona, sino una **función coordinada** que:

1. vincule elementos que ocurrieron juntos o pertenecen a una misma experiencia;
2. preserve el contexto que permite distinguir una experiencia de otra;
3. use pistas parciales para proponer recuerdos asociados;
4. deje que otros mecanismos decidan si esos recuerdos responden a la pregunta actual.

### 2.3 La actividad se propaga, pero no como un BFS literal

Una pista puede activar varias representaciones en paralelo. Las asociaciones aprendidas hacen que unas representaciones influyan en otras; la recurrencia ayuda a completar patrones, mientras la inhibición y el control reducen la competencia excesiva. La metáfora de «propagación de activación» sirve para diseñar un sistema, pero un cerebro no recorre una lista de aristas una por una.

El contexto y la meta también guían la recuperación. La misma pista puede favorecer recuerdos distintos si se pregunta por el último, por una causa, por un resultado o por un ejemplo. Tener similitud temática no equivale a responder a la intención.

### 2.4 Recencia, aprendizaje y confusión

La disponibilidad de un recuerdo no es un solo contador que baja con el tiempo. Influyen la recencia, la repetición, la importancia, la reactivación y el contexto. Aprender algo relacionado puede reforzar un acceso al recuerdo antiguo; aprender algo demasiado parecido también puede crear competencia o interferencia. Que algo sea más fácil de recuperar no lo hace automáticamente más verdadero ni más vigente.

Al recordar, las personas reconstruyen a partir de pistas y contexto. Eso permite flexibilidad, pero también errores y mezclas. Para BioRAG, la lección no es presentar errores con confianza: es separar **generación de candidatos** de **decisión final**, conservar la procedencia y permitir la abstención.

## 3. Mapa funcional para BioRAG

No hay que elegir un archivo y declararlo «el hipocampo». La analogía se reparte entre funciones distintas. En el código existen piezas que se aproximan a algunos de estos papeles; su existencia no prueba por sí sola equivalencia biológica ni que la función esté completa.

| Función | Analogía útil | Aproximación en el sistema | Límite que debe quedar claro |
|---|---|---|---|
| Representar un recuerdo | Representaciones distribuidas y pistas | Nodo de memoria, contenido, dimensiones, sinónimos, sustantivos clave y señales semánticas | Los campos describen evidencia; no son neuronas ni un episodio completo |
| Asociar recuerdos | Conectividad sináptica aprendida | Grafo `sinapsis` y otros mecanismos de asociación | Más aristas no garantizan más utilidad; importan el tipo, origen, fuerza y contexto del enlace |
| Vincular una experiencia | Indexado episódico/relacional | `core/memory/episodes.py` y sus señales temporales, junto con el contexto del recuerdo | La proximidad de tiempo o categoría es una aproximación; no equivale a representar todo el episodio y su orden causal |
| Completar desde una pista | Compleción de patrones | Semillas de búsqueda y propagación asociativa; `core/similitud_conceptual.py` documenta un proceso de dos fases análogo | Es una analogía computacional; el resultado depende de las semillas, aristas, filtros, límites y estado de la base |
| Competir y seleccionar | Atención y control de la recuperación | Búsqueda, `scoring`, reordenamiento neuronal, filtros y abstención | El ranking debe responder a la intención, no premiar solo la cantidad de asociaciones |
| Consolidar y cambiar accesibilidad | Plasticidad y consolidación | Ingesta, sinapsis y ciclos de consolidación/sueño | Cada cambio necesita evidencia, límites, trazabilidad y pruebas; «natural» no significa automáticamente correcto |

En términos sencillos:

- **Las agujas** caracterizan el recuerdo y cómo puede coincidir con una consulta.
- **Las sinapsis** permiten saltar entre recuerdos relacionados.
- **El contexto episódico** ayuda a saber qué elementos pertenecen a una misma vivencia y cuándo ocurrieron.
- **La búsqueda y el selector** deciden cuáles de los candidatos deben llegar a la respuesta.

La función más cercana al «hipocampo» sería el conjunto de **vinculación episódica + recuperación desde pistas parciales + propagación asociativa**, no todas las dimensiones del nodo ni una neurona rankeadora aislada.

## 4. Cómo debería fluir un recuerdo

Este es un modelo funcional para orientar el diseño; no afirma que todos los pasos estén implementados hoy.

```text
experiencia o recuerdo nuevo
    → representación del contenido y sus señales
    → vínculo con el episodio, el tiempo, el contexto y la procedencia
    → almacenamiento y asociaciones con origen identificable

consulta + intención + contexto permitido
    → varias pistas de recuperación
    → candidatos primarios y candidatos asociativos
    → evaluación de rutas, evidencia, contexto y competidores
    → respuesta: resuelto / ambiguo / insuficiente
    → consolidación controlada si existe evidencia fiable
```

### 4.1 Separar el contenido del episodio

Un recuerdo individual y el episodio al que pertenece no son necesariamente lo mismo. Un diseño completo debería poder relacionar varios recuerdos con un evento común sin fusionarlos ni perder sus diferencias. Para cada vínculo episódico conviene especificar, cuando se conozca:

- cuándo ocurrió el evento y cuándo se guardó o actualizó el recuerdo;
- qué elementos participaron y cuál fue su orden;
- el contexto y el motivo relevantes;
- la fuente y el grado de certeza;
- si se trata de una observación, una propuesta, una acción o un resultado.

La información contextual debe ser mínima, explícita y respetar las reglas de privacidad del proyecto. No se debe convertir el uso del agente en un registro oculto de entrenamiento.

### 4.2 Separar descubrir de decidir

La asociación debe poder proponer una pista o candidato sin que eso lo convierta inmediatamente en la respuesta. Un recorrido por el grafo responde «¿qué podría estar relacionado?»; un selector contextual responde «¿cuál de estos candidatos satisface lo que se pidió?». Son problemas distintos y deben medirse por separado.

Una salida honesta puede tener tres estados:

- **Resuelto:** hay evidencia suficiente para elegir un recuerdo.
- **Ambiguo o competido:** hay dos o más candidatos que responden plausiblemente, y falta una pista para desempatar.
- **Insuficiente:** la base no aporta evidencia adecuada; el sistema debe decirlo o pedir otra pista.

### 4.3 Conservar tanto la asociación como la incertidumbre

Los enlaces deberían distinguir, de forma auditable, su procedencia —por ejemplo, explícita, episódica, inferida o propuesta— y no tratar todos los enlaces como equivalentes. Un enlace automático no debe borrar un recuerdo ni sustituir un hecho. Si dos recuerdos discrepan, hay que conservar ambas fuentes y su tiempo, en vez de fundirlas en una versión inventada.

## 5. El problema de lo reciente y lo antiguo

La recomendación de diseño es no resolver la recencia con una única función de decaimiento global. Conviene separar al menos estos conceptos, aunque la base actual no los modele todos con el mismo detalle:

1. **Creación:** cuándo entró el recuerdo al sistema.
2. **Actualización del contenido:** cuándo cambió el hecho o su estado.
3. **Ocurrencia:** cuándo pasó el evento del que habla.
4. **Acceso o reactivación:** cuándo se consultó o volvió a activarse.
5. **Refuerzo fiable:** qué evidencia justifica fortalecer una asociación o la facilidad de acceso.

El tiempo debería ayudar a desempatar **dentro de una familia o contexto pertinente**, no volver más cierto a todo recuerdo reciente ni ocultar recuerdos antiguos. Una pregunta por «lo último» expresa una intención temporal; una pregunta por «qué ocurrió en la versión anterior» necesita recuperar lo antiguo.

Un principio de seguridad para la memoria:

> **Modificar la accesibilidad de un recuerdo no debe modificar silenciosamente lo que el recuerdo afirma.**

En la práctica, un sistema puede bajar la prioridad de un recuerdo, marcarlo como dormido u obsoleto y seguir permitiendo recuperarlo con una pista adecuada. Las actualizaciones y contradicciones deberían conservar historial y procedencia. El refuerzo de una asociación debe depender de una señal verificable y no solo de que el propio sistema la haya producido antes.

## 6. La neurona futura: selectora, no «hipocampo»

La intuición de Dennys de entrenar una neurona y después fijarla puede servir para una tarea acotada: aprender **qué candidato responde mejor a la intención**, dadas las señales que el motor ya encontró. Esa neurona sería más parecida a un selector o controlador aprendido que al hipocampo mismo.

Como mínimo, una selectora podría recibir señales de:

- la consulta, sus dimensiones y la intención expresada;
- la coincidencia del candidato con cada campo del recuerdo;
- el contexto episódico y la relación temporal pertinente;
- la ruta asociativa: saltos, tipo y peso de las aristas, convergencia de rutas y procedencia;
- la evidencia de vigencia, resultado y fuente, cuando esté disponible;
- la competencia: qué rasgo diferencia al candidato de sus rivales y si existe un empate real.

Su salida no debería ser solo «sube este nodo». También tendría que poder indicar «no hay evidencia suficiente» o «no puedo desempatar». La neurona no puede recuperar un candidato que nunca llegó al conjunto de candidatos, y no puede inferir una fecha, un resultado o una fuente que no se guardaron.

Para que una versión quede «fija» con responsabilidad:

1. entrenarla con respuestas de referencia fiables, no con sus propias predicciones;
2. incluir distractores difíciles: recuerdos del mismo tema pero de tipo, fecha o resultado distintos;
3. reservar preguntas y bases que nunca vio durante el entrenamiento;
4. compararla con el motor de base, conservar un piso y un límite de cuánto puede cambiar;
5. guardar una versión identificable y permitir retirarla si deja de pasar los controles;
6. separar los pesos de la neurona de los datos de cada persona: una cosa puede quedar congelada y la memoria seguir creciendo.

El aprendizaje en producción, el uso de señales del agente y cualquier registro asociado requieren respetar las autorizaciones y reglas de privacidad del proyecto. No se debe inferir una aprobación por el mero hecho de que técnicamente sea posible.

## 7. Qué falta para completar una memoria asociativa y qué falta para un organismo

### 7.1 Para una memoria asociativa más completa

1. **Vinculación episódica explícita:** representar qué recuerdos pertenecen a una misma experiencia y preservar tiempo, orden, contexto y procedencia.
2. **Pistas múltiples:** iniciar la recuperación desde contenido, dimensiones, relaciones, tiempo e intención, no depender de una sola coincidencia léxica.
3. **Compleción con límites:** permitir que una pista parcial llegue a recuerdos relacionados, con rutas y razones visibles, límites de expansión y control de hubs.
4. **Separación de competidores:** diferenciar recuerdos parecidos y que el criterio de selección sea relativo a los rivales, no solo a cada candidato por separado.
5. **Atención condicionada por la meta:** distinguir «lo último», «lo que falló», «el ejemplo» y «la explicación», aunque el tema sea el mismo.
6. **Gestión temporal:** separar creación, actualización, ocurrencia y acceso; recuperar versiones antiguas cuando la pregunta las pide.
7. **Plasticidad controlada:** definir cuándo crear, reforzar, debilitar, dormir o actualizar un vínculo, con origen, evidencia, límites y posibilidad de revisión.
8. **Monitoreo de certeza:** medir suficiencia y ambigüedad, mostrar procedencia y abstenerse cuando falte evidencia.
9. **Evaluación de extremo a extremo:** probar recuperación correcta, competidores, negativos, crecimiento del corpus, costo y repetibilidad en bases controladas.

### 7.2 Para un organismo artificial más amplio

MemoryBioRAG, por sí solo, es principalmente una arquitectura de memoria. Una aspiración de organismo artificial requeriría además cerrar un ciclo con:

- **percepción:** recibir señales del entorno y distinguir observación de inferencia;
- **memoria de trabajo y foco:** mantener temporalmente qué está haciendo y qué importa ahora, con reglas de privacidad;
- **metas y prioridades:** definir qué necesita resolver y qué recursos puede gastar;
- **acción y consecuencias:** actuar mediante herramientas autorizadas y evaluar el resultado;
- **modelo de sí mismo y continuidad:** saber qué aprendió, qué no sabe y de qué fuentes depende;
- **homeostasis computacional:** vigilar recursos, estabilidad, errores y condiciones para detenerse o pedir ayuda;
- **gobernanza:** permisos, límites de acción, reversión, auditoría y control humano.

Estos son requisitos de una visión de sistema, no funcionalidades que se deban añadir todas a la vez. «Vivo de silicio» puede ser el nombre de la aspiración; su cumplimiento debe definirse operacionalmente y no confundirse con vida biológica o consciencia.

## 8. Cómo saber si realmente avanzamos

La variación de EXP-Q entre una DB viva y un snapshot no demuestra por sí sola que el sistema haya aprendido ni que sea más parecido a un cerebro. Demuestra que cambió el estado de datos o las condiciones de la corrida hasta que se compruebe lo contrario. Para llamarlo adaptación hay que identificar qué cambió —recuerdo, asociación, peso, parámetro o código— y mostrar que el cambio produjo una mejora repetible.

Una validación seria debería:

- fijar código, configuración, base de origen y estado de la base para cada comparación;
- mantener snapshot y copia viva como condiciones diferentes, sin mezclar sus resultados;
- registrar métricas de recuperación, posición del objetivo, falsos positivos, abstención, latencia y costo;
- incluir consultas nuevas, recuerdos antiguos, recuerdos parecidos, asociaciones útiles, asociaciones distractoras y casos sin respuesta;
- demostrar que el sistema cambia de ganador cuando cambia la intención, no solo cuando cambia el tema;
- conservar la QA existente como piso y hacer experimentos sobre copias, nunca sobre la DB viva o el snapshot original;
- distinguir en cada informe **implementado**, **medido**, **propuesto** y **no evaluado**.

## 9. Criterio de éxito

El avance no se mide por cuántas neuronas, aristas o términos neurocientíficos se incorporan. Se mide por si el sistema puede:

1. guardar una experiencia sin confundirla con otras;
2. recuperarla desde pistas parciales y por asociaciones justificables;
3. seleccionar el recuerdo que responde a la intención presente;
4. reconocer la competencia y pedir otra pista cuando sea necesario;
5. aprender de evidencia fiable sin perpetuar sus propios errores;
6. conservar la historia y explicar de dónde salió una respuesta;
7. crecer sin degradar lo que ya resolvía.

La tesis de Dennys —**no emular por emular, sino construir un organismo de silicio**— queda traducida aquí como un programa de ingeniería: memoria asociativa, episódica y contextual; selección con criterio; plasticidad controlada; y evaluación que demuestre cada capacidad sin reclamar más de lo que la evidencia permite.

## 10. Documentos relacionados

- [Visión general de cómo recuerda BioRAG](README.md)
- [Mapa de la arquitectura neuro-simbólica](../arquitectura_neuro_simbolica/README.md)
- [Guía para crear y entrenar una neurona](../GUIA_CREAR_UNA_NEURONA.md)
