# Tareas — Spec 003: Modularización de Arquitectura

> **Fuente:** `specs/003-modularizacion-arquitectura/plan.md` y `specs/003-modularizacion-arquitectura/spec.md` (auditados y sincronizados)
> **Rama:** `modularizacion-arquitectura`
> **Regla cardinal:** Cada tarea termina con Gate verde antes de pasar a la siguiente. Un Gate rojo → `git revert` inmediato (RF-26). Prohibido `git add -A` y reescritura de algoritmos.

---

## T1: Crear rama, backups externos y baseline golden de Fase 0
- **RF cubiertos**: RF-14, RF-16, RF-23
- **Descripción**: Crear la rama `modularizacion-arquitectura`. Solicitar a Dennys la ruta externa y realizar backup completo del repo y snapshot inmutable de la **base viva real** (`MemoryBioRAG_Data/memory_biorag.db`) vía `sqlite3.backup()` + `PRAGMA wal_checkpoint(TRUNCATE)` fuera del árbol de trabajo (RF-14). Ejecutar el harness local determinista (`PYTHONHASHSEED=0`, `BIORAG_NO_LOG=1`, `BIORAG_DMN_ESTADO_PATH` fuera del repo) sobre `snapshots/qa_escape_qcr_20260811.db` para generar `golden_921.jsonl`, `golden_ids_reducido.txt` (~120 IDs) y `entorno_golden.json`. Verificar auto-identidad (segunda corrida = primera línea a línea). Prohibido commitear 6 scripts sueltos en `scripts/`.
- **Hecho cuando**:
  - [ ] Rama `modularizacion-arquitectura` creada y activa
  - [ ] Backup del repo y snapshot ANTES de la base viva guardados fuera del árbol del repositorio
  - [ ] `golden_921.jsonl` generado (921 casos con Top-5 y scores a 4 decimales sobre snapshot QA)
  - [ ] `verificar_auto_identidad` pasa (segunda corrida 100% idéntica a la primera)
  - [ ] `golden_ids_reducido.txt` contiene ~120 IDs proporcionales por categoría
  - [ ] `entorno_golden.json` registra versiones exactas de Python, numpy, SQLite
  - [ ] Gate Nivel 0 ✓ (pytest 264 + smoke + golden reducido)
- [ ] **Estado**: pendiente

---

## T2: Preparación mínima de Fase 1
- **RF cubiertos**: RF-15, RF-20
- **Descripción**: Mantener intactos en su ubicación actual los archivos sensibles (tests en raíz, dashboards, benchmarks — RF-15). No editar docstrings ni comentarios en los monolitos (`mcp_server.py`, `core/memory_store.py`) para no ensuciar los diffs de mudanza. `ARCHITECTURE.md` se difiere a la existencia de los módulos. Verificar suite base.
- **Hecho cuando**:
  - [ ] `pytest tests/ -v` → 264 tests passed, 0 errores, 0 skipped
  - [ ] Ningún docstring ni comentario en los monolitos ha sido modificado
  - [ ] Un único commit de preparación si hay cambios necesarios
- [ ] **Estado**: pendiente

---

## T3: Crear paquete MCP vacío — `__init__.py` + `_shared.py` + `server.py` (Paso 2.1)
- **RF cubiertos**: RF-5, RF-9, CL-9
- **Descripción**: Crear `core/mcp_server/__init__.py` (vacío), `_shared.py` (vacío) y `server.py` (vacío). Nada de `_build_server()` inline en este paso (evita dos servidores vivos). `_shared.py` se llenará progresivamente conforme se extraigan helpers para evitar 2 copias vivas.
- **Hecho cuando**:
  - [ ] `core/mcp_server/__init__.py` existe y está vacío
  - [ ] `core/mcp_server/_shared.py` existe y está vacío
  - [ ] `core/mcp_server/server.py` existe y está vacío
  - [ ] Gate Nivel 0 ✓ (pytest 264 + smoke + golden reducido + 42 tools / 2 resources / 1 prompt en raíz)
  - [ ] 1 commit atómico + push
