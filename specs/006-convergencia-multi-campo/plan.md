# Plan técnico — Spec 006: Convergencia Multi-Campo
## (v2 — Corregido tras revisión externa)

## Estructura de módulos

- `core/memory/search.py` → Único archivo modificado. Cambios:
  1. Mover `_ORIGENES_NO_LITERALES` a nivel de módulo (antes del loop de scoring).
  2. Añadir batch-fetch de `sustantivos_clave` usando `conceptos_todos` (ya existe).
  3. Aplicar multiplicador de convergencia post-scoring.
  (RF-1..RF-10, CL-1..CL-9, RNF-1..5)

- `core/memory/constants.py` → Añadir `CONVERGENCIA_ACTIVA` y `CONVERGENCIA_ALPHA`
  con lectura defensiva y warning vía `logging.getLogger()`.
  (RF-7, RF-7b, RF-8, CL-9)

- `tests/test_convergencia_multi_campo.py` → Tests unitarios.
  (Criterios 3, 4, 5, 6)

- `scripts/smoke_006_antes.json` / `scripts/smoke_006_despues.json` → Artefactos de
  smoke test. Generados por scripts auxiliares sobre **copias temporales** de la DB.

**No se crean nuevos módulos. No se toca `scoring.py`.**

---

## Modelo de datos interno

```python
# Nuevo dict batch-fetched, paralelo a concepto_sinonimos_map (misma clave: concepto)
sustantivos_map: dict[str, str]   # concepto -> sustantivos_clave (str cruda, puede ser "")

# Constantes nuevas en constants.py
CONVERGENCIA_ACTIVA: bool   # os.getenv("BIORAG_CONVERGENCIA_006_ACTIVA", "0") == "1"
CONVERGENCIA_ALPHA: float   # float en (0.0, 1.0) exclusive, default 0.5
```

---

## Algoritmos y lógica interna

### Corrección 1: `_ORIGENES_NO_LITERALES` — mover antes del loop

Actualmente definida en **línea 1907** (después del loop de scoring ~L1564).
Debe extraerse como **constante de módulo** al inicio de `search.py`:

```python
# Al inicio del archivo (nivel de módulo), fuera de toda función:
_ORIGENES_NO_LITERALES = {
    "typo", "expansion", "latente", "cadena", "simbolico",
    "dimensional_fallback", "semantica", "unicode", "lexico_aprendido", "sdm"
}
```

La referencia original en L1907 se elimina (o se deja como alias). Así está
disponible dentro del loop de scoring.

### Corrección 2: Batch-fetch de `sustantivos_clave`

La lista correcta es `conceptos_todos` (ya construida en L1374), **no**
`conceptos_con_sinonimos` (nombre que no existe en el código).

Insertar inmediatamente después del bloque de `concepto_sinonimos_map` (~L1452):

```python
# Batch-fetch sustantivos_clave — mismo patrón que concepto_sinonimos_map
sustantivos_map = {}
if conceptos_todos:
    ph = ",".join("?" * len(conceptos_todos))
    for row in self.cursor.execute(
        f"SELECT concepto, sustantivos_clave FROM largo_plazo WHERE concepto IN ({ph})",
        conceptos_todos
    ):
        sustantivos_map[row[0]] = row[1] or ""
```

### Corrección 3: Normalización correcta con `_tokenizar_normalizado`

**Incorrecto** (substring match, falla con acentos y subcadenas espurias):
```python
# ❌ NUNCA hacer esto
canal_concepto = 1 if any(t in concepto.lower() for t in tokens_query) else 0
```

**Correcto** (tokenización idéntica a la del resto del scoring):
```python
# ✅ Correcto — misma función que usa el scoring simbólico (L1457)
# _tokenizar_normalizado ya importada en L1457:
# from core.fallback_simbolico import _tokenizar_normalizado, ...

q_set = set(tokens_query)   # ya calculado en L1458, reutilizar sin recalcular

def _campo_activo(texto: str) -> int:
    """1 si algún token de la query aparece en el campo normalizado, 0 si no."""
    if not texto or not q_set:
        return 0
    return 1 if q_set & set(_tokenizar_normalizado(texto)) else 0
```

### Punto de inserción en el loop de scoring

Dentro del loop (~L1564), **después** de `score_hibrido = _calcular_score_hibrido(...)`
y **antes** de `resultados_con_hibrido.append(...)`:

