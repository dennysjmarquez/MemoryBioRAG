# Tareas — Spec 001: Sustantivos Clave

## T1: Baseline métricas + Función de normalización central
- **RF cubiertos**: RF-10, RF-11
- **Descripción**: Capturar baseline (pytest, evaluar_qa, test_abismo_lexico) y crear `normalizar_sustantivos_clave()` en `memory_store.py` reutilizando `_quitar_acentos` de `stemmer_es.py`.
- **Hecho cuando**:
  - [x] `pytest -q` muestra 168+ tests pasando, 0 fallidos — **Oficial run_qa_suite.sh: 168 passed/52.76s**; local con tests T1: 175 passed/64.68s (`/tmp/opencode/baseline_tests.txt`)
  - [x] `evaluar_qa.py` muestra Recall@5 ≥ 97.0% y FP = 0.0% — **Oficial run_qa_suite.sh: Recall@5=98.06%, Recall@1=90.97%, MRR=0.937, 17 fallos/875, FP=0.0% (40 válidos), GATE OK** (`scripts/qa_metrics.json` restaurado a corrida oficial 09:15)
  - [x] `test_abismo_lexico.py` muestra rescate 3/3 (100%) — **Oficial: 3/3 (100%)** (`/tmp/opencode/baseline_abismo_lexico.txt`)
  - [x] Concept Hub suite: 5/5 (100%) SIN Hub→CON Hub (metrica extra de la suite oficial)
  - [x] Función `normalizar_sustantivos_clave("Servidor, Backend,, TIMEOUT")` devuelve `"servidor,backend,timeout"`
  - [x] Función `normalizar_sustantivos_clave("conexión, Pingüino")` devuelve `"conexion,pinguino"` (tildes eliminadas, ñ preservada)
  - [x] Tests unitarios para la normalización pasan en verde (7/7 pasando)
- **Nota hallazgo**: `_quitar_acentos` (NFKD) DECOMPOne ñ (U+00F1 → n + U+0303), NO la preserva. Se compensó con marcador \x01 antes/después dentro de `normalizar_sustantivos_clave` (no se toca stemmer_es.py).
- [x] **Estado**: hecha

---

## T2: Schema DB + Triggers + Propagación en consolidación
- **RF cubiertos**: RF-4, RF-6, RF-7, RF-15
- **Descripción**: Agregar columna `sustantivos_clave TEXT DEFAULT ''` a `corto_plazo` y `largo_plazo`. Recrear FTS5 con 4 columnas. Actualizar 3 triggers (`_ai`, `_ad`, `_au`). Implementar propagación en `ciclo_sueno_consolidacion`: sobrescribe si corto_plazo tiene valor, preserva si está vacío.
- **Hecho cuando**:
  - [x] `sqlite3 memory_biorag.db ".schema corto_plazo"` muestra `sustantivos_clave TEXT DEFAULT ''`
  - [x] `sqlite3 memory_biorag.db ".schema largo_plazo"` muestra `sustantivos_clave TEXT DEFAULT ''`
  - [x] `largo_plazo_fts` tiene 4 columnas: concepto, contenido, sinonimos, sustantivos_clave
  - [x] Trigger `_au` (AFTER UPDATE) incluye `sustantivos_clave` en el INSERT a FTS5
  - [x] Test de consolidación: nodo con `sustantivos_clave="a,b"` en corto_plazo aparece en largo_plazo tras consolidar
  - [x] Test consolidación: nodo con `sustantivos_clave=""` en corto_plazo NO sobrescribe el de largo_plazo
  - [x] Tests: 9/9 pasando (`test_sustantivos_clave_schema.py`); suite completa: 184 passed/64.73s
  - [x] QA oficial: Recall@5=98.06%, FP=0.0%, 17 fallos/875, GATE OK
- [x] **Estado**: hecha — **2026-09-16**: schema + triggers + consolidación + migración DB vieja verificados

---

## T3: Validación en `_aprender_impl` + RF-21 (fail-fast)
- **RF cubiertos**: RF-1, RF-2, RF-3, RF-9, RF-14, RF-21
- **Descripción**: Bloque de validación de `sustantivos_clave` en `_aprender_impl` (después de bridges, ~línea 1936). Incluye: ausencia → error, normalización, dedup, validación cantidad (2-4), validación formato por término. Todo ANTES de escribir en `corto_plazo`.
- **Hecho cuando**:
  - [x] Llamar `biorag_aprender` sin `sustantivos_clave` → error `SUSTANTIVOS_CLAVE_AUSENTES`, nodo NO se guarda
  - [x] Llamar con 1 término → error `SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA`
  - [x] Llamar con 5 términos → error `SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA`
  - [x] Llamar con "servidor, s" (espacio) → error `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO`
  - [x] Llamar con "server@backend" (carácter especial) → error `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO`
  - [x] Llamar con "s" (1 char) → error `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO`
  - [x] Llamar con "servidor,servidor,backend" → dedup a "servidor,backend" (2 únicos → válido)
  - [x] `biorag_guardar` (alias) sin campo → mismo error
  - [x] Tests de validación pasan en verde
