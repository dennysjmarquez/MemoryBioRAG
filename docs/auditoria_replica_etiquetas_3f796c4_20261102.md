# Auditoría de la réplica H-E3-ETQ-01 — `3f796c4`

## Veredicto

**Resultados principales reproducidos; informe y arnés requieren correcciones de precisión.** No se elige política de etiquetas, no se aprueba cambiar motor y E3 sigue abierto. El commit remoto `3f796c46592669b64a1461394a3f4d878d782894` añade únicamente un informe y un runner frente a `eae3c5b`; las rutas de motor, middleware, configuración y launcher MCP inspeccionadas coinciden con la rama auditora `e71d7bc`. SHA-256 del runner: `f17b3d8a92ff2e18d5d596e4f3400355aa9497f319d5338c98ce7b1b084dc593`; del informe: `9e21da749ee1b5de2ff0bad3fc77caf5e949e1e3fc53060d32532056dc4c5ef4`.

Se ejecutó el script exacto en árbol temporal con entorno aislado, recursos NLTK locales, `PYTHONHASHSEED=0`, neurona apagada y launcher MCP stdio con guardia de ruta temporal. La réplica generó sus propias copias sintéticas; no se tocaron bases originales ni motor. No tuvimos acceso a las trazas privadas originales del operador: comparamos con el informe publicado y recalculamos sobre **nuestra** salida detallada, no cotejamos los JSON originales caso por caso.

## Reproducción y controles independientes

- **32/32 sesiones** registradas como exitosas, 176 snapshots de las diez consultas al grafo y cero errores de snapshot. Las 16 comparaciones de grafo emparejado y ocho controles de orden recogidos por el arnés coinciden; las asociaciones manuales iniciales se conservan en los 32 brazos. Los campos seleccionados de contenido, sinónimos y espejo de asociaciones del objetivo coincidieron entre los 16 pares.
- En los modos que efectivamente ejecutan la **consulta histórica**, la familia solo-etiqueta la recuperó como primario **3/3** con pista activa y **0/3** con neutral; en neutral tampoco apareció en contexto. En la familia vecino, activa **3/3** como primario y neutral **0/3** como primario, pero **3/3** en contexto. Contenido contradicho y sinónimo recuperaron el objetivo en **3/3** por brazo. Las 24 consultas de pista actual recuperaron el objetivo como primario.
- Una de las cuatro modalidades, `single_current`, **no ejecuta consulta histórica**. Por tanto, la frase del informe que atribuye esos resultados históricos a «cuatro modos» es incorrecta: son **tres modos históricos**, aunque haya cuatro modalidades totales por brazo. No cambia los resultados observados en las consultas realmente realizadas.
- Recalculamos por rol y campos capturados la comparación entre consultas aisladas y sus dos órdenes secuenciales: **16/16 coincidencias por cada rol**. `initialize` no cambió el grafo observado en 32 sesiones; en el intervalo hasta el primer tool se añadió una fila `dmn_synthesized` en 32. No se atribuye a un subpaso concreto de la apertura ni se infiere que el handshake no abrió una base.
- Un control separado volvió a ejecutar 32 sesiones e instrumentó las respuestas completas: **144 llamadas, cero indicadores MCP de error y cero respuestas con estado error**; hubo 48 llamadas `recordar`. El runner original descarta `_mcp_is_error` al construir la salida de cada `recordar`, por lo que su propia bandera de éxito no habría detectado ese indicador si hubiese venido sin `status=error`. El control confirma ausencia en nuestra segunda ejecución, no sustituye corregir el arnés.

## Integridad de etiquetas y manifiesto

El indicador `stored_pair_matches_expected` deriva la supuesta forma exacta desde el valor devuelto de la forma plegada; **no lee la columna exacta almacenada para dicha comparación**. En nuestra salida, el snapshot independiente de la fila sí registra ambas columnas y las cotejamos: **32/32** coincidieron con los valores esperados. Las etiquetas de esta fixture son ASCII, de modo que esa comprobación no prueba todavía casos donde ambas formas difieren.

Los hashes de archivo en `SHA256SUMS.json` de nuestra réplica coinciden con los bytes guardados. Sin embargo, `cue_manifest_sha256` y el valor presentado como hash privado se calculan sobre el JSON **sin** el salto de línea final que sí se escribe en el archivo: no son el SHA-256 del archivo completo. El manifiesto se vuelve a generar y sobrescribir en cada ejecución; es un inventario preservado con checksum, no una garantía técnica de inmutabilidad durante toda la prueba. Pedir que se fije un único formato de bytes, se verifique antes y después y se distingan hashes de objeto y archivo.

La salida pareada, las rutas alternativas y la aparición por contexto en neutral sostienen la conclusión limitada del informe. Ni el resultado contradictorio ni una pista histórica constituyen automáticamente falso positivo o adjudicación de vigencia. No se midió un agente autónomo, no se seleccionó reemplazo/acumulación y no se deben descartar pistas o asociaciones.

## Continuación

Solicitar al operador corregir el denominador de tres modalidades históricas, la comparación de la columna exacta y el manejo de errores de `recordar`, además de aclarar los dos hashes del manifiesto. Mantener evidencia original y correcciones separadas. Estas son correcciones del arnés y documentación, **no** autorización de parche de motor, backfill ni E4.

Evidencia privada de la reproducción y control adicional: `auditoria_e3_replica_3f796c4.tar.gz`, SHA-256 `a67b28a5a41771d7e7e65dd4950223ba9a954e9e7d6c1c79e5571de00be9e9c2`, Drive `11wn2qasWjMILFScUBP-UZlkj1VLEf98b`. Contiene trazas sintéticas y guion de control, no SQLite ni datos vivos.
