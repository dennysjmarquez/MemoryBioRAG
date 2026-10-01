# Tareas — Spec 006: Convergencia Multi-Campo
## (v2 — Corregido tras revisión externa)

> **Objetivo**: Que un nodo con la búsqueda en 4/4 campos siempre supere a uno
> que solo la tiene en 1/4 (contenido). Sin tocar los 14 pesos del motor.

---

## T1: Capturar top-5 antes del cambio (smoke test baseline — copia segura)

- **RF cubiertos**: Criterio 7a
- **Descripción**: Crear `scripts/smoke_006.py` que:
  1. Haga una copia temporal de la DB de producción (`sqlite3.backup()`).
  2. Ejecute la búsqueda sobre la copia (no la original) con
     `BIORAG_DMN_SINTESIS_ACTIVA=0 BIORAG_NO_LOG=1`.
  3. Guarde el top-5 en `scripts/smoke_006_antes.json` con: posición, concepto,
     score, origen.
  4. Elimine la copia temporal al terminar.
- **Hecho cuando**:
  - [x] `scripts/smoke_006_antes.json` existe con el top-5 de la query.
  - [x] El JSON incluye posición, concepto, score y origen de cada nodo.
  - [x] Baseline capturado en copia temporal segura (`sqlite3.backup()`).
  - [x] La DB de producción no fue modificada por el script.
- [x] **Estado**: hecha

---

## T2: Constantes de configuración en `constants.py`

- **RF cubiertos**: RF-7, RF-7b, RF-8, CL-9
- **Descripción**: Añadir `CONVERGENCIA_ACTIVA` (bool) y `CONVERGENCIA_ALPHA` (float)
  leídas desde variables de entorno. Alpha restringido a **(0.0, 1.0) exclusive** —
  usar `logging.getLogger(__name__)` para el warning (no asumir `logger` preexistente).
- **Hecho cuando**:
  - [x] `BIORAG_CONVERGENCIA_ACTIVA=0` → `CONVERGENCIA_ACTIVA = False`
  - [x] `BIORAG_CONVERGENCIA_ALPHA=2.5` → `CONVERGENCIA_ALPHA = 0.99` + warning en log
  - [x] `BIORAG_CONVERGENCIA_ALPHA=0.0` → `CONVERGENCIA_ALPHA = 0.01` + warning en log
  - [x] `python3 -c "from core.memory import constants; print(constants.CONVERGENCIA_ALPHA)"` imprime `0.5` (sin warnings)
  - [x] `python3 -m pytest tests/test_convergencia_multi_campo.py::test_alpha_clamping -v` pasa
- [x] **Estado**: hecha

---

## T3: Mover `_ORIGENES_NO_LITERALES` + batch-fetch + multiplicador

- **RF cubiertos**: RF-1..RF-10, CL-1..CL-9, RNF-1..5
- **Descripción**: Esta es la tarea central. En `search.py`:
  1. **Mover** `_ORIGENES_NO_LITERALES` a nivel de módulo (ahora está en L1907,
     después del loop; debe estar antes).
  2. **Añadir batch-fetch** de `sustantivos_clave` usando la lista `conceptos_todos`
     que ya existe (no `conceptos_con_sinonimos` — ese nombre no existe en el código).
  3. **Definir** `_campo_activo(texto)` usando `_tokenizar_normalizado` (ya importada
     en L1457) — comparación de conjuntos de tokens, **nunca** substring con `.lower()`.
  4. **Aplicar** el multiplicador post-scoring con el bypass correcto:
     no `match_exacto`, y origen consultado via `origen_scores.get(concepto, ...)`.
