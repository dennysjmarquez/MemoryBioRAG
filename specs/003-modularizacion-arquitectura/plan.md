# Plan Técnico — Spec 003: Modularización de Arquitectura

> **Rama de trabajo:** `modularizacion-arquitectura`
> **Fuente de verdad:** `specs/003-modularizacion-arquitectura/spec.md` (con clarificaciones A1–A6, C1–C2, CL-1–CL-11, CC1 incorporadas)
> **Prohibición absoluta:** Este plan no autoriza código. Solo estructura, nombres, contratos y decisiones.

---

## Estructura de módulos

### Paquete `core/mcp_server/` (Fase 2)

Destino de la descomposición de `mcp_server.py` (4 358 líneas actuales). La raíz `mcp_server.py` se convierte en shim de ≤ 15 líneas en el último commit.

| Archivo | Contenido (42 tools + 2 resources + 1 prompt) | Tamaño estimado (`wc -l`) | RF |
|---|---|---|---|
| `__init__.py` | Vacío (marca paquete) | ~3 | RF-5 |
| `_shared.py` | `_sesiones_activas`, `LIMITE_MCP`, `VENTANA_CORRECCION`, `PARAFRASIS_PENALTY`, `NOTEBOOK_ID_ORACULO`, `STALE_DAYS`, `STALE_HARD_CUTOFF_DAYS`, `ORACULO_MAX_CHARS`, `MAX_ASOCIACIONES_FLAT`, `THRESHOLD_RAFTAGA_MCP`, `PROMPT_INICIO_NOTEBOOKLM`, `QUERIES_BIORAG_INICIO`, `AGENTES_VALIDOS`, `_get_cerebro()`, `_interceptar()`, `_serializar_asociaciones()`, `_confianza_calibrada()`, `_nivel_certeza()`, `_resolver_dimensiones()`, `_parsear_fechas()`, `_buscar_nodos_viejos_relacionados()`, `_encontrar_arista_origen()` | ~430 | RF-5, CL-9, A2 |
| `server.py` | `_build_server()` cableado puro (llama `register(mcp)` por submódulo), bootstrap FastMCP con `try/except`, `core.paths.project_root()` para `.env.local` y `estado_hormiga.json` | ~90 | RF-5, RF-7, CL-6, CL-7 |
| `communication.py` | `biorag_comunicar`, `biorag_leer_mensajes`, `biorag_marcar_como_leido` + `register()` | ~165 | RF-5, RF-6 |
| `catalog.py` | `biorag_listar_categorias`, `biorag_listar_dimensiones`, `biorag_listar_tipos_dimension`, `biorag_listar_dimensiones_por_tipo` + `register()` | ~200 | RF-5, RF-6 |
| `synapses.py` | `biorag_vincular`, `biorag_desvincular`, `biorag_asociar`, `biorag_feedback` + `register()` | ~130 | RF-5, RF-6 |
| `concept_hub_tools.py` | 6 tools Concept Hub incluyendo `concept_hub_cargar_iniciales_tool` (sin `name=`) + `register()` | ~175 | RF-5, RF-6, CL-4 |
| `introspection.py` | `biorag_introspeccion`, `biorag_estado`, `biorag_mapear`, `biorag_corteza`, `biorag_metricas_historial` + `register()` — orden: introspeccion antes de estado, mapear antes de corteza | ~215 | RF-5, RF-6, CL-5 |
| `consolidation.py` | `biorag_consolidar`, `biorag_sueno` + `register()` — orden: consolidar antes de sueno | ~85 | RF-5, RF-6, CL-5 |
| `daemon.py` | `biorag_hormiguita`, `biorag_hormiguita_estado`, `biorag_estado_dmn` + `register()` | ~115 | RF-5, RF-6 |
| `session.py` | `biorag_contexto_inicio`, `biorag_contexto_fin`, `_preview()` (helper local — uso único) + `register()` | ~110 | RF-5, RF-6 |
| `oracle.py` | `_nlm_detectado`, `_consultar_notebooklm`, `_buscar_contexto_biorag_arranque`, `biorag_oraculo_inicio`, `biorag_oraculo_preguntar` + `register()` — definidos en ese orden exacto (CL-5) | ~305 | RF-5, RF-6, CL-5 |
| `sync.py` | `biorag_sync_status`, `biorag_export_sync`, `biorag_export_full` + `register()` | ~120 | RF-5, RF-6 |
| `calibrar.py` | `biorag_calibrar` + `register()` | ~55 | RF-5, RF-6 |
| `write.py` | `_aprender_impl` (~321 líneas — **deuda técnica**), `biorag_aprender`, `biorag_guardar`, `biorag_agregar_sustantivos`, `biorag_sustantivos`, `biorag_actualizar` + `register()` | ~845 **⚠ DEUDA** | RF-5, RF-6, RNF-1 |
| `search.py` | `_recordar_impl` (~753 líneas, L652–L1404 por AST — **deuda técnica**), `biorag_recordar`, `biorag_buscar` + `register()` | ~1 135 **⚠ DEUDA** | RF-5, RF-6, RNF-1 |
| `resources.py` | 2 resources MCP + `register()` | ~120 | RF-5, RF-6 |
| `prompt.py` | 1 prompt MCP + `register()` | ~50 | RF-5, RF-6 |

**Nota deuda técnica — `search.py` y `write.py`:** `_recordar_impl` mide 753 líneas (L652–L1404 por AST); `_aprender_impl` mide 321 líneas. Ambas son funciones monolíticas preexistentes que se trasladan completas e intactas (RNF-1.3). La excepción del tope de 800 líneas aplica al código de deuda técnica trasladado intacto. Se documenta en la primera línea del docstring del módulo.

**Nota regla A2 — `_shared.py`:** `_interceptar` (usado por 8 submódulos), `_resolver_dimensiones`, `_parsear_fechas`, `_serializar_asociaciones`, `_confianza_calibrada`, `_nivel_certeza`, `_encontrar_arista_origen` van a `_shared.py` porque los usan ≥ 2 submódulos. `_preview` solo la usa `session.py` → queda en `session.py`.