- [ ] **Estado**: pendiente

---

## T4: Extraer tools de bajo acoplamiento MCP (Pasos 2.2a–2.2c)
- **RF cubiertos**: RF-5, RF-6, CL-5
- **Descripción**: Extraer `communication.py` (3 tools), `catalog.py` (4 tools) y `synapses.py` (4 tools) hacia `core/mcp_server/`. Cada submódulo expone `register(mcp)`. En `_build_server()`, sustituir inline por `register()` conforme se extrae cada módulo. Si un helper pasa a `_shared.py`, desaparece de `mcp_server.py` en el mismo commit. Un commit + Gate Nivel 0 por cada archivo.
- **Hecho cuando**:
  - [ ] `core/mcp_server/communication.py` existe con 3 tools + `register()`
  - [ ] `core/mcp_server/catalog.py` existe con 4 tools + `register()`
  - [ ] `core/mcp_server/synapses.py` existe con 4 tools + `register()`
  - [ ] `_build_server()` devuelve exactamente 42 names + 2 resources + 1 prompt tras cada paso
  - [ ] Gate Nivel 0 ✓ tras cada extracción (3 verificaciones)
  - [ ] 3 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T5: Extraer tools intermedios MCP (Pasos 2.2d–2.2f)
- **RF cubiertos**: RF-5, RF-6, CL-4, CL-5
- **Descripción**: Extraer `concept_hub_tools.py` (6 tools, `concept_hub_cargar_iniciales_tool` sin `name=` — CL-4), `introspection.py` (5 tools, orden: introspeccion→estado, mapear→corteza — CL-5) y `consolidation.py` (2 tools, orden: consolidar→sueno — CL-5). `register()` en cada submódulo y cableado en `_build_server()`.
- **Hecho cuando**:
  - [ ] `core/mcp_server/concept_hub_tools.py` existe con 6 tools + `register()`
  - [ ] `concept_hub_cargar_iniciales_tool` conserva su identificador implícito sin `name=`
  - [ ] `core/mcp_server/introspection.py` existe con 5 tools en orden estricto CL-5
  - [ ] `core/mcp_server/consolidation.py` existe con 2 tools en orden estricto CL-5
  - [ ] `_build_server()` devuelve exactamente 42 names + 2 resources + 1 prompt
  - [ ] Gate Nivel 0 ✓ tras cada extracción (3 verificaciones)
  - [ ] 3 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T6: Extraer tools sesión, daemon y oráculo MCP (Pasos 2.2g–2.2i)
- **RF cubiertos**: RF-5, RF-6, CL-5, RF-7
- **Descripción**: Extraer `daemon.py` (3 tools, `estado_hormiga.json` con `project_root()`), `session.py` (2 tools + `_preview()` local — A2), `oracle.py` (2 tools + 3 helpers en orden exacto: `_nlm_detectado` → `_consultar_notebooklm` → `_buscar_contexto_biorag_arranque` → `biorag_oraculo_inicio` → `biorag_oraculo_preguntar` — CL-5).
- **Hecho cuando**:
  - [ ] `core/mcp_server/daemon.py` existe con 3 tools + `register()`
  - [ ] `core/mcp_server/session.py` existe con 2 tools + `_preview()` local + `register()`
  - [ ] `core/mcp_server/oracle.py` existe con 5 funciones en orden exacto CL-5
  - [ ] `_build_server()` devuelve exactamente 42 names + 2 resources + 1 prompt
  - [ ] Gate Nivel 0 ✓ tras cada extracción (3 verificaciones)
  - [ ] 3 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T7: Extraer sync, calibrar, resources y prompt MCP (Pasos 2.2j–2.2m)
