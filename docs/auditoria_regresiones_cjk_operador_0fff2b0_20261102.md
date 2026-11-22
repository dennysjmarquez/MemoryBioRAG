# Auditoría de regresiones del arnés CJK — `0fff2b0`

## Decisión

**Se verifican las dos regresiones sintéticas solicitadas, dentro de su alcance.** No se aprueban los parches CJK, no se modifica el motor y E3 permanece abierto. La reproducción no prueba el comportamiento de un agente completo, MCP, datos reales o un corpus grande.

## Procedimiento e integridad

Se verificó el commit exacto `0fff2b0dd25b4869299e84d737ba2dd3490598f7`: modifica el informe y el arnés, y añade un ejecutor sintético; ningún archivo de motor cambió respecto al commit anterior del operador. Los archivos de motor, configuración, evaluador y gold relevantes coinciden con el commit auditor `7994f68`. Los SHA-256 publicados del informe (`63601862d779d795b6323887d1ec6f53edd204736ababd81609d619738985dd1`), arnés (`b09a7f46a99615ea7d1113f9b927b14d5754e25d59a4c66ba633a9f5698735b2`) y ejecutor (`28c2a37f469ae8c404b4431da508c6fb65af29eca0785fa5ccc21edb463b997a`) coinciden con el commit y con el manifiesto en Drive. Los hashes de ambos JSON que enumera el manifiesto también coinciden con los metadatos de Drive.

Se ejecutó el script exacto del operador desde un checkout temporal independiente de `0fff2b0`, con entorno virtual, semillas y configuración temporal, fixture inventada y `PYTHONHASHSEED=0`. El parche OR y la captura de excepciones se aplicaron únicamente en otro árbol temporal que crea el script; ningún parche se aplicó al checkout del usuario. Salida: código 0. No se usaron insumos japoneses privados, ni bases reales, ni entrenamiento. La carpeta de Drive del operador mostró solo permiso de propietario.

## Resultados

- **Vecinos:** la copia de contexto agregó ocho enlaces sintéticos, subiendo temporalmente el límite de vecinos para el experimento. La expansión obtuvo ocho y `_result_rows(..., limit=None)` registró los ocho, con el conjunto esperado completo y primarios sin cambio. El JSON de la reproducción es byte idéntico al hash del operador: `a08e3ba728a540653689d06ca18de4fad3fbf73a57984a7aa692a60f9e73ebd7`. El arnés principal fue corregido para llamar a esa función sin límite al registrar vecinos. La regresión llama directamente al serializador y a la expansión, no ejerce todo `worker_search` de extremo a extremo. Esto no elimina los límites existentes del motor en otros escenarios ni demuestra conservación general.
- **Fallo FTS:** una envoltura del cursor lanzó `sqlite3.OperationalError` en el primer MATCH de trigramas OR; el catch instrumentado del parche temporal lo registró con el marcador esperado, la búsqueda devolvió cero primarios y la fuente sintética quedó intacta. El JSON coincide byte a byte con el hash publicado: `14e46d68c02281eeb6b53587f8ad369161563feb7bf8fed01c6372948b3d61bb`.
- **Alcance del fallo:** la distinción entre error y búsqueda vacía se hizo en el **experimento instrumentado**, leyendo su lista privada de errores. El parche propuesto original captura la excepción sin exponerla de esa manera al consumidor. No se ha demostrado que la API o MCP de producción distinga ese fallo ni que todas las rutas de error estén cubiertas; el booleano de la prueba es del arnés, no una garantía de producto.

La fuente SQLite se recrea por ejecución; el resumen integral puede tener otro hash por esa fuente, aunque los dos JSON de resultados sí coinciden. La batería no vuelve a ejecutar los 15 casos completos con el arnés actualizado; estos se reprodujeron previamente en `docs/auditoria_correccion_cjk_operador_8cf0c01_20261102.md` y sus límites siguen vigentes.

## Próximo paso

Cerrar estas dos observaciones del arnés y volver al resto de E3 según el plan: investigar los falsos positivos ingleses y las obligaciones pendientes de etiquetas con baseline y medición aislada. Mantener `を指す` como pista diagnóstica, sin filtros ni pérdida de vecinos. Si se propone un cambio de motor, presentar diff, riesgos y pruebas para revisión y autorización específica antes de aplicarlo. No avanzar a E4 ni entrenar por esta aprobación del arnés.

Evidencia privada auditora: `auditoria_regresiones_0fff2b0.tar.gz`, SHA-256 `90447558fa3f63cdffb64242b32e88e110bf0473d5cddf149ab2105ed98138f1`, Drive `1UJK8DSy3wgxkLeplHSobTqr-sF9kSelt`. El paquete contiene JSON y log sintéticos; no contiene SQLite ni datos privados vivos.
