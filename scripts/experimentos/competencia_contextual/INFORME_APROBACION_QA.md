# Aprobación MCP, búsqueda y QA — cierre del hito experimental

**Estado: hito experimental completado y medido; listo para auditoría. No es release v36.2.** Ambas variantes QA con recursos completos terminaron y pasaron sus gates. No se declara integración ni cierre productivo.

## 1. Implementación realizada

- `approval.py`: revisión con digest; confirmación bajo BEGIN IMMEDIATE, permiso exacto inyectado por el host, revalidación del antecedente, nodos y evidencia; idempotencia; recibo persistente.
- `lab_mcp.py`: servidor FastMCP stdio separado, cuatro herramientas: registrar/revisar/confirmar corrección y buscar_contextual. No modifica el registro del MCP productivo.
- `search_adapter.py`: conecta selector a buscar_por_frase en el proceso experimental conservando tuplas, scores y candidatos. Sin resolver contextual no altera el orden. Resolver explícito, no router por palabras.
- `e2e_approval_mcp.py`: cliente MCP real contra subproceso del servidor; motor BioRAG real sobre backup temporal, no un mock ni solo llamada Python al handler.
- `run_qa_pair.py`, `qa_selector_worker.py` y `comparar_qa_selector.py`: ejecución/comparación de evaluar_qa.py oficial, sin editar casos ni umbrales. Comparador bloquea ante trazas incompletas o cambios inesperados y no exporta texto privado.

Contrato previo en APROBACION_SPEC.md; operación y límites en MCP_LAB.md.

## 2. Atomicidad y conservación del grafo

La confirmación inserta claim, revisión, recibo y arista contextual en un solo commit SQLite multiarchivo: ledger.db en disco + graph.db adjunta, ambas bajo rollback journal DELETE y synchronous=FULL. No se usan los métodos Ledger.add/supersede con commits internos dentro de esa unidad de trabajo. No es una garantía de transacción distribuida ni soporta WAL/remoto.

Hallazgo del snapshot: sinapsis tiene PK(origen,destino) y una asociación manual ya existe para el par del caso. Por eso se crea sinapsis_sustitucion en la copia del grafo con `tipo='sustituye'`, contexto, IDs de claims, fecha y fuente. **No se cambia ni elimina la asociación manual.** El core no consume esta nueva tabla para BFS: la decisión experimental proviene del ledger mediante el adaptador. Esta separación evita convertir una corrección local en inhibición global.

Seguridad: el host local confiable establece LAB_PRINCIPAL y contextos LAB_GRANTS. El mensaje y los parámetros de las tools no conceden identidad/permisos. Es delegación explícita de un proceso stdio de laboratorio, no autenticación humana remota ni consentimiento fuera de banda. No desplegar como servicio productivo con estas garantías parciales.

## 3. E2E real ejecutado

Snapshot suministrado: SHA256 `07a77c801eaa56750627e1c831de91a65e6448da25e4803b86d3ae4e2446c55e`.

1. Backup SQLite a directorio temporal LAB_ONLY. Antecedente confirmado cargado como fixture; no se afirma extracción autónoma desde corpus completo.
2. Cliente MCP initialize/list_tools.
3. buscar_contextual con intención/alcance explícitos y ledger anterior: histórico seleccionado por la afirmación previa.
4. registrar_correccion con mensaje sintético: “Actualizo: la versión del proyecto en DEV pasa de 32.4 a 36.1.” → pending_confirmation.
5. revisar_correccion → digest de propuesta, contexto y contenido de nodos.
6. confirmar_correccion con digest inválido → error MCP, sin aprobación.
7. confirmar_correccion con digest revisado → approved_projected; repetición del mismo request devuelve idéntico recibo.
8. buscar_contextual → canónico Top-1; histórico sigue disponible.

Evidencia en resultados_e2e_aprobacion.json:

- Canónico: version_actual_biorag, score base 0.8.
- Histórico preservado: version_actual_biorag_v32_4_20261007.
- Lista de cinco candidatos conservada, scores idénticos dentro de la búsqueda antes/después del selector.
- Fila histórica completa idéntica en el control de este ensayo; contenido y asociación manual intactos.
- Arista tipada persistida: canónico → histórico, sustituye, alcance dev.
- Hash de fuente intacto. No DB ni contenido privado nuevo en Git.

“Antes” aquí ya incluye el ledger de fixture anterior: NO es correcto atribuir ese orden al motor base solo. El motor puede reforzar recuerdos al consultar; la aprobación en sí no actualiza largo_plazo.

## 4. QA oficial emparejada

### Piloto terminado, recursos reducidos

Ambos brazos ejecutaron los 921 casos y gates con exit=0. En esta copia faltaba db/hebbian_clusters.json, por lo que el módulo SDM podía entrar en fallback. Se conserva como piloto, no como validación final con todos los recursos del checkout.

| Métrica | Baseline | Adaptador | Diferencia |
|---|---:|---:|---:|
| R@5 | 100.00% | 100.00% | 0.00 pp |
| R@1 | 93.03% | 93.03% | 0.00 pp |
| MRR | 0.9566 | 0.9566 | 0 |
| FP | 0/40 | 0/40 | 0 |

921/921 salidas alineadas idénticas en orden y scores; categorías y todos los campos globales iguales. Evidencia: resultados_qa_piloto.json. El manifest marca hebbian_asset_manifested=false para que no se confunda con la corrida completa.

### Repetición con recursos completos

