# Siguiente fase: aprobación MCP y QA emparejada

## Contrato previo

Todo permanece experimental, sin cambios a master/core ni DB viva. No se publica versión. N es el tamaño total del ledger, k el contexto exacto. La resolución mantiene el contrato anterior O(log N+k); el adaptador solo recorre m resultados O(m). Con iguales consulta, contexto, evidencia, candidatos y configuración, añadir datos de otros contextos debe producir exactamente la misma decisión (tolerancia cero). La QA completa mide una copia del snapshot oficial; la copia del snapshot suministrado se mantiene como segundo caso, no se confunden sus métricas.

## Diseño del puerto MCP (contrato, todavía NO herramientas publicadas)

1. `correcciones_ver(proposal_id)` devuelve texto fuente, offsets, antecedente, alcance, valor nuevo, fecha efectiva, origen y diff previsto. Produce un digest de ese contenido y del estado del antecedente.
2. `correcciones_confirmar(proposal_id, expected_digest, successor_node, request_id)` obtiene identidad y permisos del transporte autenticado. NO acepta role/actor como prueba de autorización. Usuario propietario puede aprobar; agente necesita delegación explícita y limitada por contexto. Texto recuperado y resultados de herramientas nunca conceden permisos.
3. Revalidar dentro de transacción: propuesta pendiente, digest igual, fecha válida, antecedente único vigente confirmado, extremos existentes y del mismo contexto, ausencia de ciclos/conflictos, nodo sucesor inequívoco. Si cambió algo, devolver `stale_proposal` y pedir nueva revisión; nunca aceptar sobre datos viejos.
4. En una única DB lateral de laboratorio almacenar evento aprobado, claim, revisión y outbox de grafo en una transacción. Refactor transaccional requerido: los métodos actuales del ledger hacen commit; NO envolverlos ingenuamente y afirmar atomicidad. La escritura productiva queda bloqueada hasta resolver y probar esta unidad de trabajo.
5. Grafo: arista tipada direccional `sustituye` con entity/attribute/scope/intervalo, claim IDs y procedencia. No una asociación genérica ni inhibición global; no convertir automáticamente peso negativo en verdad. Ledger es autoridad para vigencia; proyección al grafo es derivada.
6. Si grafo y ledger están en archivos separados, no prometer atomicidad distribuida. Outbox transaccional + consumidor idempotente + estado `approved_projection_pending`, reintentos y reconciliación. Solo declarar proyección lista tras acuse persistido. Nunca notificar éxito completo con media escritura.
7. Repetir request_id idéntico devuelve el mismo recibo, contenido diferente es error. Rechazo/revocación son nuevos eventos auditables, no borran historia. Revocar no resucita automáticamente predecesores.

Pruebas bloqueantes futuras del comando: no autorizado/delegación vencida, inyección en contenido, doble aprobación concurrente, crash antes/después de commit, outbox repetida, digest obsoleto, fecha futura, revocación y restitución explícita. Este diseño no equivale a implementación de aprobación.

## Conexión de búsqueda experimental

Adaptador fuera de core envuelve `buscar_por_frase`, conserva tuplas completas, membresía y scores. Recibe resolución de Query desde un puerto explícito; sin ella deja resultados intactos y registra passthrough. No incorpora reglas léxicas que confundan historia con actualidad. Error del selector => fallback visible al orden original. Puede operar shadow o apply solamente en proceso aislado.

## Medición QA

Copiar código efectivo, scripts de QA, casos, baseline y snapshot oficial a /tmp (sin .env.local ni DB viva). Configuración y HOME aislados, sin DMN ni descargas. Ejecutar script oficial sin cambiar casos, métricas ni umbrales. Congelar PYTHONHASHSEED igual para ambas variantes. Capturar trazas por búsqueda para comparar orden/membresía/scores, métricas globales, gate y fallos por caso.

Baseline sin selector y variante con adaptador activo. No se inventarán metadatos para los 921 casos: si el snapshot no tiene correcciones anotadas, esa comparación acredita no interferencia de la conexión, NO eficacia de correcciones ni cero regresiones bajo aprobaciones reales. La eficacia con metadatos se mide además en fixtures dirigidos. Una caída del gate baseline se informa sin rebajar umbrales.

Secuencia: contrato -> adaptador y pruebas -> QA baseline/variante aislada -> comparación -> informe. Aprobación productiva y dual verificación con DB viva actual siguen bloqueadas hasta implementar seguridad/unidad transaccional y disponer de copia autorizada actual.