- **RF cubiertos**: RF-5, RF-6
- **Descripción**: Extraer `sync.py` (3 tools, ~120 líneas), `calibrar.py` (1 tool, ~55 líneas, nombrado `calibrar.py` para no colisionar con `core/calibracion.py`), `resources.py` (2 resources, ~120 líneas) y `prompt.py` (1 prompt, ~50 líneas).
- **Hecho cuando**:
  - [ ] `core/mcp_server/sync.py` existe con 3 tools + `register()`
  - [ ] `core/mcp_server/calibrar.py` existe con 1 tool + `register()`
  - [ ] `core/mcp_server/resources.py` existe con 2 resources + `register()`
  - [ ] `core/mcp_server/prompt.py` existe con 1 prompt + `register()`
  - [ ] `_build_server()` devuelve exactamente 42 names + 2 resources + 1 prompt
  - [ ] Gate Nivel 0 ✓ tras cada extracción (4 verificaciones)
  - [ ] 4 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T8: Extraer write.py MCP (Paso 2.2n)
- **RF cubiertos**: RF-5, RF-6, RNF-1
- **Descripción**: Extraer `core/mcp_server/write.py` conteniendo `_aprender_impl` (~321 líneas reales — deuda técnica trasladada intacta) + 5 tools (`biorag_aprender`, `biorag_guardar`, `biorag_agregar_sustantivos`, `biorag_sustantivos`, `biorag_actualizar`). Primera línea del docstring documenta deuda técnica.
- **Hecho cuando**:
  - [ ] `core/mcp_server/write.py` existe con 5 tools + `_aprender_impl` intacto (~321 líneas) + `register()`
  - [ ] `wc -l core/mcp_server/write.py` ≈ 845 (excepción 800 por deuda técnica aplicada)
  - [ ] `_build_server()` devuelve exactamente 42 names + 2 resources + 1 prompt
  - [ ] Gate Nivel 0 ✓
  - [ ] 1 commit atómico + push
- [ ] **Estado**: pendiente

---

## T9: Extraer search.py MCP (Paso 2.2o)
- **RF cubiertos**: RF-5, RF-6, RNF-1
- **Descripción**: Extraer `core/mcp_server/search.py` conteniendo `_recordar_impl` (~753 líneas reales, L652–L1404 por AST — deuda técnica trasladada intacta) + 2 tools (`biorag_recordar`, `biorag_buscar`). Primera línea del docstring documenta deuda técnica. Módulo final MCP: Gate Nivel 0 + Gate Nivel 1.
- **Hecho cuando**:
  - [ ] `core/mcp_server/search.py` existe con 2 tools + `_recordar_impl` intacto (~753 líneas) + `register()`
  - [ ] `wc -l core/mcp_server/search.py` ≈ 1135 (excepción 800 por deuda técnica aplicada)
  - [ ] `_build_server()` devuelve exactamente 42 names + 2 resources + 1 prompt
  - [ ] Gate Nivel 0 ✓ + Gate Nivel 1 ✓ (921 casos idénticos a 4 decimales)
  - [ ] 1 commit atómico + push
- [ ] **Estado**: pendiente

---

## T10: Consolidar server.py, crear shim raíz `mcp_server.py` y validar CWD (Pasos 2.3–2.4)
- **RF cubiertos**: RF-3, RF-7, CL-6, CL-7
- **Descripción**: Paso 2.3: Consolidar `core/mcp_server/server.py` como cableado puro (llama `register()` de los 15 submódulos de tools/resources/prompts, sin código inline). Efectos de arranque (`load_dotenv`, `logging.basicConfig`, warmup WordNet, `sys.path.insert` con `core.paths.project_root()`) corren al nivel de módulo al importar `server.py`; `FastMCP` se instancia dentro de `_build_server()`. Paso 2.4: Reemplazar el monolito raíz `mcp_server.py` por un shim de ≤ 15 líneas que re-exporta `_build_server` y `main` + `if __name__ == "__main__": sys.exit(main())`. Ejecutar test de validación CWD desde `/tmp` con `PYTHONPATH`. Grep previo confirma ausencia de otros imports externos a re-exportar.
- **Hecho cuando**:
  - [ ] `core/mcp_server/server.py` contiene exclusivamente `register()` × 15 submódulos + bootstrap
  - [ ] `mcp_server.py` raíz es un shim ≤ 15 líneas
  - [ ] `wc -l mcp_server.py` ≤ 15
  - [ ] Test de validación CWD (`cwd=/tmp` con `PYTHONPATH`) pasa exitosamente
  - [ ] `grep -r "from mcp_server import\|import mcp_server"` no muestra fallos de import
  - [ ] Gate Nivel 1 ✓ (42 names + 2 resources + 1 prompt + 921 casos golden)
  - [ ] 2 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T11: Crear paquete Memory + constants.py + calificar constants.NOMBRE y monkeypatches (Pasos 3.0–3.1)