**Nota tamaño `_shared.py`:** ~450 líneas estimadas (techo orientativo 500, tope duro 800 — CL-9).

---

### Paquete `core/memory/` (Fase 3) — Mapa Corregido

Destino de la descomposición de `core/memory_store.py` (7 778 líneas actuales). La fachada queda en ≤ 400 líneas orientativo / ≤ 500 líneas tope duro (RNF-1.4). Con 99 delegadores + `__init__`, 400 no cabe (la spec lo reconoce explícitamente); la estimación de ~450 requiere docstring justificación por superar 400.

**Correcciones aplicadas (revisor):**
- `scoring.py` dividido en `scoring.py` + `umbral.py` (ambos < 500 líneas — sumaban 828).
- `search.py` dividido: `rafaga.py` extrae `buscar_por_rafaga` y `validar_rafaga`.
- `ingest.py` solo `percibir_corto_plazo` y `consolidar_concepto`. `episodes.py` y `quarantine.py` restaurados.
- `adn.py` solo las 3 funciones de firma ADN pura. `validar_rafaga` va a `rafaga.py`.
- `telemetry.py` sin `_auto_generar_co_ocurrencia` ni `_clasificar_nodo_wordnet` → van a `consolidation.py`.
- `cerrar_sistema` queda en la **fachada** (`core/memory_store.py`), no en `catalog_methods.py`.
- `schema.py` incluye `_poblar_fts` y `_poblar_fts_unicode` (mismo commit que `_crear_tabla_fts`).
- `dmn.py` incluye `_registrar_acceso_nodo` (lo llama `buscar_por_frase`; `self.X()` intacto).
- `consolidation.py` incluye `_calcular_base_level_actr` (lo llama el ciclo de sueño).
- `scoring.py` incluye `_rerank_jaccard_protect_r0` (closures intactos, CL-1).
- `search.py` incluye `_buscar_en_contenido` y `_buscar_todos_en_contenido`.
- `synapses.py` mide ~523 líneas reales (no ~250); lleva justificación de una línea.
- No se crea `calibration.py`. `core/calibracion.py` no se toca.

| Archivo | Contenido | Tamaño estimado (`wc -l`) | RF |
|---|---|---|---|
| `__init__.py` | Vacío. No re-exporta `SQLiteMemoryBioRAG`. API pública sigue siendo `core.memory_store`. | ~3 | CL-8, RF-3 |
| `constants.py` | ~55 constantes de configuración y flags (`CANDIDATOS_SIMILITUD`, `MAX_SALTOS_CADENA`, `LIMITE_DEFAULT`, `UMBRAL_JACCARD`, `RAFTAGA_ACTIVA`, `JSD_*`, `DMN_*`, `EPISODIO_*`, `ANALOGIA_*`, `CAMPO_*`, `QCR_*`, `SDM_*`, `NCD_*`, `RERANKING_*`, `PPMI_VECTOR_WEIGHT`, `ADN_*`, `GABA_ACTIVO`, `BAYESIAN_*`) + funciones de módulo puras (`normalizar_sustantivos_clave`, `_qcr_levenshtein`, `_qcr_todos_cercanos`) | ~225 | RF-12, RF-3 |
| `schema.py` | `_crear_estructura_cerebral` (~513 líneas — **deuda técnica**), `_crear_tabla_data`, `_crear_tablas_nuevas_si_faltan`, `_asegurar_catalogo_dimensiones`, `_crear_tabla_fts`, `_poblar_fts`, `_poblar_fts_unicode` | ~1 200 **⚠ DEUDA** | RF-10, RNF-1.3 |
| `comms.py` | `_crear_tabla_comunicaciones`, `enviar_comunicado`, `leer_comunicados`, `marcar_como_leido` | ~130 | RF-10 |
| `dmn.py` | `iniciar_dmn`, `detener_dmn`, `notificar_actividad_usuario`, `registrar_acceso_contexto`, `obtener_bonus_contexto`, `_crear_tabla_metricas`, `_registrar_acceso_nodo` | ~140 | RF-10 |
| `synapses.py` | Grafo puro: `establecer_asociacion`, `obtener_asociaciones_enriquecidas`, `expandir_contexto_vecinos`, `_expandir_contexto_bfs`, `_evocacion_por_cadena`, `_reconstruir_camino`, `aplicar_refuerzo_dopaminergico`, `_multihop_vecinos` | ~523 **⚠ >500 — docstring justificación requerida** | RF-10 |
| `ingest.py` | Solo ingesta directa: `percibir_corto_plazo`, `consolidar_concepto` | ~122 | RF-10 |
| `episodes.py` | `_expandir_episodio_temporal`, `_afinidad_temporal_pool`, `_ts_nodo` | ~120 | RF-10 |
| `quarantine.py` | `mover_a_cuarentena`, `rescatar_de_cuarentena`, `buscar_en_cuarentena`, `purgar_cuarentena_vencida`, `_candidatos_eviccion`, `_ejecutar_eviccion` | ~180 | RF-10 |
| `consolidation.py` | `ciclo_sueno_consolidacion` (~505 líneas — **deuda técnica**), `_auto_generar_co_ocurrencia`, `_clasificar_nodo_wordnet`, `_calcular_base_level_actr` | ~694 **⚠ DEUDA — excepción 800 aplica (<800)** | RF-10, RNF-1.3 |
| `telemetry.py` | `_crear_tabla_historial_si_falta`, `_benchmark_rendimiento`, `_ultimo_benchmark`, `actualizar_log_busqueda`, `obtener_provenance_ultimo_resultado` | ~170 | RF-10 |
| `adn.py` | Solo las 3 funciones de firma ADN pura: `_cargar_firmas_adn`, `_persistir_firma_adn`, `_enriquecer_con_adn` | ~90 | RF-10 |
| `scoring.py` | `_calcular_score_hibrido`, `_calcular_jsd`, `_jsd_weight_adaptativo`, `_ncd_sim`, `_ncd_sims_pool`, `_analogia_scores_pool`, `_idf_tokens_qcr`, `_calcular_jaccard`, `_calcular_bm25_bayesiano`, `_agregar_prefix_wildcards`, `_pesar_tokens_query`, `_rerank_jaccard_protect_r0` (closures intactos, CL-1) | ~420 | RF-10 |
| `umbral.py` | Cluster calibración: `_preparar_datos_calibracion`, `entrenar_calibracion`, `calibrar_umbral_conforme`, `_score_con_calibracion`, `_debe_responder`, `buscar_con_calibracion`, `_contar_nodos_corpus`, `_cargar_calibracion_persistida`, `_persistir_calibracion`, `calibrar_y_persistir`, `nivel_certeza`, `confianza_calibrada` | ~430 | RF-10 |
| `context.py` | Solo epistémico y contexto: `_epistemico_coherencia_dimensional`, `_epistemico_evaluar`, `_epistemico_publicar`, `_epistemico_publicar_sin_consulta`, `_epistemico_encolar_vacio` | ~200 | RF-10 |
| `catalog_methods.py` | `listar_categorias`, `_resolver_categoria_id`, `_resolver_dimension_ids`, `_obtener_arbol_dimensiones`, `sync_status`, `sync_marcado`, `sync_limpiar` | ~110 | RF-10 |
| `rafaga.py` | `buscar_por_rafaga` (~343 líneas de cuerpo), `validar_rafaga` | ~370 **(bajo 500, no se parte)** | RF-10 |
| `search.py` | `buscar_por_frase` (~2 109 líneas — **deuda técnica**, funciones anidadas: `_fts_safe_term`, `_fts_safe_phrase`, `strip_accents`, `_calc_strict_cov`), `_generar_variaciones`, `buscar_recuerdo_microsegundos`, `buscar_todos_recuerdos`, `buscar_recuerdo_profundo`, `buscar_por_tokens`, `buscar_por_predicados`, `_fallback_busqueda_predicados`, `_buscar_en_contenido`, `_buscar_todos_en_contenido` | ~2 500 **⚠ DEUDA — excepción 800 aplica** | RF-10, RNF-1.3, CL-1 |

