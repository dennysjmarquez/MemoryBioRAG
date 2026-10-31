# Propuesta de rúbrica y criterios/umbrales para E1 N/G/R

**Estado:** propuesta para revisión y aprobación de Dennys. No modifica ni cierra el gold, no aprueba operativamente los umbrales y no autoriza preparar fixtures o ejecutar la campaña.

La aprobación de `e302fcd` es aprobación del **plan**, no autorización de ejecución. Esta propuesta desarrolla la rúbrica previa requerida para una futura campaña E1 completa: 88 episodios y 224 consultas, no un smoke. El smoke sintético de una consulta no cuenta como gold de evaluación ni como validación de estas etiquetas.

## 1. Principios de evaluación

1. **El objetivo y las pistas útiles son etiquetas distintas.** Objetivo es lo que responde directamente a la pregunta/decisión. Pista útil aporta una conexión defendible que ayuda a decidir, diagnosticar, recordar una condición, avanzar una acción o ampliar de forma pertinente la solución; no tiene que ser la respuesta literal.
2. **El ruido útil no se mata.** No llamar ruido a un recuerdo por ser no literal, indirecto, de otro tipo, de menor peso, de baja coincidencia léxica, o por aparecer en una arista/contexto en vez de `resultados`. El grafo puede motivar revisar una relación, pero no decide su etiqueta semántica.
3. **Ruido tonto requiere evidencia positiva de irrelevancia o daño.** Solo etiquetar así un recuerdo que no ayude a la tarea y sea distractor, contradictorio o engañoso. Si es relacionado pero no aporta una acción o inferencia clara, usar `neutral/contexto`, no `ruido_tonto`. Si no hay base para decidir, usar `no_adjudicado`, nunca completar el vacío como ruido.
4. **No perder recall por afinar precisión.** No filtrar ni eliminar recuerdos/asociaciones. Medir recall de objetivos y recall de pistas por separado, en todos los canales pertinentes. Una pista útil visible pero no literal no es falso positivo del objetivo ni ruido; es una recuperación útil en una categoría aparte.
5. Etiquetar la relación **para cada consulta concreta**: el mismo recuerdo puede ser objetivo para una consulta, pista útil para otra y neutral o irrelevante para una tercera. La mera presencia en el mismo episodio no basta.

## 2. Rúbrica por recuerdo y consulta

La anotación semántica se hace viendo la consulta y el texto íntegro del recuerdo; no se muestran tipo, peso, dirección de arista, ranking, score, canal MCP ni brazo. El grafo solo se audita después, por separado, para contrastar afirmaciones estructurales de ruta.

| Etiqueta primaria | Criterio operativo | No basta para asignarla |
|---|---|---|
| **`objetivo`** | El contenido responde directamente a la pregunta o necesidad y sostiene la decisión/acción pedida. Registrar fragmento de evidencia y una justificación de una frase. | Compartir palabras, pertenecer al episodio o ser el nodo nombrado por la ruta.
| **`pista_util`** | No reemplaza la respuesta principal, pero añade una relación concreta, condición, comprobación, causa, cautela, paso intermedio o dato no obvio que mejora la resolución o una acción válida. Puede ser serendípica si la conexión se explica con evidencia del contenido. | No literalidad, distancia de grafo, tipo/peso de sinapsis ni una asociación sin beneficio explicado.
| **`neutral_contexto`** | Tiene relación temática o contextual defendible, pero no cambia ni facilita claramente la respuesta/acción para esta consulta. No es falso positivo útil ni ruido dañino. | No debe forzarse a útil o ruido para completar categorías.
| **`ruido_tonto`** | Es irrelevante respecto de la tarea, o introduce una inferencia/acción falsa, contradictoria o distractora con riesgo de desviar. Registrar qué parte resulta irrelevante o engañosa y por qué. | No ser objetivo, aparecer por un vínculo, tener menor score/peso o ser una asociación indirecta.
| **`no_adjudicado`** | Evidencia insuficiente, ambigua o desacuerdo todavía no resuelto. Excluirlo de métricas de categoría hasta adjudicarlo. | Un array vacío o la ausencia de comentario no equivalen a “ninguno” ni a ruido.

Las etiquetas primarias son mutuamente excluyentes por par consulta–recuerdo. Si un recuerdo responde a la pregunta y además contiene una segunda pista independiente, se anota `objetivo` y se registra esa segunda proposición con evidencia en `detalle_util_adicional`; no se degrada el recuerdo entero a pista ni se cuenta dos veces como objetivo. Si existen varios objetivos suficientes, se anotan todos, con evidencia propia.

