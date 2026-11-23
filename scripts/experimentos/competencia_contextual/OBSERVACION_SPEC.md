# Interacción de correcciones — contrato previo, fase observación

Hipótesis aislada: una gramática composicional limitada de corrección explícita puede extraer propuesta y fragmentos de evidencia sin declarar verdad ni modificar el ledger. No basta una palabra de actualidad. El objetivo aquí NO es comprensión abierta del español.

Reconocer inicialmente actos directos completos:
- `Corrijo: el/la ATRIBUTO de/del ENTIDAD en ALCANCE es NUEVO, no ANTERIOR.`
- `Actualizo: el/la ATRIBUTO de/del ENTIDAD en ALCANCE pasa de ANTERIOR a NUEVO.`

No hay vocabulario de dominios. Campos desconocidos, referencias implícitas, citas, instrucciones indirectas, preguntas y formas no cubiertas producen abstención visible. El contexto de la búsqueda siguiente sigue siendo explícito, no se introduce un router por palabras.

Cada interacción lleva id estable, actor, rol y timestamp explícitos suministrados por el transporte. Rol no es autenticación; el prototipo solo admite actos directos de usuario como propuestas, nunca como confirmación automática. Se conserva texto exacto y offsets; replay idempotente, mismo id con otro contenido es error. Límite de 4096 caracteres antes de analizar. No se descargan modelos ni se llama a servicios.

Se requiere una sola afirmación previa confirmada, activa y no sustituida que coincida exactamente con entidad/atributo/alcance/valor anterior normalizados superficialmente. Si faltan antecedentes o son ambiguos, no se inventan ni se elige por score. La fecha del mensaje es observación, no prueba de fecha efectiva: se exige `effective_at` separado para simular; si falta se registra la propuesta y se pide fecha, sin simulación.

Registro lateral nuevo, rechazando conexiones que contengan largo_plazo/claims. Ledger de afirmaciones siempre solo lectura en esta fase. La simulación ocurre en backup SQLite en RAM, bajo la condición explícita `si_se_confirma`; no aplica propuestas ni recalibra scores. No hay método de aprobación productivo.

## Criterios y escala definidos antes de ejecutar

- Igualdad exacta de bytes lógicos del ledger y candidatos antes/después de observar/repetir/simular.
- Afirmaciones sin confirmación automática; errores del parser no producen acciones de escritura sobre recuerdos.
- Copia del snapshot proporcionado; nunca DB viva. La demo es una interacción sintética controlada, no evidencia de extracción general.
- N total de afirmaciones, k vecindario exacto: índice existente O(log N+k), parser O(L) sobre L acotado; simulación backup O(N), SOLO laboratorio, NO apta para path productivo. Comparar decisión exactamente antes/después de 10.000 afirmaciones ajenas, mismos mensaje/candidatos/instantes. Repetir con eventos ajenos en registro no cambia extracción.
- Mantener los 23 tests previos sin editarlos. Sin cambios de core/ledger/selector ni de ranking productivo. QA 921 sigue siendo gate pendiente de integración, no se sustituye por fixtures.
