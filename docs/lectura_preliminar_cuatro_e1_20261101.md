# Lectura preliminar de otras cuatro preguntas E1 — 2026-11-01

## Alcance

Se cotejaron las preguntas, presentaciones y originales de cuatro casos adicionales a los seis de `lectura_preliminar_seis_e1_20261101.md`: **19 pares**, con **6 desacuerdos** entre las pasadas exploratorias. Se revisaron también los elementos donde ambas coinciden, no solo los desacuerdos. El orden de selección fue el de la vista, omitiendo los seis casos ya examinados y escogiendo los primeros cuatro casos restantes con desacuerdos; no es una muestra aleatoria.

Fuente local privada: `vista_adjudicacion_sin_gold.md`, SHA-256 `eaf0a27d8eedb63b179d69f971ab2ddee90edee6041f097c7ec01e3158a5d10c`; control de pares SHA-256 `583946c1b26283b02b815f43ef11c2c8f2374872ad411178dc55329161fadaaf`. Ambos se recuperaron de Drive y sus hashes coincidieron. Esta lectura se hizo **con las opiniones y los originales a la vista**: no es ciega ni independiente, no adjudica gold y no evalúa el motor. Los títulos originales pueden sesgar el juicio; no se tratan como etiquetas correctas. El texto sintético se cita de forma limitada para explicar las dudas, sin publicar recuerdos de la base viva.

## Lectura por caso

### Indicador para aplicar idempotencia — `case-d1e13bef4f904783`

- `item-36a7005b2e768df6` dice que el duplicado permite reconocer cuándo aplicar idempotencia. Da un candidato nombrado a la pregunta; no explica cómo detectar el duplicado ni bajo qué condición exacta. Las pasadas discrepan sobre respuesta directa o pista. Si basta un indicador nombrado, puede considerarse respuesta; si se exige una comprobación operacional, falta detalle. Ambas posibilidades quedan abiertas.
- `item-026fcedda3193b2b` conecta idempotencia, reintento y comprobación del proveedor, pero no identifica qué se comprueba. Es una relación para seguir investigando, aunque Gemini la marcó directa. `item-259b70ee09656010` describe una acción concreta con la misma clave ante demora y su propósito de evitar duplicación; puede aportar procedimiento y contexto aunque no nombra explícitamente un indicador de decisión. Las pasadas discrepan en ambos.
- `item-7c5251bf99735ec7` e `item-0d4fdeacbd9efd11` contienen ejemplos sintéticos ajenos a la tarea según sus propios textos; ambas pasadas coincidieron en IP. Eso no establece una regla general para eliminar recuerdos lejanos ni demuestra que un agente explorador no pueda aprovechar contexto en otras situaciones.

### Indicador para aplicar caducidad — `case-a10f254084bef621`

- `item-54041b33b7741450` afirma que la exposición permite reconocer cuándo aplicar caducidad; ambas pasadas la marcaron directa. El texto **afirma** esa relación, pero no explica su mecanismo ni demuestra que exposición y caducidad sean equivalentes. El acuerdo no comprueba que la relación técnica sea correcta. Es importante distinguir contestar conforme a la premisa del texto de verificar la validez operativa de esa premisa.
- `item-563cceb192ed72ad` propone revocar y rotar ante exposición. Las pasadas discrepan: describe una respuesta a exposición, pero no explica aplicar caducidad ni proporciona una medida temporal. No debe tratarse revocación, rotación y vencimiento como sinónimos sin comprobarlo; puede servir como pista para investigar las relaciones.
- `item-4fd2bba466817925` relaciona caducidad, rotación y comprobación útil, sin indicar qué se comprueba; ambas pasadas la consideraron pista. `item-2825c074f59bbcc0` e `item-6e540219d0115613` son ejemplos que el propio texto presenta como ajenos a la tarea; ambas pasadas coinciden en IP. Esas coincidencias tampoco constituyen adjudicación.

### Indicador para aplicar ventana — `case-2447a2ce7312bfbf`

