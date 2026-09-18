# Tareas — Spec 003: Descubrimiento del Núcleo Temático por parte del Agente

## T1: Auditoría de brechas por superficie
- **RF cubiertos**: todos (diagnóstico previo)
- **Descripción**: Comparar la exposición de `deep` y `parafrasis` contra
  `sustantivos_clave` en las 11 superficies orientadas al agente, y ejecutar la
  documentación tal como está escrita para detectar ejemplos inviables.
- **Hecho cuando**:
  - [x] Tabla de brechas por superficie documentada en `spec.md`
  - [x] Hallazgo H-A verificado ejecutando el ejemplo verbatim de `config/prompts.py:69`
        → `SUSTANTIVOS_CLAVE_AUSENTES`, nodo NO guardado
  - [x] Hallazgo H-B verificado → `Categoria 'tipo' no existe. Validas: Architecture, ...`
  - [x] Comprobado que el alias legacy `buscar` NO aceptaba el parámetro
- [x] **Estado**: hecha

---

## T2: `ORACLE_PROMPT` — paridad con paráfrasis y ráfaga
- **RF cubiertos**: RF-D1
- **Descripción**: Plantilla propia de extracción (con la prueba del automóvil, la
  distinción `sustantivos_clave` ≠ `syn`, formato y circuito cerrado), 4 entradas nuevas
  en errores comunes, 2 ramas en el árbol de decisión y 2 pasos en el protocolo de
  guardado. Refuerzo de la regla de oro existente.
- **Hecho cuando**:
  - [x] `PLANTILLA SUSTANTIVOS_CLAVE` presente al nivel de `PLANTILLA PARÁFRASIS` / `PLANTILLA RÁFAGA`
  - [x] Errores comunes cubre: omisión al guardar, confusión con `syn`, mencionar vs tratar, omisión al buscar
  - [x] Árbol de decisión cubre búsqueda por TEMA y score bajo/ruido
  - [x] Protocolo de guardado lo lista como paso 2 (obligatorio)
  - [x] `mcp.instructions == ORACLE_PROMPT` (lo editado es lo que recibe el agente)
- [x] **Estado**: hecha — 7 tests en `TestRFD1InstruccionesDeSistema`

---

## T3: Warning pedagógico en runtime
- **RF cubiertos**: RF-D3, CL-D1, CL-D4
- **Descripción**: ⚠️ antepuesto al JSON cuando hay `query` y el núcleo está ausente o
  vacío, replicando el mecanismo de `parafrasis=None` / `dias=None` / `dimensiones=None`.
  No bloquea la búsqueda.
- **Hecho cuando**:
  - [x] Omitir el parámetro → warning con efecto (4.0x), criterio (TRATAN vs MENCIONAN) y ejemplo
  - [x] Convive con los warnings preexistentes sin reemplazarlos
  - [x] Proveerlo → no hay warning
  - [x] `""` se trata como omisión
  - [x] La búsqueda se ejecuta igual (`total >= 1`)
- [x] **Estado**: hecha — 5 tests en `TestRFD3WarningPedagogico`

---

## T4: Visibilidad del núcleo en cada resultado
- **RF cubiertos**: RF-D2, CL-D2, CL-D5, RNF-D2
- **Descripción**: Adjuntar `sustantivos_clave` y `sustantivos_clave_items` a cada item
  (resultados y contexto expandido) con batch queries, reutilizando el patrón de
  `dimensiones_semanticas`. Fallback `largo_plazo` → `corto_plazo`, tolerante a DB
  pre-migración.
- **Hecho cuando**:
  - [x] Nodo con núcleo → `sustantivos_clave='contaminacion,aire'` + `items=['contaminacion','aire']`
  - [x] Nodo legacy → `''` + `[]`
  - [x] Funciona también vía alias `buscar`
  - [x] 1 query batch por tabla (sin N+1)
- [x] **Estado**: hecha — 3 tests en `TestRFD2VisibilidadEnResultados`

---

## T5: Paridad del alias legacy `buscar`
- **RF cubiertos**: RF-D4, CL-D3
- **Descripción**: Agregar el parámetro al schema de `buscar`, pasarlo a `_recordar_impl`
  y documentarlo en la lista de parámetros de su descripción.
- **Hecho cuando**:
  - [x] `buscar(query, sustantivos_clave=...)` acepta y aplica el boost
  - [x] Término inválido vía alias → `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO`, búsqueda NO ejecutada
  - [x] Ranking idéntico entre `recordar` y `buscar` con el mismo input (paridad real, no solo kwarg aceptado)
  - [x] Parámetro opcional en el JSON Schema publicado
- [x] **Estado**: hecha — 3 tests en `TestRFD4AliasLegacyBuscar` + verificación manual de
  paridad (`nodo_boost` top-1 por ambas rutas)

---

## T6: Descripciones de tools y JSON Schema
- **RF cubiertos**: RF-D5
- **Descripción**: Documentar el parámetro en las descripciones de `recordar` (guía de
  modos, PASO 1, PARÁMETROS CLAVE), `buscar`, `aprender` (regla crítica + prueba del
  automóvil + distinción con `syn`) y `guardar`. Corregir el typo
  "boost de precisións" y agregar la nota textual que exige RF-19 del Spec 001.