**Nota fachada `core/memory_store.py`:** Después de la Fase 3, contiene `__init__` (bootstrap), `cerrar_sistema` (junto a `__init__`, no delegado), re-exports y delegadores con firma completa (RF-8, prohibido `*args, **kwargs`). Estimado: **~450 líneas** (techo orientativo 400, tope duro 500 — RNF-1.4). Si la fachada supera 500 por firmas completas y exhaustivas, la justificación de una línea en docstring basta; no se parte la fachada ni es causal de fallo.

**Delegadores `@staticmethod` sin `self`:** `_ncd_sim`, `_jsd_weight_adaptativo`, `_calcular_jsd` y `_calcular_bm25_bayesiano` son `@staticmethod`. La fachada `SQLiteMemoryBioRAG` CONSERVA el `@staticmethod` con la misma firma sin `self` (delegando a `scoring.<metodo>(...)`), garantizando que llamadas sobre la clase (`SQLiteMemoryBioRAG._ncd_sim` en `tests/test_ncd_e6.py`, `SQLiteMemoryBioRAG._jsd_weight_adaptativo` en `tests/test_jsd_adaptativo_e7.py`) y llamadas sobre instancia (`self.X()` en `buscar_por_frase`) funcionen idénticamente. El cuerpo se muda a `scoring.py` como función/staticmethod sin `self`. `_calcular_bm25_bayesiano` se trata igual.





---

### Archivos raíz conservados como shims / puntos de entrada (RF-3)

| Archivo | Rol post-migración | Tamaño objetivo |
|---|---|---|
| `mcp_server.py` | Shim: re-exporta `_build_server` y `main` desde `core.mcp_server.server`, incluye bloque `if __name__ == "__main__": sys.exit(main())` (RF-3.1). Último commit Fase 2. | ≤ 15 líneas |
| `biorag.py` | Sin cambios hasta validar Fase 3 completa. Re-exporta `SQLiteMemoryBioRAG`. | Sin tocar |
| `core/memory_store.py` | Fachada delgada con `__init__`, re-exports y ~99 delegadores de una línea. | ~450 líneas |

---

## Modelo de datos interno

No hay cambios de esquema SQLite. El modelo de datos de la DB (`largo_plazo`, `sinapsis`, `calibracion_estado` y resto de tablas) permanece **100% congelado** (RF-4). La modularización es de código Python únicamente.

### Estado mutable en memoria

| Variable / Objeto | Dónde vive | Quién accede |
|---|---|---|
| `_sesiones_activas: dict[str, float]` | `core/mcp_server/_shared.py` | `session.py`, submódulos que consulten sesiones |
| Singleton `SQLiteMemoryBioRAG` | `core/memory_service.py` → `_get_cerebro()` en `_shared.py` | Todos los submódulos MCP vía `_get_cerebro()` |
| Caches ADN, flags en caliente | Atributos de instancia en `SQLiteMemoryBioRAG` | Solo accesibles vía `self.X` en funciones de módulo |

**Invariante RF-9:** Variables globales mutables prohibidas en submódulos. El estado queda en la instancia (`self`) o en `_shared.py` para estado MCP compartido.

**Invariante CL-2 (dirección de imports):** En `core/mcp_server/`, los submódulos importan `_shared`; `server.py` es el único que importa submódulos — nunca al revés. En `core/memory/`, los submódulos **no** importan la fachada `core.memory_store` — la fachada importa los submódulos, nunca al revés.

**Invariante CL-3 (CI):** `scripts/test_regresion_scoring.py` y `scripts/test_concept_hub.py` están referenciados por ruta en `.github/workflows/ci.yml` (L40, L44). Esta spec no mueve scripts; las rutas en CI permanecen intactas.

