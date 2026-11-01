# Implementación del arnés de línea base segura N/G/R

**Estado:** el modo `synthetic_smoke` está implementado y cubierto por pruebas unitarias aisladas. En esta implementación no se construyeron fixtures, no se llamó MCP y no se ejecutaron mediciones ni QA; el smoke real limitado previo está documentado en `prueba_smoke_mcp_real_sintetica_20261030.md`.

Este documento complementa el diseño aprobado en `propuesta_linea_base_segura_memoria_20261030.md`. No cambia motor, ranking ni sinapsis.

## Código y condiciones

- `scripts/linea_base_segura.py`: helpers puros de preflight, snapshot/auditoría del grafo, versionado/cierre del gold, gates de aprobación y dos fases operativas separadas.
- `tests/test_linea_base_segura.py`: pruebas aisladas sin MCP real ni búsquedas; algunas crean SQLite sintéticas temporales para ejercer la guarda de rutas.
- N0/N1: `deep=False`, `forzar_rafaga=False`, `context_window=0`, con `asociados=False/True`, respectivamente.
- G1/G2: N1 con `context_window=1/2`.
- R: `forzar_rafaga=True`, `deep=False`, `context_window=0`, términos del gold serializados en lista fija y requisito de que **todos** los recuerdos de la fixture estén activos antes de cada consulta. No ejecuta consolidación ni W. La auditoría de R valida filas: una arista nueva solo se acepta si ambos extremos existen en gold, el par no estaba en ninguna orientación y la fila respeta campos de inserción (`rafaga_rememb`, peso 0.6, `creado_en` finito, `ultimo_uso` nulo); un refuerzo solo puede cambiar `peso` (+0.1 hasta 0.95) y `ultimo_uso`, sin alterar dirección, tipo ni fecha de creación. `sdm_dirty` solo acepta nuevas marcas para extremos de aristas insertadas. No se permite DELETE de sinapsis.
- W no figura como brazo ejecutable. Una manifestación que intente incluir W se rechaza.

## Guardas principales

1. En el modo original, el hash inicial del gold queda anclado en el arnés: `d91e9ee1437f2695b2278ff06cf2ad202e5d124c500c0f8dc22a6865e0e2497e`. Una versión distinta requiere ledger lateral de revisión; nunca sobrescribe el archivo origen. El modo explícito `synthetic_smoke` usa un manifiesto sintético autocontenido bajo el temporal y no crea ni acepta ledger de revisión del gold original.
2. La transformación estática de clave replica la entrada MCP observada (`lower()` + espacios por `_`), no una normalización Unicode supuesta. Los posibles `co_nombre` se publican como riesgos, nunca como atribución; no se filtra ni elimina ninguna asociación por tipo/peso.
3. La construcción MCP, cuando se autorice, queda bajo `BIORAG_QA_TEMP_ROOT`, corta cada tool call con hash de tablas, grafo dirigido, estados, latentes y divergencia del espejo. La fase `preparar` no ejecuta las consultas de evaluación y deja el informe fuera del repositorio.
4. Un atajo en ruta gold, aristas explícitas ausentes, nodos ausentes, colisiones preliminares, integridad fallida o discrepancia de ruta bloquea la congelación. Cada cambio gold exige motivo por episodio, archivo nuevo, hashes de origen/revisión y cierre separado (`close_gold_revision`) antes de cualquier búsqueda.
5. La repetibilidad solo se declara tras dos invocaciones MCP independientes de `preparar`, con DB distintas, `construction_id` único, manifiestos, informe final y ledger íntegro de eventos de cada build del mismo gold. `comparar` rechaza evidencia ausente/copied o construcciones estructuralmente distintas; no hay modo de medición con una sola fixture. La fase `medir` verifica esos hashes y ledgers, además del gold/fixture, preflight, cierre de revisión, hash de auditoría, aprobación y arms. Cada consulta parte de copia limpia. Respuesta MCP de error, excepciones de inicio/llamada/cierre, mutación inesperada y pérdida potencial de evidencia quedan cubiertas por pruebas de regresión. Cualquiera de los tres primeros invalida toda la corrida y detiene nuevas consultas. Antes/después, respuesta cruda/parseada, error, diffs por fila/campo y DB por consulta se guardan en un directorio persistente bajo el root temporal; no se usa `TemporaryDirectory` ni se borra evidencia al invalidarse. El informe final lleva `valida=false`, motivos y rutas de evidencia. N/G no admiten cambios fuera de telemetría append/evicción autorizada; R usa whitelist por fila/campo para `sinapsis` y `sdm_dirty`, además de telemetría.
6. Resultados, asociaciones, asociaciones enriquecidas y contexto se informan por canal; incluye hash/diffs, latencia, bytes y errores. No se aplican umbrales de éxito.

## Modo aislado `synthetic_smoke`

`load_synthetic_gold` es un cargador separado: `preparar --gold-mode synthetic_smoke` y `medir --gold-mode synthetic_smoke` lo usan sin invocar `load_gold` original. Acepta 1–4 episodios, hasta 12 nodos/24 consultas, prefijos `synthetic_`, `stratum=synthetic_smoke`, etiquetas locales y términos literales respaldados por el contenido. Normaliza a listas vacías los campos opcionales que `_result_row`/métricas consumen (`objetivos_principales`, `relacionados_utiles`, `ruido_tonto`); no infiere `espera_abstencion` y exige objetivo para consultas contestables. El loader original no se altera y sigue requiriendo sus 88 episodios y distribución exacta.

