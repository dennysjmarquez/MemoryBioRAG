# BioRAG Changelog

## v21.0 (2026-07-23)

### Features & Architecture
- **Default Mode Network (DMN) & Motor de Curiosidad Espontánea (`core/dmn_engine.py`)**: Hilo autónomo en segundo plano (`DMNEngine`) para ideación espontánea (mind-wandering) en periodos de inactividad del usuario, 100% libre de dependencias nativas externas.
- **Interrupción de Latencia Cero (`threading.Event()`)**: Interrupción inmediata del hilo autónomo DMN al recibir actividad del usuario para garantizar 0% de latencia en la atención de consultas.
- **Muestreo Resonante Cortical (Spindles Replay)**: Selección de nodos ancla de alta valencia/peso y exploración latente a 2-3 saltos para sintetizar "Insights" autónomos.
- **Concurrencia Aislada Thread-Local**: Conexión SQLite aislada por hilo en modo WAL con `PRAGMA busy_timeout = 5000`.
- **Selección Natural de Hipótesis (Decaimiento LTD Pasivo)**: Insights autónomos generados con peso inicial $W=0.50$ y valencia protegida $V_s=0.85$, sujetos a decaimiento pasivo por sueño si no reciben atención futura.
- **Presupuesto de Energía & Período Refractario**: Límite de máximo 3 ideas por ciclo de reposo con 60s de enfriamiento.
- **Integración MCP & Neuro-Visor Backend**: Herramienta `biorag_estado_dmn` y endpoint HTTP `/api/corteza/dmn`.
- **Suite de Pruebas Biológicas**: Ampliada a **112/112 pruebas biológicas aprobadas con éxito (100%)**.

---

## v20.0 (2026-07-22)

### Features & Architecture
- **Inhibición Lateral GABA en Tiempo Real en Evocación (Edelman 1987)**: Atenuación dinámica ($\times 0.60$) de competidores semánticos secundarios cuando el nodo Top-1 domina ($\ge 0.80$).
- **Error de Predicción de Recompensa Dopaminérgica (Dopamina RPE - Schultz 1997) con Factor de Inercia Sináptica**: Modulación de peso vía `biorag_feedback` ($\Delta W = +0.15$ en éxitos, depresión ajustada por inercia histórica en fallos).
- **Marcadores Somáticos e Inmunidad Cortical por Valencia (Damasio 1994)**: Columna `valencia_somatica` (0.0 a 1.0) con inmunidad absoluta a decaimiento LTD y borrado para nodos con valencia $\ge 0.80$ o categorías axiomáticas (`Principle`, `Protocol`).
- **Escalado Sináptico Homeostático (Turrigiano 2008)**: Normalización multiplicativa ($\times 0.98$) durante el sueño cuando la energía activa promedio supera $0.70$.

---

## v18.2 (2026-07-20)

### Features & Robustness
- **Neuro-Visor Dashboard v2 — Página Salud (Graph Health Audit)**: Health Score (0-100), breakdown por severidad (crítico/advertencia/ok), auditoría completa de integridad referencial, aislamiento semántico, dimensiones inactivas, nodos huérfanos. Endpoints: `/health/summary`, `/health/audit`, `/health/cleanup`. Modal de confirmación con dry-run.
- **Neuro-Visor Dashboard v2 — Página Explorar (Node Inspection)**: Panel unificado con pestañas Identidad, Conexiones (sinapsis agrupadas por tipo con pesos), Contenido (edición inline), Latentes (sinapsis transitivas con score y ruta). Toolbar con acciones: Merge, Link, Delete, Sleep.
- **Toolbar Unificado + Modales de Gestión de Nodos**: MergeModal (combinar nodos preservando sinapsis), LinkModal (crear sinapsis manual con tipo/peso), DeleteConfirm (borrado en cascada con preview), SleepConfirm (consolidación ciclo).
- **CSS Design System — Migración a Radix Themes**: Tokens unificados (`--radius-*`, `--spacing-*`, `--color-*`, `--font-*`). 12+ componentes con CSS Modules consistentes. Eliminado `globals.css` legacy.
- **Edición Inline de Contenido**: NodeIdentityPanel permite editar contenido directamente con guardado inmediato vía API.
- **Prevención de Grupos Semánticos Duplicados**: Fix en node detail y ego-graph queries. Chips de sinapsis con mejor legibilidad.
- **Text Overflow Prevention + Reorder**: NodeIdentityPanel reordenado para mejor legibilidad.