```python
# ── Convergencia Multi-Campo (Spec-006) ──────────────────────────────
if (constants.CONVERGENCIA_ACTIVA
        and not match_exacto
        and origen_scores.get(concepto, ("literal", 0.0))[0]
            not in _ORIGENES_NO_LITERALES):

    sinonimos_str = concepto_sinonimos_map.get(concepto, "")
    canales = (
        _campo_activo(concepto)
        + _campo_activo(sinonimos_str)
        + _campo_activo(sustantivos_map.get(concepto, ""))
        + _campo_activo(contenido)
    )
    convergencia = canales / 4.0
    alpha = constants.CONVERGENCIA_ALPHA
    multiplicador = alpha + (1.0 - alpha) * convergencia
    score_hibrido = round(min(1.0, score_hibrido * multiplicador), 6)
# ─────────────────────────────────────────────────────────────────────
```

### Corrección 4: Alpha — rango restringido a (0.0, 1.0) exclusive

En `constants.py`, con `logging.getLogger()` (no asumir `logger` preexistente):

```python
import logging as _logging
_log_constants = _logging.getLogger(__name__)

_alpha_raw = float(os.getenv("BIORAG_CONVERGENCIA_ALPHA", "0.5"))
if not (0.0 < _alpha_raw < 1.0):
    _alpha_clamped = max(0.01, min(0.99, _alpha_raw))
    _log_constants.warning(
        "[BioRAG.Convergencia] BIORAG_CONVERGENCIA_ALPHA=%.4f fuera de (0,1); "
        "usando %.4f. alpha=0 puede llevar scores a 0; alpha=1 deshabilita el efecto.",
        _alpha_raw, _alpha_clamped
    )
    _alpha_raw = _alpha_clamped
CONVERGENCIA_ALPHA: float = _alpha_raw
```

El rango válido es **(0.0, 1.0) exclusivo**:
- `alpha = 0.0` → score × 0 cuando convergencia = 0 → **nodo eliminado** (no "atenuado")
- `alpha = 1.0` → multiplicador = 1.0 siempre → **el cambio no tiene efecto**

### Corrección 5: Tests — qué se prueba exactamente

El test de 500 repeticiones comprueba el **multiplicador**, no el score final:
BM25 puede variar con frecuencia, pero la convergencia es binaria y debe ser igual.

```python
# ✅ Correcto
assert multiplicador_500_veces == multiplicador_1_vez

# ❌ Incorrecto — BM25 interno puede diferir
assert score_final_500_veces == score_final_1_vez
```

### Corrección 6: Smoke test — criterio de éxito es posición relativa

El multiplicador NUNCA sube un score; solo lo iguala (×1.0) o lo reduce (<1.0).
El criterio de éxito es **posición relativa**, no score absoluto:

```
✅ CORRECTO:  posición(version_actual_biorag)  <  posición(reindex_selectivo_dirty)
❌ INCORRECTO: score(version_actual_biorag) ≥ score_antes
```

Nota sobre snapshot vs. DB de producción: si `version_actual_biorag` tiene
`sustantivos_clave` en producción (4/4 → ×1.0) pero no en el snapshot (3/4 → ×0.875),
su score bajará en el benchmark pero NO en la verificación de smoke test real.
Las dos verificaciones son independientes y comparables solo entre sí mismas.

### Corrección 7: Smoke test — ejecución no destructiva

`buscar_por_frase` puede registrar accesos y el constructor puede ejecutar síntesis DMN.
Para garantizar solo lectura, el smoke test ejecuta sobre **copia temporal** de la DB:

```python
import sqlite3, tempfile, os

def _copia_segura(ruta_original: str) -> str:
    fd, tmp = tempfile.mkstemp(suffix="_smoke006.db")
    os.close(fd)
    # Abrir fuente en modo solo-lectura (uri=True previene escrituras accidentales)
    src = sqlite3.connect(f"file:{ruta_original}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp)
    src.backup(dst)
    dst.close(); src.close()
    return tmp
```

Y con variables de entorno que inhiben efectos secundarios:
```bash
BIORAG_DMN_SINTESIS_ACTIVA=0 BIORAG_NO_LOG=1 python3 scripts/smoke_006.py
```

### Corrección 8: Gate — qué verifica realmente `[GATE] OK`

El gate (`_evaluar_gate` en `evaluar_qa.py`) solo comprueba:
- Recall@5 global ≥ 97.0% (configurable)
- Fallos ≤ 24
- FP rate ≤ 15.0%
- Regresión por categoría ≤ 2.0 pp en Recall@5

