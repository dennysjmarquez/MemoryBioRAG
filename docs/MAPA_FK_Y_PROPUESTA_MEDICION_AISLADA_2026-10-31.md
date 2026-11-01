# Mapa sanitizado de violaciones FK y propuesta de medición aislada

**Estado:** documentación y propuesta solamente. No se repararon filas, no se borraron datos, no se modificó el motor, no se ejecutaron QA ni campañas. E1 sigue abierto; W sigue pendiente.

## 1. Hallazgo de integridad y límites

En la copia SQLite restaurada, `PRAGMA quick_check` devolvió `ok`; `PRAGMA foreign_key_check` informó 156 referencias sin fila padre coincidente, repartidas así:

| Relación hija → padre | Filas reportadas |
|---|---:|
| `concept_hub_bridges.hub_id` → `concept_hubs.hub_id` | 10 |
| `corto_plazo_dimensiones.concepto` → `corto_plazo.concepto` | 17 |
| `largo_plazo_dimensiones.concepto` → `largo_plazo.concepto` | 13 |
| `nodo_grupos_semanticos.concepto` → `largo_plazo.concepto` | 116 |
| **Total** | **156** |

El volcado SQL se importó con las comprobaciones FK desactivadas. La importación transaccional terminó y la comprobación física pasó, pero no existe una comprobación FK anterior a la exportación ni se dispone de la base fuente con sus sidecars WAL/SHM. Por ello, **no se atribuye la causa**: el importador pudo conservar las referencias, pero estas también pudieron estar ya en los datos exportados. Las cuentas anteriores describen la copia, no identifican recuerdos ni justifican eliminar ninguna asociación.

Los esquemas declaran `ON DELETE CASCADE` (`core/memory/schema.py`; hubs en `core/concept_hub.py`). La conexión principal activa `PRAGMA foreign_keys=ON` (`core/memory_store.py`), y la conexión DMN también lo activa (`core/dmn_engine.py`). Eso no sanea filas preexistentes al abrir la DB; las cascadas afectan operaciones posteriores realizadas con FK habilitadas.

## 2. Mapa de lectores, escritores y posibles consecuencias

Los apartados “comprobado” describen el código inspeccionado, no que se haya observado el efecto en rankings o recuerdos de la copia. Las consecuencias se mantienen como hipótesis hasta una comparación autorizada.

### A. `concept_hub_bridges.hub_id → concept_hubs.hub_id` — 10

- **Escritura/eliminación:** `core/concept_hub.py::agregar_bridges`; `eliminar_hub`; `cargar_hubs_iniciales`; la migración `migrar_tablas`. El padre se crea/actualiza en `crear_hub`. Herramientas expuestas en `core/mcp_server/concept_hub_tools.py`.
- **Lectura:** `listar_hubs`, `_indice_hubs`, `expandir_query_con_hub`, `_expandir_a_escala`, `_indice_bridges` y `_expandir_por_cobertura_idf`.
- **Comprobado:** las lecturas que parten de `concept_hubs` o construyen el mapa de hubs no incluyen un bridge cuyo `hub_id` no tenga padre. `_firma_hubs` sí cuenta todas las filas de bridges para la firma de caché.
- **Posible consecuencia:** esas filas podrían provocar invalidación/reconstrucción de caché sin aportar expansión semántica actual. Si se vuelve a crear el mismo ID de hub, sus bridges antiguos podrían entrar en el mapa; eso no se ha probado.

### B. `corto_plazo_dimensiones.concepto → corto_plazo.concepto` — 17

- **Escritura/eliminación:** `core/memory/ingest.py::percibir_corto_plazo` inserta las dimensiones del recuerdo corto; `consolidar_concepto` y `core/memory/consolidation.py::ciclo_sueno_consolidacion` propagan las asociaciones a largo plazo y eliminan las filas de corto plazo.
- **Lectura:** `core/neurona_asociativa.py::Juez._dims` consulta ambas tablas dimensionales por concepto.
- **Comprobado:** dentro del módulo standalone, esa lectura alimenta la señal de etiquetas que `Juez` considera al calcular un peso de nacimiento. La inspección estática no encontró llamadas del motor a `Juez`; por tanto no se atribuye a esta ruta efecto actual sobre búsqueda ni sobre conexiones del cerebro completo.
- **Posible consecuencia acotada:** si un concepto se evalúa directamente mediante `Juez` y comparte clave con una dimensión huérfana, esta podría entrar en su señal. No se ejecutó `Juez` sobre la copia ni se mide este efecto en la propuesta.

