# Propuesta breve de implementación — QA de asociaciones

**Fecha:** 2026-10-30
**Estado:** propuesta para revisión; la QA no está autorizada para ejecución.
**Base:** diseño aprobado con detalles de implementación pendientes.
**Alcance:** solo planificar scripts y artefactos temporales. No modificar motor, ranking ni bases originales; no iniciar E4/E5.

## 1. Atribución verificable de dos saltos

1. **Gold explícito por episodio:** registrar el nodo ancla/objetivo, el intermedio, la pista candidata y la ruta dirigida por conceptos (`ancla → intermedio → pista`), además de IDs únicos y evidencia textual. El gold etiqueta como dos saltos una ruta cuya distancia mínima validada sea exactamente 2; no basta con asignar `saltos: 2`.
2. **Validador independiente, solo lectura:** tras construir y consolidar la fixture sintética, leer el grafo final y calcular distancias mínimas. Incluir todas las aristas producidas automáticamente por `aprender`/bridges y las explícitas de `vincular`. Rechazar o reconstruir el episodio si hay atajo de un salto, ruta alternativa más corta o nodos/relaciones que vuelvan ambigua la atribución. No corregir con SQL ni cambiar el motor.
3. **Atribución por respuesta (adenda de auditoría):** guardar la respuesta MCP cruda y mapear los conceptos de `resultados` (semillas de la expansión) y `contexto_expandido` a IDs del gold. La presencia de la pista y la distancia calculada desde el grafo solo validan consistencia estructural; **no prueban el recorrido ejecutado**. Atribuir una exposición a dos saltos únicamente si la pista aparece en `contexto_expandido` con `context_window=2`, el objetivo figura como semilla y la respuesta MCP contiene una traza explícita del recorrido real que coincide con la ruta gold exacta de dos saltos. Sin esa traza, marcar literalmente `no atribuible`, incluso si el camino gold existe en el grafo. No cambiar el motor ni el formato MCP para suplir la ausencia de evidencia.
4. **Canales separados:** `resultados`, `asociaciones_enriquecidas`, `asociaciones` y `contexto_expandido` conservan métricas independientes. Una aparición en vecinos laterales no acredita dos saltos. Guardar para cada observación `episode_id`, `query_id`, concepto/ID, canal, ancla(s), distancia mínima validada y estado de atribución (`2-hop`, `1-hop`, `ambigua`, `no visible`). El formato de salida MCP no necesita modificarse.

## 2. Control de orden reproducible

- Construir un shard sintético por brazo que contenga los episodios con IDs/conceptos namespaced; congelar una plantilla y copiarla a dos rutas temporales limpias con hashes iguales antes de correr.
- Ejecutar dos recorridos MCP con igual binario/configuración y un proceso por recorrido: **orden original** de episodios y **orden inverso** de episodios. Mantener intacto el orden interno de consultas de cada episodio (principal → seguimiento fijo → control); el inverso nunca invierte ni adapta la cadena.
- Mantener iguales semilla/hash seed, reloj, variables y estado DMN aislado. Conservar transcript y respuesta cruda por llamada. Comparar por `query_id` y canal, no por posición de ejecución; informar diferencias como efecto de orden, sin reetiquetar el gold.
- La comparación se invalida si las copias iniciales no coinciden, hay mutaciones del grafo/recuerdos durante recuperación, llamadas omitidas/reintentadas sin registro o contaminación entre procesos. Las escrituras de telemetría permitidas se comparan por separado.

## 3. Revisión de dos anotadores

Para iniciar la anotación se necesitarían **dos revisores independientes**, competentes en español y en inglés para los casos incluidos, y disponibles para etiquetar todo el lote asignado. Antes de recibir resultados se les entrega:

- rúbrica congelada (escala 0–3 ya propuesta, definición de pista útil/serendipia útil frente a ruido tonto y ejemplos límite);
- contexto de tarea y consultas, más texto/contenido de cada candidato, con IDs seudónimos para permitir adjudicación;
- hoja de anotación con rating, etiqueta útil/neutral/ruido, evidencia textual y justificación breve;
- instrucciones de cegamiento: no mostrar brazo, score, rango, canal, gold ni evaluación del otro revisor; presentar candidatos en orden aleatorio independiente.

Ambos anotan el mismo conjunto sin deliberar entre sí. Luego se calcula acuerdo ordinal (kappa ponderado) y se conservan ratings originales. Los desacuerdos se adjudican por una tercera persona designada por Dennys —o por Dennys si así lo decide— sin borrar la primera anotación. Si el acuerdo cae bajo el umbral previamente aprobado, revisar la rúbrica y volver a anotar a ciegas; no cambiar etiquetas gold para acomodar resultados.

## 4. Puerta de autorización

Antes de implementar/ejecutar: aprobar el protocolo de fixtures, formato del gold, regla de atribución y de orden; congelar rúbrica y umbrales (siguen pendientes de aprobación de Dennys); confirmar los dos anotadores y quién adjudica. **Esta propuesta no ejecuta la QA ni autoriza E4/E5.** La fixture futura será sintética y temporal; no se leerán, copiarán ni modificarán DB viva o snapshot.