- **RF cubiertos**: RF-12, RF-3, RF-8, CL-8
- **Descripción**: Paso 3.0: Crear `core/memory/__init__.py` (vacío, sin re-exportar la clase — CL-8). Paso 3.1: Extraer `core/memory/constants.py` (~225 líneas, ~55 constantes y flags + funciones puras de módulo: `normalizar_sustantivos_clave`, `_qcr_levenshtein`, `_qcr_todos_cercanos`). En `core/memory_store.py` (con las funciones todavía en la clase), calificar todas las lecturas de constantes como `constants.NOMBRE` (sin tocar ifs, SQLs ni fórmulas; `logger` no se prefija; `constants.py` no importa la fachada). En este mismo commit, mover los monkeypatches de los tests de `core.memory_store.FLAG` a `core.memory.constants.FLAG` y actualizar la cadena literal esperada en los 4 asserts: `test_dim_escape.py` (`DIM_ESCAPE` → `constants.DIM_ESCAPE`), `test_dim_resonancia.py` (`"if DIM_RESONANCIA:"` → `"if constants.DIM_RESONANCIA:"`), `test_ncd_e6.py` (`"NCD_PESO * ncd_score"` → `"constants.NCD_PESO * ncd_score"`) y `test_qcr_typo_d4.py` (llamada con `QCR_TYPO_DIST`). `core/memory_store.py` re-exporta constantes y `normalizar_sustantivos_clave`.
- **Hecho cuando**:
  - [ ] `core/memory/__init__.py` existe y está vacío
  - [ ] `core/memory/constants.py` existe con constantes y funciones puras (~225 líneas)
  - [ ] Todas las lecturas de constantes en `memory_store.py` calificadas como `constants.NOMBRE`
  - [ ] Monkeypatches en tests sincronizados a `core.memory.constants.FLAG`
  - [ ] Los 4 asserts literales actualizados y pasando en verde
  - [ ] `from core.memory_store import normalizar_sustantivos_clave` sigue funcionando
  - [ ] Gate Nivel 0 ✓
  - [ ] 2 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T12: Extraer comms.py y telemetry.py (Pasos 3.2a–3.2b)
- **RF cubiertos**: RF-10, RF-8
- **Descripción**: Extraer `core/memory/comms.py` (~130 líneas: comunicaciones) y `core/memory/telemetry.py` (~170 líneas: historial, benchmark rendimiento, log búsqueda, provenance — sin co-ocurrencia ni WordNet). Patrón A1 (funciones con `self` como primer parámetro). Delegadores con firma completa en fachada.
- **Hecho cuando**:
  - [ ] `core/memory/comms.py` existe con 4 funciones (~130 líneas)
  - [ ] `core/memory/telemetry.py` existe con 5 funciones (~170 líneas)
  - [ ] Delegadores correspondientes con firma completa agregados en `core/memory_store.py`
  - [ ] Gate Nivel 0 ✓ tras cada commit (2 verificaciones)
  - [ ] 2 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T13: Extraer synapses.py y episodes.py (Pasos 3.3a–3.3b)