---

## Algoritmos y lógica interna

### A1 — Patrón de extracción: funciones de instancia, @staticmethod y delegadores

Toda extracción de método de `SQLiteMemoryBioRAG` sigue este patrón invariante:

#### 1. Métodos de instancia (con `self`):
```python
# ANTES (en memory_store.py):
def metodo(self, arg1: str, arg2: int = 0) -> bool:
    self.conn.execute(...)
    return self.otra_funcion()

# DESPUÉS (en core/memory/submodulo.py):
def metodo(self, arg1: str, arg2: int = 0) -> bool:      # ← misma firma, mismo cuerpo, sin tocar
    self.conn.execute(...)
    return self.otra_funcion()            # ← self.X() intacto, no se reescribe

# FACHADA (en core/memory_store.py):
def metodo(self, arg1: str, arg2: int = 0) -> bool:
    return submodulo.metodo(self, arg1, arg2)   # ← delegador con firma completa, prohibido *args/**kwargs
```
El cuerpo no se toca. `self` no se renombra. Las llamadas `self.X()` no se reescriben. `conn` nunca se pasa suelto.

#### 2. Métodos estáticos (@staticmethod sin `self`):
`_ncd_sim`, `_jsd_weight_adaptativo`, `_calcular_jsd` y `_calcular_bm25_bayesiano` son `@staticmethod`. Los tests llaman `SQLiteMemoryBioRAG._ncd_sim` y `SQLiteMemoryBioRAG._jsd_weight_adaptativo` sobre la clase (`tests/test_ncd_e6.py`, `tests/test_jsd_adaptativo_e7.py`), y `buscar_por_frase` los llama como `self.X()`.
- **En la fachada (`core/memory_store.py`):** Conserva el decorador `@staticmethod` con la misma firma completa delegando a `scoring.<metodo>(...)`.
- **En el submódulo (`core/memory/scoring.py`):** El cuerpo se muda intacto como función de módulo o `@staticmethod` sin `self`.
- `_calcular_bm25_bayesiano` (sin llamadores hoy) se trata de forma idéntica.

#### 3. Resolución de constantes globales y Monkeypatching en Tests (Paso 3.1):
Un `def` resuelve nombres globales en el módulo donde reside, no en `memory_store.py`. En el monolito, el código lee `JSD_ADAPTATIVO`, `NCD_ZLIB_LEVEL`, `STOPWORDS_ES`, etc., como nombres globales directos, y los tests unitarios los parchean mediante `monkeypatch` en `core.memory_store`.
- **Excepción única y obligatoria al "cuerpo intacto":** La calificación `constants.NOMBRE` se realiza una sola vez en el Paso 3.1 (T11), con las funciones todavía en la clase `SQLiteMemoryBioRAG` dentro de `core/memory_store.py`. Cada lectura de constante de configuración pasa a calificarse como `constants.NOMBRE` (importando `constants` desde `core.memory.constants`). No se toca ninguna otra línea: ni un `if`, ni un SQL, ni una fórmula matemática.
- `logger` no es una constante: no se prefija. Cada submódulo define su propio `logger`. `constants.py` no importa la fachada. `core.memory_store` re-exporta las constantes para compatibilidad.
- **Sincronización de tests en el mismo commit (Paso 3.1):** En ese mismo commit, el `monkeypatch` de los tests correspondientes pasa de `core.memory_store.FLAG` a `core.memory.constants.FLAG`. Las mudanzas posteriores de submódulos no reescriben eso: el cuerpo ya dice `constants.NOMBRE` y el submódulo importa `constants`.
- **Actualización de asserts literales (Paso 3.1):** En ese mismo commit del Paso 3.1, los 4 asserts que inspeccionan el texto exacto actualizan su cadena literal esperada:
  1. `tests/test_dim_escape.py`: `DIM_ESCAPE` → `constants.DIM_ESCAPE`
  2. `tests/test_dim_resonancia.py`: `"if DIM_RESONANCIA:"` → `"if constants.DIM_RESONANCIA:"`
  3. `tests/test_ncd_e6.py`: `"NCD_PESO * ncd_score"` → `"constants.NCD_PESO * ncd_score"`
  4. `tests/test_qcr_typo_d4.py`: la llamada con `QCR_TYPO_DIST`, al texto que quede tras calificar la constante y `_qcr_todos_cercanos`.
  El resto de los asserts se mantiene intacto. Queda prohibido borrar o debilitar tests.

#### 4. Tests que inspeccionan código fuente con `inspect.getsource` (Adaptación progresiva):
- En el Paso 3.4a (T16): solo se redirige el `inspect.getsource` de `_calcular_score_hibrido` (en `tests/test_ncd_e6.py`) hacia `core.memory.scoring._calcular_score_hibrido`.
- En el Paso 3.4h (T19), cuando se traslada `buscar_por_frase` a `core.memory.search`: se redirige el `inspect.getsource` de `tests/test_jsd_adaptativo_e7.py` hacia `core.memory.search.buscar_por_frase` (ya que vigila la llamada dentro de esa función), junto a `tests/test_dim_escape.py`, `tests/test_dim_resonancia.py`, `tests/test_qcr_idf_e3.py` y `tests/test_qcr_typo_d4.py`.
- Lo que el assert busca en el cuerpo se mantiene idéntico. No se borra ni se debilita ningún test.

### A2 — Regla de selección _shared.py vs local

```
¿El helper lo usan ≥ 2 submódulos?       → _shared.py
¿Es estado compartido (_sesiones_activas)? → _shared.py
¿Es constante global (LIMITE_MCP, etc)?   → _shared.py
En cualquier otro caso:                   → queda en su único submódulo
```

### A3 — Generación del golden reducido (~120 IDs, Fase 0)

