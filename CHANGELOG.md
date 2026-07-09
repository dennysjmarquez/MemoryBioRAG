# BioRAG Changelog

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