### C. `largo_plazo_dimensiones.concepto → largo_plazo.concepto` — 13

- **Escritura/eliminación:** propagación en `core/memory/ingest.py::consolidar_concepto` y `core/memory/consolidation.py::ciclo_sueno_consolidacion`; cambios de dimensión en `core/dmn_reflexion.py::_aplicar_veredicto_nodo`; actualización de dimensiones en `core/mcp_server/write.py::biorag_actualizar`; membresías emergentes en `core/auto_clustering.py::asignar_dimensiones_emergentes`.
- **Lectura:** `core/memory/search.py::buscar_por_frase` usa dimensiones para señales, candidatos de fallback y puntuación temática. También las consultan `core/tematica.py::{calcular_idf_dims, calcular_perfiles_presencia}`, `core/sinapsis.py::_dimensiones_comunes`, `core/similitud_conceptual.py::score_similitud_latente`, `core/sueno_vacios.py::_dim_comun`, `core/inferencia_transitiva.py::_obtener_pares_dimension_comun`, `core/sdm.py::indexar_nodo_sdm`, `core/memory/episodes.py` y otros módulos de contexto.
- **Comprobado:** algunos caminos de recuperación hacen `JOIN largo_plazo` y por ello no proponen el concepto huérfano como recuerdo. Otros cálculos agregados leen directamente la tabla puente, sin ese `JOIN`.
- **Importante para IDF:** `core/tematica.py::calcular_idf_dims` calcula `N` contando solo `largo_plazo.estado='activo'`, pero cuenta `largo_plazo_dimensiones` por dimensión **sin filtrar estado ni unir con `largo_plazo`**. Por tanto, el numerador de frecuencia incluye filas de conceptos huérfanos y también dimensiones de nodos válidos pero dormidos/no activos. El efecto no puede atribuirse solo a las 13 filas huérfanas: las filas de nodos dormidos también participan en el conteo. Si la frecuencia supera `N`, la fórmula `log(N / count)` puede ser negativa.
- **Posible consecuencia:** las frecuencias/IDF y perfiles temáticos pueden cambiar los scores comparativos cuando se calcula similitud temática. Además, `_obtener_pares_dimension_comun` no une con `largo_plazo`; una fila huérfana podría marcar un par como dimensionalmente relacionado si el mismo par aparece en una ruta sináptica candidata. No se midió si alguna de estas condiciones afecta resultados reales de la copia.

### D. `nodo_grupos_semanticos.concepto → largo_plazo.concepto` — 116

- **Escritura/eliminación:** `core/memory/consolidation.py::_clasificar_nodo_wordnet`, invocado desde `consolidar_concepto`, `ciclo_sueno_consolidacion` y `core/mcp_server/write.py::biorag_actualizar`.
- **Lectura:** clasificación de candidatos en `core/memory/search.py::buscar_por_frase` mediante `nodo_grupos_semanticos`.
- **Comprobado:** la consulta de búsqueda limita las filas de grupos a conceptos que ya están en su lista de candidatos recuperados. Un concepto sin fila padre no entra por sí mismo en esa lista.
- **Posible consecuencia:** si más adelante se crea un `largo_plazo.concepto` con la misma clave, sus etiquetas antiguas podrían influir en la similitud por grupos. No se probó este caso.

## 3. Propuesta de medición en copias — requiere aprobación antes de ejecutarse

**Objetivo:** estimar dónde y cuánto influyen filas huérfanas y filas asociadas a nodos dormidos, conservando todos los datos y sin decidir que una relación es inútil. Esto sería diagnóstico de sensibilidad, no prueba automática de causalidad ni autorización para corregir.

