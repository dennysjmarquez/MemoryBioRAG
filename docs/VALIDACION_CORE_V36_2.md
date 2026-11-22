# Validación de integración v36.2 (candidata)

## Alcance

Implementación productiva en `core/contextual` y adaptadores MCP reales; pruebas realizadas en copias bajo `/tmp`, sin configuración privada ni DB viva. No se hizo merge, tag, release ni activación en la instalación del propietario.

El worktree contenía modificaciones ajenas previas (empaquetado, rutas, documentación y tests). Se preservaron. Los archivos compartidos se publican mediante selección incremental del índice; no se incluyó indiscriminadamente ese trabajo. Se verificó por separado una exportación del **índice exacto publicable** mediante `git checkout-index`, sin cambiar de rama.

## Resultados

| Prueba | Resultado | Qué demuestra / límite |
|---|---|---|
| Suite global sobre copia del worktree final | **896 passed, 18 skipped, 2 subtests passed**, 238.63 s | Regresión del estado local efectivo; incluye pruebas ajenas no publicadas por este cambio. |
| Suite global sobre exportación del índice publicable | **894 passed, 18 skipped, 2 subtests passed**, 239.78 s | Regresión del patch realmente publicado; no certifica sistemas operativos no ejecutados. |
| Tests nuevos de correcciones | **17 passed**, 4.22 s | WAL/DELETE, bootstrap, rollback inyectado, muerte del proceso antes/después del commit, concurrencia, idempotencia, permisos, no DDL por búsqueda, esquema MCP y crecimiento con 10.000 claims ajenos. |
| E2E stdio servidor real sobre worktree | **PASS** | `mcp_server.py`, tres tools reales, luego `recordar` con contexto explícito. |
| E2E stdio servidor real sobre índice publicable | **PASS** | Mismo flujo sin depender de cambios locales ajenos. |
| QA oficial posterior al cambio, 921 casos | **921 salidas/órdenes/scores exactamente iguales** a baseline conservada; gates 0/0 | No interferencia del motor sin contexto. No es eficacia de 921 correcciones. |

### E2E MCP

Scripts y resultados versionados:

- `scripts/experimentos/competencia_contextual/e2e_core_mcp.py`
- `scripts/experimentos/competencia_contextual/resultados_core_mcp.json`
- `scripts/experimentos/competencia_contextual/resultados_core_mcp_index.json`

Se utilizó una copia de snapshot suministrado explícito (SHA256 `07a77c801eaa56750627e1c831de91a65e6448da25e4803b86d3ae4e2446c55e`). El mensaje, nodos y fechas son **interacción sintética**; no comprensión autónoma del caso. No se insertaron claims manuales: se registró una propuesta con antecedente explícito, se inspeccionó bootstrap, se rechazó digest alterado y se confirmó mediante la herramienta real. Repetir request devolvió el recibo. Ledger, arista tipada y recibo persistidos; fila histórica intacta durante aprobación, asociación manual conservada y snapshot fuente intacto. `recordar` resolvió el canónico primero sin perder candidatos ni cambiar scores; intención historical conservó el orden previo.

El primer E2E detectó que el SDK MCP desempaqueta JSON y el parámetro debía ser un **objeto**, no una cadena. Se corrigió la firma de ambos tools y se añadió test del esquema. También se corrigió el lector del harness para desenvolver `structuredContent.result`; ese fallo de lectura no era fallo del selector.

### QA posterior a integración

`resultados_qa_core.json` conserva métricas, hashes y comparación completa. R@5=100%, R@1=93.03%, MRR=0.9566, FP=0/40, 875 positivas + 40 negativas; seis ambiguas fuera de ese denominador. Hay dos registros de fallo en ambos lados: no se borraron ni relajaron gates.

La corrida usa el evaluador oficial intacto sobre la copia del worktree del core nuevo, con instrumentación de no-interferencia del laboratorio (`qa_selector_worker.py`, ledger vacío/contexto ausente). La baseline procede de la corrida emparejada anterior con todos los assets y snapshot idéntico, no se recalculó en este turno. La instrumentación aún usa el wrapper del laboratorio: **esta QA no invoca 921 veces el nuevo puerto MCP contextual**. La integración contextual real se cubre por E2E y tests dedicados, no por extrapolación de la QA del motor. No se afirma certificación universal ni equivalencia biológica.

## Estado operativo

Código implementado y probado para integración; **v36.2 candidata**, escritura apagada de fábrica. El propietario decide backup, contextos delegados y activación stdio en su entorno. Sigue pendiente validación en su instalación real y cualquier política de autoridad remota. Digest no autentica; la delegación local permite aprobar al agente que controla ese proceso. SSE permanece denegado.

Guía: [CORE_V36_2.md](CORE_V36_2.md). Contrato previo: [CONTRATO_CORE_V36_2.md](investigacion/memoria_silicio/CONTRATO_CORE_V36_2.md).