### Database & Architecture
- **metricas_cognitivas Refactor (FK-based)**: Claves foráneas reales `largo_plazo_id` → `largo_plazo.id` y `categoria_dominante_id` → `categorias.id`. Eliminada columna `concepto` duplicada. Índices optimizados. Migración idempotente con validación de integridad.

### Tests & Calidad
- 95/95 tests ✓
- Latencia búsqueda: ~2.8ms
- RAM: ~20 MB

---

## v18.1 (2026-05-15)

### Features & Robustness
- **Prevención de Caminos Cíclicos en Inferencia Transitiva**: Implementación del rastreo del camino recorrido (`ruta`) en la CTE recursiva de SQLite para prevenir la acumulación de ciclos fantasma de 3 o más saltos (ej. A -> B -> C -> B).
- **Filtro de Compatibilidad de Tipos de Relación**: Restricción estricta de la propagación de sinapsis latentes para evitar la acumulación de ruido estadístico casual (`co_ocurrencia -> co_ocurrencia`). Ahora solo se extienden relaciones compatibles semánticamente (`co_semantica`, `co_nombre`) o a través de puentes de alta confianza (`manual`, `sinonimo_explicito`, `test`).
- **Alineamiento de Timezones en Consultas MCP**: Estandarización de `timezone.utc` en el parseo de filtros de fecha relativa (`desde`/`hasta`) en `mcp_server.py`, garantizando búsquedas e inferencias independientes de la zona horaria local del host.
- **Suite de Verificación de Inferencia**: Validación de los asserts del grafo en una base de datos en memoria para prevención de ciclos, bloqueo de ruido y propagación por puente de confianza.

---

## v18.0 (2026-07-12)

### Features & Robustness
- **Capa 13 de Fallback Simbólico (Capa 2.1)**: Integración de distancia de Levenshtein normalizada y WordNet bilingüe (ES + EN) con traducción opcional (`BIORAG_TRADUCCION_ACTIVA=1`).
- **Relajación de Tokens Cortos**: Soporte mejorado para acrónimos y versiones breves de longitud `>= 2` (como `"cv"`, `"v6"`, `"ia"`) en WordNet, mientras que el filtro trigram de SQLite (`PALABRA_COMPLETA`) ahora se aplica selectivamente solo a tokens `<= 4` caracteres para prevenir colisiones ruidosas sin afectar palabras largas.
- **Scoring Simbólico Integrado**: Los nuevos puntuadores `score_simbolico_concepto` y `score_simbolico_sinonimos` actúan como un boost (`max()`) sobre las señales del score híbrido.
- **Unificación de BM25**: Consolidación de la constante de normalización a `abs(val) / (abs(val) + 3.0)` en todas las rutas de búsqueda para garantizar la comparabilidad matemática de resultados.
- **Rebalanceo Equitativo de Pesos**: Corrección del exceso de pesos en la fórmula del score híbrido (reduciendo la suma de 1.05 a exactamente 1.0) mediante el rebalanceo de `concepto_ratio` a 0.175 y `sinonimos_ratio` a 0.125. Esto previno la distorsión por saturación del techo de score y elevó el Recall@1 al **78.02%** en la suite QA.
- **Optimización de Consultas FTS5 con `CROSS JOIN`**: Reestructuración de 8 consultas clave de búsqueda entre tablas virtuales FTS5 (`largo_plazo_fts`, `largo_plazo_fts_unicode`) y la tabla indexada `largo_plazo` utilizando `CROSS JOIN`. Esto fuerza al planificador de consultas de SQLite a resolver primero el `MATCH` de FTS5, logrando una reducción masiva de latencia de ~500ms a **<10ms** (~100x de aceleración) al evitar escaneos de tablas completas.
- **Suite de QA Fase 1 (Precisión Semántica)**: Transición de aserciones unitarias básicas a un dataset estático estandarizado (`casos_qa_baseline_v1.jsonl`) con **921 casos de prueba reales** que evalúan el motor de búsqueda en 8 categorías lingüísticas, logrando un **93.76% de Recall@5** y **87.63% de Recall@1** sin regresiones.
- **Suite de QA Fase 2 (Estrés, Robustez y Escala)**: Implementación de scripts de diagnóstico avanzados:
  - `fuzz_qa.py` (Fase 2A): Evalúa la resiliencia ante inyecciones de SQL, desbalanceos y cadenas corruptas (**33/33 casos aprobados**).
  - `concurrencia_qa.py` (Fase 2B): Valida el aislamiento multi-hilo en SQLite WAL y el transporte asíncrono HTTP SSE de MCP (**0 bloqueos o colisiones**).
  - `escala_qa.py` (Fase 2C): Benchmarking de latencia en volúmenes crecientes de datos de grafos sintéticos (hasta 50,000 nodos).
  - Telemetría pasiva (Fase 2D): Logging de búsquedas y retroalimentación interactiva con `biorag_marcar_resultado`.