Harness local (no se commitea como script nuevo en `scripts/`): reutiliza el mismo protocolo de `evaluar_qa.py` (resolución de etiquetas y exclusión de `ambiguo` incluidas sobre `snapshots/qa_escape_qcr_20260811.db`). Lee los 921 casos, calcula la distribución por categoría, toma una muestra proporcional + pocos negativos, escribe los IDs a `golden_ids_reducido.txt`. Solo la lista de IDs se commitea si Dennys lo autoriza tras revisarla. Los IDs no se vuelven a sortear nunca.

### A4 — Orden de extracción MCP (Paso 2.2)

`communication.py` primero, `catalog.py` segundo, avanzando en orden creciente de dependencias hacia `search.py` (mayor acoplamiento, última). En cada commit intermedio, `_build_server()` devuelve siempre 42 tools (CL-6).

### A5 — Transición incremental de `_build_server`

```
Commit N:     _build_server llama register() de los X módulos ya extraídos
              + mantiene inline el cuerpo de las (42−X) tools restantes
              → Gate Nivel 0: siempre 42 names + 2 resources + 1 prompt ✓

Commit final: _build_server solo llama register() × 15 submódulos
              → mcp_server.py raíz se reemplaza por shim ≤ 15 líneas
```

---

## Decisiones técnicas y arquitectura

### D1 — Paquetes, no módulos planos

- **Decisión:** `core/mcp_server/` y `core/memory/` son paquetes Python con `__init__.py` vacío.
- **Alternativa descartada:** módulos únicos `core/mcp_server.py` y `core/memory.py`.
- **Por qué:** La división en 15 submódulos (con `register()`) más `server.py` y `_shared.py` supera el límite por archivo. El paquete permite añadir submódulos sin renombrar el módulo padre. La convención de import queda estable.
- **Restricción de constitución:** Pilar 1 — el paquete no altera las rutas de import externas.

### D2 — `_shared.py` como única fuente de verdad MCP

- **Decisión:** Un único `_shared.py` centraliza estado, constantes y helpers usados por ≥ 2 submódulos. Los helpers de uso único quedan en su submódulo.
- **Alternativa descartada:** Copiar globals en cada submódulo.
- **Por qué:** Copiar produce divergencia de estado (`_sesiones_activas` desincronizado entre `session.py` y `write.py`). `_shared.py` con techo 500/800 evita el anti-patrón de monolito nuevo (CL-9).
- **Restricción clave (sin dos copias vivas):** `_shared.py` se crea vacío en el Paso 2.1. Se llena progresivamente: cuando un helper se muda a `_shared.py`, desaparece de `mcp_server.py` en el mismo commit. Nunca hay dos copias vivas del mismo helper.

### D3 — Fachada con delegadores con firma completa (RF-8, RNF-1.4), sin `__getattr__`

- **Decisión:** Cada método tiene un delegador explícito con firma completa (parámetros, nombres, tipos y defaults — prohibido `*args, **kwargs`) en `core/memory_store.py`.
- **Alternativa descartada:** `__getattr__` mágico o delegadores abreviados con `*args, **kwargs`.
- **Por qué:** Manda RF-8. Si la fachada supera 500 líneas debido a las firmas largas y completas, la justificación de una línea en docstring basta (RNF-1.4); no es causal de fallo ni se parte la fachada.
- **Restricción de constitución:** Pilar 3 (fallos visibles): un método sin delegador falla explícitamente en runtime.

### D4 — `core/memory/__init__.py` vacío (no re-exporta la clase)

- **Decisión:** `core/memory/__init__.py` es vacío. La API pública sigue siendo `from core.memory_store import SQLiteMemoryBioRAG`.
- **Alternativa descartada:** Re-exportar la clase para comodidad.
- **Por qué:** Dos caminos de import para la misma clase generan ambigüedad en `isinstance()`. El paquete `core.memory` lo importa solo la fachada (CL-8).
- **Restricción de constitución:** Pilar 1 — los consumidores existentes importan de `core.memory_store`; ese path no desaparece.

### D5 — `core.paths.project_root()` para rutas de entorno en todo bloque movido

- **Decisión:** Todo bloque movido que use `_PROJECT_ROOT` o `__file__` pasa a usar `core.paths.project_root()`. En el Paso 2.4 (T10), `server.py` ejecuta el arranque a nivel de módulo al importarse (`load_dotenv`, `logging.basicConfig`, warmup WordNet, `sys.path.insert` con `core.paths.project_root()`). FastMCP se instancia dentro de `_build_server()`, igual que hoy. En el Paso 2.4 se ejecuta la validación CWD desde `/tmp`.
- **Alternativa descartada:** Ejecutar validación CWD en el Paso 2.1 (cuando `server.py` está vacío y el arranque sigue en la raíz).
- **Por qué:** En el Paso 2.1 el arranque aún reside en la raíz; el test miraría el archivo incorrecto. En el Paso 2.4 el shim delega a `server.py` y se valida la resolución de paths.

### D6 — Deuda técnica: funciones monolíticas se mueven intactas

- **Decisión:** `buscar_por_frase` (~2 109 líneas), `_recordar_impl` (~753 líneas, L652–L1404 por AST), `_aprender_impl` (~321 líneas), `ciclo_sueno_consolidacion` (~506 líneas) y `_crear_estructura_cerebral` (~514 líneas) se trasladan completas, sin partición interna.
- **Alternativa descartada:** Subdividir en esta iteración.
- **Por qué:** La partición interna es reescritura, que la spec prohíbe explícitamente (RNF-1.3). La excepción del tope de 800 aplica al archivo que aloja la función monolítica; el resto del código del archivo sí queda bajo 800. La deuda se registra en la tabla de cierre de módulo.
- **Restricción de constitución:** Pilar 1 — tocar el cuerpo es el riesgo mayor; mover es seguro.

### D7 — Entorno determinista para golden

- **Decisión:** Todas las corridas de gate usan `PYTHONHASHSEED=0`, `BIORAG_NO_LOG=1`, `BIORAG_DMN_ESTADO_PATH` fuera del repo. El entorno se congela en `entorno_golden.json` con versiones exactas de Python, numpy, SQLite.
- **Alternativa descartada:** Comparar solo métricas agregadas (Recall@5 global).
- **Por qué:** Dos corridas con hash seeds distintos pueden producir Top-5 en distinto orden. El golden compara caso a caso (4 decimales) para detectar cualquier regresión de comportamiento (CL-10).

