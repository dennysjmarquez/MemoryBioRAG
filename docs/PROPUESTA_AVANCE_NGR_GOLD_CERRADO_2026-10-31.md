# Propuesta para avanzar hacia N/G/R con gold cerrado — 2026-10-31

**Estado:** propuesta solamente. No autoriza preparar bases/fixtures, iniciar MCP, medir ni ejecutar QA completa. **W sigue pendiente.**

## 1. Alcance recomendado y gold adecuado

La medición v2 aprobada valida una sola consulta sintética y el camino de ejecución de `N0/N1/G1/G2/R`; no es la línea base real. No debe ampliarse a conclusiones de utilidad, ruido, cobertura de pistas ni rendimiento general: `relacionados_utiles` y `ruido_tonto` están vacíos/no adjudicados.

Para la próxima propuesta de medición N/G/R con alcance E1, el gold candidato debe ser el E1 completo congelado: **88 episodios/224 consultas** y sus etiquetas, inicialmente anclado al SHA-256 `d91e9ee1437f2695b2278ff06cf2ad202e5d124c500c0f8dc22a6865e0e2497e`. Esto es una recomendación para revisión, no confirmación de que hoy esté adjudicado o listo. Si Dennys elige otro gold o pide corregir etiquetas, crear una versión/ledger lateral nuevo y conservar intactos el archivo base, la v2 sintética y sus resultados. No usar bases originales.

La preflight semántica del gold debe terminar **antes de exponer resultados de cualquier brazo**:

1. Revisar todas las consultas, objetivos, pistas útiles, asociaciones útiles/serendípicas, ruido, abstenciones e idioma conforme a la rúbrica. La etiqueta vacía significa no adjudicada, no ausencia demostrada. Solo las categorías cerradas antes de buscar entran en sus métricas; el resto se excluye y se declara sin evaluar.
2. Adjudicar cada episodio con evidencia textual y juicio relativo a su consulta. Ningún enlace se declara ruido por tipo, peso, coincidencia de nombre o por no ser el objetivo literal. La conectividad es evidencia de grafo, no etiqueta semántica automática.
3. Si el gold conserva afirmaciones de ruta o pista, verificarlas contra el grafo completo que se espera construir. No reclamar distancia, unicidad o ruta que el grafo contradiga. Revisar enlaces automáticos completos; no borrarlos ni filtrarlos para forzar el gold.
4. Registrar decisiones, episodios modificados/excluidos, responsables, fecha y diferencias frente a la versión anterior en un ledger lateral. Obtener revisión y **cierre de gold antes de la primera consulta de medición**. Fijar hash de versión y hash de cierre. Si el cierre no se puede acreditar antes de observar resultados, detenerse.
5. Después del cierre, no cambiar el gold a la luz de resultados. Toda modificación posterior exige nueva versión, motivo, nuevo cierre y una campaña separada; no mezclar métricas pre/post revisión.

## 2. Diseño de preparación aislada

Solo tras autorización expresa para construir:

- Crear un `BIORAG_QA_TEMP_ROOT` nuevo, fuera del repo y de cualquier base original. Copiar dentro el gold cerrado y sus manifiestos. Las bases de plantilla empiezan vacías; nunca apuntar `BIORAG_PATH` a datos originales.
- Hacer preflight sin escrituras: integridad, nombres/keys MCP únicos, límites de gold, hash y términos. Registrar posibles `co_nombre` como riesgo, no como predicción de edge ni motivo para excluir conexiones.
- Construir **dos fixtures independientes desde cero**, cada una en su propia DB y sesión MCP stdio. Mismo gold, configuración/entorno/clock fijados y `construction_id` distinto. No clonar A para llamar B independiente.
- Guardar manifest, respuesta cruda/parseada, error, hashes antes/después, diff por fila/campo y corte completo del grafo después de cada llamada MCP. Conservar aristas directas en ambas direcciones, tipos, pesos, timestamps, latentes, estado activo/dormido, espejo CSV y diferencias.
- Comparar las dos construcciones antes de congelar. Requerir igualdad estructural en los campos acordados, dos ledgers completos e independientes y mismo hash de gold. Divulgar los hashes lógicos/DB que difieran por metadatos; `REPEATABLE_PAIR` no significa igualdad byte a byte.