1. **Preparar una copia aislada autorizada y reproducible.** Registrar origen y hashes. Para una DB SQLite en WAL, crear snapshot consistente con la API de backup de SQLite o detener/quiescer escritores y preservar DB/WAL/SHM como conjunto. Si la fuente sigue siendo el volcado SQL, documentar que es una restauración lógica y que no permite verificar cambios WAL no incluidos en el volcado. No abrir ni escribir la fuente original.
2. **Fijar acceso de solo lectura y guardar evidencia privada.** Abrir la copia en `mode=ro`, comprobar `quick_check` y `foreign_key_check`, guardar un manifiesto sanitizado con hash, método y versiones. Ninguna reparación, `DELETE`, `UPDATE`, migración, entrenamiento o escritura sobre la copia medida.
3. **Desglosar, no descartar.** Mediante consultas `SELECT` solamente, contar para cada relación las referencias con padre ausente y, donde aplique, las filas con padre existente separadas por los valores reales de `estado` (activo, dormido u otros). En dimensiones, calcular por ID los tres componentes —activos válidos, no activos válidos y huérfanos— y el IDF que produciría cada componente. Mantener visible el valor actual, que incluye tanto no activos válidos como huérfanos.
4. **Comparar sensibilidad funcional sin mutar datos.** En una fase separada y previamente aprobada, congelar un conjunto acotado de consultas diagnósticas, código, parámetros y candidatos. Calcular en memoria las señales/ordenes actuales y las variantes de lectura que separan esos componentes, siempre desde la misma copia read-only y sin crear vistas/tablas persistentes. Registrar para cada caso cambios de score/orden y señales técnicas observadas; objetivos o pistas solo si existe anotación explícita y aprobada. La falta de etiqueta no cuenta como pérdida y un cambio de rango no se declara regresión sin objetivo validado. Incluir diferencias, no solo promedios. No mezclar estas consultas con E1 ni usar su gold para entrenar.
5. **No inferir inutilidad ni causalidad.** Reportar tanto asociaciones huérfanas como dimensiones válidas de nodos dormidos; una diferencia entre variantes solo localiza sensibilidad bajo esa lectura. No borrar ni reparar. Si aparece una corrección candidata, presentar evidencia, alcance y diff para aprobación previa.
6. **Puertas de autorización.** Antes de esta medición, Dennys aprueba el conjunto de consultas, el presupuesto y el manifiesto exactos. Hasta entonces este documento es solo propuesta: no iniciar consultas de medición, QA, MCP o agentes. E1 sigue separado y sin campaña; W continúa pendiente.

### 3.1 Alcance corregido y propuesta de verificación pequeña — NO ejecutar sin aprobación

**Corrección explícita:** `scripts/casos_qa_baseline_v1.jsonl` es un archivo de casos de QA, pero pasar sus 921 filas directamente por una búsqueda no reproduce por sí solo la QA original. Se retira el presupuesto anterior de 6.500 unidades y también la propuesta de 974 consultas a `Juez._dims`: no son una medición aprobada ni un protocolo válido para atribuir pérdidas.

La inspección estática de `scripts/evaluar_qa.py` muestra que su QA transforma la consulta mediante `_consulta_buscada` (y puede añadir `BIORAG_QA_RUIDO`), puede resolver etiquetas con normalización/fuzzy matching y aparta queries contradictorias; por caso establece el estado del esperado (`activo`, o `dormido` para esa categoría), elige profundidad `profundo` si `deep`, categoría `dormido` o `negativo`, y en otro caso `activos`; usa `limite=5` e `ignore_peso_sinaptico=True`, y restaura después `estado` y `peso_sinaptico`. La búsqueda profunda puede despertar resultados y escribir estado, peso y acceso (`core/memory/search.py`, rama `profundidad == 'profundo'`). Por tanto no se ejecutará `scripts/evaluar_qa.py`: modifica su copia y su protocolo no es el diagnóstico read-only que aquí se propone.

El archivo conserva 921 casos/IDs únicos y su SHA-256 es `c76a71465f7a9be647094d79f00ffcebd742b00a6c12fa4ae90cf2c3d0654f4c`. Esto identifica un **conjunto candidato**, no afirma que se esté reproduciendo la QA oficial ni que sus `concepto_esperado` sean gold revisado. No se ejecutó ninguna de sus consultas.

#### Verificación de fidelidad propuesta (muestra pequeña)

Muestra exacta, seleccionada solo por metadatos del JSONL, sin divulgar sus textos:

| ID de caso | Metadatos usados únicamente para selección | Profundidad del diagnóstico propuesto |
|---|---|---|
| `0001` | categoría `literal`, `deep=false`, tiene `concepto_esperado` | `activos` |
| `0492` | categoría `dormido`, `deep=true`, tiene `concepto_esperado` | `activos` |
| `0882` | categoría `negativo`, `deep=true`, sin `concepto_esperado` | `activos` |

La profundidad uniforme `activos` es deliberada: no se cambian estados para imitar el setup de QA y no se despiertan nodos. Se usa el `query` bruto del campo, sin ruido ni `_consulta_buscada`; categoría, `deep` y `notes` no se convierten en etiquetas. Esta muestra verifica fidelidad del **diagnóstico local definido abajo**, no replica ni puntúa la QA original.

**Cálculo de C0 y variantes:** cargar a una conexión SQLite `:memory:` independiente, mediante backup desde la copia privada de auditoría abierta en modo estrictamente read-only; esta es la restauración lógica del dump SQL descrita en §1, no la DB original con WAL/SHM. Desechar el clon al acabar cada llamada. Si el archivo fuente tiene `-wal` o `-shm`, o no puede abrirse sin riesgo de escritura/lectura incompleta, abortar y pedir una forma autorizada de snapshot; no abrir el motor sobre la fuente. Llamar al método existente `SQLiteMemoryBioRAG.buscar_por_frase` sin alterar código, usando el clon efímero. C0 no instala vistas: consulta todas las relaciones existentes. C1–C4 y C5 usan vistas **TEMP** que ocultan solo las filas definidas en la tabla de condiciones y leen las tablas originales mediante `main.*`; no hacen `DELETE`, `UPDATE`, `INSERT`, migraciones ni cambios persistentes. Las seis condiciones quedan así:

| Código | Cálculo de lectura |
|---|---|
| C0 | Sin filtro; relaciones actuales completas. |
| C1 | Vista TEMP de `concept_hub_bridges` que omite solo filas sin hub padre. |
| C2 | Vista TEMP de `largo_plazo_dimensiones` que omite huérfanas y conserva dimensiones con padre válido en cualquier estado. |
| C3 | Vista TEMP de dimensiones largo plazo que conserva solo filas cuyo padre está `estado='activo'`; contraste C2–C3 separa sensibilidad a válidos no activos de huérfanos. `N` de IDF no cambia: sigue contando nodos activos. |
| C4 | Vista TEMP de `nodo_grupos_semanticos` que omite solo filas sin nodo padre. |
| C5 | C1+C2+C4 simultáneamente, contraste combinado, no recomendación de limpieza. |

Para los tres casos se fija: página 1; límite 5; `profundidad='activos'`; `ignore_peso_sinaptico=True`; `categoria=None`; `preview_chars=1`; `context_window=0`; `historial_fallos=None`; `dimensiones_dict=None`; `dimensiones_ids=None`; `parafrasis_list=None`; `desde_ts=None`; `hasta_ts=None`; `modo_estricto=False`; `usar_inferencia=True`; `buscar_por_rol=None`; `ordenar_por='relevancia'`; `permitir_expansion_empate=False`; `expandir_episodio=False`; `analogia=False`; `sustantivos_clave_boost=None`; `convergencia_limite=None`. Entorno fijado sin cargar `.env.local`: `BIORAG_NEURONA=0`, `BIORAG_NEURONA_ASOCIATIVA=0`, `BIORAG_NO_LOG=1`, `BIORAG_DMN_SINTESIS_ACTIVA=0`, `BIORAG_EPISODIO_TEMPORAL=0`, `BIORAG_ANALOGIA_DETECTAR=0`, `BIORAG_MULTIHOP_EXPANSION=0` y `BIORAG_HUB_ENABLED=1` (para que C1 contraste una ruta habilitada). No se entrena ni se escribe log. Se captura en el manifiesto privado la configuración efectiva restante de `core/memory/constants.py` y demás flags de búsqueda, que debe ser idéntica en los 21 calls; no se carga configuración ambiental implícita.