### D8 — Latencia: excepción explícita al revert automático

- **Decisión:** Variaciones de latencia no disparan revert automático. Dennys juzga el lag revisando el informe de gate.
- **Alternativa descartada:** Aplicar revert si p95 aumenta más de N%.
- **Por qué:** Dos corridas idénticas del mismo código ya varían por ruido de máquina. Un umbral fijo produciría falsos reverts. El revert es exclusivamente por Top-5 o score distinto (CC1, RF-26).

---

## Contrato de interfaces externas

### Puntos de entrada congelados (RF-1, RF-2, RF-3)

| Interfaz | Contrato | Verificación |
|---|---|---|
| `mcp_server.main()` | Arranca el servidor MCP; mismo comportamiento observable | Smoke test + fuzz_qa.py |
| `mcp_server._build_server()` | Devuelve exactamente 42 `name=`, 2 resources, 1 prompt | Gate Nivel 1: listado de names |
| `core.memory_store.SQLiteMemoryBioRAG` | Mismas firmas de todos los métodos públicos | pytest tests/ -v (264 tests) |
| `core.memory_store.normalizar_sustantivos_clave` | Misma firma y comportamiento | tests existentes |
| `biorag.main()` | Mismo comportamiento CLI | pytest tests/test_biorag_cli.py |

### Imports externos registrados (no se rompen)

```python
from mcp_server import _build_server   # scripts/fuzz_qa.py, test_memory.py:1146
import mcp_server as m                 # tests/test_sustantivos_clave_tools.py, test_bateria_extraccion.py, test_sustantivos_clave_recordar.py, test_sustantivos_clave_validacion.py
from core.memory_store import SQLiteMemoryBioRAG       # biorag.py, mcp_server.py, tests
from core.memory_store import normalizar_sustantivos_clave  # scripts/
```

El shim raíz `mcp_server.py` re-exporta `_build_server` y `main`. Un `grep` previo al commit del shim confirma que no existen otros imports a re-exportar (CL-7).

---

## Secuencia de fases y harness de Fase 0

### Fase 0 — Harness local (sin commitear scripts nuevos en `scripts/`)

Todo el tooling de Fase 0 se implementa como un harness local que reutiliza el mismo protocolo de `evaluar_qa.py` (resolución de etiquetas y exclusión de `ambiguo` sobre `snapshots/qa_escape_qcr_20260811.db`). No se crean 6 scripts nuevos en `scripts/`. Los artefactos generados son:

| Artefacto | Propósito | Commiteable |
|---|---|---|
| `golden_921.jsonl` | 921 casos con env determinista (Top-5 + scores 4 decimales sobre `snapshots/qa_escape_qcr_20260811.db`) | Solo si Dennys autoriza |
| `golden_ids_reducido.txt` | ~120 IDs proporcional a categoría + pocos negativos | Solo si Dennys autoriza |
| `entorno_golden.json` | Python version, numpy version, SQLite version, variables `BIORAG_*` | Solo si Dennys autoriza |
| Snapshot ANTES de Base Viva | `sqlite3.backup()` + `PRAGMA wal_checkpoint(TRUNCATE)` de la **base viva real** `MemoryBioRAG_Data/memory_biorag.db` — inmutable. **Fuera del árbol del repo**, en ruta que Dennys indique al inicio de la Fase 0. | No |
| Backup completo del repo | Copia íntegra del repo. **Fuera del árbol del repo**, en ruta que Dennys indique. No se usa `_backup_monolito_pre_modularizacion/`. No se edita `.gitignore`. | No |
| Verificación auto-identidad | Segunda corrida del golden, comparación línea a línea | No (resultado pass/fail) |

**Al inicio de la Fase 0, el agente pregunta a Dennys la ruta destino fuera del árbol para el backup del repo y el snapshot ANTES de la base viva.** No se hardcodea ninguna ruta.

### Fase 1 — Preparación mínima (sin mover módulos, sin tocar docstrings de monolitos)

No se editan docstrings ni comentarios de `mcp_server.py` ni de `core/memory_store.py` (para no ensuciar el diff de la mudanza posterior). `ARCHITECTURE.md` puede esperar a que los módulos existan (Fase 2/3). Verificar `pytest tests/ -v` sigue en verde. Un único commit de preparación si hay algo que preparar.

### Fase 2 — Orden estricto de extracción MCP

```
2.0  (rama ya existe: modularizacion-arquitectura)
2.1  Crear core/mcp_server/__init__.py (vacío) + _shared.py (vacío) + server.py (vacío)
     Nada de _build_server() inline en este paso.
     → Gate Nivel 0 ✓ → commit → push
2.2a Extraer communication.py  → Gate Nivel 0 ✓ → commit → push
2.2b Extraer catalog.py        → Gate Nivel 0 ✓ → commit → push
2.2c Extraer synapses.py       → Gate Nivel 0 ✓ → commit → push
2.2d Extraer concept_hub_tools.py → Gate Nivel 0 ✓ → commit → push
2.2e Extraer introspection.py  → Gate Nivel 0 ✓ → commit → push
2.2f Extraer consolidation.py  → Gate Nivel 0 ✓ → commit → push
2.2g Extraer daemon.py         → Gate Nivel 0 ✓ → commit → push
2.2h Extraer session.py        → Gate Nivel 0 ✓ → commit → push
2.2i Extraer oracle.py         → Gate Nivel 0 ✓ → commit → push
2.2j Extraer sync.py           → Gate Nivel 0 ✓ → commit → push
2.2k Extraer calibrar.py       → Gate Nivel 0 ✓ → commit → push
2.2l Extraer resources.py      → Gate Nivel 0 ✓ → commit → push
2.2m Extraer prompt.py         → Gate Nivel 0 ✓ → commit → push
2.2n Extraer write.py          → Gate Nivel 0 ✓ → commit → push
2.2o Extraer search.py (último, mayor acoplamiento)
     → Gate Nivel 0 + Nivel 1 ✓ → commit → push
2.3  Consolidar server.py como cableado puro (solo register() × 15)
     → Gate Nivel 1 (42 names + 2 resources + 1 prompt verificados) ✓ → commit → push
2.4  Reemplazar mcp_server.py raíz por shim ≤ 15 líneas
     (Efectos de arranque al importar server.py; validación CWD desde /tmp)
     → Gate Nivel 1 ✓ → commit → push
```