- **Pruebas QA Adversarias**: Ampliación de la suite QA local a 534 casos, incluyendo 30 controles negativos adicionales para validar la robustez de tokens de 2 caracteres (manteniendo 0% de Falsos Positivos).
- **Centralización de Stopwords**: Creación de `core/stopwords.py` para unificar y aislar listas de stopwords en español, inglés y tokens de control, previniendo la contaminación lingüística en Levenshtein.

---

## v17.1 (2026-07-11)

### Features & Robustness
- **Auto-Clustering Robusto**: Implementación de una migración única (`migration_autoclustering_v1`) para limpiar dimensiones auto-generadas legacy inactivas.
- **Desambiguación Dinámica Jaccard**: Reutilización inteligente de nombres de dimensiones mediante el cálculo del solapamiento Jaccard contra miembros de clusters existentes (con umbral de coincidencia >= 0.5).
- **Saneamiento de Miembros Locales**: Eliminación automática de miembros obsoletos locales al reutilizar y renombrar una dimensión existente.
- **Purga Global Inactiva**: Eliminación definitiva de dimensiones auto-generadas inactivas que no tengan miembros asociados al final del ciclo de consolidación.
- **Similitud Conceptual Stateless**: Remoción del diccionario mutable global `_grafo_cache` en `core/similitud_conceptual.py` para garantizar la seguridad de hilos frente a accesos concurrentes de múltiples agentes.

---

## v17.0 (2026-07-10)

### Features
- **Oráculo de NotebookLM Mejorado**: Nueva herramienta `biorag_oraculo_preguntar` para realizar consultas cruzadas directas con el nombre obligatorio del agente. Redefinición de `oraculo_inicio` para tareas exclusivas de arranque.
- **Mensajería Broadcast**: Rastreo de lectura individual en el canal compartido por medio de la columna `leido_por` en la tabla `comunicaciones`.
- **Higiene de Mensajería**: Nueva herramienta `marcar_como_leido` para evitar el re-procesamiento de notificaciones de cartelera, y obligatoriedad del parámetro `origen` en las comunicaciones.
- **Configuración de Agentes**: Actualización de la documentación interna y directrices de persistencia/firma en BioRAG.

---

## v16.0 (2026-07-09)

### Features
- **Etiquetado de Roles Semánticos (SRL)**: Soporte para análisis de estructura relacional (Sujeto-Verbo-Objeto-Contexto). Almacenamiento persistente e indexación de roles en SQLite para búsquedas por roles relacionales.
- **Inferencia Transitiva en Grafos (Fuzzy Reasoning)**: Descubrimiento de relaciones conceptuales indirectas. Cálculo por caminos multi-hop con atenuación matemática (decay 0.7) y prevención de bucles infinitos usando CTE recursiva en SQLite.
- **Auto-Clustering de Dimensiones Emergentes**: Detección autónoma de comunidades temáticas mediante el algoritmo de Label Propagation (LPA) sobre el grafo de sinapsis. Creación e indexación de dimensiones dinámicas emergentes (`auto_`) asociadas a los nodos de forma nativa en Python.
- **Búsqueda por Rol y Boost de Confianza**: Parámetro `buscar_por_rol` y scoring híbrido mejorado mediante la adición de dimensiones autogeneradas multiplicadas por su confianza.

### Database Changes
- **`predicados` y `corto_plazo_predicados`**: Nuevas tablas para almacenar estructura de roles SRL.
- **`sinapsis_latentes`**: Tabla caché de sinapsis transitivas indirectas con índices por origen y destino.
- **`dimensiones_semanticas`**: Columnas añadidas: `auto_generada` (INTEGER), `confianza` (REAL) y `generado_en` (REAL).

### Tests
- **Tests 80-86**: Verificación completa del pipeline de inferencia transitiva, prevención de bucles, almacenamiento SRL, búsqueda por rol, auto-clustering LPA, coseno ponderado y regresión.

---

## v15.0 (2026-07-09)