- **Hecho cuando**:
  - [ ] `_ORIGENES_NO_LITERALES` está a nivel de módulo (accesible desde el loop).
  - [ ] `sustantivos_map` se construye con 1 sola query SQL usando `conceptos_todos`.
  - [ ] `_campo_activo` usa `_tokenizar_normalizado` (conjunto, no substring).
  - [ ] Nodo con tokens en 4/4 campos → multiplicador = 1.0.
  - [ ] Nodo con tokens solo en `contenido` → multiplicador = 0.625 (alpha=0.5).
  - [ ] `BIORAG_CONVERGENCIA_ACTIVA=0` → score idéntico al baseline.
  - [ ] Origen `sdm` / `semantica` / `dimensional_fallback` → multiplicador = 1.0.
  - [ ] `match_exacto=True` → multiplicador = 1.0.
  - [ ] `pytest tests/test_convergencia_multi_campo.py -v` → 7 tests en verde.
- [ ] **Estado**: pendiente

---

## T4: Tests unitarios (`test_convergencia_multi_campo.py`)

- **RF cubiertos**: Criterios de finalización 3, 4, 5, 6
- **Descripción**: Crear los 7 tests unitarios. Nota crítica: el test de 500
  repeticiones verifica que el **multiplicador** sea idéntico, no el score final
  (BM25 puede variar con frecuencia, la convergencia no).
  Para probar distintos valores de `CONVERGENCIA_ALPHA`, usar `importlib.reload`
  o subprocess — no cambiar env vars después de importar.
- **Hecho cuando**:
  - [ ] `pytest tests/test_convergencia_multi_campo.py -v` → 7 tests en verde, 0 fallidos.
  - [ ] Test 1: 4/4 campos activos da score final mayor que 1/4, con mismo score base.
  - [ ] Test 2: El **multiplicador** es idéntico para 1 o 500 repeticiones en contenido.
  - [ ] Test 3: Flag desactivado → multiplicador = 1.0.
  - [ ] Test 4: `match_exacto=True` → multiplicador = 1.0.
  - [ ] Test 5: origen `sdm` → multiplicador = 1.0.
  - [ ] Test 6: tokens vacíos (query stopwords) → multiplicador = 1.0.
  - [ ] Test 7: alpha=2.5 → warning en log + CONVERGENCIA_ALPHA = 0.99.
- [ ] **Estado**: pendiente

---

## T5: Validación final — benchmark + smoke test + R@1/MRR explícito

- **RF cubiertos**: RNF-5, Criterios 1, 2, 7b
- **Descripción**: Doble verificación post-implementación:
  (a) Gate automático del benchmark.
  (b) Verificación explícita de Recall@1 y MRR — el gate solo verifica Recall@5.
  (c) Smoke test de posición relativa sobre copia temporal de producción.
- **Hecho cuando**:
  - [ ] `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py`
        produce `[GATE] OK`.
  - [ ] Verificación explícita pasa:
        `qa_metrics.json: recall_at_1 ≥ 88.76%` y `mrr ≥ 0.916`.
  - [ ] `scripts/smoke_006_despues.json` existe con el nuevo top-5 (copia temporal).
  - [ ] **Posición** de `version_actual_biorag` < posición de `reindex_selectivo_dirty`
        en el nuevo top-5. (El score absoluto puede bajar — lo que importa es el orden.)
  - [ ] Los 5 nodos del nuevo top-5 son temáticamente coherentes con "versión de biorag".
  - [ ] La DB de producción no fue modificada.
- [ ] **Estado**: pendiente

---

## Cobertura de requisitos

| RF | Cubierto por |
|----|--------------|
| RF-1 | T3 |
| RF-2 | T3, T4 |
| RF-3 | T3, T4 |
| RF-4 | T3, T4 |
| RF-5 | T3, T4 |
| RF-6 | T3, T4 |
| RF-7 | T2, T3, T4 |
| RF-7b | T2, T4 |
| RF-8 | T2, T4 |
| RF-9 | T3, T4 |
| RF-10 | T3 |
| RNF-1 | T3 |
| RNF-2 | T3 |
| RNF-3 | T3 |
| RNF-4 | T3 |
| RNF-5 | T5 |
| CL-1..CL-9 | T3, T4 |
| Criterio 7a | T1 |
| Criterio 7b | T5 |
