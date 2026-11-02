# Auditoría de las cuatro correcciones E3 — `24287a4`

## Veredicto

**Se aceptan las cuatro correcciones del informe y arnés, con los límites de esta prueba.** La réplica confirma las observaciones sintéticas principales; no elige una política de etiquetas, no constituye evaluación completa agente+cerebro y no autoriza cambios de motor. E3 continúa abierto y E4 espera.

La cabeza remota del operador cotejada es `24287a425dd05e5ab04476bb697c72a4d9e1777d`. Frente a `6d47725` cambia únicamente informe y runner. Sin diferencias en `core`, middleware, configuración o `biorag.py`. SHA-256 runner `44014aa42c59803827f885060f88bf6d6f97aa68fceaeea788b8323f7649ce25`; informe `ca122b49059c66fe3029ccddb7c559f6f1f52453a086d4a37591ae61f30cd965`.

Se ejecutó el runner exacto en extracción temporal, dependencias aisladas, NLTK local, `PYTHONHASHSEED=0` y neurona apagada. El servidor y las 32 copias usaron MCP stdio bajo raíz temporal, sin datos vivos ni parche. La salida detallada se escribió en un directorio nuevo ignorado. Código de salida 0.

## Comprobaciones

1. **Denominador:** se registraron 24 llamadas históricas, 24 actuales y 48 `recordar`. La histórica se ejecutó en tres modalidades por familia y brazo; la cuarta solo busca la actual. El informe ahora refleja los denominadores correctos.
2. **Columnas:** el runner compara directamente con los valores SQL de las columnas plegada y exacta. En nuestra salida ambas coincidieron con lo esperado en **32/32** brazos. Las etiquetas de esta fixture son ASCII: el resultado no sustituye un control específico con formas exactas y plegadas diferentes.
3. **Error MCP:** `isError` se conserva y la función de validación rechaza tanto indicador MCP como `status=error`. Probamos artificialmente ambos valores y verificamos que se rechazan; se acepta el caso normal. En nuestra corrida, cero de los 48 resultados mostró esas dos señales. La prueba artificial ejercita parser y función de decisión, no una caída real del servidor a través de stdio.
4. **Hashes:** verificamos por separado el SHA-256 del archivo del manifiesto, el JSON canónico y los bytes del reporte: coinciden con sus campos y `SHA256SUMS.json`. El runner relee y verifica las escrituras y vuelve a comprobar los archivos al terminar de guardarlos. En nuestra salida, el manifiesto del reporte y el guardado coinciden al compararlos independientemente. No hay una comparación automática entre un hash fijado antes de las 32 sesiones y otro al finalizar las sesiones; no se presenta como prueba de inmutabilidad durante todo el experimento.

La ejecución produjo **176 snapshots** de nueve tablas y una proyección, sin errores registrados; 16 comparaciones de grafo coincidentes, ocho controles de orden iguales y asociaciones manuales preservadas en 32 brazos. Para el término histórico, solo-etiqueta dio primario 3/3 en activo y 0/3 en neutral; en vecino, neutral 0/3 primario y 3/3 en contexto. Contenido contradicho y sinónimo dieron primario 3/3 por brazo. La consulta actual recuperó el objetivo en los casos informados. No se infiere que pista antigua signifique ruido, que una contradicción sea un falso positivo ni que el agente haya adjudicado vigencia.

No tuvimos acceso a la carpeta privada original y a la copia preservada del operador; su igualdad byte a byte es una comprobación reportada por él, no verificada independientemente en esta auditoría. Nuestra ejecución y evidencia son independientes y no sobrescriben las anteriores.

## Continuación

Se cierran las observaciones documentales y de arnés de `5fda6fa` dentro de su alcance; conservar los límites anteriores como información, sin convertirlos en obstáculos automáticos para el resto del plan. Continuar E3 con baseline y pistas completas; cualquier mejora al motor requiere diff, evidencia y autorización específica. No se selecciona reemplazo o acumulación ni se avanza a E4 por estas mediciones.

Evidencia auditora privada: `auditoria_e3_replica_24287a4.tar.gz`, SHA-256 `0a051fea6b74f961a9905adede93eb512a7f3c0655a8c5c499f0ab7f18c44155`, Drive `1NBsxxByYd3b9oDviG6OXiKgUzT8U5aT0`. Contiene trazas sintéticas y log, sin bases SQLite ni datos vivos.