Nueva copia/corrida independiente, sin cambiar el piloto en marcha. Se añadió el recurso Hebbiano del checkout y se fijaron OPENBLAS_NUM_THREADS/OMP_NUM_THREADS/MKL_NUM_THREADS=1 en ambos brazos. Los casos, script, gates y snapshot se conservan; baseline y variante siempre comparten configuración.

**Ambas variantes terminaron, gate OK (exit=0), comparador exit=0.** Resultado definitivo para este ensayo en resultados_qa_aprobacion.json:

| Métrica | Baseline | Adaptador | Diferencia |
|---|---:|---:|---:|
| R@5 | 100.00% | 100.00% | 0.00 pp |
| R@1 | 93.03% | 93.03% | 0.00 pp |
| MRR | 0.9566 | 0.9566 | 0 |
| FP | 0/40 (0%) | 0/40 (0%) | 0 |

**921/921 salidas idénticas** en orden/membresía/scores; 0 casos cambiados, 0 estados inesperados del adaptador. Categorías y todos los campos globales iguales. La fuente QA conserva hash. El snapshot oficial no trae campeón neuronal entrenado; no se entrenó uno ni se apagó la neurona para favorecer el ensayo. La neurona no actuó en ninguna variante. El E2E usa otro snapshot suministrado; no se debe confundir ambos corpus ni inferir que comparten estado neuronal.

SHA256 del backup del snapshot oficial usado como fuente QA: aa7ac66f9fe76d194eeaf578b4e14ba965e94eab40247dace35854df094aa25c.
SHA256 del archivo original del repositorio: 104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796. Coincide con su blob Git original. Los archivos original/backup difieren solo en seis bytes de cabecera SQLite (offsets 27,42,43,95,98,99), no en páginas de datos: backup no exige igualdad binaria con el original. Una comprobación inicial que comparó ambos hashes directamente se corrigió; cada fuente se verifica contra su propia referencia. Ver resultados_integridad.json.
SHA256 recurso Hebbiano: 7b49d729d354ce08e9479efdcf581f5fc9b23f780bdd587b3e99979cd7d1a57b.

Los hashes del script evaluador, casos y ambas trazas se incluyen en el resumen sanitizado. Las trazas completas tienen hashes distintos porque registran estados baseline/passthrough distintos; sus salidas de búsqueda se compararon campo por campo, no por igualdad del archivo completo.

El evaluador procesa 921 casos, pero calcula recall/MRR global sobre 875 consultas positivas no ambiguas; hay 40 negativos y 6 casos de consultas contradictorias (3 queries distintas) tratados aparte. La resolución de 3 etiquetas obsoletas pertenece al evaluador existente, no a este cambio. Hay registros de fallos ambiguos fuera del recall global; no se ocultan diciendo “921 respuestas correctas”.

Alcance esencial: ledger vacío y puerto de contexto ausente en QA. Esto valida **no interferencia del cableado**, NO eficacia de aprobaciones en 921 contextos anotados. La eficacia de corrección se prueba en el E2E dirigido. No se suministran relaciones oro para hacer mejorar las métricas.

## 5. Tests y disciplina de aislamiento

### Laboratorio

59 tests unittest PASS: los 23 originales intactos, observación/adaptador y nuevos controles de aprobación. Prueban excepciones en las dos fases de escritura, muerte real antes de commit y recuperación de ambos archivos, muerte después de commit con pérdida de acuse, repetición y concurrencia de requests, digest obsoleto, contenido de nodo cambiado, autorización por contexto, presupuesto visible, retorno a un valor anterior con claims acíclicos y no interferencia con otro alcance. Crecimiento: 10.000 afirmaciones ajenas dejan digest y decisión intactos (tolerancia cero). Revisión limitada a 4096 claims y 1 MiB serializado; error visible, no truncado.

### Suite global del proyecto

`pytest tests/ -q` en copia aislada del código efectivo: **879 passed, 18 skipped, 2 subtests passed, 0 failed**, exit=0. Las 18 pruebas omitidas requieren una DB viva en el momento de importación, no proporcionada por seguridad. No equivale a haber ejecutado esas 18 integraciones contra datos vivos. Resumen sanitizado en resultados_suite_global.json.

Incidencias corregidas del harness: primera corrida tuvo 3 fallos, dos por el recurso Hebbiano omitido y otro por forzar DMN off en una prueba que necesita activar síntesis. Sin esa variable quedaban 2; al incluir el recurso, los tres casos pasan y la repetición global completa queda verde. **No se editaron tests/core ni se relajó una aserción para conseguirlo.** No atribuir esos fallos iniciales al motor ni borrarlos de la historia del ensayo.

## 6. Lo que falta para afirmar v36.2 lista

- Resolver integración y migración del grafo contextualizado sin sustituir asociaciones útiles, y evaluar consumidores/backup/concurrencia de producción.
- Definir autenticación/delegación y revisión humana productivas; el host de laboratorio no reemplaza esa política.
- Corpus independiente con correcciones aprobadas y casos tardíos/multivalor/conflictos; el parser actual reconoce solo dos familias completas.
- Resolución contextual/intención con abstención y evaluación; hoy son entradas explícitas.
- Doble verificación con una copia autorizada actual de la DB viva; el snapshot suministrado no acredita el estado actual.
- Revisar omisiones de suite global y gates de publicación con el usuario.

No se cambió VERSION, core, master ni DB viva. Este hito entrega implementación experimental auditable, no una promesa de cero regresiones universales ni una release publicada.
