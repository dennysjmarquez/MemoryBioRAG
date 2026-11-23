# Arquitectura propuesta — NO implementada ni aprobada para producción

Esta propuesta amplía, no describe como existente, el prototipo de scripts/experimentos/competencia_contextual. Fuentes y límites en FICHAS.md. Prioridad inmediata: QA emparejada y aprobación segura. No hay migraciones ni dependencia nueva en este documento.

## Principio: separar dimensiones

No usar una cadena única `rumor → hipótesis → confirmado → vigente`: mezcla certeza y tiempo. Un hecho confirmado puede ser histórico; una propuesta puede referirse al presente sin estar aprobada. “Confirmado” significa aprobado bajo una política concreta, NO verdad universal.

- **Epistémica:** proposed / approved / disputed / rejected, con evidencia y política.
- **Temporal:** applicable / superseded / expired / future / unknown, siempre respecto a contexto e instante.
- **Operacional:** committed / projection_pending / projected / failed.
- **Cardinalidad:** single / multi / unknown por atributo y contexto. Si no se sabe, no suponer sustitución.

## Puertos y capas

```text
Interacción autenticada / agente delegado
    → episodio original + extracción candidata con offsets
    → propuesta pendiente
    → revisión/aprobación con digest y revalidación
    → transacción: eventos + claim + revisión + outbox
    → proyecciones idempotentes: grafo / índices derivados

Consulta → recuperación híbrida existente → candidatos intactos
    → resolución contextual y temporal explícita o abstención
    → selector acotado → anotación de evidencia → respuesta
                              ↘ histórico/conflictos/pistas conservados
```

La PPMI-SVD actual es una representación local ya existente; no introducir otra base vectorial por moda. Índices, embeddings y resumen son proyecciones reconstruibles, nunca fuentes de aprobación. Si la proyección está retrasada, exponer ese estado, no fingir sincronía.

## Esquema conceptual

No ejecutar como SQL/migración. Nombres ilustrativos, sujetos a examen transaccional.

| Registro | Campos principales | Restricciones necesarias |
|---|---|---|
| episode | id, actor_id, session_id, transport_ref, raw_text_ref, content_hash, recorded_at | fuente exacta, permisos de lectura; hash no autentica por sí solo |
| memory_event | seq, id, request_id, kind, actor_id, policy_id, recorded_at, payload, previous_hash?, hash? | append-only por API; request_id único con payload idéntico; contra admin requiere controles externos |
| claim_version | id, entity_id, attribute, scope_id, value, cardinality, episode_id, evidence_span, valid_from, valid_until, event_seq | tiempo válido explícito/unknown; no fechas inventadas; claves y fuente válidas |
| claim_assessment | claim_id, event_seq, epistemic_status, evidence_refs, approver_id | estado derivado de eventos, no sobrescritura destructiva |
| revision | id, successor_claim, predecessor_claim, scope_id, valid_from, valid_until, approval_event | contexto idéntico; acíclico; misma autoridad requerida; no supersede multivalor implícito |
| proposal | id, extraction, source_episode, predecessor_fingerprint, expected_digest | propuesta no confirmada; revalidar bajo lock al aprobar |
| approval_receipt | request_id, proposal_id, digest, policy_id, actor_id, event_seq | idempotencia; no confiar en role declarado por texto |
| projection_outbox | id, event_seq, target, payload_hash, state, retries, last_error | commit junto a evento; entrega al menos una vez, efecto exactamente idempotente |
| projection_checkpoint | target, last_event_seq, version | permitir reconciliar/reconstruir y detectar lag |

### Bitemporalidad real

`valid_from/valid_until`: cuándo se aplica el hecho en el mundo. `recorded_at/event_seq`: cuándo el sistema conoció/aprobó cada declaración. Reconstruir el estado **tal como se sabía en K** por eventos hasta K y luego evaluar validez en T. Una proyección puede materializar system_from/system_until para eficiencia; las correcciones retroactivas no reescriben los eventos originales.

