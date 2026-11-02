# Réplica sintética de H-E3-ETQ-01: controles emparejados

- **Fecha:** 2026-11-02
- **Controles de referencia:** auditoría del commit `e71d7bc0927f137a6a51bf5afb8d6261755061a3`
- **Estado:** réplica completada; investigación E3 abierta. Sin cambios al motor, sin decisión de política y sin avance a E4.

## Alcance y método

Se ejecutaron fixtures sintéticas, exclusivamente mediante MCP stdio sobre copias temporales. No se abrieron ni modificaron bases reales. Cada familia parte del mismo origen emparejado en los brazos «pista activa» y «neutral de igual longitud». Se reemplaza una sola etiqueta variable, mientras las demás etiquetas, contenido, asociaciones manuales, sinónimos y configuración permanecen fijos. Las columnas de etiqueta exacta y plegada se escriben y verifican coherentemente.

Se cubrieron cuatro rutas diseñadas: pista solo en etiqueta; pista en contenido con una contradicción textual; pista presente en sinónimos; y pista presente en un vecino enlazado. El manifiesto íntegro conserva todas las pistas y los textos sintéticos usados, incluidos los elementos ausentes del brazo consultado; cada conjunto de evidencia incluye su hash SHA-256. Se mantuvo el reloj fijo y un estado/copia independiente para cada sesión. Las consultas se ejecutaron en ambos órdenes y, además, en copias aisladas equivalentes.

El experimento comprende **32 sesiones MCP stdio** (4 familias × 2 brazos × 4 modos: dos órdenes y dos consultas aisladas), **16 pares** activo-neutral y 8 comprobaciones de orden por brazo/familia. Se conservaron **176 snapshots** antes de stdio, tras initialize y la primera llamada de herramienta, tras escritura y tras cada consulta. Cada snapshot contiene todas las filas de **nueve tablas de grafo** (`sinapsis`, `sinapsis_latentes`, `sinapsis_cuarentena`, `largo_plazo_dimensiones`, `grupos_semanticos`, `nodo_grupos_semanticos`, `concept_hubs`, `concept_hub_nodes`, `concept_hub_bridges`) más una proyección de todas las filas `largo_plazo(concepto, asociaciones)`: diez consultas SQL por snapshot. No es una copia de todas las tablas SQLite ni de todos los campos de `largo_plazo`. Las 1.760 consultas SQL de snapshot terminaron sin error. La igualdad se compara por filas completas de las nueve tablas y por filas completas de la proyección, no por conteos ni pesos redondeados.

## Resultados observados

- **32/32 sesiones** terminaron sin error o inconclusión. En los 16 pares, los payloads almacenados coincidieron con las etiquetas esperadas y las filas completas del grafo fueron iguales entre brazos en cada etapa comparable.
- Las **8/8 comparaciones de orden** dieron el mismo resultado por rol de consulta y el mismo grafo final exacto. Las consultas aisladas se mantuvieron en copias equivalentes.
- Las asociaciones manuales iniciales se conservaron en todos los snapshots de las 32 sesiones. No se detectaron aristas manuales perdidas.
- Las filas antes de stdio y después de `initialize` fueron idénticas en **32/32 sesiones**. Entre el snapshot posterior a initialize y el posterior a la primera llamada (`sustantivos`) se observó una arista `dmn_synthesized` nueva en cada sesión (**32 en total**); no se observó otra arista nueva entre esa etapa y la escritura. Esto informa el intervalo observado: no atribuye el cambio al handshake por sí solo ni demuestra qué subpaso interno lo causa.
- Para la consulta de pista histórica, en la familia «solo etiqueta» el brazo activo encontró el objetivo como resultado primario en los cuatro modos; el neutral no lo encontró ni como primario ni en contexto en esos cuatro modos.
- En la familia con contradicción en el contenido, ambos brazos recuperaron el objetivo como primario en los cuatro modos; la pista también estaba en el contenido, de modo que el resultado no aísla el efecto de la etiqueta.
- En la familia de sinónimos, ambos brazos recuperaron el objetivo como primario en los cuatro modos; había una ruta alternativa por sinónimo.
- En la familia de vecino enlazado, el brazo activo recuperó el objetivo como primario en los cuatro modos; en el brazo neutral no apareció como primario, pero sí en el contexto expandido en los cuatro modos.
- Las consultas de la pista actual, que se mantuvo fija entre brazos, recuperaron el objetivo como primario en todas las ejecuciones correspondientes.

## Interpretación y límites

La diferencia de la familia sin ruta alternativa y la recuperación primaria con pista activa en la familia de vecino son **observaciones compatibles** con que la etiqueta activa influya en la recuperación de estos fixtures. No establecen una causa general ni una política de retención, reemplazo o acumulación. Las rutas por contenido, sinónimos y vecinos muestran por qué el contraste debe evaluarse por canal y por contexto.

En particular, recuperar un término que aparece en un registro textual contradicho **no** demuestra por sí solo un falso positivo ni que el motor o un agente haya adjudicado vigencia a ese recuerdo. La réplica mide resultados de recuperación sintética, no verdad, vigencia o adjudicación. No se reetiquetaron casos gold, no se fusionaron recuerdos ni se hizo backfill.

No se propone ni se aplica cambio al motor. No se selecciona reemplazo frente a acumulación. E3 permanece abierto y no se avanza a E4.

## Evidencia y reproducibilidad

El agregado de este documento es la evidencia sintética publicable. El manifiesto íntegro y las trazas por caso —incluidos textos sintéticos, consultas, etiquetas y snapshots— son privados y están excluidos del control de versiones. La evidencia inicial permanece intacta en `.private_evidence/e3_tag_replica_e71d7bc_20261102/`; se conservó además una copia byte-a-byte, verificada por checksum, en `.private_evidence/e3_tag_replica_e71d7bc_20261102_original_preserved/`. La corrida final del arnés corregido está separada en `.private_evidence/e3_tag_replica_e71d7bc_20261102_corrected_02/`; volvió a producir 32 sesiones válidas, 176 snapshots y cero errores de consulta. Los conjuntos de evidencia guardados en esos directorios privados conservan checksums verificables y no se deben publicar.

Desde la rama del operador, con las dependencias de `requirements.txt`:

```bash
python -m venv /tmp/e3-mcp-venv
/tmp/e3-mcp-venv/bin/pip install -r requirements.txt
PYTHONHASHSEED=0 /tmp/e3-mcp-venv/bin/python scripts/replicar_hipotesis_etiquetas_controles_e3.py
```

El arnés corregido crea por defecto un directorio UTC nuevo bajo `.private_evidence/`; también acepta `--evidence-dir <ruta-nueva-bajo-.private_evidence>`. Rechaza rutas fuera de ese directorio y no sobreescribe una carpeta de evidencia existente. Genera allí el manifiesto, el reporte detallado y sus checksums, e imprime únicamente el resumen agregado.