Para una consulta realmente sin respuesta/pista conocida, registrar estado explícito `adjudicado_sin_objetivo` / `adjudicado_sin_pista`; dejar listas vacías solo junto a ese estado. `no_adjudicado` es estado distinto. Las métricas de utilidad/ruido no se publican para categorías cuya etiqueta siga vacía o sin adjudicar.

## 3. Reglas de inclusión y recall

- **Objetivos:** medir recuperación en `resultados` por separado (R@1, R@5 y MRR@5); un objetivo que aparece solo en contexto o asociaciones se informa como cobertura lateral y no satisface el R@5 del objetivo principal.
- **Pistas útiles:** medir sus apariciones en `asociaciones_enriquecidas`, `asociaciones`, `contexto_expandido` y la unión deduplicada, conservando canal y rango original. La unión no permite atribuir a G1/G2 una ruta que el MCP no trazó. Reportar tanto número de pistas como porcentaje de consultas/episodios con al menos una pista recuperada.
- **Ruido:** informar exposición por separado para `resultados` y canales laterales; nunca mezclar un vecino útil con falsos positivos del objetivo. Un resultado desconocido o no revisado no se cuenta automáticamente como ruido.
- **Abstención:** en consultas adjudicadas sin respuesta, contar como falso positivo solo una salida principal que presenta como respuesta un recuerdo adjudicado como engañoso/ruido para esa consulta. Una pista/contexto pertinente no invalida una abstención del objetivo; reportar canales por separado.
- **Sin filtros de grafo:** no borrar, omitir ni rebajar sinapsis para hacer coincidir el gold. No utilizar tipo, peso o literalidad para derivar etiquetas.

Gold E1 candidato: 96 consultas contestables (principal y seguimiento de 48 episodios positivos) y 128 consultas de abstención/control, según su composición actual. Recontar desde el hash de gold que se cierre; cualquier cambio en preguntas/etiquetas modifica denominadores y exige recalcular criterios antes de observar resultados.

## 4. Criterios y umbrales candidatos para aprobación

Los valores siguientes son **propuestas a revisar**, no resultados, aprobación operativa ni thresholds incorporados al arnés. Dennys debe aprobarlos o reemplazarlos antes de la campaña y fijarlos junto con rúbrica, hash de gold y plan de análisis. No se adaptan tras observar los resultados. Los umbrales protegen recall y distinguen daños; no son autorización para cambiar motor, ranking o grafo.

| Área | Umbral candidato | Interpretación |
|---|---|---|
| **Calidad de adjudicación previa** | 100% de las 224 consultas revisadas por ambos; cero desacuerdos sin resolver; cada etiqueta positiva con evidencia/justificación; cada categoría vacía marcada explícitamente como adjudicada sin casos o pendiente. | Sin cierre si un caso requerido sigue `no_adjudicado`. Un vacío no se transforma en negativo. |
| **Acuerdo humano** | Acuerdo bruto ≥85% y kappa ponderado ordinal ≥0,70 antes de adjudicación; calcular también por idioma y estrato cuando haya denominador suficiente. | Referencia mínima para que la rúbrica sea aplicable; no se usa para desechar asociaciones útiles ni para sustituir la adjudicación. Si no se alcanza, aclarar la rúbrica y repetir anotación ciega antes del cierre. |
| **Recall de objetivo** | En cada uno de N0/N1/G1/G2/R: R@5 ≥95% de las consultas contestables (con el E1 actual, al menos 92/96) y no más de **un objetivo adicional perdido** frente a N0 en comparación pareada. | Guardarraíl primario. Una mejora de pistas no compensa una regresión superior en objetivos. R@1/MRR se reportan, no reemplazan R@5. |
| **Recall de pistas** | En brazos con asociaciones/contexto habilitados (N1/G1/G2/R), recuperar ≥70% de las pistas útiles adjudicadas en la unión de canales y exponer ≥1 pista en ≥75% de consultas principales positivas que tengan una pista gold. | El resultado por canal se mantiene separado. N0 se informa como referencia, no se exige que el brazo sin canal lateral alcance el mismo piso. |
| **Ruido tonto lateral** | ≤10% de candidatos laterales efectivamente revisados pueden ser `ruido_tonto`; informar también frecuencia por consulta y distribución de neutral/contexto. | Solo cuenta ruido explícitamente adjudicado. `neutral_contexto`, desconocidos y no adjudicados no se reclasifican como útiles ni ruido. |
| **Controles de abstención** | En las 128 consultas de abstención, ≤5% (máximo 6/128 con la composición actual) con un candidato `ruido_tonto` como primer resultado principal; cero mutaciones no autorizadas. | Una relación útil/contextual no es un falso positivo de objetivo; se publican los canales laterales aparte. |