- **RF cubiertos**: RF-10, RF-8
- **Descripción**: Extraer `core/memory/synapses.py` (~523 líneas reales: grafo puro — asociaciones, enriquecidas, BFS, cadena, camino, dopamina, multihop; docstring con justificación >500) y `core/memory/episodes.py` (~120 líneas: expansión temporal, afinidad temporal pool, ts nodo). Patrón A1 con delegadores en fachada.
- **Hecho cuando**:
  - [ ] `core/memory/synapses.py` existe con 8 funciones (~523 líneas) y docstring de justificación
  - [ ] `core/memory/episodes.py` existe con 3 funciones (~120 líneas)
  - [ ] Delegadores con firma completa en fachada
  - [ ] Gate Nivel 0 ✓ tras cada commit (2 verificaciones)
  - [ ] 2 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T14: Extraer quarantine.py e ingest.py (Pasos 3.3c–3.3d)
- **RF cubiertos**: RF-10, RF-8
- **Descripción**: Extraer `core/memory/quarantine.py` (~180 líneas: ciclo cuarentena y evicción) e `core/memory/ingest.py` (~122 líneas: solo `percibir_corto_plazo` y `consolidar_concepto`). Patrón A1 con delegadores en fachada.
- **Hecho cuando**:
  - [ ] `core/memory/quarantine.py` existe con 6 funciones (~180 líneas)
  - [ ] `core/memory/ingest.py` existe con 2 funciones (~122 líneas)
  - [ ] Delegadores con firma completa en fachada
  - [ ] Gate Nivel 0 ✓ tras cada commit (2 verificaciones)
  - [ ] 2 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T15: Extraer dmn.py y consolidation.py (Pasos 3.3e–3.3f)
- **RF cubiertos**: RF-10, RF-8, RNF-1.3
- **Descripción**: Extraer `core/memory/dmn.py` (~140 líneas: ciclo DMN y `_registrar_acceso_nodo`) y `core/memory/consolidation.py` (~694 líneas de cuerpo: `ciclo_sueno_consolidacion` de 505 líneas trasladada intacta por deuda técnica, `_auto_generar_co_ocurrencia`, `_clasificar_nodo_wordnet`, `_calcular_base_level_actr`). La excepción de deuda técnica aplica a `ciclo_sueno_consolidacion`; si el archivo supera 800 debido a esa función monolítica no se parte ni se recorta. Delegadores con firma completa en fachada. Gate Nivel 0 + Gate Nivel 1 tras consolidation.
- **Hecho cuando**:
  - [ ] `core/memory/dmn.py` existe con 7 funciones (~140 líneas)
  - [ ] `core/memory/consolidation.py` existe con 4 funciones (~694 líneas) y docstring documentando deuda técnica
  - [ ] Delegadores con firma completa en fachada
  - [ ] Gate Nivel 0 ✓ (2 veces) + Gate Nivel 1 ✓ (tras consolidation)
  - [ ] 2 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T16: Extraer scoring.py + getsource de score híbrido (Paso 3.4a)
- **RF cubiertos**: RF-10, RF-8, CL-1
- **Descripción**: Extraer `core/memory/scoring.py` (~420 líneas: `_calcular_score_hibrido`, `_calcular_jsd`, `_jsd_weight_adaptativo`, `_ncd_sim`, `_ncd_sims_pool`, `_analogia_scores_pool`, `_idf_tokens_qcr`, `_calcular_jaccard`, `_calcular_bm25_bayesiano`, `_agregar_prefix_wildcards`, `_pesar_tokens_query`, `_rerank_jaccard_protect_r0` con closures intactos).
  1. Conservar `@staticmethod` en la fachada para `_ncd_sim`, `_jsd_weight_adaptativo`, `_calcular_jsd`, `_calcular_bm25_bayesiano` sin `self`.
  2. En este commit, redirigir ÚNICAMENTE el `inspect.getsource` de `_calcular_score_hibrido` (en `tests/test_ncd_e6.py`) hacia `core.memory.scoring._calcular_score_hibrido`. (`test_jsd_adaptativo_e7.py` mira `buscar_por_frase` y se mantiene vigilando esa función hasta T19).
  Gate Nivel 0 + Gate Nivel 1.
