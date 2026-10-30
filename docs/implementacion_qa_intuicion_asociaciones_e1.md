# Implementación propuesta de QA E1 — asociaciones

**Estado:** código preparado para auditoría; QA no ejecutada. Los umbrales siguen pendientes de aprobación de Dennys. No inicia E4/E5.

## Artefactos

- `scripts/casos_qa_intuicion_asociaciones_e1.jsonl`: gold sintético congelado en código fuente: 88 episodios, 48 positivos y 40 controles; 224 consultas lógicas (172 en español, 52 en inglés); 340 nodos y 56 aristas explícitas. Cada consulta declara `espera_abstencion`, `respuesta_gold` y `tipo_consulta`, incluso cuando no tiene objetivo. Cada positivo declara al menos dos recuerdos de apoyo, pistas útiles con evidencia literal/justificación y dos distractores separados. Las superficies repetidas tienen objetivos y pistas revisados por significado, fragmentos literales por concepto y justificaciones; el validador rechaza etiquetas incompletas, evidencia que no aparece en el recuerdo y grupos que mezclen respuesta y abstención.
- `scripts/evaluar_qa_intuicion_asociaciones_e1.py`: construcción y ejecución futura del protocolo; `resultados` y `contexto_expandido` se extraen solo del campo principal `concepto` de cada elemento; sus asociaciones anidadas permanecen en canales laterales. Incluye métricas por canal/idioma/estrato, rangos, latencia y bytes; sin umbrales de éxito ni mutaciones del motor/ranking.
- `scripts/qa_stdio_server_intuicion.py`: lanza las tools FastMCP existentes por stdio y exige `BIORAG_PATH` dentro de `BIORAG_QA_TEMP_ROOT`. No arranca el daemon global.
- `scripts/analizar_anotaciones_qa_e1.py`: calcula acuerdo y diferencias de dos lotes de anotación; no aplica umbral.

## Ejemplos de revisión semántica del gold

La evidencia literal se lee junto con la pregunta; no basta con compartir vocabulario ni con que el recuerdo aparezca en el mismo grupo. Cada objetivo y pista de consulta repetida tiene su fragmento y su justificación por concepto en el JSONL.

- **Objetivo — pedidos duplicados:** «¿Cómo evitar pedidos duplicados si el proveedor demora?» → `qa_pos_direct_01_objetivo`: «reutilizar la misma clave de idempotencia en cada reintento; el proveedor devuelve el resultado previo y no crea un pedido duplicado». Responde al mecanismo causal. Un recuerdo que recomendara únicamente reintentar no se aceptaría como objetivo.
- **Pista — pedidos duplicados:** `qa_pos_direct_01_apoyo_util`: «la retención de la clave idempotente [debe] cubrir todo el horizonte de reintentos». No sustituye la respuesta principal; añade la condición para que la deduplicación siga vigente durante los reintentos.
- **Abstención — color de interfaz:** «What color was selected for the queue interface?» → cero objetivos y cero pistas. Razón gold: «no memory in this fixture records a selected interface color; decorative notes do not state the requested value».

La misma revisión ajustó recuerdos objetivo para que respondan literalmente a la intención semántica: invalidar/versionar claves tras actualizar caché, preparar instantánea verificada y rollback para una migración, probar una restauración aislada para verificar backups y revocar/rotar un token expuesto. Las consultas repetidas enumeran únicamente conceptos revisados, con evidencia y razón; no se infiere validez por compartir la pregunta.

## Ruta efectiva de dos saltos

La fixture se construye exclusivamente en un temporal con llamadas MCP `recordar` (preflight), `aprender`, `consolidar` y `vincular`. El validador posterior lee solo esa fixture y construye el grafo efectivo a partir de sus filas `sinapsis`, incluidas conexiones automáticas y explícitas. Para cada episodio con ruta gold `objetivo → intermedio → pista`, calcula BFS y exige que el gold sea el único camino mínimo estructural de dos saltos; atajos, alternativas mínimas o ausencia de ruta detienen la corrida. Este camino **estructural del grafo** no se presenta como recorrido real de MCP.