### Presupuesto exacto previsto de llamadas MCP

Para el gold E1 candidato actualmente anclado (88 episodios, 340 nodos, 56 aristas Gold y 224 consultas), una llamada MCP significa una invocación de herramienta; no cuenta arranque/cierre de proceso, snapshots locales, SQLite ni comparación local:

| Fase | Cálculo | Llamadas MCP previstas |
|---|---:|---:|
| Preparación, construcción A | 340 `recordar` de preflight + 340 `aprender` + 88 `consolidar` + 56 `vincular` | **824** |
| Preparación, construcción B independiente | Mismo desglose | **824** |
| **Preparación total (dos construcciones)** | 680 `recordar` + 680 `aprender` + 176 `consolidar` + 112 `vincular` | **1.648** |
| Medición N0 | 224 consultas × 1 `recordar` | **224** |
| Medición N1 | 224 consultas × 1 `recordar` | **224** |
| Medición G1 | 224 consultas × 1 `recordar` | **224** |
| Medición G2 | 224 consultas × 1 `recordar` | **224** |
| Medición R | 224 consultas × 1 `recordar` | **224** |
| **Medición total (cinco brazos)** | 5 × 224 | **1.120** |
| **Total planeado** | Preparación + medición, sin reintentos | **2.768** |

Es un techo de plan para el gold E1 **sin cambios** y la lista completa N0/N1/G1/G2/R. Si la revisión semántica cambia nodos, aristas, episodios o consultas, recalcular y someter el presupuesto exacto junto al nuevo hash y a la aprobación; no comenzar con esta cifra desactualizada. No hay retries automáticos ni reanudación: cualquier fallo detiene el proceso, conserva evidencia y deja el gasto real en o por debajo del techo de su fase.
- Tras aprobar explícitamente los hashes, preparar una plantilla seleccionada (por convención, A) y hacer copias limpias por consulta×brazo. Las llamadas no comparten estado mutable. El run guarda su propia copia, y ni el original temporal ni ninguna base original reciben escrituras de los brazos.
- Eliminar del plan —no del grafo— cualquier condición que dependa de etiquetas aún vacías. Las cuatro vías/canales se conservan separados y se informan por canal.

## 3. Brazos propuestos y qué responden

| Brazo | Configuración | Qué observa | Aislamiento/precaución |
|---|---|---|---|
| **N0** | Normal, `deep=False`, `forzar_rafaga=False`, `context_window=0`, `asociados=False`. | Recuperación principal del objetivo en `resultados`. | Sin expansión ni ráfaga; copia nueva por consulta. |
| **N1** | Igual a N0, `asociados=True`. | Efecto de serializar asociaciones en los canales de salida. | No atribuir una diferencia del canal lateral a cambio de ranking sin comparar `resultados` en el par N0/N1. |
| **G1** | N1 con `context_window=1`; `deep=False`, ráfaga apagada. | Contexto BFS activo a profundidad 1. | No es un brazo de despertar. |
| **G2** | N1 con `context_window=2`; `deep=False`, ráfaga apagada. | Contexto BFS activo a profundidad 2. | No inferir ruta realmente recorrida a partir de BFS offline; sin traza MCP suficiente, marcar atribución como no disponible. |
| **R** | `forzar_rafaga=True`, términos fijados de antemano por el gold, `deep=False`, `context_window=0`. | Vía de ráfaga forzada y sus posibles efectos de filas/canales. | Antes de cada consulta comprobar todos los nodos activos; proceso de dormir/despertar detenido en la copia. Si algo está dormido, estado cambia, aparece mutación no permitida o falla una guarda, abortar. |
| **W** | No incluido. | Ninguno en esta propuesta. | Sigue pendiente; no simularlo con SQL, consolidación u otro brazo. |

