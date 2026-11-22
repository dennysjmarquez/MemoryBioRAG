# Prototipo: perspectiva temporal explícita en MCP

## Estado y alcance

Prototipo sobre la rama de la sesión `arena/6459e2d0-memorybiorag`, alineada previamente con master `908aa2a`. Arena no permite crear/cambiar de rama durante esta sesión. No se modificó master, no se abrió DB viva ni se ejecutó activación local. No se publica nueva versión estable.

Para ensayar en una **copia** con el servidor MCP real:

```sh
BIORAG_TEMPORAL_PROTOTYPE=1 BIORAG_PATH=/ruta/a/copia.db python mcp_server.py
```

**Default actualizado por solicitud del propietario: `BIORAG_TEMPORAL_PROTOTYPE=1`.** Sin variable también queda activo. `BIORAG_TEMPORAL_PROTOTYPE=0` desactiva el contrato nuevo y recupera el contrato previo v36.2. Con valor 1, `recordar` y `buscar` rechazan cualquier llamada sin `contexto_vigencia.mode` antes de abrir el cerebro, devolviendo `status=error`, `codigo`, `mensaje`, `parametro_faltante` y `busqueda_ejecutada=false` (además de los alias anteriores). Es validación obligatoria en ejecución; no es todavía una ruptura general del esquema de clientes estables. Los clientes deben enviar el modo; llamadas antiguas sin él se rechazan deliberadamente. Un proceso que conserve una variable explícita en 0 seguirá desactivado hasta cambiar su configuración y reiniciarlo. No se infiere intención por palabras clave, paráfrasis ni nombres de nodo.

## Contrato

| mode | Cuándo usarlo | Campos adicionales |
|---|---|---|
| `relevancia` | Conceptos/recuerdos pertinentes sin afirmar actualidad. No sirve de escape si el usuario pidió vigencia. | Ninguno. |
| `recientes` | Recuerdos registrados más recientemente. No implica hechos más recientes ni vigentes. | `time_basis: "registro"` |
| `antiguos` | Recuerdos registrados más antiguamente. | `time_basis: "registro"` |
| `vigente` | Estado aplicable en una fecha y contexto exactos, con evidencia aprobada. | `entity`, `attribute`, `scope`, `at` |
| `historico` | Antecedentes sustituidos a esa fecha dentro del mismo contexto. No significa necesariamente el primer recuerdo guardado. | Los mismos. |
| `ambos` | Priorizar vigentes y antecedentes, con grupos explícitos. | Los mismos. |

Ejemplos de argumentos:

```json
{"query":"qué es un grafo","sustantivos_clave":"grafo","contexto_vigencia":{"mode":"relevancia"}}
```

```json
{"query":"decisiones del proyecto","sustantivos_clave":"decisiones,proyecto","contexto_vigencia":{"mode":"recientes","time_basis":"registro"}}
```

Para `vigente`, no copiar valores de ejemplo arbitrarios: usar entidad/atributo/alcance **exactos del ledger aprobado** y el instante UNIX consultado. No dar a `at` una fecha fija y llamarla «hoy». No inventar campos para satisfacer el contrato. Los ejemplos previos con `intent=current` corresponden al contrato estable sin el interruptor experimental; no mezclarlos con `mode`.

`creado_en` es fecha de registro, con posibles fechas heredadas de migraciones; no acredita fecha del hecho. Fechas ausentes, cero o no finitas quedan al final y se informan en `unknown_dates`. Una fecha heredada válida tampoco es prueba de antigüedad real. La fecha del hecho no está implementada en recientes/antiguos: se rechaza otra base temporal.

## Resultados e incertidumbre

`competencia_contextual` incluye modo, estado, cobertura, grupos y evidencia de decisión cuando existe. Todos los modos preservan candidatos y scores; cambia la prioridad, NO se borran ni se ocultan históricos.

- `VIGENCIA_NO_RESUELTA`: falta evidencia, hay conflicto o el candidato respaldado está fuera del pool. La respuesta incluye advertencia: resultados exploratorios; **no afirmar que Top-1 sea vigente**.
- `HISTORIA_NO_RESUELTA`: no se encontró antecedente respaldado dentro del pool.
- `groups` distingue `vigente`, `historico`, `conflict` y `sin_evidencia`; un candidato desconocido no se convierte en histórico automáticamente.
- `coverage=retrieved_pool_only`: se reordena el pool recuperado, posiblemente ya limitado/paginado. No se promete el recuerdo más antiguo/reciente de toda la DB. Los filtros existentes por días/fechas siguen acotando la recuperación.
- `relevancia` preserva el ranking anterior, incluidos matches de nombres. No promete resolver preguntas de vigencia. Arreglar vigencia NO requiere renombrar ni dormir recuerdos.

## Correcciones: nuevo default solicitado

`BIORAG_CORRECTIONS` pasa a default **1**, también en `.env.example`. Una configuración existente que diga `0` sigue desactivando el puerto: el default no sobrescribe `.env.local` ni configuración MCP.