### Features
- **Clasificación Simbólica WordNet**: Mapeo léxico-semántico de conceptos y sinónimos a las 45 categorías ontológicas de WordNet (lexnames).
- **nltk_data Local y Aislada**: Descarga e inicialización de WordNet en la ruta del proyecto `MemoryBioRAG_Data/nltk_data` para garantizar la autonomía y soporte 100% offline.
- **Score Híbrido de 9 Señales**: Incorporación del `grupo_score` como la 9ª señal de relevancia con un 10% de peso en la fórmula del score híbrido.
- **Cascaded Node Deletion**: Soporte de borrado en cascada (`ON DELETE CASCADE`) para remover automáticamente registros en la tabla puente `nodo_grupos_semanticos` cuando se elimina un concepto de largo plazo.

### Database Changes
- **`grupos_semanticos`**: Tabla de catálogo que indexa las categorías lexicográficas fijas de WordNet.
- **`nodo_grupos_semanticos`**: Tabla puente relacional que asocia conceptos con sus respectivos grupos semánticos, con restricciones de clave foránea en cascada.

---

## v14.0 (2026-07-08)

### Features
- **Auditoría Técnica Completa**: Mapeo de 25 técnicas y algoritmos biológicos frente a sus equivalentes de la industria (Elasticsearch, Lucene, ACT-R, etc.).
- **Optimización y Estabilidad**: Refactor del pipeline de búsqueda de 12 capas en cascada, auto-guardado en sesiones y ráfaga de reminiscencia integrada.

---

## v13.0 (2026-07-05)

### Features
- **Filtro temporal PRE-hoc**: `desde_ts`/`hasta_ts` como parámetros de `buscar_por_frase`. El filtro `creado_en` se aplica en SQL FTS5 durante la búsqueda, no post-hoc. Elimina desperdicio de cómputo en búsquedas con filtro de fecha.
- **Índices SQL `estado` y `creado_en`**: `idx_estado` y `idx_creado_en` en `largo_plazo`. Queries temporales y por estado usan índice en vez de full scan.

### Bug Fixes
- **`score_parafrasis_best` siempre 0.0**: Corregido (de verdad esta vez). Ahora calcula el mejor score desde `last_origen_scores` cuando el origen es "parafrasis".
- **Doble asignación `score_top`**: Eliminada línea duplicada en `_recordar_impl`.
- **LIKE concepto sin `temporal_params`**: La búsqueda LIKE en concepto (Capa 2) inyectaba `clause` con `?` temporales pero no pasaba los parámetros. Crasheaba con "Incorrect number of bindings" cuando se usaba filtro temporal.
- **`sql_unicode` sin `temporal_params`**: Fallback unicode61 prefix no pasaba parámetros temporales.
- **`sql` (expansión semántica) sin `temporal_params`**: Fallback de expansión semántica no pasaba parámetros temporales.
- **Tests JSON parsing**: Tests 69h, 69i y 78 ahora manejan warnings prependidos al JSON.

### Architecture
- **Filtro temporal en 6 execute calls**: `temporal_params` inyectado en NEAR, FTS5 AND, FTS5 OR, unicode61, expansión semántica, y Snap reciente.
- **Safety net post-hoc**: Fallbacks no-FTS5 (LIKE, trigram, latente) mantienen filtro post-hoc como respaldo, ahora acelerado por `idx_creado_en`.

### Tests
- 78/78 tests verdes

---

## v12.0 (2026-07-04)

### Features
- **`creado_en` en largo_plazo**: Columna temporal que registra cuándo se consolidó cada concepto. Registros antiguos heredan `ultimo_acceso`. Permite filtros temporales en búsquedas.
- **Filtros temporales en `recordar`**: Nuevos parámetros `dias`, `desde`, `hasta` para buscar por rango de fechas. Ejemplo: `recordar(query='error', dias=5)` trae errores de los últimos 5 días.
- **Filtro por autor**: Nuevo parámetro `autor` en `recordar` para filtrar por nombre del agente en memoria compartida. Ejemplo: `recordar(query='lesson', autor='athena')`.
- **`query` opcional en `recordar`**: Si se omite `query`, `recordar` funciona como log cronológico puro — trae los N recuerdos más recientes ordenados por `creado_en DESC`. Combina con `dias`/`desde`/`hasta`/`autor`.
- **`desvincular(a, b)`**: Tool de plasticidad negativa interactiva. Elimina la sinapsis bidireccional entre dos conceptos cuando aparece un falso positivo. El cerebro mejora con cada corrección.
- **Ráfaga con dimensiones**: `buscar_por_rafaga` ahora acepta `dimensiones_ids` para scoring dimensional (25% del score híbrido). Coseno binario discreto.
- **Match exacto ×2.0**: Concepto normalizado == query normalizado recibe multiplicador de score ×2.0.
- **Degradación progresiva 3 niveles**: FTS5 → fuzzy → sinonimos cuando la query no tiene resultados.
- **Trazaabilidad completa**: Response JSON incluye scores por capa (`capa_literal`, `capa_parafrasis`, `capa_rafaga`), `match_exacto`, `total_candidatos_todos`, y `dimensiones_solicitadas`.
- **Directiva de Higiene de Falsos Positivos**: Cuando un agente detecta un falso positivo que llegó por sinapsis, ejecuta `desvincular` automáticamente para limpiar el grafo.