**No verifica Recall@1 ni MRR.** El baseline de referencia es
`scripts/qa_metrics_baseline.json` (v31.3), **no** `baseline_oficial_20260826.txt`
(root). Son archivos distintos con métricas distintas.

En T5, además del gate automático, se añade verificación manual explícita:
```bash
python3 -c "
import json
with open('scripts/qa_metrics.json') as f: m = json.load(f)['global']
print(f'Recall@1: {m[\"recall_at_1\"]:.2f}%')
print(f'MRR:      {m[\"mrr\"]:.4f}')
assert m['recall_at_1'] >= 88.76, 'REGRESIÓN en Recall@1'
assert m['mrr'] >= 0.916, 'REGRESIÓN en MRR'
print('R@1 y MRR: OK')
"
```

---

## Decisiones técnicas

- **Decisión:** `_ORIGENES_NO_LITERALES` como constante de módulo (no local al loop).
  - **Alternativa descartada:** Duplicar el set dentro del loop de convergencia.
  - **Por qué:** No duplicar datos. El set existe para reutilizarse.

- **Decisión:** Usar `_tokenizar_normalizado` (ya importada en L1457) para los canales.
  - **Alternativa descartada:** `token in campo.lower()` (substring).
  - **Por qué:** Substring falla con acentos (`conexion` ≠ `conexión`), produce falsos
    positivos (bio ⊂ biorag), y es distinto a cómo el resto del sistema normaliza.

- **Decisión:** Alpha restringido a (0.0, 1.0) exclusive.
  - **Alternativa descartada:** [0.0, 1.0] inclusive.
  - **Por qué:** alpha=0 puede llevar un score a 0 (CL-6 quedaría violado).
    alpha=1 desactiva el mecanismo silenciosamente sin [GATE] error.

- **Decisión:** Smoke test sobre copia temporal, no sobre DB de producción directamente.
  - **Alternativa descartada:** DB producción con flags de desactivación.
  - **Por qué:** Los flags solo cubren escrituras conocidas; el backup es la única
    garantía real de no-modificación.

---

## Contrato de interfaces externas

Sin cambios en ninguna interfaz pública. Variables de entorno nuevas:
- `BIORAG_CONVERGENCIA_006_ACTIVA` → `"0"` (default) / `"1"` (experimental)
- `BIORAG_CONVERGENCIA_ALPHA` → float en `(0.0, 1.0)`, default `"0.5"`

Recomendado documentar en `.env.example` junto con las demás variables.

---

## Estrategia de tests

| Test | RF | Criterio | Qué se afirma |
|------|----|----------|---------------|
| `test_4campos_supera_1campo` | RF-3, RF-4 | C-3 | Mismo score base, 4/4 > 1/4 en score final |
| `test_binario_frecuencia` | RF-2 | C-4 | **Multiplicador** idéntico para 1 o 500 repeticiones |
| `test_flag_desactivado` | RF-7, RF-7b | C-5 | Score no cambia con `CONVERGENCIA_ACTIVA=False` |
| `test_match_exacto_bypass` | RF-9 | C-6 | `match_exacto=True` → multiplicador = 1.0 |
| `test_alpha_clamping` | RF-8, CL-9 | - | alpha=2.5 → warning + uso de 0.99 |
| `test_origen_semantico_bypass` | CL-7 | - | Origen `sdm` → multiplicador = 1.0 |
| `test_tokens_vacios` | CL-3 | - | query 100% stopwords → multiplicador = 1.0 |

**Tests de proceso de módulo:**
Las constantes de `constants.py` se leen al importar. Para probar distintos valores
de `BIORAG_CONVERGENCIA_ALPHA`, usar `importlib.reload(constants)` tras cambiar
`os.environ`, o invocar con `subprocess` en un proceso nuevo.

### Gate final (T5)
```bash
# Paso 1 — Gate automático
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py

# Paso 2 — Verificación explícita de R@1 y MRR (no cubiertas por el gate)
python3 -c "
import json
with open('scripts/qa_metrics.json') as f: m = json.load(f)['global']
assert m['recall_at_1'] >= 88.76, f'REGRESIÓN R@1: {m[\"recall_at_1\"]:.2f}%'
assert m['mrr'] >= 0.916, f'REGRESIÓN MRR: {m[\"mrr\"]:.4f}'
print(f'R@1={m[\"recall_at_1\"]:.2f}%  MRR={m[\"mrr\"]:.4f}  OK')
"
```