**Se eliminan `BIORAG_CORRECTIONS_PRINCIPAL` y `BIORAG_CORRECTIONS_GRANTS`:** no se leen ni limitan temas. El cliente MCP stdio local confiable puede corregir cualquier contexto soportado. `local-mcp` es una etiqueta automática de procedencia en recibos, NO identidad autenticada. No exponer ese proceso a clientes no confiables. SSE continúa denegado. Mantener `BIORAG_CORRECTIONS=0` si se quiere deshabilitar expresamente. No se eliminan contexto semántico, revisión ni confirmación explícita. El servicio ya no recibe principal/grants; consumidores Python directos deben migrar a `Corrections(path)`; las firmas de las tools de corrección no cambian. Recibos previos siguen siendo idempotentes sin reconfigurar la identidad antigua; propuestas pendientes requieren revisar de nuevo bajo la política nueva.

Este cambio de default y eliminación de permisos sustituye la descripción «apagado por defecto» de los informes históricos v36.2, que documentan lo que se probó entonces. La autorización por contexto no se elimina.

## Cerrar el problema de datos en la instalación real

Debe hacerlo el propietario/agente **en su entorno**, con backup y revisión, no Arena sobre el snapshot:

1. Verificar el proceso MCP/código realmente cargado y reiniciarlo tras cambiar configuración.
2. Inspeccionar contenido, procedencia, valores y fechas de los recuerdos implicados. No asumir que una nota es vigente por su nombre.
3. Identificar el contexto semántico correcto; no hay permisos por tema que configurar. No copiar `biorag/version/dev` si los hechos pertenecen a otro contexto.
4. Registrar propuesta mediante `registrar_correccion`; si falta ledger, antecedente y fecha explícitos para bootstrap revisable.
5. Revisar evidencia y digest. Confirmar solo si refleja la sustitución autorizada. Pueden existir varios antecedentes: una única arista no acredita todas las relaciones posibles.
6. Repetir **la pregunta natural original** con `mode=vigente` y contexto aprobado, no buscando el ID canónico. Verificar estado `resolved`, candidato, scores/candidatos conservados e histórico mediante sus modos.

No se deben inventar sustituciones, promover cualquier fecha reciente, dormir nodos ni renombrarlos para pasar el caso. Una DB sin evidencia seguirá respondiendo que no puede establecer vigencia; es una limitación explícita, no una activación incompleta que deba disimularse.

## Validación

- Pruebas del contrato: `tests/test_temporal_perspective_prototype.py`.
- E2E servidor MCP real: `scripts/experimentos/competencia_contextual/e2e_perspective_mcp.py`. Usa copia de snapshot suministrado, mensaje/fechas sintéticos y aprobación mediante tools; no siembra claims por SQL. Ver resultados acompañantes.
- Suite global de copia publicable más prototipo: **924 passed, 18 skipped, 2 subtests passed**, 226.55 s, tras eliminar los permisos temáticos. Las 47 pruebas dedicadas de correcciones/perspectiva pasan (4.13 s); incluyen tres dominios, WAL/DELETE y repetición de recibos con identidad antigua. Contrato estable por defecto; pruebas dedicadas activan el contrato nuevo. No significa que clientes antiguos pasen sin migración con el interruptor activo: sus llamadas sin mode deben rechazarse por diseño.
- QA oficial: **921 casos, gate 0 (aprobado)**. R@5=100%, R@1=93.03%, MRR=0.9566, FP=0/40. Métricas globales y categorías exactamente iguales a la corrida core anterior. Dos registros diagnósticos de fallo se conservan. No se recogió una traza nueva para afirmar igualdad exacta de scores/orden caso por caso. Evalúa motor, no 921 llamadas al MCP ni eficacia de 921 correcciones. Casos, evaluador y umbrales intactos; `resultados_qa_perspectiva.json` conserva hashes y comparación. El motor de búsqueda no cambió durante la corrida; la retirada final de permisos se verificó además con suite global y E2E MCP nuevos.

## Separación respecto a `language.py`

`core/contextual/language.py` es el parser conservador del mensaje de **registro de correcciones**, invocado por `Corrections.register`. No procesa consultas de recuperación ni selecciona modos. Su gramática española limitada es una restricción del registro textual, no una inferencia temporal automática. `perspective.validate` solo comprueba la decisión explícita del agente; `perspective.apply` la ejecuta. No se implementó detección de palabras como «último» o «antes» para decidir un modo.

El cambio de default es una ruptura intencional de interfaz MCP. Los resultados anteriores de suite global corresponden al default anterior; no se deben atribuir sin repetirlos al nuevo default. El benchmark de motor no comprueba que clientes antiguos envíen el modo.

## Registro estructurado de correcciones: contrato nuevo

`registrar_correccion` ya no interpreta el mensaje. Exige `contexto` con entity,
attribute y scope exactos y `valor_anterior`, `valor_nuevo` explícitos. Conserva
mensaje original en cualquier idioma y nodos/fechas. No normaliza ni traduce IDs
por su cuenta: el agente debe reutilizar identificadores existentes. La secuencia
registrar/revisar/confirmar permanece, con digest e idempotencia. La tool llama
`Corrections.register_structured`; el método Python `register` queda como legado
compatible y es el único que importa el parser español al invocarse explícitamente.
No hay detección de modo por idioma en búsqueda. Los ejemplos anteriores de
registro textual describen el contrato inicial, no la firma MCP actual.