### Bug Fixes
- **Validación de dimensiones simétrica**: `_recordar_impl` ahora BLOQUEA búsqueda si recibe dimensiones inválidas (antes las ignoraba silenciosamente). Consistente con `_aprender_impl`.
- **`score_parafrasis_best` siempre 0.0**: Corregido — ahora trackea correctamente el mejor score de paráfrasis.
- **`NameError` en trazabilidad**: `self.last_todos` y `self.last_origen_scores` ahora se inicializan correctamente.
- **Ráfaga creaba sinapsis con tokens sueltos**: Ahora solo crea sinapsis si el token existe como concepto activo en `largo_plazo`. Previene hiperconectividad (ej: nodo "flor" con 59 sinapsis irrelevantes).
- **`vincular_por_sinonimos` buscaba en contenido**: Ahora solo busca en `concepto` y `sinonimos`, NO en `contenido`. Previene conexiones espurias por mención incidental.
- **`asociaciones` CSV desincronizado**: `_sincronizar_asociaciones()` se ejecuta en las 4 rutas de escritura (auto_vincular, vincular_por_sinonimos, desvincular, establecer_asociacion). CSV siempre refleja el estado real de sinapsis.
- **Filtros temporales post-truncado**: `dias/desde/hasta/autor` ahora se aplican ANTES del truncado, no después. Previene 0 resultados cuando los top-score no coinciden con el filtro temporal.
- **`parafrasis_list` desconectado en `buscar_por_frase`**: `fts_match` se calculaba pero nunca se usaba. Ahora se conecta directamente a las queries FTS5. Eliminado el hack de `mcp_server.py` que pasaba el string OR como texto natural.
- **`biorag_buscar` sin `dimensiones=None`**: Alias legado ahora acepta `dimensiones` como opcional, consistente con `biorag_recordar`.
- **`dim_dict` → `dimensiones_dict`**: Refactor de `_resolver_dimensiones` como helper compartido. Fix de `NameError` en `_aprender_impl`.
- **`dimensiones_invalidas` no definida**: Fix de `NameError` post-refactor. Variable restaurada después del helper.
- **Bug argumentos posicionales en scoring**: `_calcular_score_hibrido` recibía `contenido` en el parámetro `pesos_tokens`. Fix: usar keyword argument `contenido=contenido`. El scoring ahora ajusta correctamente por centralidad del token.
- **score_hibrido 0.0 en modo cronológico**: Ahora retorna `min(1.0, peso_sinaptico)` en vez de 0.0. Los resultados cronológicos muestran relevancia real.

### Architecture
- **Pipeline colapsado a 2 pasos**: PASO 1 obligatorio (paráfrasis+dimensiones), PASO 2 fallback (ráfaga). De 4 pasos a 2.
- **Fórmula score híbrido**: 55% BM25 + 25% peso_sináptico + 10% asociaciones + 10% dim_score.
- **Fórmula ráfaga con dimensiones**: 0.40 densidad + 0.25 peso + 0.10 asoc + 0.25 dim_score.
- **Paráfrasis optimizado**: 1 query FTS5 OR en vez de N queries separadas. Penalización ×0.95 en Python.
- **Homeostasis sináptica**: `sinapsis` y `largo_plazo.asociaciones` siempre sincronizados.
- **Reordenar fallbacks**: Typo (trigram) ahora corre ANTES de latente (Jaccard). Un typo match es más confiable que similitud latente. Benchmark: promedio 186ms → 58.8ms.
- **Helpers compartidos**: `_resolver_dimensiones()` y `_parsear_fechas()` extraídos para eliminar duplicación entre `_recordar_impl` y `_aprender_impl`.