- **Hecho cuando**:
  - [ ] `core/memory/scoring.py` existe con 12 funciones de score (~420 líneas)
  - [ ] Fachada conserva `@staticmethod` delegando a `scoring.<metodo>(...)`
  - [ ] `inspect.getsource` de `_calcular_score_hibrido` en `test_ncd_e6.py` adaptado y en verde
  - [ ] Gate Nivel 0 ✓ + Gate Nivel 1 ✓ (921 casos idénticos a 4 decimales)
  - [ ] 1 commit atómico + push
- [ ] **Estado**: pendiente

---

## T17: Extraer umbral.py, context.py, catalog_methods.py y adn.py (Pasos 3.4b–3.4e)
- **RF cubiertos**: RF-10, RF-8
- **Descripción**: Extraer `core/memory/umbral.py` (~430 líneas: calibración conforme y certeza epistémica separada de scoring), `core/memory/context.py` (~200 líneas: epistémico y coherencia dimensional), `core/memory/catalog_methods.py` (~110 líneas: categorías, dimensiones, sync — recordando que `cerrar_sistema` permanece en la fachada) y `core/memory/adn.py` (~90 líneas: 3 funciones de firma ADN pura). Delegadores con firma completa en fachada.
- **Hecho cuando**:
  - [ ] `core/memory/umbral.py` existe con cluster de calibración (~430 líneas)
  - [ ] `core/memory/context.py` existe con funciones de contexto y epistémico (~200 líneas)
  - [ ] `core/memory/catalog_methods.py` existe (~110 líneas) y `cerrar_sistema` permanece en la fachada
  - [ ] `core/memory/adn.py` existe con 3 funciones ADN (~90 líneas)
  - [ ] Delegadores con firma completa en fachada
  - [ ] Gate Nivel 0 ✓ tras cada commit (4 verificaciones)
  - [ ] 4 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T18: Extraer schema.py (Paso 3.4f)
- **RF cubiertos**: RF-10, RF-8, RNF-1.3
- **Descripción**: Extraer `core/memory/schema.py` (~1200 líneas: `_crear_estructura_cerebral` de 513 líneas trasladada intacta por deuda técnica, `_crear_tabla_data`, `_crear_tablas_nuevas_si_faltan`, `_asegurar_catalogo_dimensiones`, `_crear_tabla_fts`, `_poblar_fts`, `_poblar_fts_unicode` en el mismo commit). Excepción 800 por deuda técnica. Delegadores en fachada. Gate Nivel 0 + Gate Nivel 1.
- **Hecho cuando**:
  - [ ] `core/memory/schema.py` existe con 7 funciones de esquema (~1200 líneas)
  - [ ] `_crear_estructura_cerebral` intacta + `_poblar_fts` y `_poblar_fts_unicode` presentes
  - [ ] Docstring documenta deuda técnica
  - [ ] Gate Nivel 0 ✓ + Gate Nivel 1 ✓
  - [ ] 1 commit atómico + push
- [ ] **Estado**: pendiente

---

## T19: Extraer rafaga.py y search.py + sincronización getsource restante (Pasos 3.4g–3.4h)
- **RF cubiertos**: RF-10, RF-8, RNF-1.3, CL-1
- **Descripción**: Paso 3.4g: Extraer `core/memory/rafaga.py` (~370 líneas: `buscar_por_rafaga` de 343 líneas de cuerpo y `validar_rafaga`). Paso 3.4h: Extraer `core/memory/search.py` (~2500 líneas: `buscar_por_frase` de 2109 líneas intacta con closures anidadas `_fts_safe_term`, `_fts_safe_phrase`, `strip_accents`, `_calc_strict_cov` + variaciones, microsegundos, tokens, predicados, búsqueda en contenido). En este commit, adaptar `inspect.getsource` en `tests/test_jsd_adaptativo_e7.py`, `tests/test_dim_escape.py`, `tests/test_dim_resonancia.py`, `tests/test_qcr_idf_e3.py` y `tests/test_qcr_typo_d4.py` hacia `core.memory.search.buscar_por_frase` o funciones movidas. Gate Nivel 0 + Gate Nivel 1.
- **Hecho cuando**:
  - [ ] `core/memory/rafaga.py` existe con `buscar_por_rafaga` y `validar_rafaga` (~370 líneas, bajo 500, no se parte)
  - [ ] `core/memory/search.py` existe con `buscar_por_frase` intacta + closures anidadas (~2500 líneas)
  - [ ] Docstrings documentan deuda técnica
  - [ ] `inspect.getsource` en `test_jsd_adaptativo_e7.py`, tests de escape, resonancia y QCR adaptados y pasando al 100%
  - [ ] Gate Nivel 0 ✓ + Gate Nivel 1 ✓ (921 casos idénticos a 4 decimales)
  - [ ] 2 commits atómicos + push
