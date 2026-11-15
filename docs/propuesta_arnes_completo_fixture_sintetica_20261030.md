# Revisión de propuesta: arnés completo con gold sintético pequeño

**Estado: propuesta para auditoría; no ejecutada.** La autorización del smoke limitado no cuenta como congelación ni como aprobación para medir.

## Compatibilidad con las guardas actuales

La preparación (`prepare_fixture`) y `audit_repeatability` ya pueden usar un gold sintético autocontenido. La medición completa (`measure_baseline`), en cambio, **no puede usarlo honestamente tal como está**: si su SHA-256 no es `BASE_GOLD_SHA256`, el arnés exige un ledger de revisión y cierre del gold que se deriva del gold original. Fabricar ese ledger para el sintético fingiría una revisión de origen que nunca ocurrió. No se debe crear ese artefacto ni cambiar el SHA del original para franquear la guarda.

Por eso, la ruta actual debe parar antes de la medición. Para poder probar después N/G/R de extremo a extremo, propongo añadir al **arnés auxiliar únicamente** un modo explícito `synthetic_smoke`, separado del camino original. No sería una excepción automática por hash ni un relajamiento de `validate_freeze_approval`:

- El modo exige que el gold, sus manifiestos y las fixtures estén bajo el nuevo `BIORAG_QA_TEMP_ROOT`; los resuelve y comprueba con la guarda de rutas actual. Rechaza rutas fuera del temporal.
- El gold lleva un `synthetic_gold_manifest_v1` propio: `provenance="synthetic"`, hash exacto, esquema, autoría/procedencia declarada y `original_gold_read=false`; no contiene `source_sha256` ni se presenta como revisión del gold original.
- El esquema del gold sintético será mínimo pero completo para el arnés: un episodio, tres nodos, dos aristas y consultas/etiquetas sintéticas para calcular canales y métricas. No se reutiliza ningún texto, identificador o etiqueta del corpus original.
- El modo sigue exigiendo dos llamadas independientes a `prepare_fixture`: dos SQLite nuevas, dos sesiones MCP reales, rutas/`construction_id`/ledgers distintos, mismo hash del gold sintético y estructura repetible. Copiar una construcción no cuenta como segunda.
- La guarda de medición exige una aprobación **real y posterior** de Dennys sobre los hashes concretos del gold sintético, grafo, par repetible y brazos. Primero se presenta un manifiesto candidato sin aprobación; se detiene la ejecución y se solicita confirmación explícita. Solo tras esa confirmación se registra el artefacto aprobado. No se rellena `aprobado_por` por anticipado ni se reaprovecha la autorización del smoke.
- Con esa aprobación y sin alterar el camino original, `measure_baseline` usa copias aisladas para los brazos configurados N0/N1, G1/G2 y R; verifica canales separados y diffs por fila/campo. W queda fuera. Un fallo controlado se prueba en otra DB sintética; se verifican el evento, `run_failure.json` y sus hashes, y la corrida se marca inválida.

## Verificación previa y condiciones de parada

Antes de habilitar `synthetic_smoke`, añadir pruebas negativas que demuestren que el camino original no acepta el manifiesto sintético, que el modo sintético rechaza hashes/rutas/ledgers discordantes y que la falta de aprobación no llega a iniciar ningún brazo. Las pruebas positivas deben pasar por los validadores y MCP reales, no reemplazar las guardas con mocks. Un gate sin aprobación debe fallar de forma esperada y conservar su evidencia.

**No ejecutar ahora preparación MCP, prueba ni medición.** No leer ni modificar el gold o bases originales; no cambiar motor ni ranking. Si un MCP falla, preservar la evidencia y no reintentar sobre esa base. W sigue pendiente.