### Data Cleanup
- 681 sinapsis espurias eliminadas (477 rafaga_rememb huérfanas + 204 sinonimo_explicito de arquitectura_busqueda_dimensional)
- 362 nodos activos sincronizados

### Tests
- Tests 73-78: ráfaga con dimensiones, score con dim_score, match exacto ×2.0, fallback dimensional, penalización paráfrasis ×0.95, trazabilidad.
- 78/78 tests verdes

### Coordinación Athena ↔ Artemis
- Canal simbiótico: diseño colaborativo de created_en, desvincular, higiene de falsos positivos
- Artemis detectó bug de `asociaciones` desincronizado y ejecutó fix completo
- Protocolo de memoria compartida documentado en docstring de `recordar`

---

## v11.1 (2026-06-29)

### Features
- **Etiquetado Emocional y Cognitivo (Opción B)**: Integración nativa de etiquetas sinápticas estandarizadas (`emocion_afecto`, `emocion_frustracion`, `emocion_preocupacion`, `emocion_satisfaccion`) a través de la columna existente `sinonimos`.
- **Diccionario Semántico Auto-Sustentable**: El motor siembra equivalencias bidireccionales en tiempo de inicio para que búsquedas por palabras cotidianas (ej. `"cariño"`, `"molesto"`) evoquen los recuerdos correspondientes.
- **Middleware de Autoguardado Emocional**: Adaptación del detector de la sesión para capturar expresiones de sentimientos y clasificar de forma autónoma con la etiqueta emocional correspondiente.

### Tests
- **Test 72**: Cobertura completa de evocado de recuerdos mediante tags emocionales y verificación del interceptor.
- 72/72 tests verdes exitosos.

---

## v11.0 (2026-06-29)

### Features
- **Indexación de concept_ids**: Indexación persistente de identificadores conceptuales únicos (`conceptos_ids`) basados en grupos conexos (Union-Find) de equivalencias semánticas.
- **Boosting de Relevancia Conceptual**: Aumento del factor de relevancia (1.2x) en el cálculo del score híbrido para coincidencias semánticas del mismo clúster conceptual.

### Tests
- **Test 71**: Verificación de la propagación del boost conceptual y validez del score tras consolidación.

---

## v10.2 (2026-06-28)

### Features
- **Parafrasis SIEMPRE**: cuando se pasa `parafrasis`, el sistema busca TODAS las variantes sin excepción. El objetivo es cognición, no eficiencia. El agente piensa siempre, el sistema busca siempre.
- **Umbral ELIMINADO**: `PARAFRASIS_THRESHOLD` removido. El threshold 0.5 era un gate de eficiencia que contradecía el objetivo de cognición del diseño.
- **Penalización conservada**: ×0.95 para variantes no exactas. El query original (i==0) mantiene factor 1.0.

### Fixes
- `parafrasis` de `List[str]` → `Optional[str]` (estilo `rafaga_palabras`)
- Validación obligatoria: si `parafrasis` se pasa y está vacío → error con mensaje explicativo
- Errores de sintaxis en edición del bloque paráfrasis corregidos

### Tests
- 70/70 tests verdes

### Principios aprendidos
- `principio_tres_capas_biorag`: tres capas para cerrar gap semántico sin embeddings (paráfrasis + rafaga + inferencia)
- `leccion_feature_b_inferencia_ruido`: inferencia automática produce ruido, usar como herramienta de sugerencia

---

## v10.1 (2026-06-28)

### Bug Fixes
- **ORDER BY corregido**: fórmula `(1.0 - 0.5 * peso)` → `(0.5 + 0.5 * peso)`. El bug penalizaba nodos con peso alto (0.99 → factor 0.505). Ahora prioriza correctamente (0.99 → factor 0.995).

### Features
- `poblar_sinonimos_desde_contenido()`: extrae keywords del contenido de nodos con peso ≥ 0.5, guarda en columna `sinónimos`. Triggers AFTER UPDATE reindexan FTS automáticamente. Idempotente.

### Tests
- Test 70: verifica ORDER BY con dos nodos mismo contenido (peso 0.95 vs 0.1) — pesado aparece primero. Verifica garbled query extrema no crashea.
- 70/70 tests verdes

---

## v10.0 (2026-06-27) — Anterior

- Recall semántico vía sinónimos y typo-tolerance
- Búsqueda fuzzy: resiliencia ante garbled queries
- Boost sináptico: nodos Profile priorizados en ORDER BY
- Auto-vincular: pasadas co_nombre y co_semantica