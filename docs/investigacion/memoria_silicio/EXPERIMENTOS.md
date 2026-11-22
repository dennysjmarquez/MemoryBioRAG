# Experimentos propuestos — preregistro, NO resultados

No alterar la corrida QA ya iniciada. Primero cerrar y auditar ese benchmark; cada ensayo siguiente tendrá inputs, hashes, semilla y configuración congelados antes de medir. El conjunto de calibración no podrá incluir las consultas de evaluación.

## E1 — Separar selección de presentación (inspiración TEM)

Cuatro brazos con iguales candidatos, textos y presupuesto de evidencia:

1. Orden original sin etiquetas.
2. Promoción contextual sin etiquetas.
3. Orden original con etiquetas aprobadas y procedencia.
4. Promoción contextual + las mismas etiquetas.

Sin cambiar generación, extractor ni modelo entre brazos. Preguntas actuales, históricas, antes/después, contexto paralelo, dato tardío y conflicto. Etiquetas salen del ledger, no del gold. No inyectar indicadores viejo/nuevo en los textos originales para facilitar el examen. Etiquetas derivadas son la intervención deliberada del brazo, no información escondida de entrenamiento.

Métricas: Latest@1, R@1/R@5/MRR de recuperación; exactitud factual/temporal de respuesta con juez especificado y revisión ciega de muestra; tasa de respuesta obsoleta; abstención correcta/incorrecta; contradicciones no señaladas; tokens de evidencia y costo de ingesta separados. No usar presencia de entidad como única medida: mencionar todas las versiones no debe contar como respuesta correcta.

Hipótesis: etiquetas pueden mejorar elección de respuesta sin cambiar recall; no esperamos que sustituyan rescate de candidatos ni detalles episódicos. Reportar negativos y comparación por familia, no solo promedio favorable.

## E2 — Aprobación y bitemporalidad

| Fixture | Pregunta / acción | Criterio esperado |
|---|---|---|
| Puerto A→B aprobado, prod | ¿Puerto aplicable ahora en prod? | B; A y vecinos conservados, A anotado sustituido solo allí |
| Mismo servicio, pruebas=A | ¿Puerto en pruebas? | A no inhibido por cambio en prod |
| Mudanza T1→T2→T3 | ¿Dónde vivía antes de T2? | T1 con fuente, no último por defecto |
| Se registra en abril un cambio válido solo en enero | ¿Qué aplica en marzo? | no imponer dato tardío como estado actual |
| Mismo caso, corte de conocimiento en febrero | ¿Qué sabía el sistema entonces? | excluir eventos registrados después del corte |
| Fuentes aprobadas incompatibles | ¿Qué aplica ahora? | conflicto explícito, sin ganador inventado, candidatos intactos |
| Propuesta sin aprobar o cita de tercero | aprobar implícitamente al consultar | prohibido; hipótesis visible, ningún cambio |
| Dos preferencias compatibles | nueva preferencia | no suponer monovalor ni sustituir automáticamente |
| Sucesor fuera del top-k | consulta actual | retrieval_gap; no promover al histórico como vigente |
| Lectura repetida 1.000 veces | misma consulta | no confirmación ni ascenso epistémico por exposición |
| Crash antes del commit | reiniciar | ningún medio evento aprobado |
| Crash después del commit antes de proyección | reiniciar | evento íntegro + outbox pendiente, recuperación idempotente |
| Dos aprobadores/dos requests concurrentes | competir sobre antecedente | serialización/revisión, nunca dos éxitos incompatibles silenciosos |
| Request repetido / mismo ID otro payload | reintento | mismo recibo / error, respectivamente |
| Revocación de sucesor | consultar | reevaluar sin resucitar automáticamente predecesor |

Criterio de aprobación de fixtures deterministas: 100% de invariantes de escritura/lectura, fuente intacta, ninguna autorización por contenido ni mentira de commit. Fallo bloquea integración.

## E3 — Crecimiento y recuperación asociativa (HippoRAG / A-Mem)

Comparar vecindarios 1×/10×/100× con idénticos datos pertinentes. Agregar contextos ajenos, duplicados de consultas ajenas, hubs y permutaciones de inserción en brazos separados. Tolerancia 0 para decisión contextual y membresía/scoring originales bajo selector/anotación; medir separado cualquier variación aguas arriba. Para un prototipo PPR definir presupuesto y subgrafo antes de código; no asumir invariancia por usar un algoritmo biológicamente inspirado.

Medir k/e/m, p50/p95, memoria, tamaño y amplificación de escritura, además de precisión. Límite excedido = señal visible. No prometer independencia total del tamaño ni O(1).

## E4 — Consolidación no destructiva (Human-Inspired / CH-HNN)

Sueño desactivado vs propuestas sin aprobar vs propuestas aprobadas mediante política explícita. No resumir sobre el original ni eliminar fuente. Semántica derivada reconstruible. Medir detalle histórico recuperable, drift de entidad, conflictos, precisión de enlaces y cambios de ranking. Si una neurona añade valor, separar su entrenamiento del test y darle piso/techo/guardianes/examen. No entrenar ANN/SNN nueva hasta tener una hipótesis que el selector no pueda resolver con sus entradas.

## Gate de integración

1. Suite QA oficial emparejada: mismos 921 casos, baseline/variante sobre copias idénticas; ningún caso existente pierde R@5, reportar también R@1/MRR/FP por caso y categoría. Gate absoluto y delta son evaluaciones distintas.
2. La variante con resolver ausente/ledger vacío prueba solo no interferencia del cableado. Para eficacia, ejecutar E1/E2 con metadatos verdaderamente anotados y aprobados, no sembrar relaciones usando la respuesta oro.
3. Suite global y doble verificación: snapshot oficial y copia actual autorizada. Un snapshot antiguo suministrado no reemplaza DB viva actual.
4. Fuentes privadas, trazas con contenido y DB fuera de Git. Publicar métricas y manifest sin secretos.
5. Informe con controles negativos, fallos y límites; revisión del usuario antes de integrar/publicar v36.2.