- [ ] **Estado**: pendiente

---

## T20: Consolidar fachada `core/memory_store.py` (Paso 3.5)
- **RF cubiertos**: RF-11, RF-8, RNF-1.4
- **Descripción**: Consolidar `core/memory_store.py` como fachada delgada: `__init__` (bootstrap), `cerrar_sistema` (junto a `__init__`, sin delegar), re-exports de constantes/funciones puras y delegadores con firma completa explícita (prohibido `*args, **kwargs`). Estimado ~450 líneas (techo orientativo 400, tope 500 orientativo/justificado; si las firmas completas hacen que supere 500, la justificación de una línea en docstring basta). Auditoría completa `wc -l` de todos los submódulos. Gate Nivel 1.
- **Hecho cuando**:
  - [ ] `core/memory_store.py` contiene `__init__`, `cerrar_sistema`, re-exports y delegadores con firma completa
  - [ ] Prohibido `__getattr__` y prohibido `*args, **kwargs` (RF-8, RF-11)
  - [ ] Si `wc -l core/memory_store.py` > 400, docstring de justificación presente
  - [ ] Tabla de auditoría `wc -l` de todos los archivos generada en el commit
  - [ ] Gate Nivel 1 ✓
  - [ ] 1 commit atómico + push
- [ ] **Estado**: pendiente

---

## T21: Gate Nivel 2 — Validación Final y Entrega
- **RF cubiertos**: RF-27, RF-17
- **Descripción**: Ejecutar la suite completa de validación final: `run_qa_suite.sh` (875/875 Recall@5, 0 FP sobre `snapshots/qa_escape_qcr_20260811.db`), `fuzz_qa.py` (33/33 passed), verificación dual no-tautológica usando el snapshot de la **base viva real** congelado en Fase 0 (`MemoryBioRAG_Data/memory_biorag.db`) como sustrato fijo e inmutable para ambas corridas (código pre-modularización en `antes.jsonl` vs código modularizado en `despues.jsonl` — 100% identidad caso a caso). Generar informe final auditado con tablas de líneas y métricas entregado directamente a Dennys. El merge a `master` lo ejecuta Dennys (RF-17).
- **Hecho cuando**:
  - [ ] `./scripts/run_qa_suite.sh` → 100.00% Recall@5 (875/875), 0 fallos, 0.00% FP (0/40) sobre snapshot QA
  - [ ] `python3 scripts/fuzz_qa.py` → 33/33 passed
  - [ ] Verificación dual sobre snapshot congelado de la base viva: `antes.jsonl` == `despues.jsonl` (100% identidad caso a caso)
  - [ ] Informe final de Gate Nivel 2 redactado con tablas de auditoría `wc -l` y métricas entregado a Dennys
  - Nota: El merge a `master` lo ejecuta exclusivamente Dennys; el agente termina su labor con la entrega del informe.
- [ ] **Estado**: pendiente

---

## Cobertura de requisitos