- `item-970fde37355b25cc` afirma que la saturación permite reconocer cuándo aplicar ventana; ambas pasadas la marcaron directa. Nombra un candidato, pero no define saturación, umbral ni cómo decidir sobre la ventana. La suficiencia depende de si se pide solo un nombre; su corrección técnica requiere evidencia adicional.
- `item-d9c91fe84dbd2abf` propone aplicar limitación de tasa para un límite de solicitudes, pero no indica qué medir ni cómo identificar la saturación; las pasadas discrepan entre pista y directa. `item-bb8f907e89722e82` conecta ventana y limitación con una comprobación sin especificarla; ambas la consideraron pista. Ambos pueden orientar una búsqueda posterior sin resolver por sí solos la pregunta en todos sus sentidos.
- `item-7402a89d5b575737` e `item-26b5199e72015c64` son ejemplos sintéticos descritos como ajenos; ambas pasadas coinciden en IP. No se aplica por ello ningún filtro al sistema.

### Medida ante demora — `case-96a1129f50c84805`

- `item-795c194abced8229` ofrece usar una clave estable al reintentar y afirma que el proveedor deduplica; ambas pasadas la marcaron directa. Es una medida concreta, pero depende de la conducta atribuida al proveedor y la pregunta aislada no especifica el escenario completo. Esa dependencia no se convierte automáticamente en hecho sobre un proveedor real.
- `item-b9cb379ae73351db` propone conservar la clave durante todo el horizonte de reintentos e identifica el riesgo de caducidad prematura. Las pasadas discrepan entre pista y directa. Es una medida concreta relacionada con seguridad de reintentos, aunque no ordena por sí misma cómo actuar ante la demora; su utilidad no depende de resolver esa clasificación.
- `item-b4f2eec82ba01887` propone registrar una comprobación para que otra persona continúe; ambas pasadas la marcaron neutral. Puede ayudar a la continuidad operativa sin especificar la comprobación ni responder necesariamente a la demora. `item-4013a1066f40ee90` es un ejemplo sintético declarado ajeno; ambas coinciden en IP. Ningún acuerdo certifica la etiqueta ni autoriza descartes.

## Transformaciones y riesgo de anclaje

Los **19 originales** llevan un encabezado numerado retirado en la presentación; los cuerpos mostrados coinciden por pares tras retirar ese encabezado. Se observaron encabezados que sugieren objetivo, pista, paso intermedio, guía, apoyo o distractor. Retirarlos reduce ese encuadre, pero también elimina información contextual o de prioridad que podría influir en una lectura. No se concluye automáticamente que el impacto sea material o inmaterial para cada uso, ni que un encabezado indique la respuesta correcta. En estos cuatro casos no se observó reemplazo del marcador de acción primaria ni eliminación de sufijo.

## Hallazgos transversales y estado

1. **Indicador nombrado frente a condición comprobable:** una palabra puede contestar una pregunta que pide un nombre, pero no equivale a un procedimiento, umbral o validación. La pregunta debe determinar qué nivel se exige, sin desechar la pista.
2. **Respuesta al texto frente a corrección del dominio:** una presentación puede afirmar una relación y parecer contestar literalmente; eso no verifica la relación en el mundo ni la hace segura para operar. Caducidad/exposición y ventana/saturación son ejemplos para comprobación, no errores técnicos adjudicados automáticamente.
3. **Acción, condición y apoyo:** una medida concreta o una nota de continuidad pueden aportar información útil aunque la pregunta pida otra clase de dato. Un acuerdo entre revisores tampoco equivale a verdad o irrelevancia universal.
4. **Agente más cerebro:** estas observaciones examinan textos aislados, no trayectorias reales. El valor asociativo final puede aparecer después de otras búsquedas y no puede medirse desde estas etiquetas. No se exige revelar intuiciones ni se infiere causalidad de una secuencia.

En conjunto con la lectura anterior se han examinado **10 preguntas y 49 presentaciones** mediante estas dos lecturas no ciegas. Permanecen pendientes las restantes, la revisión humana de las 156, los 28 desacuerdos como adjudicaciones y W. Ninguna etiqueta gold se cambia o aprueba. No se ejecutó E1, no se entrenaron neuronas y no se alteraron motor ni bases.
