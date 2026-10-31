# Propuesta revisada: rúbrica, trayectorias y umbrales para E1 N/G/R

**Estado:** propuesta para revisión de Dennys. No modifica ni cierra el gold, no aprueba operativamente los umbrales y no autoriza preparar fixtures o ejecutar la campaña.

La aprobación de `e302fcd` es aprobación del **plan**, no autorización de ejecución. El plan de 2.768 llamadas está **planificado**, no autorizado para ejecutarse, y solo aplica si el gold no cambia. E1 es la campaña completa de 88 episodios/224 consultas; no es un smoke. El smoke sintético de una consulta no es gold de evaluación ni valida estas etiquetas.

## 1. Principios de evaluación

1. **Objetivo y pista útil son distintos.** El objetivo responde directamente a la pregunta/decisión. Una pista puede ser indirecta, inesperada o no útil de inmediato y aun así orientar una búsqueda posterior o contribuir a llegar al recuerdo objetivo.
2. **El ruido útil no se mata.** No llamar ruido a un recuerdo por ser no literal, indirecto, de otro tipo, de menor peso, de baja coincidencia léxica, por no llevar directamente al objetivo ni por aparecer en contexto/asociaciones en vez de `resultados`. No filtrar, borrar, ocultar ni cortar conexiones para mejorar una métrica.
3. **Ruido tonto requiere evidencia positiva de irrelevancia o daño.** Una pista no se vuelve ruido por no haber sido seguida, por no producir una respuesta inmediata o porque la trayectoria acabó antes de probar su valor. Si está relacionada pero su aporte no se confirma, clasificarla como neutral/potencial/no atribuible, no como ruido.
4. **No convertir la evaluación en una carrera por recuperar más candidatos.** Separar recuperación de objetivo, descubrimiento de pistas, uso de pistas, resultado final y coste de llamadas. Más búsquedas o más asociaciones visibles no equivalen por sí solas a mejora.
5. Etiquetar la relación por **consulta y por trayectoria**: un recuerdo puede ser objetivo para una pregunta, puente para una búsqueda posterior, útil tardío para el resultado final o neutral para otra pregunta. La mera pertenencia al episodio o al grafo no basta.

## 2. Rúbrica semántica: recuerdo, pista y ruido

La anotación se hace sobre la pregunta/tarea y el texto íntegro del recuerdo; no se muestran a los anotadores tipo, peso, dirección de arista, score, ranking, canal MCP ni brazo. Una pista que emerge durante la cadena se evalúa con el historial completo, no solo contra la pregunta inicial.

| Etiqueta | Criterio operativo | No basta para asignarla |
|---|---|---|
| **`objetivo`** | El recuerdo responde directamente a la necesidad actual o contiene la evidencia que permite responder. Registrar fragmento probatorio y justificación. | Compartir palabras, pertenecer al episodio o ser el nodo nombrado por una ruta.
| **`pista_util`** | Aporta un vínculo, condición, comprobación, causa, cautela o acción que puede ayudar a decidir o a formular una búsqueda posterior. Puede ser útil ahora, más tarde o solo al verse el trayecto completo. | No ser literal, no llevar directamente al objetivo, o no tener efecto inmediato.
| **`puente_de_busqueda`** | Pista que inspira una consulta posterior semánticamente relacionada. Marcar la consulta siguiente y el fragmento/ID que la motivó, si esto es observable o está declarado por el agente. Puede ser un puente aunque el objetivo no se alcance. | Que la consulta siguiente ocurra después; la sucesión temporal sola no demuestra que la pista la causó.
| **`utilidad_tardia_confirmada`** | Pista que no fue útil inmediatamente pero que, en el trayecto completo, ayuda a interpretar una búsqueda intermedia o a llegar/justificar el recuerdo objetivo. Requiere adjudicación con evidencia de los pasos posteriores. | La simple presencia previa al objetivo o una similitud léxica.
| **`potencial_no_confirmado`** | Relación semánticamente plausible, pero la trayectoria no alcanza un punto que permita confirmar su aporte. No se cuenta como pista confirmada ni como ruido. | Que no se haya confirmado en esta trayectoria.
| **`neutral_contexto`** | Contexto relacionado que no tiene un aporte concreto demostrado en la tarea observada. | No debe forzarse a útil o ruido para completar categorías.
| **`ruido_tonto`** | Contenido positivamente irrelevante, engañoso, contradictorio o distractor para la tarea/decisión observada; requiere evidencia y motivo. | No ser objetivo, no ser seguido, no producir éxito inmediato, tener menos peso o ser asociación indirecta.
| **`no_adjudicado`** | Evidencia insuficiente o desacuerdo aún sin resolver. Se excluye de métricas de categoría. | Un array vacío o una etiqueta faltante no equivalen a “ninguno” ni a ruido.