Mostrar numeradores/denominadores, intervalos de confianza por episodio (no tratar consultas del mismo episodio como observaciones independientes), resultados por idioma/estrato y diferencias pareadas. Con el tamaño de E1, intervalos amplios o falta de acuerdo se describen como **inconclusos**, no se “arreglan” cambiando etiquetas. Umbrales de kappa y desempeño son gates propuestos para revisar; no se declara éxito/no éxito hasta la aprobación escrita de Dennys.

## 5. Flujo de dos anotadores y adjudicador

### A. Anotación del gold, antes de observar resultados

1. **Dennys congela el protocolo:** aprueba versión de rúbrica, ejemplos frontera, criterios/umbrales, denominadores y hoja de registro. Se asignan dos anotadores independientes y un adjudicador. Ninguno recibe resultados de N/G/R; los anotadores tampoco se comunican ni concilian durante su primera pasada.
2. **Cegamiento:** entregar a cada anotador la misma consulta y textos de recuerdos necesarios, con IDs seudónimos y orden aleatorio distinto. Ocultar etiquetas gold vigentes, brazo, ranking/score, canal, tipo/peso/orientación de enlaces y comentarios del otro anotador. No pedirles inferir validez por grafo.
3. **Registro independiente:** cada persona marca respuesta/abstención, uno o más objetivos, pistas útiles, neutral/contexto, ruido solo con evidencia, estado explícito de categorías vacías, fragmento textual y justificación breve. Registrar versión de la hoja, tiempo y anotador. No borrar las decisiones originales.
4. **Acuerdo y desacuerdos:** calcular acuerdo bruto y kappa ponderado sobre la pasada independiente. El adjudicador revisa todas las discrepancias, todo `no_adjudicado` y cualquier diferencia objetivo↔pista/ruido; consulta la misma evidencia textual, documenta razonamiento y emite decisión final. No se resuelve por mayoría automática ni por tipo/peso.
5. **Cierre:** si el acuerdo no llega al umbral propuesto, revisar ambigüedades con Dennys y repetir a ciegas antes de resultados. Archivar versiones iniciales, acta de adjudicación, revisión de rúbrica y ledger de cambios. Cerrar el gold incluso si no cambió ningún JSONL, con hash no-op, fecha previa a cualquier resultado y `changed_episode_ids=[]`. Si el gold cambia, crear versión lateral nueva y repetir el cierre; no sobrescribir base ni reinterpretar resultados pasados.

### B. Revisión ciega de candidatos recuperados, después de una futura medición autorizada

Si se desea juzgar salidas no contempladas en el gold, crear un conjunto de anotación **separado**: deduplicar los pares consulta–recuerdo presentados por cualquier brazo/canal, ocultar brazo, score, rango y etiqueta gold, aleatorizar orden, y hacer que ambos anotadores clasifiquen de forma independiente con la misma rúbrica. El canal se reincorpora solo después de la decisión semántica. El adjudicador resuelve discrepancias y conserva las tres anotaciones. Estas etiquetas evalúan salidas; no reescriben el gold cerrado. Cualquier nueva conclusión que requiera cambiar gold inicia otra versión y campaña, nunca una corrección retrospectiva para favorecer un brazo.

## 6. Revisión de Dennys y condición de uso

Pendiente de aprobación explícita de Dennys:

- rúbrica, ejemplos y tratamiento de neutralidad/ambigüedad;
- umbrales candidatos de acuerdo, recall de objetivos, recall de pistas y ruido;
- anotadores, adjudicador, hoja/crosswalk protegido y fechas de cierre;
- manifiesto de protocolo/umbrales ligado al hash del gold y cerrado antes de observar resultados.

**Esta entrega es solo documentación.** No se prepararon bases o fixtures, no se inició MCP, no se ejecutaron mediciones ni QA. No se cambió motor, ranking, asociaciones ni gold. No autoriza la campaña aprobada como plan en `e302fcd`. **W sigue pendiente.**
