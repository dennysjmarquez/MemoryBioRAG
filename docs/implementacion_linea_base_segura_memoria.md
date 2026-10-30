# Implementación del arnés de línea base segura N/G/R

**Estado:** implementado y cubierto por pruebas unitarias aisladas; no se construyó fixture, no se llamó MCP y no se ejecutó medición ni QA.

Este documento complementa el diseño aprobado en `propuesta_linea_base_segura_memoria_20261030.md`. No cambia motor, ranking ni sinapsis.

## Código y condiciones

- `scripts/linea_base_segura.py`: helpers puros de preflight, snapshot/auditoría del grafo, versionado/cierre del gold, gates de aprobación y dos fases operativas separadas.
- `tests/test_linea_base_segura.py`: pruebas sin MCP, SQLite ni lectura de bases.
- N0/N1: `deep=False`, `forzar_rafaga=False`, `context_window=0`, con `asociados=False/True`, respectivamente.
- G1/G2: N1 con `context_window=1/2`.
- R: `forzar_rafaga=True`, `deep=False`, `context_window=0`, términos del gold serializados en lista fija y requisito de que **todos** los recuerdos de la fixture estén activos antes de cada consulta. No ejecuta consolidación ni W.
- W no figura como brazo ejecutable. Una manifestación que intente incluir W se rechaza.

## Guardas principales

1. El hash inicial del gold queda anclado en el arnés: `d91e9ee1437f2695b2278ff06cf2ad202e5d124c500c0f8dc22a6865e0e2497e`. Una versión distinta requiere ledger lateral de revisión; nunca sobrescribe el archivo origen.
2. La transformación estática de clave replica la entrada MCP observada (`lower()` + espacios por `_`), no una normalización Unicode supuesta. Los posibles `co_nombre` se publican como riesgos, nunca como atribución; no se filtra ni elimina ninguna asociación por tipo/peso.
3. La construcción MCP, cuando se autorice, queda bajo `BIORAG_QA_TEMP_ROOT`, corta cada tool call con hash de tablas, grafo dirigido, estados, latentes y divergencia del espejo. La fase `preparar` no ejecuta las consultas de evaluación y deja el informe fuera del repositorio.
4. Un atajo en ruta gold, aristas explícitas ausentes, nodos ausentes, colisiones preliminares, integridad fallida o discrepancia de ruta bloquea la congelación. Cada cambio gold exige motivo por episodio, archivo nuevo, hashes de origen/revisión y cierre separado (`close_gold_revision`) antes de cualquier búsqueda.
5. La repetibilidad exige comparar dos construcciones MCP por `comparar`; si difieren, no se acepta un baseline pareado. El alcance de una sola fixture requiere manifiesto de repetibilidad `MATERIALIZED_ONLY` con motivo explícito. La fase `medir` verifica hash exacto gold/fixture, preflight estructural, manifest de cierre (si hay revisión), hash de auditoría recalculado, informe de repetibilidad fijado por hash, lista exacta de brazos y aprobación explícita de Dennys. Cada consulta parte de copia limpia; cualquier mutación inesperada invalida y detiene el informe conservando sus diffs. N/G no admiten cambios de grafo/estado; R admite solo telemetría más `sinapsis`/`sdm_dirty`, y ningún cambio de estado de nodo.
6. Resultados, asociaciones, asociaciones enriquecidas y contexto se informan por canal; incluye hash/diffs, latencia, bytes y errores. No se aplican umbrales de éxito.

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

Si la comparación difiere, no usar `REPEATABLE_PAIR`; caracterizarla o documentar y aprobar alcance `MATERIALIZED_ONLY` con motivo. Tras revisar el grafo y cerrar toda modificación de gold, una persona debe emitir un manifiesto de congelación externo que contenga `estado=APROBADO`, `aprobado_por=Dennys`, hashes exactos de gold y fixture, hash del informe de grafo recalculado, hash exacto del informe de repetibilidad, `arms=[N0,N1,G1,G2,R]`, `wake_W_included=false`; si gold fue revisado, debe incluir además hash del ledger de cierre. Solo entonces el comando de medición puede ejecutarse con `--repetibilidad /ruta/externa/repetibilidad.json --ejecutar-linea-base`. El código no genera ni autoaprueba ese manifiesto.

No ejecutar `scripts/evaluar_qa_intuicion_asociaciones_e1.py` ni su `run_async` como parte de estas fases. No pasar rutas de bases reales.
