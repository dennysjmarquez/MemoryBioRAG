# Auditoría E3: etapas del candidato `6369951`

Se revisó `6369951`, hijo de `8a7fa13`: cinco archivos de diagnóstico/documentación, sin modificación de `core/`. `git diff --check` y `py_compile` de ambos scripts modificados pasaron. La réplica ejecutó el mismo runner del operador, con `PYTHONHASHSEED=0`, en un checkout y DB sintéticos aislados.

## Hallazgo reproducido

Para la consulta distante con paráfrasis, la primera sentencia MATCH fue `SELECT COUNT(*)`: retornó **una fila, valor 0**. La segunda sentencia MATCH devolvió el objetivo; las sondas del mismo SQL y filtros encontraron ese objetivo en la rama de paráfrasis, no en la de query ni en las dos de etiquetas. El candidato apareció en `todos` y después en `resultados_con_hibrido` con score 0.0686 y origen lateral `literal`. La traza de líneas lo observó retirado de `resultados_con_hibrido` justo después del filtro de prefijo. El SQL `PALABRA_INICIO_ANCHO` recibió el candidato y no devolvió ninguna fila. El código clasifica el candidato como literal para el filtro y evalúa el token de la query original en concepto, contenido, sinónimos y etiquetas. El método retornó lista vacía y `total=1`; MCP respondió con `total=0` y lista vacía mediante su contingencia.

Por tanto, para esta fixture y ruta observada la exclusión ocurrió en el filtro dentro de `buscar_por_frase`, no cuando MCP recibió y filtró una lista no vacía. La etiqueta lateral `literal` con valor de origen 0.0 y el score híbrido 0.0686 son valores distintos. El total interno corresponde a una etapa anterior al filtro: no se debe interpretarlo como cantidad final devuelta. No se demuestra con esto la frecuencia, impacto ni semántica deseada en otras consultas, ni se propone eliminar el filtro o cambiar motor. El código lo documenta como protección frente a falsos positivos de subcadenas y preserva resultados de ciertos orígenes no literales; cualquier alternativa requeriría medir ambos lados sin perder pistas.

## Alcance

3 pares y 6 brazos baseline/instrumentado: 12 búsquedas, 24 llamadas MCP contando aperturas, 0 flags MCP de error. Los JSON completos parseados coincidieron en los seis brazos. Sin cambios en los snapshots observados: nueve tablas de grafo completas y proyección `largo_plazo(concepto, asociaciones)`, no toda la DB. La instrumentación usa proxy de cursor, consultas de rama y traza de líneas runtime: su equivalencia se observó solo en estos brazos. Suite completa y evidencia privada del operador no se repitieron/consultaron; no se verifican hashes de `run03`.

Evidencia de réplica privada en Drive, ID `1xscLLxNql7QovuI8Yd3pO9H7Qve25l57`, archivo `auditoria_e3_6369951_20261103.tar.gz`, SHA-256 `ec083ea057861d1b80d5acfa5a6348ed78d7f56624dd0eae58530b84e872cb7f`. E3 sigue abierto, E4 no iniciado; bases originales no se abrieron.