El conjunto exacto de brazos del manifiesto deberá corresponder a los brazos realmente autorizados; nunca incluir W por defecto. La ejecución mide solo este gold, esta fixture y estas consultas; es descriptiva, sin umbrales de aprobación automáticos.

## 4. Hashes y autorización previos a iniciar brazos

Antes de correr una consulta, volver a calcular y comparar con los artefactos presentes:

- hash de gold cerrado, manifiesto/ledger y hash del cierre;
- hashes físicos y lógicos de A y B, junto con `construction_id` y manifiestos de construcción;
- hash del informe de grafo recalculado y hash del reporte de repetibilidad;
- commit/código del arnés, configuración de ejecución, arms exactos y versión del esquema;
- hash del candidato de congelación y del manifiesto de aprobación.

Después de que Dennys revise gold, grafo, mutaciones previstas, pareo y hashes concretos, registrar una aprobación **separada**. Para el modo original, usar el manifiesto externo de congelación descrito en el protocolo; para `synthetic_smoke`, el formato `synthetic_freeze_approval_v1` correspondiente. Debe contener `APROBADO`, `aprobado_por=Dennys`, gold/fixture, manifiesto, grafo, cierre y repetibilidad exactos, lista cerrada de brazos y `wake_W_included=false`. No reutilizar la aprobación del smoke v2 para otro gold, fixture, código o informe. El manifiesto candidato no equivale a aprobación y el arnés debe rechazar cualquier discrepancia.

## 5. Whitelist de mutaciones y evidencia

Antes de medir, cotejar la whitelist por fila/campo contra el commit exacto del motor; no ampliar la whitelist después de ver un resultado.

- **N/G:** permitir únicamente las escrituras de telemetría que se hayan confirmado como esperadas. Rechazar cambio de arista, tipo, peso o estado de recuerdo fuera de esa regla.
- **R:** permitir solo las inserciones/refuerzos documentados por el arnés: extremos dentro del gold, par no preexistente para insert, campos/tipo/peso/timestamps aprobados, sin DELETE, más la telemetría permitida. Separar inserción nueva, refuerzo de arista existente y no-op; conservar orientación original y espejo sin asumir que el tipo codifica procedencia inmutable.
- Por cada llamada: `before.json`, `call.json`, `after.json`, `diff.json`, stdout/stderr, llamada MCP cruda/parseada, error/exception, hashes de tablas, grafo, estados, latencia/bytes y DB aislada. Evidencia incremental persistente incluso al invalidar. Reportar hash de cada artefacto y conservar las copias temporales usadas.
- Limitar presupuesto de llamadas antes de autorizar: calcularlo a partir de consultas cerradas × brazos × repeticiones/copies, y reservar número máximo de reintentos. No hacer retries silenciosos ni reanudar un brazo inválido bajo la misma aprobación.

## 6. Condiciones de parada

**Antes de cualquier brazo:** detenerse si falta un archivo, ruta sale del temporal, hash no coincide, aprobación/cierre no cubre los hashes actuales, gold no está cerrado, existe etiqueta necesaria no adjudicada, informe de grafo/repetibilidad no se puede recalcular, un build no es independiente, integridad falla, nombre colisiona, o el presupuesto/configuración/commit difiere.

**Durante preparación/medición:** detener nuevas llamadas y conservar el run si ocurre cualquier startup/transport/tool/teardown error, respuesta MCP de error, excepción de snapshot/serialización/persistencia, evidencia incompleta, diff inesperado, cambio de edge/estado fuera de whitelist, fallo de integridad, mutación de fixture original, R encuentra nodo inactivo, o se alcanza el límite de llamada/reintento. Registrar qué brazo/consulta se completó y cuáles no; no borrar, reparar ni filtrar la asociación en el sitio. La corrida parcial se marca inválida y requiere diagnóstico y nueva autorización/hashes para reintentar.

