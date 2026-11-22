# Auditoría de dos fixtures sintéticas MCP — 2026-10-30

## Dictamen

**Detenerse antes de mediciones.** Las dos preparaciones independientes son estructuralmente comparables según `fixture_repeatability_v2`, pero la ruta del gold no es única en el grafo observado: un atajo directo de tipo `co_nombre` conecta `synthetic_amber` con `synthetic_ivory`. No se borró, desactivó ni modificó ninguna conexión. No se ejecutaron brazos de medición ni QA completa. La aprobación de hashes sigue pendiente; este informe no pretende representar una aprobación operativa de Dennys. **W continúa pendiente.**

## Alcance y procedencia

- Se usó exclusivamente el gold sintético pequeño `synthetic_gold.jsonl`; su SHA-256 es `88c55d48a393fbc421caa455b08d92dd5c083c5e4167e31cfc229fb52397a316`. El manifiesto correspondiente declara `original_gold_read=false` y su SHA-256 es `b3a8cc48059889adac8e30c9dec9093b08c758bfad87dfd6093fc75b2b8b3495`.
- Se hicieron dos preparaciones desde bases nuevas e independientes, cada una con una sesión MCP real, sin copiar una fixture para fabricar la otra. Cada build tuvo 9 llamadas MCP: 3 `recordar`, 3 `aprender`, 1 `consolidar` y 2 `vincular`.
- Resultado: cero errores de llamada en ambos builds; no hay fallos en el resumen (`errors: []`). Evidencia por llamada, argumentos, respuesta, errores, cambios de aristas y hashes de tablas antes/después está preservada en el directorio `docs/auditoria_preparaciones_sinteticas_mcp_2026-10-30/evidencia/`.
- No se consultaron ni utilizaron bases originales. Las bases sintéticas SQLite no se incluyen en el repositorio; se preservan gold, manifiestos, reportes, eventos MCP y hashes.

## Resultados por preparación

| Build | `construction_id` | Eventos | Nodos activos | SHA-256 lógico de fixture | Estado |
|---|---|---:|---:|---|---|
| A | `320457ac34044280bc8cf2e4c9d9572f` | 9 | 3/3 | `dae4e010d9c3af3a40533f87f24c171ad8cbb3591dc4228a928784647f24140a` | `requiere_revision_gold` |
| B | `9a26b91a8b29400c9a8bb0fe18327205` | 9 | 3/3 | `de8acd58de5abd7e41713042c6ef1219dcec4af70fa65ffdd2bd8426faab5a26` | `requiere_revision_gold` |

En ambas hay 3 nodos activos, 0 dormidos, 0 sinapsis latentes y 6 aristas dirigidas. El informe de repetibilidad registra `schema=fixture_repeatability_v2`, `mode=REPEATABLE_PAIR`, builds independientes verificados, `identical_structural=true` y `differences={}`. Los SHA-256 lógicos de las dos fixtures son distintos: esa diferencia se conserva y se explica abajo; por tanto, el resultado no significa identidad íntegra de base de datos.

## Grafo observado y bloqueo

Las seis aristas dirigidas observadas, idénticas en ambas fixtures, son:

- `synthetic_amber` ↔ `synthetic_cobalt`
- `synthetic_amber` ↔ `synthetic_ivory`
- `synthetic_cobalt` ↔ `synthetic_ivory`

Las seis son de tipo `co_nombre`, peso `0.65`. El gold declara la ruta `synthetic_amber → synthetic_cobalt → synthetic_ivory`; sus dos aristas están presentes y los tres nodos están activos. Sin embargo, también existe el enlace directo `synthetic_amber → synthetic_ivory`: la distancia mínima observada es **1**, y `exactamente_dos_saltos_unico=false`. Ambas preparaciones bloquean la congelación estructural con `ruta_gold_2_saltos_no_es_unica`.

Este atajo es evidencia observada, no una etiqueta de “ruido”. No se filtró por tipo ni peso, y no se borró ninguna conexión para forzar el recorrido de dos saltos. La decisión sobre el gold y cualquier nueva autorización quedan para revisión posterior.

## Repetibilidad: alcance y divergencias

La auditoría estructural `REPEATABLE_PAIR` sí verificó que las preparaciones independientes del mismo gold producen el mismo grafo auditado y que el conjunto de membresías semánticas coincide al comparar por nombre de grupo. Una comparación adicional, de solo lectura, encontró diferencias de hash de tabla en `grupos_semanticos`, `nodo_grupos_semanticos` y `sync_log`:

- Las dos tablas de grupos usan el mismo conjunto de 22 nombres y las 63 membresías normalizadas por nombre son iguales; varían los IDs/orden numéricos asignados a grupos.
- `sync_log` conserva tres timestamps por build: A `1793416725.0`, B `1793416728.0` (diferencia de 3 segundos). Esos valores hacen que el hash lógico completo de la fixture sea distinto.
- En consecuencia, **se confirmó repetibilidad estructural bajo el comparador existente, no identidad exacta de todas las tablas ni reproducibilidad byte a byte**. El comparador reporta `differences={}` para el alcance que evalúa; no se debe interpretar como ausencia de diferencias de toda la base.

Los detalles de esta comparación están en `evidencia/readonly_comparison.json`; el resumen del par, hashes de artefactos y manifiestos MCP originales están en `evidencia/pair_summary.json` y los dos subdirectorios `evidencia/build_a/` y `evidencia/build_b/`. `evidencia/SHA256SUMS` permite verificar los artefactos conservados.

## Acciones y límites

1. Se registraron resultados, llamadas, errores y hashes; no se corrigió el grafo ni se cambiaron mecanismos del motor.
2. Se detuvo el flujo ante la falta de unicidad de ruta; **no** se ejecutó ningún brazo de medición, la QA completa, ni se tocaron conexiones.
3. La aprobación de hashes está pendiente de una decisión posterior. Este registro documenta una auditoría técnica, no una aprobación de Dennys.
