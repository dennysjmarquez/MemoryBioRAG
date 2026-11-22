# Estado final del hito experimental — aprobación/búsqueda/QA

Informe de referencia: [INFORME_APROBACION_QA.md](INFORME_APROBACION_QA.md). Sustituye los estados intermedios anteriores de este archivo. No es aprobación de release v36.2.

## Completado

- Servidor MCP stdio de laboratorio: registrar/revisar/confirmar corrección y buscar_contextual. Fuera de core/MCP productivo.
- Transacción SQLite local ledger + grafo tipado, con digest, contexto delegado, revalidación, recibos idempotentes, concurrencia, rollback y recuperación tras muerte de proceso.
- Proyección sinapsis_sustitucion en copia del grafo; preserva asociaciones manuales del esquema sinapsis actual, cuya PK solo admite un tipo por par.
- E2E cliente MCP real + motor real + snapshot suministrado en backup temporal: canónico Top-1, histórico y cinco candidatos conservados, scores intactos, digest inválido rechazado, fuente intacta. Datos de interacción/antecedente son fixtures, contexto explícito.
- 59 tests de laboratorio PASS, incluyendo crecimiento con 10.000 afirmaciones ajenas.
- Suite global efectiva en copia con recursos completos: 879 PASS, 18 SKIP por ausencia de DB viva, 2 subtests PASS, 0 FAIL. No se relajaron ni editaron tests/core.
- QA oficial 921 casos, baseline y adaptador: ambas terminadas y gate OK. Con recursos completos, R@5=100%, R@1=93.03%, MRR=0.9566, FP=0/40 en ambos brazos. 921 salidas idénticas en orden y scores; categorías/globales iguales.
- QA usa ledger vacío/resolver ausente: valida no interferencia de conexión, no eficacia de aprobaciones sobre 921 contextos.

## Evidencia persistida

- resultados_qa_aprobacion.json: comparación final con recurso Hebbiano, hashes de fuente/script/casos/trazas, gates y denominadores.
- resultados_qa_piloto.json: ensayo previo con recursos reducidos, marcado explícitamente; no mezclar con validación final.
- resultados_suite_global.json: resumen de suite global y errores de preparación ya corregidos.
- resultados_e2e_aprobacion.json: interacción MCP, recibo, arista y búsqueda.
- manifest_aprobacion.json: hashes de implementación medida.

## Temporales de esta sesión (pueden no persistir)

- /tmp/biorag-phase3/results: piloto emparejado terminado.
- /tmp/biorag-phase5/results: pareja final completa, trazas y métricas oficiales.
- /tmp/biorag-phase4-global-complete.xml y .log: suite global con recursos correctos.
- /tmp/biorag-approval-tests-final.txt y /tmp/biorag-approval-e2e-final.log: tests/E2E.

No hay que relanzar procesos terminados por no encontrar estos temporales en otra sesión. Usar resúmenes persistidos y comandos reproducibles; no inventar nuevos resultados.

## Pendiente antes de producción

Seguridad/delegación productiva, migración del grafo contextualizado y consumidores, corpus independiente de correcciones, resolución de intención/contexto, casos multivalor/revocación/bitemporalidad avanzada y doble verificación con copia actual autorizada. No hubo cambios a master/VERSION/core ni DB viva por este hito. Revisar diff aislado del directorio experimental, preservando el worktree preexistente.