Al final, verificar que las fixtures base siguen con los hashes iniciales, y ejecutar una auditoría final de diffs antes de publicar el informe. Un `exit_code=0` sin `invalidaciones=[]`, auditorías por fila/campo válidas y hashes de salida conservados no basta para considerar válida la campaña.

## 7. Qué falta probar de R

La medición v2 ya ejecutó R en una consulta sintética con todos los nodos activos, pero no cambió aristas; es un smoke de llamada/canal, no prueba completa de la semántica de ráfaga. Las pruebas unitarias aisladas existentes simulan un refuerzo permitido y un cambio de tipo prohibido, pero no sustituyen integración real. Antes de basar conclusiones en R, proponer y autorizar pruebas aisladas de:

1. Inserción nueva elegible, ambos extremos del gold, `sdm_dirty`, espejo y whitelist de columnas.
2. Refuerzo de arista existente, dirección/orientación inversa, incremento/techo de peso, `ultimo_uso`, conservación de tipo y `creado_en`.
3. Par ya presente/no candidato y repetición idempotente: confirmar no duplicación y clasificar como refuerzo/no-op según la regla real.
4. Todos los nodos activos antes de **cada** R; nodo dormido o transición inesperada debe detener antes de una llamada posterior.
5. No-op y errores después de una mutación parcial, verificando rollback o conservación exacta del diff y ninguna llamada siguiente.
6. Qué cubre R forzado frente a fallback natural: son condiciones distintas; R no demuestra que el fallback se active ni cómo se comporta en datos generales.

No incluir ni mezclar despertar. W sigue pendiente.

## 8. Qué falta probar del manejo de fallos

Las pruebas unitarias actuales cubren clasificación de respuesta MCP de error, fallo de transporte, mutación inesperada con diff persistido, persistencia fuera de un temporal efímero y fallos mock de startup/llamada/teardown. La medición sintética aprobada completó sin errores; no fue una prueba de fallo real. Antes de una campaña de alcance completo, añadir y aprobar pruebas aisladas para:

- proceso MCP real que no inicia, termina inesperadamente, agota timeout o no cierra; conservar código, stdout/stderr y respuesta parcial;
- fallo de `snapshot`/inspector antes o después de una llamada, fallo de escritura/hash/serialización y disco lleno: el run debe invalidarse y el evidence root parcial permanecer legible;
- error MCP después de haber producido cambios, respuesta ausente/malformada, excepción en cada fase y teardown tras respuesta exitosa;
- mutación inesperada en N/G y R; demostrar que no se dispara otra consulta/arm ni retry automático tras primera invalidación;
- fallos de validación de gold/approval/hashes antes de iniciar MCP: cero llamadas, cero run roots de medición y mensaje de gate identificable;
- rechazo de evidence incompleta, duplicada/copiada o hashes cambiados, y correspondencia entre exit code, `valida=false`, motivo y artefactos persistidos.

Estas pruebas son pruebas del arnés en copias/mocks, no QA completa ni licencia para usar bases originales.

## Recomendación de secuencia

1. Revisar y cerrar el gold E1/candidato semántico sin resultados.
2. Auditar whitelist, presupuesto de llamadas, casos R y fallos aislados.
3. Pedir autorización separada para preparar dos fixtures nuevas e independientes de ese gold (si el gold difiere de v2, las v2 no se reciclan como plantilla).
4. Revisar grafo/estados/repetibilidad, publicar hashes y candidate manifest.
5. Solo con aprobación real de esos hashes, correr N/G/R en copias limpias; detener ante la primera invalidación y publicar evidencia parcial íntegra.

**Nada de esta secuencia se ejecutó al redactar la propuesta.** No se prepararon bases, no se iniciaron MCP, no se midieron brazos y no se ejecutó QA completa. W sigue pendiente.
