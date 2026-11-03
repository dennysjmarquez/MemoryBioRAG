# Fe de erratas y auditoría de feedback MCP E3

**Fecha:** 2026-11-02. Complementa `docs/e3_feedback_recordar_respuesta_sintetica_20261102.md` y registra los límites de verificación de las fe de erratas anteriores. No sustituye evidencia ni acepta conclusiones previas.

## Fe de erratas sobre verificabilidad

En este checkout, la rama activa estaba sincronizada con `035cf7875202ba03fdbbcbf6d9db4df8ea5b85d5`. El directorio `.private_evidence/` con las corridas anteriores citadas en informes y fe de erratas no está presente. Por tanto, **en esta auditoría no se verificaron sus hashes, archivos fuente, ni la preservación local de esas corridas**. Los informes versionados describen los resultados históricos, pero no bastan para validar de nuevo los artefactos privados. No se recrearon ni sobrescribieron los nombres de corrida anteriores.

La fe de erratas `docs/e3_corrigendum_excepciones_snapshot_20261102.md` conserva su registro publicado, pero sus afirmaciones sobre la comprobación de hashes fuente no pudieron ser verificadas independientemente en este checkout. Esta nota corrige el alcance de lo que podemos afirmar hoy; no altera ni invalida automáticamente aquella medición.

## Reproducción nueva: ruta de paráfrasis

Se completó el runner sintético `scripts/diagnosticar_feedback_recordar_respuesta_stdio_e3.py`: reenvía `modo_estricto` al límite MCP, añade una variante estricta y un control sin paráfrasis, y compara la recuperación MCP con controles FTS5 directos sobre la copia sembrada. Las nuevas salidas se guardaron en `.private_evidence/e3_feedback_paraphrase_trace_20261102_audit01/`, directorio nuevo, no rastreado; no se publican consultas ni payloads privados.

| Observación agregada (6 casos sintéticos) | Resultado |
|---|---:|
| Llamadas MCP `recordar` completadas | 6 |
| Llamadas con bandera MCP `isError` / excepción Python escapada | 0 / 0 |
| Respuestas con resultados | 3 |
| Aviso de brecha presente; respuestas con resultados y aviso | 6; 3 |
| Caso base con coincidencia literal objetivo | Sí (1 resultado; traza de capa paráfrasis 0.0) |
| Paráfrasis sola: término presente en FTS5 del fixture | Sí |
| Paráfrasis sola: resultado objetivo por MCP, modo normal / estricto | No / no (0 resultados en ambos) |
| Consulta sin paráfrasis: resultado objetivo por MCP | No (0 resultados) |
| Fechas legibles presentes en resultados | 0 de 3 |
| Errores de las sondas de snapshot | 0 |

La consulta FTS5 directa confirma que el término de paráfrasis está indexado y puede localizar el nodo sintético. **No demuestra que el flujo MCP recupere ese nodo por paráfrasis**: los dos casos MCP diseñados para ello no lo devolvieron. Tampoco se demostró una atribución errónea de un resultado efectivamente devuelto como `literal`; esa hipótesis queda abierta y sin confirmar. La búsqueda sin paráfrasis también devolvió cero en esta configuración, lo que limita la interpretación causal del contraste. No se modificó el motor.

Las seis llamadas reprodujeron aviso de brecha; tres de sus respuestas contenían resultados. “Con resultados” describe únicamente la presencia de resultados en la respuesta; no se evaluó ni se afirma su utilidad para una persona. Esto es un agregado sintético, no una afirmación de fallo operacional en datos reales. Las fechas persistidas no se emitieron como fechas legibles en los tres resultados observados. Los sondeos de unión de fecha y esquema se conservan en el reporte privado; no deben confundirse con fallos de MCP.

## Integridad, alcance y controles

- La evidencia nueva incluye `stdio_cases_full.json` (SHA-256 `10e47a5bb865b0f22890e5c24862bd00ce10989f56f4cdf04236aa56b57f150f`), `synthetic_manifest.json` (SHA-256 `6a5fb18b0053594b37c478a68231caae318091b18da668339f01cddd484c92e8`) y su `SHA256SUMS.json`. Se conservan fuera de Git bajo el directorio privado indicado.
- Los snapshots cubren filas completas de las nueve tablas de grafo listadas por el runner y la proyección `largo_plazo(concepto, asociaciones)`. **No son copia completa de SQLite.** No se descartaron pistas ni asociaciones.
- El runner sembró y operó sobre copias sintéticas temporales; bases originales abiertas: 0. Sin escrituras a bases originales.
- `python -m py_compile scripts/diagnosticar_feedback_recordar_respuesta_stdio_e3.py`: correcto.
- `PYTHONHASHSEED=0 PYTHONPATH=. python scripts/diagnosticar_feedback_recordar_respuesta_stdio_e3.py --evidence-dir .private_evidence/e3_feedback_paraphrase_trace_20261102_audit01`: finalizó con código 0.
- Suite completa: **824 passed, 2 subtests passed**.

## Límites y decisiones

Esta reproducción no reemplaza una auditoría de los artefactos privados ausentes ni la aceptación de la auditora. La reproducción anterior de agregados sintéticos atribuida a la auditora no se repitió aquí. La conclusión de la investigación de paráfrasis permanece provisional. Este cambio toca solo el arnés y esta documentación: **motor intacto; parches CJK sin aplicar; no E4**. No se tocó la investigación paralela de corrupción SQLite o instalador, ni se propuso reparación automática.