Las etiquetas `objetivo`, `pista_util`, `neutral_contexto` y `ruido_tonto` son por par consulta–recuerdo; una pista puede recibir además etiquetas de trayectoria `puente_de_busqueda` o `utilidad_tardia_confirmada`. Si un recuerdo contiene respuesta y una pista adicional independiente, se mantiene `objetivo` y se anota la proposición adicional aparte; no se degrada el recuerdo ni se duplica el objetivo. El mismo recuerdo puede tener roles distintos en diferentes búsquedas.

Para listas vacías, exigir estado explícito `adjudicado_sin_objetivo`, `adjudicado_sin_pista` o equivalente. `no_adjudicado` es distinto. No reportar métricas de utilidad/ruido para categorías vacías no adjudicadas.

## 3. Protocolo propuesto para búsquedas encadenadas con agente y MCP real

Esta es una **extensión secundaria** de la evaluación fija, no una reinterpretación de las 224 consultas ni una autorización de ejecución. Su objetivo es registrar qué hace el agente con los resultados MCP reales a lo largo de una trayectoria.

### Semillas y límite de trayectoria

- Propuesta de conjunto: una tarea inicial por episodio, 88 en total: la consulta `principal` de cada episodio positivo (48) y un control preseleccionado por episodio negativo (40), balanceado por estrato. Fijar las 88 semillas en el manifiesto antes de observar salidas.
- Para cada tarea×brazo, iniciar desde una copia limpia aislada. El agente usa el servidor MCP real y solo la herramienta de búsqueda `recordar`; cada llamada sucesiva conserva el estado de diálogo del agente y la misma copia aislada de esa trayectoria. No llamar `aprender`, `vincular`, herramientas de edición ni despertar nodos.
- Máximo propuesto: **3 búsquedas MCP por trayectoria** (una inicial y hasta dos seguimientos), sin reintentos automáticos. Es un límite de presupuesto para esta evaluación, no una definición de cómo debe recordar ni un comportamiento deseable del agente. La sesión compartida que necesitó cuatro llamadas ilustra que el límite puede interrumpir un proceso todavía útil: si se alcanza antes de resolver, marcar `interrumpida_inconclusa_por_presupuesto`, conservar la trayectoria y no concluir “no hay recuerdo”, “no existe pista” ni “falló el agente”. El agente puede parar antes; no hay objetivo de usar las tres llamadas. Registrar el motivo de parada.
- El prompt, modelo/versión, parámetros, herramientas disponibles y política de parada se congelan antes del primer resultado. El agente no ve gold, objetivos, etiquetas ni respuestas esperadas; recibe la tarea y las respuestas reales de MCP. No se modifica el motor/ranking ni se recortan conexiones para generar una pista “limpia”.
- Cada transición conserva una ficha compacta del agente —`source_step`, IDs de recuerdos citados si los declara, intención de búsqueda y consulta siguiente—, sin pedir ni registrar razonamiento privado extenso. Retener los mensajes visibles de la interacción, el sobre exacto del tool call y la respuesta MCP en orden. Esta ficha es una declaración del agente, no prueba de causalidad.

### Trayectoria y evidencia que deben conservarse

Por cada tarea y brazo, mantener una secuencia ordenada e inmutable:

1. Consulta inicial exacta, configuración N/G/R y hashes de copia/fixture.
2. Para cada paso: `step_id`, consulta exacta y argumentos enviados, proceso/sesión MCP, respuesta cruda y parseada, candidatos completos, canales, rangos/score tal como fueron devueltos, trazas explícitas MCP si existen, errores y tiempos.
3. Registro del agente entre llamadas: memoria(s) que declara haber usado, intención, consulta siguiente exacta o decisión de parar. No sustituirlo por una explicación generada retrospectivamente.
4. Cuándo y en qué canal aparece por primera vez cada objetivo; si el agente lo incorpora a su respuesta final; qué evidencia/IDs cita; y resultado final evaluado por los anotadores.
5. Hashes, eventos, errores y snapshots/diffs disponibles; ninguna discrepancia se corrige en sitio. Las aristas se conservan completas.