### Fase 3 — Orden estricto de extracción Memory

```
3.0  Crear core/memory/__init__.py (vacío)
     → commit
3.1  Extraer constants.py + funciones de módulo puras
     (normalizar_sustantivos_clave, _qcr_levenshtein, _qcr_todos_cercanos)
     Calificación constants.NOMBRE en core/memory_store.py
     Sincronización de monkeypatches en tests a core.memory.constants.FLAG
     Actualización de 4 asserts literales (DIM_ESCAPE, DIM_RESONANCIA, NCD_PESO, QCR_TYPO_DIST)
     core/memory_store.py re-exporta constantes y funciones puras
     → Gate Nivel 0 ✓ → commit → push
3.2a Extraer comms.py          → Gate Nivel 0 ✓ → commit → push
3.2b Extraer telemetry.py      → Gate Nivel 0 ✓ → commit → push
3.3a Extraer synapses.py        → Gate Nivel 0 ✓ → commit → push
3.3b Extraer episodes.py        → Gate Nivel 0 ✓ → commit → push
3.3c Extraer quarantine.py      → Gate Nivel 0 ✓ → commit → push
3.3d Extraer ingest.py          → Gate Nivel 0 ✓ → commit → push
     (solo percibir_corto_plazo, consolidar_concepto)
3.3e Extraer dmn.py             → Gate Nivel 0 ✓ → commit → push
3.3f Extraer consolidation.py   → Gate Nivel 0 + Nivel 1 ✓ → commit → push
     (_auto_generar_co_ocurrencia, _clasificar_nodo_wordnet, _calcular_base_level_actr incluidos)
3.4a Extraer scoring.py         → Gate Nivel 0 + Nivel 1 ✓ → commit → push
     (Redirigir inspect.getsource de _calcular_score_hibrido en test_ncd_e6.py)
3.4b Extraer umbral.py          → Gate Nivel 0 ✓ → commit → push
3.4c Extraer context.py         → Gate Nivel 0 ✓ → commit → push
3.4d Extraer catalog_methods.py → Gate Nivel 0 ✓ → commit → push
3.4e Extraer adn.py             → Gate Nivel 0 ✓ → commit → push
3.4f Extraer schema.py          → Gate Nivel 0 + Nivel 1 ✓ → commit → push
     (_poblar_fts, _poblar_fts_unicode incluidos en el mismo commit)
3.4g Extraer rafaga.py          → Gate Nivel 0 ✓ → commit → push
3.4h Extraer search.py (último, mayor riesgo)
     (Redirigir inspect.getsource en test_jsd_adaptativo_e7, test_dim_escape, test_dim_resonancia, test_qcr_*)
     → Gate Nivel 0 + Nivel 1 ✓ → commit → push
3.5  Consolidar fachada core/memory_store.py (~450 líneas, techo 400 orientativo / 500 duro con justificación si las firmas lo superan — RNF-1.4)
     cerrar_sistema queda en la fachada; wc -l auditoría completa
     → Gate Nivel 1 ✓ → commit → push
```

### Gate Nivel 2 — Final de toda la spec

```bash
./scripts/run_qa_suite.sh   # 100.00% Recall@5 (875/875), 0 fallos, 0.00% FP (0/40) sobre snapshots/qa_escape_qcr_20260811.db
python3 scripts/fuzz_qa.py  # 33/33 passed
# Verificación Dual no-tautológica (Pilar 5):
# ANTES: código pre-modularización corrido sobre una COPIA del snapshot de la BASE VIVA congelado en Fase 0 (MemoryBioRAG_Data/memory_biorag.db) → antes.jsonl
# DESPUÉS: código modularizado corrido sobre OTRA COPIA de ese mismo snapshot de base viva → despues.jsonl
# Comparación: antes.jsonl vs despues.jsonl → 100% identidad caso a caso
# NO se usa una copia fresca de la base viva al final (puede haber mutado durante el trabajo)
# El snapshot de la base viva de Fase 0 es el sustrato fijo e inmutable para ambas corridas.
```

El informe final auditado se entrega directamente a Dennys. El merge a master lo ejecuta Dennys (RF-17).

---

## Estrategia de tests

### Gate Nivel 0 — Por cada extracción individual

- `pytest tests/ -v` → 264 tests, 0 fallos, 0 errores, 0 skipped (RF-24.1)
- Smoke test de imports:
  ```bash
  python3 -c "from mcp_server import _build_server, main; print('OK')"
  python3 -c "from core.memory_store import SQLiteMemoryBioRAG, normalizar_sustantivos_clave; print('OK')"
  python3 -c "import biorag; print('OK')"
  ```
- Golden reducido (~120 IDs fijos): igualdad estricta Top-5 + scores 4 decimales vs baseline local (RF-24.3)
- **Inventario MCP (en Fase 2):** `_build_server()` devuelve exactamente 42 `name=`, 2 resources, 1 prompt. No se espera al Gate Nivel 1 para esto (RF-24.4).
- Counting: `wc -l` del archivo modificado; comparar contra estimado del plan.

### Gate Nivel 1 — Por cada módulo completo extraído