`prepare_fixture(..., gold_mode="synthetic_smoke", synthetic_manifest_path=...)` y `measure_baseline(..., gold_mode="synthetic_smoke", synthetic_manifest_path=...)` vuelven a cargar el gold desde el archivo y comparan canónicamente la lista de episodios recibida con la lista parseada. Una discrepancia falla antes de MCP o de cualquier brazo. En `medir`, el gold, manifiesto, aprobación, informe de repetibilidad y ambas fixtures tienen que estar bajo `BIORAG_QA_TEMP_ROOT`; la ruta del gold original se rechaza. El `synthetic_gold_manifest_v1` debe declarar `provenance="synthetic"`, `original_gold_read=false`, ruta y SHA-256 exactos, y no puede incluir `source_sha256`/`source_gold_sha256` ni `derived_from_original`.

El prefijo común `synthetic_` activa avisos estáticos de posible `co_nombre`. Son riesgos, no una predicción ni un filtro de asociaciones. La preparación conserva el grafo observado y su auditoría; no se presupone que tenga solo las aristas Gold o que sea una cadena. Antes de aprobar, Dennys debe inspeccionar la fixture/preparation report y las aristas reales; los hashes aprobados fijan el grafo concreto. La prueba sintética incluye una arista extra observada y confirma que un atajo de ruta se informa como bloqueo, sin borrar la asociación.

La aprobación no se crea automáticamente. Tras revisión humana del gold, grafo y dos construcciones, Dennys debe confirmar los hashes exactos y emitir un `synthetic_freeze_approval_v1` que incluya `gold_mode="synthetic_smoke"`, `estado="APROBADO"`, `aprobado_por="Dennys"`, `synthetic_gold_manifest_sha256`, `gold_sha256`, `fixture_sha256`, `graph_review_sha256`, `repeatability_report_sha256`, `arms=[N0,N1,G1,G2,R]` y `wake_W_included=false`. El arnés comprueba estas correspondencias con los artefactos actuales antes de crear el run root; si falta la aprobación, ningún brazo arranca. Las pruebas usan vectores sintéticos en memoria para validar la lógica, pero no escriben ni usan una aprobación operacional.

Ejemplos de uso **futuro, no ejecutados**. La preparación requiere su autorización explícita; la medición requiere además revisión y aprobación real de los hashes:

```bash
python scripts/linea_base_segura.py preparar \\
  --gold-mode synthetic_smoke \\
  --gold "$BIORAG_QA_TEMP_ROOT/synthetic_gold.jsonl" \\
  --synthetic-manifest "$BIORAG_QA_TEMP_ROOT/synthetic_gold_manifest.json" \\
  --db "$BIORAG_QA_TEMP_ROOT/build-a/fixture.sqlite" \\
  --temp-root "$BIORAG_QA_TEMP_ROOT" \\
  --salida /ruta/externa/preparation.json \\
  --ejecutar-preparacion

python scripts/linea_base_segura.py medir \\
  --gold-mode synthetic_smoke \\
  --gold "$BIORAG_QA_TEMP_ROOT/synthetic_gold.jsonl" \\
  --synthetic-manifest "$BIORAG_QA_TEMP_ROOT/synthetic_gold_manifest.json" \\
  --fixture "$BIORAG_QA_TEMP_ROOT/build-a/fixture.sqlite" \\
  --temp-root "$BIORAG_QA_TEMP_ROOT" \\
  --aprobacion "$BIORAG_QA_TEMP_ROOT/approval.json" \\
  --repetibilidad "$BIORAG_QA_TEMP_ROOT/repeatability.json" \\
  --salida /ruta/externa/synthetic-baseline.json \\
  --ejecutar-linea-base
```

La ejecución anterior no se realizará sin una autorización futura explícita para esos hashes. W no se incluye.

## Comandos futuros (no ejecutados en esta tarea)

La construcción temporal requiere autorización previa, además de la bandera explícita. Exportar `BIORAG_QA_TEMP_ROOT` a una ruta nueva fuera del repositorio y pasar exactamente la misma ruta como `--temp-root`; el código rechaza raíces no configuradas, el repo y sus directorios padre.

```bash
python scripts/linea_base_segura.py preparar \
  --gold scripts/casos_qa_intuicion_asociaciones_e1.jsonl \
  --db "$BIORAG_QA_TEMP_ROOT/fixture-e1.sqlite" \
  --temp-root "$BIORAG_QA_TEMP_ROOT" \
  --salida /ruta/externa/preflight.json \
  --ejecutar-preparacion
```

Construir una segunda fixture independiente bajo el mismo root y comparar, sin buscar:

```bash
python scripts/linea_base_segura.py comparar \\
  --primera "$BIORAG_QA_TEMP_ROOT/fixture-e1-a.sqlite" \\
  --segunda "$BIORAG_QA_TEMP_ROOT/fixture-e1-b.sqlite" \\
  --temp-root "$BIORAG_QA_TEMP_ROOT" \\
  --salida /ruta/externa/repetibilidad.json
```

Si los dos ledgers de construcción no son completos/independientes o las estructuras difieren, `comparar` falla; no hay modo de medición con una sola fixture. En modo original, tras revisar el grafo y cerrar toda modificación de gold, una persona debe emitir un manifiesto de congelación externo que contenga `estado=APROBADO`, `aprobado_por=Dennys`, hashes exactos de gold y fixture, hash del informe de grafo recalculado, hash exacto del informe `REPEATABLE_PAIR`, `arms=[N0,N1,G1,G2,R]`, `wake_W_included=false`; si gold fue revisado, debe incluir además hash del ledger de cierre. Solo entonces el comando de medición puede ejecutarse con `--repetibilidad /ruta/externa/repetibilidad.json --ejecutar-linea-base`. El código no genera ni autoaprueba ese manifiesto.

No ejecutar `scripts/evaluar_qa_intuicion_asociaciones_e1.py` ni su `run_async` como parte de estas fases. No pasar rutas de bases reales.