El **presupuesto planificado, no autorizado, de 2.768 llamadas** cubre solo las dos construcciones y las 224 consultas de una sola llamada en cada uno de cinco brazos. No cubre esta extensión secuencial. Si Dennys la aprueba con el alcance propuesto, su tope adicional sería `88 tareas × 5 brazos × 3 búsquedas = 1.320 llamadas MCP` (menos si el agente para antes), sin reintentos. El techo combinado meramente propuesto sería 4.088 solo si el gold no cambia y se autorizan ambos componentes. El uso de modelo/agente, llamadas auxiliares del proveedor y arranque/cierre de procesos se contabiliza aparte del número de herramientas MCP. Todo cambio del conjunto o arms exige recalcular y obtener autorización antes de ejecutar.

### Mantener N/G/R y detectar ráfaga, despertar o mutaciones en cada paso

`deep=False` no basta para demostrar que no ocurrió una ráfaga ni que el estado quedó intacto. Para cada llamada de cada trayectoria, exigir parámetros efectivos, traza y auditoría antes/después:

| Brazo | Parámetros que deben mantenerse en cada búsqueda |
|---|---|
| **N0** | `deep=False`, `asociados=False`, `context_window=0`, `forzar_rafaga=False`, `rafaga_palabras=None`. |
| **N1** | Igual a N0 salvo `asociados=True`. |
| **G1/G2** | Igual a N1 con `context_window=1/2`. |
| **R** | `deep=False`, `asociados=True`, `context_window=0`, `forzar_rafaga=True`; `rafaga_palabras` se deriva por regla congelada de `sustantivos_clave` de esa consulta, no de una instrucción independiente u oculta del agente. Congelar antes cómo obtener esos términos para consultas dinámicas y persistirlos. |

Antes de cada llamada comprobar y registrar que los argumentos realmente enviados coinciden con el manifiesto; no corregirlos en silencio. En N/G, omitir `rafaga_palabras`/enviarlo como `None`: con la interfaz actual pasar términos incluso con `forzar_rafaga=False` puede habilitar el fallback automático. Rechazar llamada N/G si llegan términos de ráfaga o `forzar_rafaga=True`. Registrar respuesta `trazabilidad.capa_rafaga`; si marca actividad en N/G, invalidar y parar. Si falta la traza, no afirmar que la ausencia de capa quedó observada; señalarlo como no verificable y exigir una guarda previa compatible con la versión congelada antes de interpretar el brazo.

En cada paso, sobre la copia propia de `tarea×brazo`, capturar antes/después estado de todos los nodos, filas de recuerdos/sinapsis/`sdm_dirty`, grafo completo, hashes, respuesta MCP y diff por fila/campo. Comprobar integridad/estado antes y después; en **R**, todos los nodos deben estar activos antes de cada llamada y seguirlo después. `N/G` no permiten cambios en sinapsis ni estados; R permite solo mutaciones de ráfaga de su whitelist fija y nunca cambio/despertar de estado. Si aparece un nodo dormido donde R exige activo, `estado` cambia, hay mutación fuera de whitelist, parámetros derivan o se detecta ráfaga en N/G, parar la cadena, conservar evidencia y marcarla inválida/interrumpida; no seguir con el paso siguiente ni alterar conexiones. Los cambios de grafo permitidos de R permanecen en la copia de esa trayectoria para que el siguiente paso refleje el estado observado; no se restauran/filtran entre pasos. Cada otra tarea y brazo parte de copia limpia e independiente.

## 4. Qué se observa y qué no se puede atribuir

Clasificar explícitamente cada conclusión:

