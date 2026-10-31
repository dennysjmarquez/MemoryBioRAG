# Reintento limpio de preparación de fixtures sintéticas v2 con MCP — 2026-10-31

## Resultado

Se crearon dos fixtures nuevas desde cero, en bases SQLite vacías y rutas temporales nuevas, con dos sesiones MCP stdio reales independientes. Los dos comandos `preparar` y el comando `comparar` finalizaron con **código 0**. Cada informe de CLI coincide byte por byte con su `preparation_report.json` persistido. Las salidas y códigos exactos se conservaron en la carpeta de evidencia.

Ambas preparaciones terminan en `listo_para_auditoria_humana`, con `baseline_searches_run=0`. Esto no es aprobación humana ni aprobación de hashes para medición. No se ejecutaron brazos de medición ni QA completa. W sigue pendiente.

## Gold aprobado y manifiestos operativos

- Gold: `synthetic_gold_v2` publicado; SHA-256 `5d83616a63be7c73bbea8bb90452091316d7e238835013440a6fd939c13d16d8`.
- Manifiesto de versión publicado: SHA-256 `ed433826d89229f75e8af1c57b48c9c4fe3e808e4e14eaa1103ea8cac8d64b1f`.
- Cada build usó su propia copia temporal del gold y un manifiesto operativo separado que enlaza ambos hashes publicados. SHA-256 de manifiestos operativos: A `eaa6d4235f07e21daa479433cbe0107b5d5f120a9224a1c2debb3d996c0ad451`; B `8a5d47f77e6d7213eb4daea66092e7b6a9c4965998833f1cd0821cab936a7d3e`.
- `original_gold_read=false`. No se usaron bases originales ni las DB de intentos anteriores.

## Construcciones y resultados exactos

| Build | `construction_id` | Salida `preparar` | Eventos MCP | Errores de llamadas MCP | Nodos activos | SHA-256 lógico de fixture | SHA-256 del archivo SQLite |
|---|---|---:|---:|---:|---:|---|---|
| A | `1f72ea5a530245b5ba0616a563be8a0e` | 0 | 9 | 0 | 3/3 | `cf9aaf50e0b36007c9c00cc4b7335c47c0d1dda1bd598bef561cdcf9c8bace55` | `72793a764a131d4ed5d0d8db13fa3e2199abe2b55d03aaedb4c6818bcdb9e14f` |
| B | `3c3ace91cf934ff8927e59b8accd046d` | 0 | 9 | 0 | 3/3 | `911a275343d51d2264ccb7dbd6ac423709acde1c7a37b087dedeceddc045ba12` | `8b7afebd73cd852ab47eb8649a463090f4d6fe50c3f99bdf03816f4e8b86671d` |

Cada ledger contiene las mismas nueve etapas: 3 `recordar` de preflight, 3 `aprender`, 1 `consolidar` y 2 `vincular`. Se conservaron las 18 llamadas con argumentos, respuesta, `call_errors`, cambios y hashes de tablas. `errors_inventory.json` registra códigos de salida, estado de manifiestos/informes, cero errores de herramienta y clasificación de `stderr`.

### Salida exacta de los comandos

Build A:

```text
{"estado": "listo_para_auditoria_humana", "gold_sha256": "5d83616a63be7c73bbea8bb90452091316d7e238835013440a6fd939c13d16d8", "fixture_sha256": "cf9aaf50e0b36007c9c00cc4b7335c47c0d1dda1bd598bef561cdcf9c8bace55", "baseline_searches_run": 0, "salida": "/tmp/biorag_v2_clean_pair_y77rdhst/build_a/preparation_report_cli.json"}
```

Build B:

```text
{"estado": "listo_para_auditoria_humana", "gold_sha256": "5d83616a63be7c73bbea8bb90452091316d7e238835013440a6fd939c13d16d8", "fixture_sha256": "911a275343d51d2264ccb7dbd6ac423709acde1c7a37b087dedeceddc045ba12", "baseline_searches_run": 0, "salida": "/tmp/biorag_v2_clean_pair_y77rdhst/build_b/preparation_report_cli.json"}
```

Comparación:

```text
{"mode": "REPEATABLE_PAIR", "independent_builds_verified": true, "identical_structural": true, "salida": "/tmp/biorag_v2_clean_pair_y77rdhst/repeatability_report.json"}
```

Los tres códigos de salida (`preparar` A, `preparar` B, `comparar`) fueron `0`. Los `stderr` crudos de 908 bytes por preparación también están archivados; contienen mensajes de PMI y de establecimiento de sinapsis, no excepciones. Los ledgers MCP de ambos builds tienen cero `call_errors` y no registran `run_failure` ni fallos de cierre.

## Auditoría del grafo completo

Los dos grafos observados son idénticos en nodos, aristas directas, sinapsis latentes y divergencias espejo:

- 3 nodos; los tres están `activo`; 0 dormidos.
- 6 aristas dirigidas, todas tipo `co_nombre`, peso `0.65`: ambas direcciones de amber–cobalt, amber–ivory y cobalt–ivory.
- 0 sinapsis latentes y 0 divergencias espejo.
- Las parejas explícitas de v2 están presentes. `rutas_2_saltos=[]`, porque v2 no declara ninguna ruta de dos saltos.

La conexión directa amber–ivory continúa íntegra y visible junto con todas las demás. No se borró, filtró ni ignoró ninguna conexión por tipo o peso. El auditor muestra cero bloqueos estructurales para las afirmaciones que v2 sí contiene; esto no equivale a aprobación humana para congelar o medir.

## Repetibilidad y alcance de la comparación

`repeatability_report.json` confirma `mode=REPEATABLE_PAIR`, `independent_builds_verified=true`, `identical_structural=true`, `differences={}` y `failure=null`. Los IDs de construcción y las rutas de las bases son distintos; ambas usan el mismo SHA-256 del gold.

Los hashes lógicos de fixtures no son iguales. Una comparación de solo lectura encontró diferencias en hashes de `grupos_semanticos`, `nodo_grupos_semanticos` y `sync_log`. Los 22 nombres de grupos y las 63 membresías normalizadas por nombre de grupo coinciden; varían IDs/orden numéricos. Los timestamps `sync_log` son A `1793420364.0` y B `1793420368.0` (tres filas por build). Por tanto, se confirmó repetibilidad estructural según el comparador, no identidad byte a byte ni igualdad de todas las tablas. Los valores detallados están en `evidencia/readonly_table_comparison.json`.

## Conservación, límites y próxima decisión

La nueva evidencia está en `docs/auditoria_fixtures_sinteticas_v2_mcp_reintento_2026-10-31/evidencia/`: copias temporales del gold y manifiesto operativo por build, manifiestos de corrida, informes CLI y persistidos, llamadas/eventos, `stderr`, códigos de salida, comparación, grafo observado completo y hashes. `SHA256SUMS` verifica el conjunto. Las DB SQLite no se incluyen en Git; sus hashes están registrados.

La evidencia de los dos intentos anteriores con error permanece intacta en `docs/auditoria_fixtures_sinteticas_v2_mcp_2026-10-30/evidencia/`; su `SHA256SUMS` original sigue verificando. Estos resultados limpios son un nuevo par, no una reclasificación retroactiva de aquellos intentos.

No se ejecutaron brazos de medición, consultas de evaluación ni QA completa. Las etiquetas vacías de `relacionados_utiles` y `ruido_tonto` siguen no adjudicadas; no se calcularon ni presentan métricas de esas categorías. La aprobación de hashes para medir queda pendiente de la revisión posterior.
