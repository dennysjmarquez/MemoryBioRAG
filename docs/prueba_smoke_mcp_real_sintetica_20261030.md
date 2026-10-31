# Smoke test MCP real con fixture sintética — 2026-10-30

## Alcance

Prueba pequeña y aislada autorizada por Dennys. Se usó el transporte MCP stdio real del arnés con tres nodos sintéticos (`amber`, `cobalt`, `ivory`) y bases SQLite recién creadas bajo `/tmp/biorag_smoke_real_5spai895`. No se leyó ni modificó el gold original ni bases originales. No se llamó a `measure_baseline`, no se ejecutó QA completa y no se cambió motor ni ranking. W permanece pendiente.

Los argumentos completos de las nueve llamadas de preparación, las respuestas MCP completas de N0/G1/R, canales, errores y hashes están en [`evidencia_smoke_mcp_real_sintetica_20261030.json`](evidencia_smoke_mcp_real_sintetica_20261030.json). Los sidecars extensos de la preparación se conservaron bajo el temporal indicado; no se agregaron bases SQLite al repositorio.

## Procedimiento

1. Crear temporal nuevo externo al repositorio y fijarlo como `BIORAG_QA_TEMP_ROOT`.
2. Crear un gold sintético de un episodio con tres nodos y dos aristas (`amber—cobalt—ivory`).
3. Ejecutar `await prepare_fixture(fixture_path, temp_root, [episode], synthetic_gold_path)` usando `MCPProcess` real. La construcción produjo nueve eventos persistidos: tres `recordar` de preflight, tres `aprender`, un `consolidar` y dos `vincular`.
4. Copiar la fixture construida a tres SQLite temporales independientes; llamar al MCP real mediante `guarded_mcp_call` con N0, G1 y R y la misma consulta sintética `cobalt pigment`.
5. Separar resultados, contexto expandido, asociaciones y asociaciones enriquecidas usando el extractor del arnés. Cada brazo cambió solo las tablas esperadas de telemetría (`log_busquedas`, `nodo_accesos_historial`); no se informaron errores de transporte/tool.
6. En otra base y sesión MCP temporal, llamar deliberadamente a la herramienta inexistente `__controlled_missing_tool__`; guardar la respuesta MCP y el marcador `run_failure.json`, y verificar que ambos archivos existen.

## Llamadas de medición de canales (no es línea base)

Argumentos comunes: `query="cobalt pigment"`, `sustantivos_clave="cobalt,pigment"`, `limite=5`.

- **N0:** `deep=false`, `asociados=false`, `context_window=0`, `forzar_rafaga=false`.
- **G1:** `deep=false`, `asociados=true`, `context_window=1`, `forzar_rafaga=false`.
- **R:** `deep=false`, `asociados=true`, `context_window=0`, `forzar_rafaga=true`, `rafaga_palabras="cobalt,pigment"`.

Resultados observados:

| Brazo | Resultados principales (orden real) | Contexto expandido | Asociaciones / enriquecidas | Traza MCP |
|---|---|---|---|---|
| N0 | `cobalt`, `amber` | vacío | vacío / vacío | `capa_rafaga=0`, `total_candidatos_todos=2` |
| G1 | `cobalt`, `amber` | `ivory` | `amber`, `cobalt`, `ivory` / `amber`, `cobalt`, `ivory` | `capa_rafaga=0`, `total_candidatos_todos=2` |
| R | `cobalt`, `amber` | vacío | `amber`, `cobalt`, `ivory` / `amber`, `cobalt`, `ivory` | `capa_rafaga=2`, `total_candidatos_todos=2` |

Los tres canales se conservaron separados: el elemento `ivory` aparece en `contexto_expandido` de G1, no se fusionó con `resultados`; las asociaciones permanecen en sus canales. El campo `status` no viene en las respuestas de búsqueda exitosas (respuesta MCP parseada sin errores); `errors=[]` en cada brazo.

## Preparación, error encontrado y corrección del arnés

La primera llamada real a `prepare_fixture` quedó inválida y preservada. El MCP rechazó `aprender` porque el esquema live requiere `dimensiones`; el arnés no enviaba ese argumento. Respuesta cruda exacta:

```text
Error executing tool aprender: 1 validation error for biorag_aprenderArguments
dimensiones
  Field required [type=missing, input_value={'concepto': 'amber', 'co...'busqueda_previa': True}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
```

La excepción final registrada fue:

```text
RuntimeError: MCP aprender falló; corrida inválida, evidencia: /tmp/biorag_smoke_real_jbaf2pw_/construction/synthetic_fixture.sqlite.evidence
```

El arnés ahora envía `dimensiones="{}"`: JSON vacío, sin atribuir etiquetas semánticas nuevas a los datos sintéticos. No se modificó el motor. La prueba corregida de preparación terminó `listo_para_auditoria_humana`, con 9 eventos, `construction_id=faf0a43764e24a8ea9bb8de40ef61a8d`, `fixture_sha256=8de3bcbb1fe9b29d41328fac731710b9ac2188c313d89384bd671d9b58ff4347` y `graph_blockers=[]`.

## Fallo controlado y evidencia conservada

Llamada MCP deliberadamente inválida: herramienta `__controlled_missing_tool__`, argumentos `{}`. Respuesta cruda exacta y parseo:

```text
Unknown tool: __controlled_missing_tool__
```

```json
{"_mcp_is_error": true, "mensaje": "Unknown tool: __controlled_missing_tool__", "status": "mcp_error"}
```

No fue un error de transporte ni de teardown (`call_errors=[]`); fue un error explícito MCP (`_mcp_is_error=true`). Evidencia guardada y comprobada:

- `/tmp/biorag_smoke_real_5spai895/controlled_failure/failure.evidence/controlled_failure_event.json`
- `/tmp/biorag_smoke_real_5spai895/controlled_failure/failure.evidence/run_failure.json`
- Resultado: ambos archivos presentes (`both_files_preserved=true`). Sus SHA-256 se incluyen en el JSON de evidencia.

La corrida de preparación que falló al faltar `dimensiones` también permanece marcada inválida, con sus dos eventos y `run_failure.json`, bajo `/tmp/biorag_smoke_real_jbaf2pw_/construction/synthetic_fixture.sqlite.evidence`.

## Cambios y verificación

Se ajustó únicamente el arnés auxiliar para enviar el argumento requerido por el servidor MCP y se añadió una prueba unitaria que impide perderlo. Sin cambios en `core/`, ranking, motor ni datos persistentes originales.

```text
.........................                                                [100%]
25 passed in 0.18s
```

Además, `py_compile` y `git diff --check` finalizaron correctamente. La ejecución MCP aquí descrita fue una prueba smoke pequeña, no una medición de línea base ni QA completa.