- **Observado en MCP:** llamada, consulta exacta, respuesta/candidato/canal/rango, orden temporal y aparición de objetivo. Se acredita con log crudo/parseado y hash.
- **Declarado por el agente:** el registro estructurado dice qué recuerdo usó para componer la siguiente consulta. Prueba lo que el agente declaró, no el mecanismo interno que causó la decisión.
- **Adjudicado semánticamente:** los revisores juzgan si la pista ofrece un puente defendible a la siguiente búsqueda o ayuda más tarde en la trayectoria. Es una valoración humana sobre el trayecto observado, no una traza de ejecución interna.
- **Ruta MCP atribuible:** solo si la respuesta contiene traza explícita suficiente (`desde`, `hasta`, ruta/saltos) y concuerda con el grafo activo de la copia. La presencia en `contexto_expandido` o el shortest path calculado offline no demuestra que MCP recorriera esa ruta.
- **No atribuible:** si falta traza o vínculo verificable entre recuerdo y siguiente consulta, aunque la pista preceda al objetivo. Registrar “no atribuible”, no inferir causalidad por orden temporal, coaparición o similitud textual.

Una trayectoria puede mostrar que el objetivo aparece después de una pista y que la siguiente consulta del agente se relaciona con ella; se reporta como **contribución compatible observada**, no como prueba de que esa pista fuera necesaria o causara el éxito. Sin una comparación causal autorizada no atribuir causalidad. Esta propuesta no prescribe quitar, ocultar ni cortar recuerdos/conexiones para crear contrafactuales.

## 5. Reglas de medición y umbrales revisados

Los valores siguen siendo propuestas para Dennys. Se evita premiar volumen de búsqueda, precisión aparente obtenida suprimiendo asociaciones, o recall agregado que solo mejora acumulando llamadas.

### Guardarraíl que se mantiene

- El piso **R@5 del objetivo ≥95%** sobre las 96 consultas contestables actuales (al menos 92/96) sigue siendo solo un umbral candidato, aún no aprobado por Dennys. Medirlo en `resultados` de la primera búsqueda. Se retira la tolerancia propuesta de “una pérdida”: no hay margen de no-inferioridad aprobado.
- En toda comparación N/G/R, reportar diferencias pareadas exactas frente a N0 para recall de objetivo y recall/cobertura de pistas útiles adjudicadas, por separado, con numeradores/denominadores por canal/estrato. Cualquier descenso se señala como regresión; no ocultarlo en un promedio ni compensarlo con ganancia de otra categoría. No declarar mejora global si uno de esos recalls disminuye. La interpretación final de Dennys queda pendiente de aprobar el criterio de decisión.
- En la extensión encadenada, informar objetivo encontrado tras llamada 1, 2 o 3 y si el agente lo usó en la respuesta. No sustituir el R@5 inicial por “recuperado alguna vez”. La curva por paso siempre va acompañada del número/coste de llamadas. Si se alcanza el límite antes de resolver, registrar trayectoria interrumpida/inconclusa, no ausencia de recuerdo.
- R@1/MRR y canales laterales se presentan aparte; no redefinen el objetivo ni borran pistas útiles.

### Umbrales anteriores retirados como metas de optimización

- **Retirar** `recall de pistas ≥70%` y `cobertura de episodio ≥75%` como criterios de aprobación: podrían incentivar más búsquedas, más salidas o una clasificación permisiva de utilidad. Mantenerlos solo como estadísticas descriptivas, desglosadas por canal, paso y número de llamadas; toda pista tardía o potencial se explica aparte.
- **Retirar** el máximo porcentual de `ruido_tonto` (antes ≤10%) y el umbral porcentual de ruido en abstenciones (antes ≤5%) como metas de aprobación/ranking. Una proporción depende de qué apareció y cuántas llamadas se hicieron, y puede inducir a suprimir asociaciones. En su lugar, informar conteos y tasas por trayectoria/paso/canal, con denominador de candidatos efectivamente adjudicados, y revisar cada caso perjudicial. `neutral_contexto`, `potencial_no_confirmado` y `no_adjudicado` quedan fuera del numerador de ruido.
- Un falso recuerdo presentado como respuesta final en una tarea de abstención se marca como **incidente para revisar**, conservando evidencia; no genera permiso para filtrar el grafo. Cualquier llamada o mutación fuera de alcance invalida la ejecución conforme a las guardas, no se “arregla” alterando conexiones.

### Métricas de trayectoria, sin premiar más llamadas