| RF | Cubierto por |
|---|---|
| RF-1 | T3 (delegadores MCP), T11–T20 (fachada con firma completa) |
| RF-2 | T4–T9 (42 names), T10 (verificación en shim) |
| RF-3 | T10 (shim `mcp_server.py`), T11 (re-exports `constants.py` y `normalizar_sustantivos_clave`) |
| RF-4 | Invariante — sin cambios DDL en ninguna tarea |
| RF-5 | T3 (`__init__.py` y `_shared.py`), T4–T9 (15 submódulos MCP) |
| RF-6 | T4–T9 (función `register(mcp)` y docstring con names) |
| RF-7 | T6 (`daemon.py`), T10 (`core.paths.project_root()` en `server.py` y test CWD `/tmp`) |
| RF-8 | T11 (calificación `constants.NOMBRE` y monkeypatches), T12–T19 (patrón A1: funciones con `self`, delegadores `@staticmethod` sin `self`, tests `inspect.getsource` adaptados) |
| RF-9 | T3 (`_shared.py` para sesiones), T11–T19 (estado en instancia `self`) |
| RF-10 | T12–T19 (clusters de dominio extraídos intactos) |
| RF-11 | T20 (fachada delgada con delegación explícita con firma completa, sin `__getattr__`) |
| RF-12 | T11 (`constants.py` + re-exports hacia consumidores externos) |
| RF-14 | T1 (backup del repo y snapshot ANTES de base viva externos, harness determinista local sobre snapshot QA) |
| RF-15 | T2 (invarianza de archivos sensibles y sin edición prematura de monolitos) |
| RF-16 | T1 (rama `modularizacion-arquitectura`) |
| RF-17 | T21 (merge a `master` ejecutado exclusivamente por Dennys) |
| RF-18 | T3–T20 (commit atómico + push tras cada Gate verde) |
| RF-19 | T3–T20 (`git revert` inmediato si cualquier gate falla) |
| RF-20 | T1–T21 (mensajes de commit con estándar y tabla de auditoría) |
| RF-21 | Invariante — bases de datos, snapshots y archivos prohibidos fuera de commits |
| RF-22 | Invariante — prohibido `git add -A` y `git checkout` ciego |
| RF-23 | T1–T21 (entorno determinista `PYTHONHASHSEED=0`, `BIORAG_NO_LOG=1`, DMN externo) |
| RF-24 | T1 (harness Gate Nivel 0), T3–T20 (Gate Nivel 0 tras cada extracción) |
| RF-25 | T9, T10, T15, T16, T18, T19, T20 (Gate Nivel 1 con 921 casos) |
| RF-26 | T3–T20 (revert automático por Top-5/score, excepción de latencia explícita) |
| RF-27 | T21 (Gate Nivel 2: suite QA completa + fuzz + Verificación Dual no-tautológica sobre snapshot de base viva) |
| RNF-1 | T3–T20 (`wc -l` físicos, topes orientativos/duros, justificaciones y deuda documentada) |
| RNF-2 | T21 (latencia reportada en informe, cero dependencias externas nuevas) |
| CL-1 | T16 (`_rerank_jaccard_protect_r0`), T19 (`buscar_por_frase` con closures intactas) |
| CL-2 | T3 (imports hacia `_shared.py`), T11 (submódulos memory no importan fachada) |
| CL-3 | Invariante — scripts referenciados en `ci.yml` no se mueven |
| CL-4 | T5 (`concept_hub_cargar_iniciales_tool` sin `name=`) |
| CL-5 | T4–T6 (orden interno de definiciones: `consolidation.py`, `introspection.py`, `oracle.py`) |
| CL-6 | T4–T9 (`_build_server()` devuelve 42 names en cada commit intermedio) |
| CL-7 | T10 (grep previo al shim `mcp_server.py`) |
| CL-8 | T11 (`core/memory/__init__.py` vacío, sin re-export) |
| CL-9 | T3 (`_shared.py` con techo 500/800, llenado progresivo) |
| CL-10 | T1 (golden congelado, nunca regenerado para tapar regresión) |
| CL-11 | T21 (`run_qa_suite.sh` comando canónico de Gate Nivel 2) |

> **Nota RF-13 (hueco):** El hueco se mantiene sin renumeración para preservar la estabilidad de referencias.

---

*Tareas guardadas en `specs/003-modularizacion-arquitectura/tasks.md`. Todos los RF tienen cobertura.*
