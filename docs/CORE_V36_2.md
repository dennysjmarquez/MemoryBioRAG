# v36.2 — Correcciones contextuales integradas (candidata)

El código está en `core/contextual` y el servidor MCP real registra las herramientas. No usa imports desde scripts de laboratorio. Esta versión NO convierte el sistema en un ser vivo ni comprende cualquier corrección en lenguaje libre. La publicación/tag/merge no son automáticos.

## Activación segura

Por defecto `BIORAG_CORRECTIONS=0`: herramientas enumerables pero escrituras denegadas antes de abrir/migrar la DB. El propietario del proceso stdio debe delegar contextos exactos en su configuración MCP/env:

```json
{
  "BIORAG_CORRECTIONS": "1",
  "BIORAG_CORRECTIONS_PRINCIPAL": "propietario-local",
  "BIORAG_CORRECTIONS_GRANTS": "[[\"servicio alfa\",\"puerto\",\"producción\"]]"
}
```

Esto delega aprobación al cliente/agente que puede llamar a ese proceso; **no obliga a que una persona haga clic ni verifica identidad remota**. Un agente con acceso delegado puede aprobar. No conceder esos permisos a clientes no confiables. `--sse` siempre deniega correcciones hasta diseñar autenticación remota; un digest NO es contraseña, firma ni autenticación. No guardar secretos en mensajes. Las variables del propietario no son parámetros de tools.

Hacer backup antes de habilitar. Desde Arena solo se ensayan copias; no se abre la DB viva ni se cambia la configuración local del usuario.

## Flujo de uso

Guardar primero ambos recuerdos mediante las herramientas existentes. Después:

1. `registrar_correccion(id, mensaje, nodo_anterior, nodo_sucesor, observado_en, efectivo_desde, anterior_desde?)`.
2. `revisar_correccion(id)`: inspeccionar mensaje, offsets, valores, alcance, fechas, contenido de nodos, contexto previo, `bootstrap_predecessor` y digest.
3. Solo si la propuesta es correcta, `confirmar_correccion(id, digest, request_id)`.
4. Consultar con `recordar` o `buscar`, usando `contexto_vigencia` JSON explícito:

```json
{"entity":"servicio alfa","attribute":"puerto","scope":"producción","at":1790000000,"intent":"current"}
```

Las fechas son segundos UNIX explícitos, no ejemplos para copiar sin verificar. `observado_en` y `efectivo_desde` no son equivalentes. `intent` admite current/historical/identifier/generic. Solo current promueve; los otros conservan orden, no generan por sí mismos una respuesta histórica. Campos exactos de entidad/atributo/alcance deben coincidir con los normalizados de la propuesta (minúsculas y espacios normalizados).

La búsqueda textual conserva la exigencia existente de `sustantivos_clave`. Ejemplo de mensaje soportado: `Corrijo: el puerto del servicio alfa en producción es 8443, no 8080.` También admite `Actualizo: ... pasa de ... a ...`. Fuera de la gramática conservadora se abstiene; no es un clasificador semántico general.

### Inicio sin fixtures

Si no hay afirmaciones previas en el ledger, la propuesta puede incluir `anterior_desde` explícito. No se confirma nada al registrar. La revisión marca **bootstrap_predecessor=true**: al confirmar, el propietario/agente estará aprobando tanto la interpretación del antecedente como la sustitución. Sin fecha previa explícita se bloquea. No se pretende que el sistema haya descubierto o verificado esos hechos por su cuenta.

Si hay afirmaciones previas, la confirmación exige un único antecedente aprobado y aplicable que coincida con valor/nodo/contexto; conflictos o antecedentes ambiguos bloquean. No tratar atributos multivalorados como si fueran monovalorados.

## Persistencia y atomicidad

Tablas aditivas `ctx_claims`, `ctx_revisions`, `ctx_proposals`, `ctx_approvals`, `ctx_synapses` en la MISMA DB BioRAG. `ctx_synapses.tipo='sustituye'` conserva IDs de claims y alcance; la proyección se une al ledger para entidad/atributo/tiempo/procedencia. No reemplaza la tabla sinapsis, que solo admite un tipo por par y puede contener asociaciones manuales que deben sobrevivir.

Una conexión propia por operación, BEGIN IMMEDIATE, revalidación de digest/contexto/nodos/permisos y commit de claims+revisión+arista+recibo. Compatible con WAL y rollback sin forzar journal_mode ni checkpoint de la DB. Si hay fallo antes del commit, se revierte todo. Si se pierde el acuse después del commit, el mismo request devuelve el recibo persistido. Otro contenido con el mismo ID es error. Una misma propuesta no se aprueba dos veces.

La propuesta original es auditabilidad de aplicación, NO almacenamiento criptográficamente inmutable ante un administrador. Los originales y los datos derivados se distinguen; un recibo acredita que se aprobó una operación, no que sus valores sean verdad universal o sigan vigentes para siempre.

## Búsqueda

Sin `contexto_vigencia` no se añade resolución contextual al camino previo. Con él, el selector opera sobre candidatos del MCP real sin borrar vecinos ni cambiar sus campos o scores. La respuesta añade `competencia_contextual` con resolved/unknown/conflict/retrieval_gap/passthrough/fallback_error. No asumir que Top-1 es vigente cuando el estado no es resolved. Un candidato correcto fuera del pool requiere otra recuperación, no puede ser inventado.

La búsqueda no crea tablas ni confirma nada; si no hay ledger, unknown y orden intacto. La migración aditiva ocurre al abrir el servicio de correcciones explícitamente habilitado. BFS no usa las aristas de sustitución como asociaciones excitatorias; la prioridad contextual deriva del ledger. No se cambia el significado de pesos Hebbianos.

## Escala y límites

Índices por entidad/atributo/alcance/fecha; límite 4096 afirmaciones por contexto y revisión de 1 MiB con error explícito, sin truncado oculto. Añadir datos ajenos no debe cambiar digest ni decisión (tolerancia cero). No se promete O(1), invariancia automática del BM25 ni independencia de toda DB/datos. Las lecturas no verifican afirmaciones por repetición.

Faltan resolución de lenguaje abierto/intención implícita, revocación, multivalor, consultas bitemporales avanzadas y políticas de autoridad remota. No quedan implementadas por actualizar el número de versión.

## Validación y publicación

Contrato previo: `docs/investigacion/memoria_silicio/CONTRATO_CORE_V36_2.md`. Pruebas nuevas: `tests/test_contextual_corrections.py`, con WAL/rollback, bootstrap, crecimiento, permisos, concurrencia y recuperación tras muerte del proceso.

Los resultados del laboratorio en `scripts/experimentos/competencia_contextual/INFORME_APROBACION_QA.md` son antecedente; no confundirlos con resultados integrados. La validación completada de esta integración, incluyendo suite del patch publicable y E2E MCP real, está en [VALIDACION_CORE_V36_2.md](VALIDACION_CORE_V36_2.md). v36.2 permanece candidata operativa: no se declara release estable, Windows/macOS ejecutados ni DB viva actual verificada.