- Benchmark 921 casos: identidad exacta Top-5 + scores 4 decimales vs `golden_921.jsonl` (RF-25.1)
- Para módulos MCP: `_build_server()` devuelve exactamente 42 names + 2 resources + 1 prompt (RF-25.2, complementario al check del Nivel 0)
- Verificación de rutas de entorno (Criterio 8): se lanza un subproceso con `cwd=/tmp` y `PYTHONPATH=raíz_del_repo` que importa `core.mcp_server.server` y llama `_build_server()`. Confirma que `.env.local` y `estado_hormiga.json` se resuelven vía `core.paths.project_root()` independientemente del CWD. **No** se usa `os.chdir("/tmp")` seguido de import (rompe el path).

### Rollback

- Cualquier variación en Top-5 o score (4 decimales): `git revert <commit>` inmediato (RF-26)
- Latencia: se reporta en informe de gate, Dennys decide (CC1, RF-26)
- Gate rojo nunca se "arregla" regenerando el golden (CL-10)

### Tests de regresión clave

| Test | Qué cubre | RF |
|---|---|---|
| `tests/test_memory_core.py` (importa `test_memory.py:11`) | API completa `SQLiteMemoryBioRAG` | RF-1, RF-8 |
| `tests/test_sustantivos_clave_tools.py` | `import mcp_server as m` — shim funciona | RF-3, RF-2 |
| `tests/test_bateria_extraccion.py` | `import mcp_server as m` | RF-2, RF-3 |
| `tests/test_sustantivos_clave_recordar.py` | `import mcp_server as m` | RF-2, RF-3 |
| `tests/test_sustantivos_clave_validacion.py` | `import mcp_server as m` | RF-2, RF-3 |
| `scripts/fuzz_qa.py` (`from mcp_server import _build_server`) | 33 casos adversariales, shim funciona | RF-3, RF-27 |
| `scripts/run_qa_suite.sh` | 875/875 Recall@5, 0 FP | RF-27 |
| Golden reducido (~120 IDs) | Identidad exacta post cada extracción | RF-24, RF-25 |

---

## Auditoría de entrega (formato por commit)

Cada commit de cierre de módulo incluirá en el cuerpo del mensaje:

```
TABLA AUDITORÍA:
archivo                                  | wc -l
-----------------------------------------|------
core/mcp_server/communication.py        |   165
core/mcp_server/_shared.py              |   450

FUNCIONES:
función                  | wc -l | nota
-------------------------|-------|---------------
biorag_comunicar         |    38 |
biorag_leer_mensajes     |    67 |
_recordar_impl           |   753 | DEUDA TÉCNICA (L652–L1404)

DEUDA TÉCNICA PENDIENTE:
- buscar_por_frase (~2109 líneas) — pendiente Fase 3, Paso 3.4h
```

---

## Cobertura de RF (verificación completa)

| RF | Cubierto por | Sección |
|---|---|---|
| RF-1 | Delegadores explícitos en fachada; pytest 264 tests | D3, Tests |
| RF-2 | 42 names congelados en submódulos; Gate Nivel 1 | Estructura MCP, Gates |
| RF-3 | Shims en raíz conservados; imports registrados listados | Interfaz |
| RF-4 | Sin cambios DDL — fuera del scope de este plan | — |
| RF-5 | Tabla de 15 submódulos MCP (con `register()`) con distribución exacta | Estructura módulos MCP |
| RF-6 | Cada submódulo expone `register(mcp)` y docstring con names | Estructura módulos MCP |
| RF-7 | `core.paths.project_root()` en todo bloque movido que use `_PROJECT_ROOT` o `__file__` | D5 |
| RF-8 | Patrón A1 (función módulo con `self`, cuerpo intacto); delegadores con firma completa (sin `*args/**kwargs`) | A1, D3 |
| RF-9 | Estado en instancia o `_shared.py`; no globales en submódulos | Modelo datos |
| RF-10 | Cada cluster se extrae como bloque intacto; secuencia Fase 3 | Secuencia |
| RF-11 | Fachada ≤ 500 líneas, sin `__getattr__` | D3, Módulos memory |
| RF-12 | `constants.py` con re-export hacia consumidores externos | Módulos memory |
| RF-14 | Harness local de Fase 0 (sin 6 scripts nuevos); snapshot ANTES + backup repo | Fase 0 |
| RF-15 | Archivos sensibles fuera del scope; sin tocar | spec.md §RF-15 |
| RF-16 | Todo trabajo en `modularizacion-arquitectura` | Secuencia |
| RF-17 | Merge a master solo por Dennys tras Gate Nivel 2 | Gates |
| RF-18 | Commit atómico + push tras cada Gate Nivel 0 verde | Secuencia |
| RF-19 | Git revert inmediato si gate falla | Rollback |
| RF-20 | Mensajes de commit con tabla auditoría | Auditoría |
| RF-21 | Archivos prohibidos en commits (spec §RF-21) | — |
| RF-22 | `git add -A` y checkout ciego prohibidos | — |
| RF-23 | `PYTHONHASHSEED=0`, `BIORAG_NO_LOG=1`, `BIORAG_DMN_ESTADO_PATH` | D7 |
| RF-24 | Gate Nivel 0 detallado (pytest + smoke + golden reducido + inventario MCP en Fase 2) | Tests |
| RF-25 | Gate Nivel 1 detallado (921 casos + 42 names) | Tests |
| RF-26 | Revert por Top-5/score; excepción latencia explícita | D8, Rollback |
| RF-27 | Gate Nivel 2 detallado (run_qa_suite.sh + fuzz + Dual no-tautológico) | Tests |
| RNF-1 | `wc -l` para todo; topes orientativo/duro; deuda registrada | D6, Auditoría |
| RNF-2 | Latencia reportada en gate; sin deps externas nuevas | D8 |

> **RF-13 (hueco):** El hueco se mantiene. No se renumeran requisitos ya citados (A6).

---

*Plan guardado en `specs/003-modularizacion-arquitectura/plan.md`.*
*Todos los RF tienen cobertura.*
*La siguiente fase es **Fase 5: Tareas** — skill `sdd-tareas`.*