- **Hecho cuando**:
  - [x] Las 6 tools relacionadas mencionan el parámetro en su descripción
  - [x] `aprender` advierte OBLIGATORIO y el código de error
  - [x] `guardar` lista el parámetro como REQUERIDO en su descripción (brecha detectada por el propio test)
  - [x] Nota textual de RF-19 presente en el schema del parámetro
  - [x] `recordar` explica el peso BM25 4.0x
- [x] **Estado**: hecha — 4 tests en `TestRFD5DescripcionesDeTools` (parametrizado sobre 6 tools)

---

## T7: Prompt MCP y observabilidad
- **RF cubiertos**: RF-D6, RF-D7
- **Descripción**: Regla del núcleo temático en `biorag-system-prompt` (el prompt que el
  agente copia a su system prompt) y registro del valor **normalizado** en
  `log_busquedas.params_json`.
- **Hecho cuando**:
  - [x] El prompt incluye la regla, el código de error, el ejemplo y las tools hermanas
  - [x] `' Servidor, CONEXIÓN '` se registra como `'servidor,conexion'` (normalizado, no el crudo)
  - [x] La omisión se registra como `None` (permite auditar adopción real)
- [x] **Estado**: hecha — 1 test en `TestRFD6PromptMCP` + 2 en `TestRFD7Observabilidad`

---

## T8: Documentación orientada al agente (RF-D8)
- **RF cubiertos**: RF-D8 (corrige H-A y H-B)
- **Descripción**: Corregir los ejemplos rotos y agregar el parámetro en las cuatro
  superficies que el agente o el humano leen fuera del servidor MCP.
- **Hecho cuando**:
  - [x] `config/prompts.py`: ejemplos de `aprender` con `sustantivos_clave` + `bridges`,
        `cat="tipo"` reemplazado por categorías válidas, gobernanza y PASO 1/PASO 2 con el
        parámetro, tools `biorag_sustantivos` / `biorag_agregar_sustantivos` listadas,
        conteo de tools corregido (23 → 42, verificado contra el servidor real)
  - [x] `AGENTS.md`: 4 filas nuevas en la tabla de pitfalls (omisión al guardar, confusión
        con `syn`, omisión al buscar, nodos legacy vacíos)
  - [x] `skills/biorag-sync/SKILL.md`: flujo INVARIANT (Paso 1/2/4) con el parámetro,
        ejemplos de `aprender` corregidos, tabla de tools actualizada + 2 tools nuevas
  - [x] `plugin/opencode-biorag-remember-plugin.ts`: `REMINDER_RECALL` instruye el boost y
        `REMINDER_BIORAG` advierte que sin el campo el guardado se rechaza
- [x] **Estado**: hecha

---

## T9: Métricas post-cambio y verificación final (RF-D9, RNF-D1)
- **RF cubiertos**: RF-D9, RNF-D1, RNF-D3
- **Descripción**: Ejecutar la suite oficial completa y comparar contra la baseline.
- **Hecho cuando**:
  - [x] `bash scripts/run_qa_suite.sh` → `EXIT=0`, `[GATE] OK`
  - [x] Recall@5 = 98.06% (baseline 98.06%) — sin cambio
  - [x] Recall@1 = 90.74% (baseline spec.md 90.74%) — sin cambio
  - [x] MRR = 0.9355 (baseline spec.md 0.9355) — sin cambio
  - [x] FP = 0.00% (0/40) — sin cambio
  - [x] Fallos = 17/875 (baseline 17) — sin cambio
  - [x] Concept Hub 5/5 (100%) CON HUB — sin cambio
  - [x] Abismo léxico 3/3 (100%) — sin cambio
  - [x] `scripts/test_regresion_scoring.py` → todos los tests pasan
  - [x] Suite completa: **295 passed / 0 failed** (263 previos + 32 nuevos, 0 regresiones)
  - [x] Artefactos generados por las corridas restaurados a HEAD (higiene: no commitear
        outputs con rutas del sandbox)
- [x] **Estado**: hecha — cero regresión. El motor de scoring, el esquema y los pesos BM25
  no se modificaron (RF-D9).

---

## Cobertura de requisitos

| RF | Implementación | Test |
|---|---|---|
| RF-D1 | `ORACLE_PROMPT` (mcp_server.py) | `TestRFD1InstruccionesDeSistema` (7) |
| RF-D2 | batch adjunto a items | `TestRFD2VisibilidadEnResultados` (3) |
| RF-D3 | bloque `_warnings` | `TestRFD3WarningPedagogico` (5) |
| RF-D4 | schema + pass-through en `buscar` | `TestRFD4AliasLegacyBuscar` (3) |
| RF-D5 | descripciones + JSON Schema | `TestRFD5DescripcionesDeTools` (9) |
| RF-D6 | `prompt_biorag()` | `TestRFD6PromptMCP` (1) |
| RF-D7 | `params_log` | `TestRFD7Observabilidad` (2) |
| RF-D8 | 4 archivos de documentación | verificación manual + ejemplos ejecutables |
| RF-D9 | ausencia de cambios en motor/schema | suite QA oficial + `test_regresion_scoring.py` |

Total: **32 tests nuevos**, suite global **295 passed**.
