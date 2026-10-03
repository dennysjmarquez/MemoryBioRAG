# Tareas — Spec 007: Convergencia Multi-Campo (Bonus Aditivo Post-QCR)

> Plan base: `specs/007-convergencia-multi-campo/plan.md`
> Orden de ejecución: T1 → T2 → T3 → T4 → T5.
> Cada tarea ≤ 30 min. No avanzar a la siguiente sin que los checks de la actual estén en verde.

---

## T1: Añadir `CONVERGENCIA_BONUS_MAX` a `constants.py`

- **RF cubiertos**: RF-7, RF-7b, RF-8, RF-9, CL-9
- **Descripción**: En `core/memory/constants.py`, añadir lectura de `BIORAG_CONVERGENCIA_BONUS_MAX`
  con clamp (`0.001` si ≤ 0, `1.0` si > 1.0) y `logging.warning` para cada caso
  fuera de rango. Mantener `CONVERGENCIA_ALPHA` intacta por retrocompatibilidad.
- **Hecho cuando**:
  - [ ] `constants.CONVERGENCIA_BONUS_MAX` existe y su valor por defecto es `0.05`.
  - [ ] Con `BIORAG_CONVERGENCIA_BONUS_MAX=-1`, `constants.CONVERGENCIA_BONUS_MAX == 0.001`
        y el log contiene `"<= 0; usando 0.001"`.
  - [ ] Con `BIORAG_CONVERGENCIA_BONUS_MAX=2.5`, `constants.CONVERGENCIA_BONUS_MAX == 1.0`
        y el log contiene `"> 1.0; usando 1.0"`.
  - [ ] `constants.CONVERGENCIA_ALPHA` sigue existiendo con el mismo valor que antes.
  - [ ] `pytest tests/test_convergencia_multi_campo.py::test_bonus_max_clamp_bajo -q` pasa.
  - [ ] `pytest tests/test_convergencia_multi_campo.py::test_bonus_max_clamp_alto -q` pasa.
- [ ] **Estado**: pendiente

---

## T2: Crear `tests/test_convergencia_multi_campo.py` con 7 tests unitarios

- **RF cubiertos**: RF-2, RF-4, RF-5, RF-6, RF-7, RF-7b, RF-8, RF-11, CL-3, CL-9
- **Descripción**: Crear el archivo de tests antes de modificar `search.py`. Los tests
  deben ser puros y directos:
  1. `test_canales_4_4_supera_1_4` — dado mismo `score_base`, nodo 4/4 supera a nodo 1/4.
  2. `test_binario_500_vs_1_mismo_bonus` — 500 menciones en `contenido` == 1 mención.
  3. `test_desactivado_bonus_cero` — `CONVERGENCIA_ACTIVA=False` → sort key = `score_base`.
  4. `test_score_base_r4_intacto` — las tuplas no mutan: `r[4]` = `score_base`.
  5. `test_qset_vacio_no_aplica` — `q_set = set()` → bloque convergencia no se ejecuta.
  6. `test_bonus_max_clamp_bajo` — clamp de valor inferior.
  7. `test_bonus_max_clamp_alto` — clamp de valor superior.
- **Hecho cuando**:
  - [ ] El archivo `tests/test_convergencia_multi_campo.py` existe.
  - [ ] Tests 6 y 7 pasan (T1 completado).
  - [ ] Tests 1–5 están escritos y fallan (RED) a la espera de la implementación en `search.py`.
  - [ ] `pytest tests/test_convergencia_multi_campo.py -q` muestra 2 PASSED y 5 FAILED.
- [ ] **Estado**: pendiente

---

## T3: Eliminar bloque multiplicativo v1 de `search.py`

- **RF cubiertos**: RF-11, RF-12, CL-5, CL-7
- **Descripción**: En `core/memory/search.py`, eliminar el bloque previo
  `# ── Convergencia Multi-Campo (Spec-006) ──` (L1739–L1756).
  `score_hibrido` pasa directamente a `r[4]` sin ninguna modificación multiplicativa.
