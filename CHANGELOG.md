# BioRAG Changelog

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