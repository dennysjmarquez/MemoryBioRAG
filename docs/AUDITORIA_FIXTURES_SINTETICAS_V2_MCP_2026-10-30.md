# Auditoría de dos fixtures sintéticas v2 con MCP real — 2026-10-30

## Dictamen y alcance

Se construyeron dos fixtures desde bases nuevas e independientes, usando sesiones MCP reales y copias temporales separadas de `synthetic_gold_v2.jsonl`. El hash de ambas copias coincide con el gold v2 publicado. La comparación del arnés devuelve `REPEATABLE_PAIR`, con construcciones independientes e idéntica estructura auditada.

El grafo completo observado es un triángulo: hay seis aristas dirigidas, ambas direcciones para amber–cobalt, amber–ivory y cobalt–ivory. **No se eliminó ni filtró ninguna conexión.** v2 no declara `ruta_2_saltos`; por tanto, la auditoría no afirma ni prueba una ruta única de dos saltos. La presencia del enlace directo amber–ivory permanece reportada.

**La preparación y la auditoría no son aprobación para medir.** No se ejecutaron brazos de medición ni QA completa; `baseline_searches_run=0`. La aprobación de hashes para medición queda pendiente de revisión posterior. W sigue pendiente.

## Gold/manifiesto y linaje

- Versión publicada: `synthetic_gold_v2`.
- SHA-256 del gold v2: `5d83616a63be7c73bbea8bb90452091316d7e238835013440a6fd939c13d16d8`.
- SHA-256 del manifiesto de versión publicado: `ed433826d89229f75e8af1c57b48c9c4fe3e808e4e14eaa1103ea8cac8d64b1f`.
- Cada build recibió su propia copia temporal del gold y un manifiesto operativo compatible con el arnés. Ambos manifiestos operativos enlazan la versión y SHA publicados; sus hashes son diferentes porque cada uno fija su propia ruta temporal: A `a9bc3d3fdc6ece5c52cff15c4f1300f0a39c38bcad6cab84065ff6a5d4f0a7dc`, B `83ab1f41f95917f0be64eb0b1afb62f9cbbdfb33dfaf210a37459083547b0ab0`.
- El manifiesto operativo permite preparación MCP solamente; no es aprobación de medición ni aprobación atribuida a una persona. El gold original no se leyó ni utilizó.

## Builds MCP

| Build | `construction_id` | Llamadas/eventos | Errores de llamada MCP | Nodos activos | Aristas dirigidas | SHA-256 lógico de fixture |
|---|---|---:|---:|---:|---:|---|
| A | `62c741169df44600b768cf3b71d17d96` | 9 | 0 | 3/3 | 6 | `00a5a27a573314fcecebfc9f86212153f587e347f7dc70b8f106c7ecb97c1af4` |
| B | `d59853d846644bab902e412c51059b90` | 9 | 0 | 3/3 | 6 | `fe79fefcb4168a6c86eda29c3a634710664a9730dae25a6a4b0e9b83c478b40c` |

Cada ledger contiene 3 llamadas `recordar` de preflight, 3 `aprender`, 1 `consolidar` y 2 `vincular`. Todas las llamadas fueron MCP real, sin errores de transporte o de herramienta. En ambos builds, `consolidar` estableció las seis aristas `co_nombre`, peso `0.65`, para los tres pares del triángulo. Los snapshots incluyen estados y espejos: los tres nodos están `activo`, no hay nodos dormidos, sinapsis latentes ni divergencias espejo.

La auditoría del gold v2 reporta cero nodos y aristas explícitas ausentes, `rutas_2_saltos=[]`, cero bloqueos de congelación estructural y `listo_para_auditoria_humana`. Ese resultado solo significa que el gate estructural de v2 no encontró un requisito declarado que el grafo incumpliera; **no** equivale a revisión humana completada, aprobación de hashes, congelación para medir ni evaluación de utilidad/ruido.

## Repetibilidad y diferencias entre bases

El comparador registra `schema=fixture_repeatability_v2`, `mode=REPEATABLE_PAIR`, `independent_builds_verified=true`, `identical_structural=true`, `differences={}` y `failure=null`. Los `construction_id`, rutas de DB y ledgers son distintos; ambos builds usan el mismo hash del gold.

Los hashes lógicos y físicos completos de las fixtures son distintos. Una comparación de solo lectura encontró diferencias de hash en tres tablas:

- `grupos_semanticos` y `nodo_grupos_semanticos`: los IDs/orden de filas cambian; los 22 nombres de grupo y las 63 membresías normalizadas por nombre de grupo coinciden.
- `sync_log`: las tres marcas temporales son `1793417832.0` en A y `1793417875.0` en B, con una diferencia de 43 segundos.

Por eso, `REPEATABLE_PAIR` acredita repetibilidad en el alcance estructural que compara —nodos, aristas directas, sinapsis latentes y divergencias espejo—, no igualdad de todas las tablas ni identidad byte a byte. Los hashes de tabla se preservan en cada `preparation_report.json`; el análisis normalizado está en `evidencia/readonly_table_comparison.json`.

## Incidencia de serialización posterior a MCP

En ambos comandos `preparar`, las nueve llamadas MCP concluyeron y el arnés persistió los manifiestos, eventos y `preparation_report.json`. Después, al serializar el informe de salida, el CLI terminó con código 1 por `TypeError: Object of type set is not JSON serializable` (`_prepare_cli` → `serialize_report`). No es un error MCP ni una llamada fallida; la evidencia de preparación se había escrito antes de ese paso. La comparación `comparar` sí terminó correctamente. La traza cruda de B se conserva en `evidencia/build_b/cli_stderr.log`; el error de ambos builds está resumido en `evidencia/cli_postprocessing_errors.json`.

La incidencia debe permanecer visible y resolverse antes de tratar futuras salidas del CLI como ejecuciones limpias. No se modificó el arnés en esta preparación.

## Etiquetas vacías, mediciones y conservación

En v2, `relacionados_utiles=[]` y `ruido_tonto=[]` significan **no adjudicadas**. No demuestran ausencia de pistas, asociaciones útiles o ruido. No se ejecutaron cálculos de métricas ni consultas de evaluación, y ninguna métrica de esas categorías se presenta como evaluada.

El archivo `evidencia/SHA256SUMS` verifica los artefactos archivados. Se incluyen gold v2 publicado, manifiesto publicado, copias temporales y manifiestos operativos por build, manifiestos de corrida, los 18 eventos MCP con respuestas y `call_errors`, reportes de preparación, grafo observado completo, comparación de repetibilidad, análisis RO de tablas y error de postprocesamiento. Las bases SQLite no se añaden al repositorio.