Informar, por tarea, brazo y paso: (a) objetivo en resultados/contexto/asociaciones; (b) primera llamada donde aparece; (c) respuesta final correcta y respaldo citado; (d) pistas previstas e inesperadas, utilidad inmediata/tardía, puente a la siguiente consulta, neutralidad, potencial no confirmado o ruido adjudicado; (e) llamadas acumuladas, consultas repetidas, consulta sin avance y motivo de parada. Publicar `éxito@1`, `éxito@2`, `éxito@3` como una curva descriptiva con coste, sin convertir el valor mayor en éxito automático ni fijar un umbral de éxito por número de búsquedas.

La cobertura de pistas se informa como distribución/recall solo sobre etiquetas cerradas y candidatos adjudicados; no se rellena con negativos por ausencia. El ruido se adjudica con la rúbrica de §2 y con el contexto de la trayectoria completa: que una pista no ayude inmediatamente o no llegue al objetivo no basta para llamarla ruido.

## 6. Dos anotadores independientes y adjudicador

### A. Gold, antes de resultados

1. Dennys aprueba y versiona rúbrica, criterios, umbrales y hoja; designa dos anotadores competentes en español/inglés y un adjudicador. El gold se revisa aunque no cambie el JSONL.
2. Ambos anotan las mismas consultas y recuerdos relevantes independientemente, con IDs seudónimos y orden distinto. Se ocultan etiquetas existentes, resultados de brazos, ranks/scores/canales, enlaces y tipo/peso del grafo. Registran rol, evidencia, justificación y estado explícito de categorías vacías.
3. Mantener cada anotación original. Como las etiquetas `objetivo`/`pista`/`neutral`/`ruido` son nominales y no tienen un orden ordinal justificado, no usar kappa ponderado. Calcular acuerdo bruto y Cohen κ **no ponderado** para las categorías mutuamente excluyentes; para etiquetas múltiples, informar acuerdo por etiqueta/clase (incluido acuerdo positivo) y conservar tablas de confusión. Los propuestos ≥85% de acuerdo bruto y κ ≥0,70 siguen sujetos a aprobación. Si no se alcanzan, aclarar rúbrica y repetir la pasada ciega antes del cierre, nunca después de observar resultados.
4. El adjudicador resuelve todas las discrepancias objetivo↔pista↔neutral↔ruido y todo caso no adjudicado, basándose en consulta y evidencia textual. Registra decisión y razón; no usa voto automático ni características de sinapsis.
5. Cerrar el hash y ledger antes de cualquier resultado, incluso con cierre no-op del gold base. Los adjudicadores de resultados posteriores no reescriben el gold cerrado.

### B. Trayectorias y pistas inesperadas, después de una campaña autorizada

Un conjunto distinto presenta a ambos revisores la trayectoria completa en orden temporal, pero oculta brazo, score, rango y orden de preferencia entre brazos. Cada revisor marca: pistas que no estaban en el gold inicial; si inspiraron la consulta siguiente; si el aporte fue inmediato, tardío, puente, potencial no confirmado o neutral; si el objetivo aparece después y si la respuesta final está respaldada. Deben citar pasos/IDs y fragmentos, y separar observación, declaración del agente e inferencia semántica. No etiquetan como ruido una pista porque no sea seguida o no conduzca directamente al objetivo.

El adjudicador resuelve desacuerdos después de conservar ambas etiquetas iniciales. Una relación que solo es temporal o plausible queda “no atribuible” o “potencial”, no causal ni automáticamente útil. El gold y sus métricas originales permanecen congelados; cualquier cambio requiere nueva versión y nueva aprobación antes de otra medición.

## 7. Revisión de Dennys y límites

Pendiente de aprobación explícita de Dennys: rúbrica, umbrales de acuerdo/recall, tratamiento de pistas tardías e inesperadas, alcance de las 88 trayectorias, máximo de tres búsquedas, prompt/modelo/parámetros del agente, política de parada y presupuesto adicional.

**Solo documentación:** no se prepararon bases/fixtures, no se inició MCP, no se ejecutaron agentes, mediciones ni QA. No se modificó motor, ranking, grafo ni gold. La extensión de trayectorias no está incluida en la autorización del plan anterior ni en sus 2.768 llamadas. **W sigue pendiente.**