Una nueva declaración tardía puede describir un intervalo pasado sin sustituir el estado presente. Se debe dividir o coexistir intervalos de forma explícita y revisada. Nunca convertir orden de ingesta o versión numérica mayor en regla de verdad.

## Regla de aprobación / fallo

1. El usuario revisa evidencia y alcance; el transporte verifica identidad/delegación, no el contenido del mensaje.
2. Comenzar unidad de trabajo (p. ej. BEGIN IMMEDIATE en DB lateral única). Releer propuesta y contexto. Digest incluye los extremos, intervalos, evaluaciones y versión de política pertinentes.
3. Validar permiso vigente, request_id, extremos, cardinalidad, fechas, ciclos, conflictos y ausencia de cambios. Si cambió el contexto, stale_proposal y nueva revisión.
4. Insertar evento, claim, evaluación aprobada, revisión y outbox en UN commit. Los métodos Ledger actuales hacen commits propios: requieren refactor y tests; NO son ya esta unidad transaccional.
5. Consumir outbox a grafo/índice con clave estable por evento. Una arista de sustitución tipada nunca es una asociación simétrica ni cambia pesos Hebbianos globales.
6. Si falla una proyección: recibo approved_projection_pending; reintentar. Si falla antes de commit: no hay aprobación parcial. Una excepción no debe presentarse como éxito.
7. Rechazo/revocación: nuevo evento. Revocar un sucesor no reactiva automáticamente todos los anteriores. Evaluar evidencia restante y declarar unknown/conflict si corresponde.

No prometer atomicidad entre DB independientes, grafo y vector. Fuente de verdad transaccional + outbox/reconciliación es distinta de transacción distribuida. El selector puede usar ledger committed mientras se informa lag de las proyecciones; la recuperación puede sufrir gaps, que deben detectarse.

## Recuperación y presentación

- El puerto de intención devuelve alcance/tiempo con evidencia o unresolved; no una regla `si contiene hoy`.
- Recuperación híbrida encuentra pistas; selector usa evidencia aprobada pertinente, no trata score como probabilidad de verdad.
- Decisión sobre contexto completo indexado, no solo los candidatos que llegaron. Si falta el nodo aplicable, retrieval_gap, sin declarar vigente al anterior.
- Mantener todas las tuplas/candidatos/scores. Anotar cada evidencia: fuente, aprobación, validez, sustitución e incertidumbre. No imprimir `[vigente]` para un candidato sin respaldo ni propagar etiquetas anteriores fuera de su alcance.
- Histórico exige dos preguntas distintas: “¿qué se aplicaba en T con lo que sabemos ahora?” y “¿qué creíamos en K acerca de T?”. Passthrough histórico actual no responde automáticamente ninguna de ellas.
- Rescate fuera del pool: nueva búsqueda explícita y trazada, presupuesto y membresía comparados. No inventar un candidato.

## Crecimiento e invariancia

N total de registros; k afirmaciones/e revisiones del contexto; m candidatos; L texto. Índices `(entity,attribute,scope,valid_from)` y por eventos/fuente. Meta de selección O(log N+k+e+m), NO O(1). Anotación por lote para evitar m escaneos globales. Presupuestos superados producen señal visible, nunca truncamiento escondido.

Para mismo mensaje, consulta, contexto, instante, policy, evidencia y candidatos: agregar 10×/100× datos de contextos ajenos debe mantener decisión y anotaciones exactas (tolerancia cero). No prometemos invariancia de BM25 ni PPR global sin medir. También probar alias/hubs y orden de inserción; decidir de antemano qué cambios son pertinentes.

## Inspiración biológica delimitada

- Separación episódica/semántica: fuente rápida estable y abstracción lenta reconstruible.
- Competencia/inhibición: priorización contextual explicable, no borrado ni veto global.
- Sueño: genera propuestas, detecta cadenas y conflictos con procedencia; no se autoautoriza.
- Plasticidad: incorpora feedback aprobado; repetición de lectura no verifica.
- Homeostasis: evita dominación por frecuencia/conectividad; no poda historia por percentiles globales.

Las equivalencias anteriores son funcionales y deben medirse. No son afirmaciones sobre neuronas biológicas, consciencia o afecto.
