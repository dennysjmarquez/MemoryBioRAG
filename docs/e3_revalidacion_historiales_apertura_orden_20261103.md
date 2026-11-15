# E3: revalidación sintética de historiales, vecinos, apertura y orden

**Fecha:** 2026-11-03. Reejecución en fixtures sintéticos con scripts existentes. Sin consultas ni recuerdos reales, sin bases originales, sin cambios al motor, sin adjudicar pistas y sin avanzar a E4.

## MCP stdio: apertura y orden

La matriz de `scripts/diagnosticar_mcp_stdio_apertura_orden_etiquetas_e3.py` cubrió 16 sesiones: dos supuestos de historial (faceta aún útil y registro contradicho en el contenido), dos payloads de etiquetas (reemplazo actual y lista acumulada enviada explícitamente como contrafactual), dos rutas de escritura y ambos órdenes de consulta histórica/nueva.

| Control agregado | Resultado |
|---|---:|
| Sesiones MCP stdio / llamadas de herramienta | 16 / 80 |
| Flags MCP `isError` capturados | 0 |
| Estados de las 16 escrituras | `ok` en 16/16 |
| `recordar`: campo `status` | ausente en 32/32; no se contó como error |
| Consultas `recordar` con el objetivo en resultados | 28/32 |
| Pares que mantuvieron el mismo hit/rango al invertir el orden | 8/8 |

El handshake `initialize` no cambió el snapshot de aristas. La primera herramienta real de cada sesión añadió exactamente una fila `dmn_synthesized`; se conservaron las cuatro filas manuales iniciales en los 16 brazos. No se añadieron ni quitaron aristas después de escribir etiquetas ni después de ninguna de las 32 búsquedas. En las 28 respuestas con el objetivo, las asociaciones mostraron los dos vecinos manuales; el contexto expandido incluyó además el vecino creado por DMN al abrir. Esto separa aristas iniciales de la adición DMN, y observación de compatibilidad de atribución causal.

Por supuesto de historia: en la fixture de faceta útil, la pista antigua no recuperó el objetivo con el payload de reemplazo (0/4 órdenes/rutas) y sí lo recuperó cuando se envió la lista acumulada como valor entrante (4/4). La pista nueva se recuperó en ambas ramas. En la fixture con contradicción escrita en el contenido, la consulta histórica recuperó el nodo bajo ambas cargas (8/8); eso es compatible con coincidencia en contenido y no resuelve qué afirmación es verdadera. No se selecciona política de retención.

## Rutas directas registradas: alcance separado

Se ejecutó además `scripts/diagnosticar_rutas_mcp_historial_pistas_vecinos_e3.py`: ocho brazos (dos historias, dos cargas y dos rutas). Llama directamente funciones MCP registradas con dependencias aisladas; **no usa transporte stdio** y no se suma a las 16 sesiones anteriores. Las ocho escrituras y lecturas de etiquetas quedaron `ok`. De 24 consultas internas (histórica, nueva y estable por brazo), 22 devolvieron el objetivo; la histórica lo recuperó en 6/8 y la nueva en 8/8. En las 22 recuperaciones se expusieron los dos vecinos manuales en asociaciones y contexto. Esta prueba complementa, pero no sustituye, la medición stdio.

## Evidencia, alcance y reproducción

- Matriz stdio completa, incluidos snapshots por etapa: `.private_evidence/e3_mcp_open_order_20261103_run02/stdio_matrix.json`; SHA-256 `c6d98611c15942f03acb47d457c27e86bd0dc90a3caf0498d8ac7bf97b023932`.
- Rutas directas registradas: `.private_evidence/e3_routes_histories_neighbors_20261103_run01/direct_routes.json`; SHA-256 `808e4af6572016ef298cb73456a954be32de134d1677cfb597de5645e0c461c7`.
- El snapshot de la matriz stdio de este runner es de filas de `sinapsis`; **no es copia completa de SQLite ni el snapshot de nueve tablas**. Para la prueba de paráfrasis, el harness distinto conserva nueve tablas completas de grafo y la proyección `largo_plazo(concepto, asociaciones)`, tampoco una copia completa de SQLite.
- La reejecución stdio confirmó 0 excepciones de proceso durante la corrida; el runner ahora conserva los flags de error MCP por llamada y los resultados de `recordar` por consulta. `py_compile` del runner fue correcto.

Estos resultados son reproducciones acotadas en fixtures, no evidencia de que el orden nunca importe ni de que una política de etiquetas sea correcta en otros datos. Se preservan ambas cargas experimentales y todas las asociaciones sembradas. E3 sigue abierto.