La BFS de `sinapsis` valida únicamente la estructura del fixture; **no prueba qué recorrido ejecutó recordar**. La atribución `atribuible_2_saltos` exige además una traza explícita retornada por MCP en `trazabilidad.rutas_expansion`, con `desde`, `hasta`, `ruta` y `saltos`, que demuestre exactamente `objetivo → intermedio → pista`, y que concuerde con las aristas activas del fixture. La pista debe aparecer en `contexto_expandido` con `context_window=2` y el objetivo en `resultados`. Sin esa prueba del recorrido real se registra literalmente **«no atribuible»**; no se infiere la ruta de la presencia en contexto ni del shortest path calculado offline. El MCP actual no expone esa traza, así que el arnés será conservador y no atribuirá dos saltos en esa interfaz, sin modificar motor, ranking ni formato MCP. Las apariciones en `resultados`, `asociaciones_enriquecidas` o `asociaciones` se contabilizan separadamente y nunca prueban dos saltos.

## Control de orden y conteo

Cada condición usa una copia SQLite consistente de la misma plantilla temporal y un proceso MCP stdio independiente. El launcher congela `time.time()` en ese hijo y asigna un archivo DMN temporal distinto por DB; el hash seed y la neurona quedan fijados en el entorno. A/B/C1/C2 recorren 224 consultas en bloques por posición; D recorre las consultas agrupadas por episodio y mantiene principal → seguimiento → control; D-inv invierte solamente el orden de episodios y mantiene intacta cada cadena. La comparación D/D-inv se empareja por `query_id` y reporta cambios de canal, rango y atribución; las copias deben coincidir en hash de tablas antes de empezar.

Conteo previsto: **224×6 = 1.344 búsquedas** en A, B, C1, C2, D y D-inv. El gold tiene 340 nodos, 88 episodios y 56 enlaces explícitos: armar la fixture requiere 340 preflights `recordar` + 340 `aprender` + 88 `consolidar` (uno por episodio) + 56 `vincular` = **824 llamadas MCP**. Total previsto de ejecución completa: **2.168 llamadas MCP**. No hay reintentos automáticos; el reporte distingue intentos de búsqueda, respuestas recibidas y errores. Cualquier repetición manual se registra como otra réplica/corrida y suma su propio conteo. Los percentiles se calculan sincrónicamente; `union_canales` combina las cuatro salidas sin indexar una clave sintética inexistente. El archivo final pasa por `json.dumps(..., allow_nan=False)` antes de escribirse.

## Escrituras permitidas durante `recordar`

El arnés compara hashes de todas las tablas antes/después de cada brazo. Con `BIORAG_NO_LOG=0`, `BIORAG_AUTOGUARDADO_HEURISTICO=0` y estado DMN temporal, solo admite:

- `log_busquedas`: fila de telemetría por búsqueda completada y actualización de `params_json` por el wrapper MCP;
- `nodo_accesos_historial`: accesos a resultados principales, con la retención FIFO definida por el motor.

No se admiten cambios en recuerdos, sinapsis/grafo, puentes, pesos, estado o ranking, ni en otras tablas. Una diferencia no permitida falla la corrida como contaminada; no se corrige en sitio. Las consultas llevan `deep=False`, ráfaga no forzada y búfer/autoguardado inactivo.

## Dos anotadores

Al concluir una futura ejecución, el arnés prepara dos JSONL con los mismos candidatos, ordenados aleatoriamente de forma independiente, identificadores seudónimos y sin brazo, score, rango, canal ni gold. El crosswalk queda en un archivo `*_crosswalk_PRIVADO.json`, que no se comparte con revisores. Se necesitan dos revisores independientes competentes en español e inglés para los casos incluidos, la rúbrica congelada y la hoja con rating 0–3 (`0=irrelevante/engañoso`, `1=contexto relacionado no accionable`, `2=pista útil`, `3=hallazgo serendípico que amplía una acción válida`), etiqueta `respuesta_principal`/`pista_util`/`neutral`/`ruido_tonto`, evidencia y justificación. Anotan sin deliberar entre sí; luego `analizar_anotaciones_qa_e1.py` informa kappa ponderado, acuerdo y diferencias, sin umbral de corte ni decisión automática. Dennys debe confirmar quién adjudica desacuerdos y aprobar la rúbrica/umbrales antes de recopilar etiquetas.

## Guardas de ejecución

El script exige `--ejecutar`, `--salida` fuera del repositorio, `PYTHONHASHSEED=0` y `BIORAG_NEURONA=0`; por defecto no ejecuta. Cada servidor hijo vuelve a validar que la DB esté dentro del temporal. Solo se conserva el reporte solicitado; las bases temporales se eliminan al terminar.
