# Plan Técnico — Spec 007: Convergencia Multi-Campo (Bonus Aditivo Post-QCR)

## Estructura de módulos

- `core/memory/constants.py` → Añadir `CONVERGENCIA_BONUS_MAX` con lectura defensiva,
  clamping (`0.001` - `1.0`) y logging warning. Preservar `CONVERGENCIA_ALPHA` por retrocompatibilidad.
  (RF-7, RF-7b, RF-8, RF-9, CL-9)

- `tests/test_convergencia_multi_campo.py` → Suite completa de 7 tests unitarios puros
  (TDD: escritos antes de la implementación en search.py).
  (RF-2, RF-4, RF-5, RF-7, RF-7b, RF-8, RF-11, CL-3, CL-9)

- `core/memory/search.py` → Limpiar bloque multiplicativo v1 e insertar el sort por bonus
  aditivo inmediatamente tras el sort monotónico post-QCR (~L1995).
  (RF-1..RF-6, RF-10..RF-12, CL-1..CL-8, CL-10, RNF-1..RNF-4)

- `scripts/smoke_007.py` → Script de smoke test no destructivo sobre copia temporal de la DB viva
  (`sqlite3.backup()`).
  (RF-13, RNF-5, Criterio 7)

**No se crean nuevos módulos. No se modifica `scoring.py` ni el esquema de la base de datos.**

---

## Modelo de datos interno

```python
# En constants.py:
CONVERGENCIA_ACTIVA: bool = os.getenv("BIORAG_CONVERGENCIA_ACTIVA", "1") == "1"
CONVERGENCIA_BONUS_MAX: float = 0.05  # Rango (0.0, 1.0], controlado por BIORAG_CONVERGENCIA_BONUS_MAX
CONVERGENCIA_ALPHA: float = 0.5  # Deprecado en Spec 007, mantenido por compatibilidad
```

---

## Algoritmos y lógica interna

### 1. Limpieza de v1 en `core/memory/search.py`
Se elimina el bloque multiplicativo previo en el loop de scoring (~L1739–L1756) para que `score_hibrido` pase directamente a `r[4]` como `score_base` inalterado.

### 2. Inserción del sort por bonus aditivo post-sort-monotónico
En `search.py`, justo después del ordenamiento base `resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)`:

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

Reutiliza:
- `q_set`: conjunto de tokens normalizados ya calculado en L1478.
- `_campo_activo`: evaluador binario con `_tokenizar_normalizado` en L1480.
- `concepto_sinonimos_map` y `sustantivos_map`: diccionarios obtenidos por batch queries.

---

## Estrategia de tests

| Test | RF Cubierto | Comprobación |
|------|-------------|--------------|
| `test_canales_4_4_supera_1_4` | RF-4, RF-5 | Mismo `score_base`, nodo 4/4 obtiene mayor score_ranking que 1/4 |
| `test_binario_500_vs_1_mismo_bonus` | RF-2, CL-4 | 500 repeticiones en contenido producen el mismo canal activo (1) que 1 repetición |
| `test_desactivado_bonus_cero` | RF-7, RF-7b | Con `CONVERGENCIA_ACTIVA=False`, bonus=0 y orden idéntico a `score_base` |
| `test_score_base_r4_intacto` | RF-6, RF-11 | La tupla retornada en `r[4]` conserva `score_base` sin inflación |
| `test_qset_vacio_no_aplica` | CL-3 | Si `q_set` está vacío (solo stopwords), no se aplica alteración |
| `test_bonus_max_clamp_bajo` | RF-8, CL-9 | Valor ≤ 0 se clampea a 0.001 con warning |
| `test_bonus_max_clamp_alto` | RF-8, CL-9 | Valor > 1.0 se clampea a 1.0 con warning |

---

## Gate de validación y benchmark

1. **Benchmark formal (921 casos congelados):**
   ```bash
   BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db BIORAG_CONVERGENCIA_ACTIVA=1 python3 scripts/evaluar_qa.py
   ```
   Exige: `[GATE] OK`, Recall@5 ≥ 97.0%, Recall@1 ≥ 88.76%, MRR ≥ 0.916, FPR = 0.0%.

2. **Smoke Test DB Viva (No destructivo vía `sqlite3.backup()`):**
   Verifica inversión de orden para la query `"cual es la ultima version de biorag"` posicionando `version_actual_biorag` en TOP-1/TOP-2.