**Comprobación de fidelidad y no escritura:** antes/después, cotejar SHA-256 y existencia/hash de sidecars del snapshot; `quick_check`; hash de esquema y de filas de tablas principales entre snapshot y clon; confirmar que C0 no tiene vistas TEMP y lee las relaciones `main`; para cada variante confirmar por `SELECT` que la vista TEMP produce exactamente la partición definida frente a `main`. En cada llamada, un authorizer de SQLite deniega DML/DDL sobre `main` y `temp` y un trazador registra las sentencias. Si `buscar_por_frase` intenta escribir, el callback registra la acción denegada; el arnés marca el proceso como inválido aunque el motor capture o silencie la excepción, termina ese proceso, descarta el clon, detiene toda la verificación y no reporta resultados parciales. Se vuelve a cotejar el hash de la fuente y las filas del clon; no se reintenta hasta presentar un método alternativo y obtener aprobación. Cualquier divergencia de snapshot, resolución de nombre inesperada o diferencia de datos también aborta. Repetir C0 en un clon fresco por caso debe reproducir los mismos conceptos y orden; scores se comparan solo si también resultan deterministas, sin forzar reloj ni alterar el motor. Ningún resultado de esta prueba se interpretará como cambio de calidad.

**Aislamiento de cachés:** cada una de las 21 llamadas se ejecutaría en un proceso Python nuevo, con una conexión `:memory:` privada (sin URI `cache=shared`) y una instancia nueva del motor; no se comparte proceso, conexión, instancia ni caché entre condiciones. Esto reinicia tanto las cachés por instancia (p. ej. perfiles/IDF y scores temáticos) como las globales de módulos (`concept_hub` `_INDICE_HUBS`/`_CACHE_BRIDGES`, `tematica._cache_ausencia` y cachés de similitud). Neurona de ranking apagada y proceso nuevo evitan reutilizar su estado; vistas TEMP se instalan solo en la conexión de esa condición. No se precalientan ni se limpian cachés manualmente: todas las condiciones miden arranque en frío, y las tres repeticiones C0 también arrancan en frío. Cualquier uso de caché persistente entre procesos se detecta en la inspección y detiene la comparación; tiempos no son resultado de esta prueba.

**Presupuesto propuesto para esta verificación, no para la medición completa:** 3 casos × 6 condiciones = 18 búsquedas locales, más 3 repeticiones C0 en procesos/clones frescos = **21 llamadas a `buscar_por_frase` como máximo**; 21 procesos y clones efímeros, hasta 21 vistas TEMP y cero escrituras permitidas en tablas `main`/`temp` durante cada búsqueda. 0 llamadas MCP, agente, servicio externo, entrenamiento o campaña E1. No hay presupuesto aprobado para ejecutar las 921 filas ni para una medición mayor; si la verificación pasa, se presentará otro protocolo y presupuesto antes de pedir autorización.

#### Objetivos y pistas: sin etiquetas inventadas

`concepto_esperado` solo se registra, cuando existe, como **etiqueta declarada por el archivo y no validada como gold**: se puede mostrar su presencia/rango exacto, sin resolverla por fuzzy matching y sin llamar a un cambio de rango “pérdida” o “ganancia”. Si falta, el caso se marca “sin objetivo anotado”; nunca como fallo. `notes` y `categoria` no se reinterpretan como objetivos ni pistas. Para esta muestra no hay campo estructurado `pistas`; se reporta únicamente el origen técnico que el buscador ya exponga (`last_origen_scores`, si está disponible), con ese nombre y no como pista semántica. Objetivos/pistas semánticos solo podrán evaluarse si el auditor entrega y aprueba anotaciones explícitas con su fuente; hasta entonces quedan no evaluados.

#### Límite del diagnóstico y estado

Esto sería un diagnóstico **local del método de búsqueda con neurona de ranking apagada** (`BIORAG_NEURONA=0`), no una evaluación MCP ni del agente ni del cerebro completo. `BIORAG_NEURONA_ASOCIATIVA=0` también queda fijada; además, la inspección estática de `core/neurona_asociativa.py` dice que `Juez` no está conectado al motor, por lo que se retira cualquier inferencia sobre su efecto real en búsqueda. Las asociaciones y los estados originales se preservan; una fila dormida no devuelta bajo profundidad `activos` no cuenta como pérdida. E1 sigue abierto y W pendiente. Esta verificación pequeña también requiere aprobación explícita antes de ejecutarse.

**Sanitización:** este documento contiene únicamente tablas, funciones, conteos agregados y razonamiento de código. No incluye recuerdos, valores de filas, IDs de registro, pesos neuronales, identificadores de Drive ni hashes privados.