- **Hecho cuando**:
  - [ ] Las líneas L1739–L1756 ya no existen en `search.py`.
  - [ ] `pytest tests/ -q --ignore=tests/test_convergencia_multi_campo.py` pasa con 0 regresiones.
  - [ ] El test `test_score_base_r4_intacto` pasa (r[4] = score_base sin tocar).
  - [ ] `pytest tests/test_convergencia_multi_campo.py -q` muestra 3 PASSED (tests 4, 6, 7).
- [ ] **Estado**: pendiente

---

## T4: Añadir sort por bonus aditivo post-sort-monotónico en `search.py`

- **RF cubiertos**: RF-1, RF-2, RF-3, RF-4, RF-5, RF-6, RF-10, RF-11, RF-12, RF-13, CL-1..CL-8, CL-10, RNF-1..RNF-4
- **Descripción**: En `core/memory/search.py`, inmediatamente después de
  `resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)` (~L1995), insertar:
  ```python
  # ── Spec-007: Bonus Aditivo de Convergencia Multi-Campo ───────────────────────
  if constants.CONVERGENCIA_ACTIVA and q_set:
      def _bonus_conv(r) -> float:
          conc, cont = r[0], r[1]
          canales = (
              _campo_activo(conc)
              + _campo_activo(concepto_sinonimos_map.get(conc, ""))
              + _campo_activo(sustantivos_map.get(conc, ""))
              + _campo_activo(cont)
          )
          bonus = constants.CONVERGENCIA_BONUS_MAX * max(0, canales - 1) / 3.0
          return min(1.0, r[4] + bonus)

      resultados_con_hibrido.sort(key=_bonus_conv, reverse=True)
  # ─────────────────────────────────────────────────────────────────────────────
  ```
- **Hecho cuando**:
  - [ ] `pytest tests/test_convergencia_multi_campo.py -q` muestra **7 PASSED, 0 FAILED**.
  - [ ] `git diff core/memory/search.py` muestra únicamente la inserción del bloque de sort.
  - [ ] `r[4]` de los resultados no contiene el bonus (verificado por `test_score_base_r4_intacto`).
- [ ] **Estado**: pendiente

---

## T5: Gate completo — benchmark 921 casos + smoke test producción

- **RF cubiertos**: RF-13, RNF-5 (Criterios 1 y 7 de la spec)
- **Descripción**: Verificación final en 3 pasos:
  1. **Paso 5a (Baseline con flag OFF):**
     `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db BIORAG_CONVERGENCIA_ACTIVA=0 python3 scripts/evaluar_qa.py`
  2. **Paso 5b (Gate con flag ON):**
     `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db BIORAG_CONVERGENCIA_ACTIVA=1 python3 scripts/evaluar_qa.py`
     Umbral: Recall@5 ≥ 97.0%, Recall@1 ≥ 88.76%, MRR ≥ 0.916, FPR = 0.0%.
  3. **Paso 5c (Smoke test DB viva no destructivo):**
     Copia temporal de `MemoryBioRAG_Data/memory_biorag.db` vía `sqlite3.backup()` y consulta de validación.
- **Hecho cuando**:
  - [ ] **Paso 5a**: `evaluar_qa.py` produce `[GATE] OK` idéntico al baseline.
  - [ ] **Paso 5b**: `evaluar_qa.py` produce `[GATE] OK` sin regresión.
  - [ ] **Paso 5c**: `version_actual_biorag` mejora ranking en producción sin mutar la base original.
- [ ] **Estado**: pendiente

---

## Cobertura de requisitos

| RF / RNF / CL | Tarea que lo cubre |
|---------------|-------------------|
| RF-1, RF-3, RF-10 | T4 |
| RF-2, RF-4, RF-5, RF-6 | T2, T4 |
| RF-7, RF-7b, RF-8, RF-9, CL-9 | T1, T2 |
| RF-11, RF-12 | T2, T3, T4 |
| RF-13, RNF-5 | T5 |
| CL-1..CL-8, CL-10 | T4 |
| RNF-1..RNF-4 | T4 |
