# Lectura preliminar de seis preguntas E1 — 2026-11-01

## Alcance y límites

Se examinaron las seis preguntas del paquete ciego en las que la primera pasada no asignó ninguna respuesta directa y la segunda asignó al menos una. Son **6 de las 33 preguntas** del paquete; sus 30 presentaciones fueron leídas en conjunto con las opiniones de ambos agentes y la vista de los originales. No son una evaluación del motor, una muestra representativa del gold completo ni prueba de pérdida de recall.

Esta lectura la realiza una agente que ya vio las dos opiniones, el contexto de la conversación y los textos originales. **No es ciega ni independiente**, no sustituye una adjudicación humana y no establece etiquetas gold. Los códigos opacos se usan solo para trazar los pares; no se consultaron los campos de roles gold del crosswalk para tomar estas decisiones. La vista original puede incluir títulos que sugieren rol: se consideraron solo como riesgo de anclaje, no como verdad.

Para cada pregunta se identifica lo que efectivamente pide, evidencia pertinente y lo que queda sin especificar. Una asociación puede ser una pista valiosa aunque no conteste directamente; no se propone descartar, filtrar ni borrar ningún recuerdo. El mismo fragmento puede tener otro papel en otra consulta o trayectoria.

## Lectura pregunta por pregunta

| Pregunta | Evidencia y lectura provisional | Duda que debe seguir abierta |
|---|---|---|
| **¿Cómo espaciar los reintentos?** (`case-6352fef77de3f695`) | `item-e0acc655c88dd1c8` vincula *backoff* con reintentos; `item-1be1e007df311b65` relaciona timeout y reintento. Ninguno indica intervalos ni explica una regla de espera en el texto presentado. Ambos pueden orientar otra búsqueda. | Si se permite conocimiento técnico externo, nombrar *backoff* puede identificar una familia de estrategias; si se exige que el propio texto explique el mecanismo, queda como pista. No se fuerza una categoría definitiva. Dennys ya observó que timeout/reintento está relacionado pero no explica el espaciado; el auditor explicó *backoff* antes de solicitar su criterio y pudo influir. |
| **¿Qué parámetro distribuye las solicitudes en el tiempo?** (`case-9c485d0cfe811d9b`) | `item-562eeed945a79972` menciona ventana y su asociación con limitación de tasa; `item-9175b880f74ea00d` menciona el mecanismo general. El texto no describe la función temporal de la ventana ni un valor. | Que el término *ventana* sea suficiente depende del conocimiento permitido y de si la pregunta pide un nombre o una explicación de funcionamiento. La asociación con limitación puede servir para continuar buscando aunque no resuelva por sí sola. |
| **¿Qué señal anticipa el vencimiento?** (`case-2642bfbbafbaf920`) | `item-78611093974f8256` menciona alerta asociada a rotación de certificado; `item-c0c99dedd2886bdc` relaciona vencimiento con rotación. El texto no dice cuándo se dispara la alerta ni que sea previa al vencimiento. | Una alerta puede ser candidata a señal, pero el carácter anticipatorio no está expresado en el texto. Rotar ante un vencimiento y anticiparlo no son necesariamente la misma tarea. |
| **¿Qué se puede revisar para detectar una versión obsoleta?** (`case-7ca46cc4a66273b4`) | `item-b72648ff7f328b8f` describe invalidar o versionar claves tras una actualización para evitar datos viejos; `item-1b9e98f5751a58fe` vincula versionado y actualización de caché. Son pistas sobre el problema, pero no explicitan una comparación que detecte una versión obsoleta. | Mitigar lecturas viejas puede ayudar a investigar qué revisar, pero no equivale necesariamente a describir una comprobación de detección. El primer texto no fue transformado. |
| **¿Qué tipo de concesión temporal libera un bloqueo abandonado?** (`case-d74505328854887f`) | `item-477e0165ee99ebbf` nombra *lease* asociado a bloqueo; `item-b4646619caacd14a` menciona concurrencia y bloqueo. La definición de concesión temporal y su liberación al vencer no aparece en esos textos. | Si quien interpreta conoce el término, *lease* podría identificar el tipo; sin ese conocimiento, la afirmación visible solo asocia componentes. La pregunta presupone una relación temporal que debe verificarse, no rellenarse silenciosamente. |
| **What check allows a safe retry?** (`case-1155d1aa247141b4`) | `item-ddfdeb1c077b56bc` relaciona cola bloqueada con *safe replay*; `item-336d81a260e4feaa` describe enviar un mensaje inválido a una cola de mensajes fallidos. Ninguno especifica en el texto qué comprobación permite afirmar que repetir es seguro. | Una condición operacional, una ruta alternativa y una comprobación de seguridad no son automáticamente equivalentes. Pueden orientar una búsqueda posterior, pero no debe inferirse una contraindicación o una respuesta completa sin más evidencia. |

Los otros textos de estas seis preguntas incluyen trazabilidad genérica y ejemplos que declaran no guardar relación con la tarea. Sus funciones dependen de la pregunta y el contexto; esas descripciones no son una regla global de filtrado. Los juicios preliminares no se convierten en cambios del gold.

## Efecto de las transformaciones

El control mecánico de los 30 pares registra **29 textos modificados y uno idéntico**. Se aplicaron 25 eliminaciones de títulos, cuatro reemplazos del marcador de acción primaria y una eliminación de sufijo; una presentación recibió dos reglas, por lo que 30 aplicaciones corresponden a 29 textos cambiados.

La eliminación de títulos puede retirar un encuadre que sugiere objetivo, pista o irrelevancia. El cambio de «acción primaria» a «acción» conserva la acción, pero elimina un matiz de prioridad. El sufijo en inglés también declara prioridad. Ninguna de esas marcas agrega por sí misma la regla temporal, el indicador, la comprobación o la definición que falta en los ejemplos anteriores. Esto es una **lectura provisional de agente**, no una prueba concluyente de impacto semántico ni un registro completo de las 156 presentaciones.

## Propuesta acotada para avanzar sin perder pistas

En lugar de decidir automáticamente un único rol, registrar dos observaciones separadas por par:

1. **Evidencia textual:** qué parte exacta de la necesidad puede contestarse usando el texto visible; si se nombra una técnica, indicador o acción, conservar ese dato sin inventar una explicación o un valor que no aparece.
2. **Interpretación o búsqueda del agente:** qué podría aportar el conocimiento declarado del agente y qué búsqueda sucesiva permitiría comprobar la asociación. Esta es una posibilidad o una conducta observada, según corresponda; no una explicación retrospectiva de lo que el agente hizo ni una certeza sobre causalidad.

Si una respuesta depende del significado de un término no definido en el recuerdo, anotar esa dependencia y mantener abierta la clasificación. Si el texto solo aporta contexto o una posible pista, conservarlo para la trayectoria; no equiparar «no resuelve directamente» con «ruido». Esta propuesta es una guía provisional, no una modificación de la rúbrica aprobada ni una autorización para cambiar gold.

## Siguiente paso y estado

Agrupar las dudas transversales antes de solicitar criterio humano puntual: (1) cuánto conocimiento externo puede completarse al juzgar una respuesta directa, (2) nombre de técnica frente a explicación o valor, y (3) contexto, acción o condición frente a indicador/comprobación solicitados. Mantener por separado el valor de una pista para búsquedas sucesivas. Las seis preguntas no agotan las demás discrepancias ni la evaluación de originales del paquete completo.

Gold abierto; 28 desacuerdos pendientes; cotejo semántico humano de 156 elementos pendiente; W pendiente. No se ejecutó E1, ni se entrenaron neuronas, ni se modificaron motor o bases.