- [x] **Estado**: hecha — **2026-09-16**: Algoritmo A implementado en `_aprender_impl` (mcp_server.py) + plumb aditivo `sustantivos_clave` en `percibir_corto_plazo` (memory_store.py, default `""` backward-compatible). Tests «Hecho cuando» en `tests/test_sustantivos_clave_validacion.py` (8/8 verde). Suite completa: **192 passed/54.93s** (184 previos + 8 T3, 0 regresiones). E2E: `aprender` sin campo → `SUSTANTIVOS_CLAVE_AUSENTES`; `'Servidor,Servidor,timeout, Conexión'` → `'servidor,timeout,conexion'` guardado en corto_plazo.

---

## T4: Tools MCP `biorag_agregar_sustantivos` + `biorag_sustantivos`
- **RF cubiertos**: RF-16, RF-17
- **Descripción**: Dos tools nuevas en `mcp_server.py`. Ambas buscan en largo_plazo con fallback a corto_plazo. `agregar_sustantivos` valida y actualiza (trigger `_au` sincroniza FTS5). `sustantivos` lee el campo.
- **Hecho cuando**:
  - [x] `biorag_agregar_sustantivos(concepto="nodo_test", sustantivos_clave="a,b")` → `{"status":"ok","sustantivos_anteriores":"","sustantivos_nuevos":"a,b"}`
  - [x] `biorag_agregar_sustantivos(concepto="nodo_inexistente", ...)` → error `NODO_NO_ENCONTRADO`
  - [x] `biorag_agregar_sustantivos` con nodo que ya tiene campo → muestra `sustantivos_anteriores` vs `sustantivos_nuevos`
  - [x] `biorag_sustantivos(concepto="nodo_test")` → `{"status":"ok","sustantivos_clave":"a,b","items":["a","b"]}`
  - [x] `biorag_sustantivos(concepto="nodo_inexistente")` → error `NODO_NO_ENCONTRADO`
  - [x] `biorag_sustantivos` con nodo sin campo → `{"status":"ok","sustantivos_clave":"","items":[]}`
  - [x] Tests pasan en verde (`tests/test_sustantivos_clave_tools.py` 9/9 PASSED; suite completa 201/201 PASSED en 69.91s)
- [x] **Estado**: hecha — **2026-09-16**: `biorag_agregar_sustantivos` y `biorag_sustantivos` implementadas en `mcp_server.py` con validación completa (fail-fast, dedup, min/max 2-4 términos, formato), búsqueda en `largo_plazo` con fallback a `corto_plazo` y manejo transparente de triggers FTS5. Cobertura: 9 tests unitarios en verde, suite global 201/201 passed (0 regresiones).

---

## T5: BM25 weights (8 locations) + `biorag_recordar` optional param + Accent normalization en queries
- **RF cubiertos**: RF-5, RF-18, RF-19, RF-20
- **Descripción**: Actualizar `bm25(largo_plazo_fts, 5.0, 1.0, 2.0)` → `bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0)` en 8 ubicaciones de `memory_store.py` + 1 en `sinapsis.py`. Agregar parámetro opcional `sustantivos_clave` a `biorag_recordar` MCP y `_recordar_impl`. Aplicar `_quitar_acentos` a queries en `buscar_por_frase`.
- **Hecho cuando**:
  - [x] `grep -n "bm25(largo_plazo_fts" memory_store.py sinapsis.py` muestra 9 líneas con 4 pesos (5.0, 1.0, 2.0, 4.0) ✅ 8+1=9
  - [x] `grep -n "bm25(largo_plazo_fts" memory_store.py sinapsis.py` NO muestra líneas con 3 pesos (5.0, 1.0, 2.0) ✅ 0
  - [x] `biorag_recordar` acepta `sustantivos_clave` opcional ✅
  - [x] `biorag_recordar` con `sustantivos_clave="x@y"` → error de formato, búsqueda NO se ejecuta ✅ test validation pass
  - [x] `biorag_recordar` con `sustantivos_clave=""` → búsqueda normal (sin boost) ✅ test pass
  - [x] Query "conexión" matchea nodo con "conexion" almacenado (accent normalization) ✅ test pass
  - [x] Tests pasan en verde ✅ 207/207
- [x] **Estado**: completada

---

