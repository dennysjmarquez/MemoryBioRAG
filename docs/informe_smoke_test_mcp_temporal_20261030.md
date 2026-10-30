# Resultado del smoke test MCP temporal

**Fecha:** 2026-10-30

**Estado:** completado con hallazgo; no es una aprobación semántica ni de ranking.

**Autorización:** recibida explícitamente antes de ejecutar.

## Resultado

- Transporte: servidor FastMCP real por `stdio`, con `MCPProcess` y el launcher `scripts/qa_stdio_server_intuicion.py`.
- Extracción: `parse_tool_result`, `main_result_concepts`, `context_concepts` y `response_concepts` del arnés auditado `scripts/evaluar_qa_intuicion_asociaciones_e1.py`.
- Base: nueva DB bajo `/tmp/biorag-smoke-mcp-w5gsf3j4/`; se confirmó el guardrail de raíz temporal. Se comprobó integridad `ok` y cuatro nodos activos; después se eliminó el directorio temporal.
- Secuencia completada: cuatro pares `recordar` de búsqueda previa + `aprender`, un `consolidar`, dos llamadas `vincular` y un `recordar` final: **12 llamadas MCP**, sin errores de transporte ni errores de herramienta registrados.
- Antes de cada `aprender`, la búsqueda previa real por MCP devolvió `total=0` y no halló coincidencia exacta.
- Los cuatro `aprender`, `consolidar` y los dos `vincular` respondieron `status=ok`.

## Hallazgo importante

La respuesta final expuso por separado los canales. El extractor del arnés observó:

- `resultados`: `smoke_mcp_reintento_objetivo`, `smoke_mcp_reintento_idempotencia`.
- `contexto_expandido`: `smoke_mcp_reintento_backoff`, **`smoke_mcp_color_favorito`**.
- Los campos laterales `asociaciones` y `asociaciones_enriquecidas` también incluyeron el recuerdo sintético del color. La respuesta MCP cruda guardada en el JSON lo etiqueta como `tipo_sinapsis: co_nombre` junto a `smoke_mcp_reintento_objetivo` (fuerza de arista `0.53`, peso de vecino `0.98`) y junto a `smoke_mcp_reintento_idempotencia`.

Esto confirma el tipo que informó la respuesta final, pero **no cuándo ni por qué nació la arista**. No hubo snapshots entre llamadas, y el snapshot final del grafo no guardó tipos por fila; el resultado no atribuye la creación a una llamada concreta.

Aunque el smoke solo llamó explícitamente `vincular` para objetivo↔idempotencia y objetivo↔backoff, el snapshot final de la DB temporal contenía seis aristas bidireccionales: esas dos y cuatro aristas adicionales entre los otros pares, incluida la nota de color. **Por tanto, la separación estructural de canales fue observable, pero la expectativa de que el ruido sin valor no apareciera como asociación/contexto no se cumplió.**

El snapshot se tomó tras la secuencia completa, sin snapshots intermedios; no se atribuye cuándo ni qué llamada produjo las aristas adicionales. No se cambió motor, configuración ni ranking para alterar el resultado.

## Evidencia exacta

`docs/resultados_smoke_test_mcp_temporal_20261030.json` conserva los argumentos, respuesta MCP cruda, respuesta parseada, llamadas y errores (lista vacía), los conceptos extraídos por canal, el estado final de la DB temporal y las restricciones aplicadas. La DB temporal fue eliminada después de registrar esa evidencia.

No se ejecutó la QA completa. No se midieron criterios de ranking ni se fijaron umbrales; permanecen pendientes.
