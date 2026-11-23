# Auditoría E3: atribución e historia `8a7fa13`

Se revisó el diff de `8a7fa13` y se reprodujeron sus dos runners en copia sintética aislada, con `PYTHONHASHSEED=0`; no hay cambios de `core/`. `git diff --check` y compilación de los tres scripts modificados pasaron. Se repitieron las pruebas seleccionadas de autoexpansión, convergencia e identidad Unicode: **48 passed**. No se repitió la suite completa de 824 y 2 subtests.

## Resultado de la réplica

Tres pares, cada brazo baseline e instrumentado: **12 búsquedas, 24 llamadas MCP contando aperturas, cero flags MCP**. Las respuestas JSON completas parseadas coincidieron baseline/instrumentación en 6/6 brazos. Los snapshots de grafo y la proyección monitorizada no cambiaron, tanto durante apertura como búsqueda. Esto no cubre toda la base ni prueba equivalencia general, especialmente porque la instrumentación ejecuta consultas adicionales.

En la consulta distante, la segunda sentencia MATCH efectivamente devolvió la fila objetivo. En las sondas con el mismo SQL y filtros, la rama de consulta no la devolvió, la de paráfrasis sí, y las dos ramas de etiquetas no. El pool observado al finalizar contenía el objetivo con origen lateral `literal`, valor `0.0`, pero la respuesta MCP no lo incluyó, con o sin paráfrasis. Esta instrumentación mejora la anterior: sí captura las filas que consume el cursor para esa sentencia, y las sondas contrafactuales prueban qué ramas coinciden en ese estado de la fixture. No identifica la puerta de exclusión ni demuestra que ese `0.0` sea el score final, un fallo del calibrador o una anulación por convergencia. La asignación de `literal` es compatible con la rama del código; la telemetría observa el origen después del método, no la línea exacta de asignación.

En los otros dos pares, el objetivo aparece con y sin paráfrasis, con origen lateral `simbolico`; no son evidencia de pérdida ni de ausencia de contribución de variantes. La emulación del bucle histórico sobre core actual reproduce el resultado informado: objetivo 0.06707 con política separada y ausente con llamada combinada en el caso distante; los otros dos aparecen bajo ambas políticas con scores diferentes. **No se ejecutó el core histórico:** este contraste no demuestra el resultado que habría producido `0bf6e2be` de extremo a extremo.

## Historia y límites

La inspección previa de `0bf6e2be` confirmó llamadas separadas, repetición de query, factor 0.95 sobre variantes y merge por concepto. Se revisó adicionalmente `e5a40e0`: el MCP pasa una lista en una llamada y `buscar_por_frase` construye un OR; el merge externo y factor anterior desaparecen de esa ruta. `e5a40e0` es un commit de merge: estos hechos comparan estados y rutas, no establecen por sí solos el primer instante de cada cambio en todas las ramas. El resto de la cronología del operador no fue revisado exhaustivamente aquí. El historial de origen de la ráfaga y su relación con paráfrasis sigue abierto.

No se ha medido la afirmación de que el 99% de casos tengan atribución suficiente, ni se adopta como umbral. Tampoco hay razón demostrada para cambiar el motor o introducir un campo `matched_by`; las sondas adicionales son de diagnóstico. FTS combinado no aporta por sí solo la procedencia de cada alternativa: estas sondas comparan coincidencias por rama en el mismo estado, con el alcance limitado del parser y los casos usados.

Evidencia de réplica sintética privada: `auditoria_e3_8a7fa13_20261103.tar.gz`, Drive ID `18JfnqxjSBPQVaMhidcfa8huFqGU0ASLw`, SHA-256 `21ccffeb6eef1a414547a7b0dbc632f64cfb0014be0a17282cf7de5c62374c7b`. Se ejecutó el mismo arnés del operador, no uno independiente; no se accedió a su evidencia privada `run07` y por ello no se comparan sus hashes. E3 sigue abierto; no se inicia E4 ni se aprueba parche de motor.