## T6: Tests unitarios completos para todas las tools
- **RF cubiertos**: Todos (cobertura de tests)
- **Descripción**: Crear/atualizar tests para: RF-16 (agregar_sustantivos), RF-17 (sustantivos), RF-19 (recordar boost), RF-20 (recordar validación), RF-21 (aprender fail-fast), RF-18 (accent normalization), RF-5 (BM25 boost). Los tests deben ser independientes y ejecutables con `pytest tests/ -v`.
- **Hecho cuando**:
  - [ ] `pytest tests/ -v` muestra tests nuevos en verde
  - [ ] Cobertura de todos los RFs verificada en tabla de cobertura al final de este archivo
  - [ ] 0 tests fallidos
- [ ] **Estado**: pendiente

---

## T7: Post-change métricas + Comparación + Verificación final
- **RF cubiertos**: RF-12, RF-13
- **Descripción**: Ejecutar las mismas métricas del baseline. Comparar con diff. Si hay regresión → revertir. Verificar que todos los tests existentes pasan sin cambio.
- **Hecho cuando**:
  - [ ] `pytest -q` muestra 168+ tests pasando (mismo o mayor que baseline)
  - [ ] `evaluar_qa.py` muestra Recall@5 ≥ 97.0% y FP = 0.0%
  - [ ] `diff baseline_qa_*.txt post_qa_*.txt` no muestra regresiones
  - [ ] Demo manual: guardar nodo con sustantivos_clave → buscar → verificar boost temático
- [ ] **Estado**: pendiente

---

## T8: Verificación de instalación — DB nueva y DB migrada (RF-22)
- **RF cubiertos**: RF-22
- **Descripción**: Verificar explícitamente que la columna `sustantivos_clave` y la FTS5 de 4 columnas quedan garantizadas en las DOS rutas de instalación. La implementación ya existe (T2); esta tarea prueba que el comportamiento especificado se cumple en ambos caminos.
- **Hecho cuando**:
  - [ ] DB nueva desde cero: `.schema corto_plazo` y `.schema largo_plazo` muestran `sustantivos_clave TEXT DEFAULT ''` SIN ejecutar ALTER
  - [ ] DB nueva: `largo_plazo_fts` se crea con 4 columnas (concepto, contenido, sinonimos, sustantivos_clave)
  - [ ] DB nueva: un `aprender` con sustantivos_clave funciona end-to-end (guardar → FTS5 → consolidar)
  - [ ] DB migrada: copia de DB sin la columna → arranque aplica ALTER a ambas tablas + rebuild FTS5
  - [ ] DB migrada: nodos pre-existentes quedan intactos (solo suman la columna vacía)
  - [ ] Tests de schema/migración pasan (9/9 del T2) documentados como evidencia de RF-22
- [ ] **Estado**: pendiente

---

## T9: Batería de extracción multi-modelo (RF-23)
- **RF cubiertos**: RF-23
- **Descripción**: Ejecutar la batería `specs/001-sustantivos-clave/bateria_extraccion.md` para validar que la extracción de sustantivos clave es correcta en guardado y búsqueda. Correr con el modelo principal (Athena-OEC) y registrar; si la configuración lo permite, correr con un 2º modelo/agente y comparar en la matriz.
- **Hecho cuando**:
  - [ ] Batería existe con ≥6 casos (cada uno con `Esperado` y `Prohibido`)
  - [ ] Corrida modelo principal: cada texto → extracción coincide con `Esperado` y NUNCA con `Prohibido`
  - [ ] Guardado: `aprender` con la extracción es aceptado (2-4 términos, formato válido)
  - [ ] Búsqueda: `recordar` con la extracción recupera el nodo en top resultados
  - [ ] Corrida 2º modelo (si configurado): misma verificación y comparación registrada en la matriz
  - [ ] Resultados documentados en la tabla de registro de la batería
- [ ] **Estado**: pendiente

---

## Cobertura de requisitos

| RF | Cubierto por |
|----|-------------|
| RF-1 | T3 |
| RF-2 | T3 |
| RF-3 | T3 |
| RF-4 | T2 |
| RF-5 | T5, T6 |
| RF-6 | T2 |
| RF-7 | T2 |
| RF-8 | T3 (mismo impl que aprender) |
| RF-9 | T3 |
| RF-10 | T1 |
| RF-11 | T1 |
| RF-12 | T7 |
| RF-13 | T7 |
| RF-14 | T3 |
| RF-15 | T2 |
| RF-16 | T4 |
| RF-17 | T4 |
| RF-18 | T5 |
| RF-19 | T5 |
| RF-20 | T5 |
| RF-21 | T3 |
| RF-22 | T8 |
| RF-23 | T9 |

**23/23 RFs cubiertos** ✅
