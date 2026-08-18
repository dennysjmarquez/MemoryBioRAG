# Verificación del Umbral Conforme 0.63 — Lo que realmente se midió

**Fecha:** 2026-08-17
**Autor:** Athena-OEC (corrección tras auditoría)
**Estado:** VERIFICADO — la tabla anterior era engañosa

---

## Lo que se afirmó (y estaba mal)

```
| Métrica         | Baseline (legacy) | Con umbral conforme (0.63) |
|-----------------|-------------------|---------------------------|
| R@5             | 96.03%            | 96.37% ✅                  |
| FP              | 25% (10/40)       | 0% (0/40) ✅               |
```

**Problema:** esa tabla no mide lo que dice.

---

## Por qué es engañosa

### 1. El QA NO pasa por el umbral conforme

`evaluar_qa.py:96` llama a `buscar_por_frase()`. El commit `d67acb2` **quitó el umbral de ahí**.

```
evaluar_qa.py:96
  → db.buscar_por_frase(query, ...)   # SIN umbral
  → buscar_por_frase() devuelve todo  # motor puro
  → FP se mide con BIORAG_FP_THRESHOLD=0.25  # legacy, NO conforme
```

**La columna "Con umbral conforme (0.63)" mide el motor SIN filtro.**

### 2. R@5 subió — prueba de que no se aplicó filtro

Un filtro de abstención solo puede **quitar** resultados, nunca añadir aciertos.

- R@5 baseline: 96.03% (846/881)
- R@5 "con umbral": 96.37% (849/881)

**Subió 3 casos.** Eso prueba que no se aplicó ningún filtro. La mejora viene de que la DB actual tiene 975 nodos vs 866 del snapshot frozen (más nodos = más aciertos).

### 3. FP 0% no es del umbral conforme

El FP se mide en `evaluar_qa.py:111`:
```python
fp_threshold = float(os.environ.get('BIORAG_FP_THRESHOLD', '0.25'))
fps = [r for r in results if r[4] >= fp_threshold]
```

Esa es la constante **legacy** (0.25), no el umbral conforme (0.63). El 0% no es atribuible a la calibración.

### 4. "50 negativos de 16 queries" rompe independencia

El método conforme requiere: **1 query → 1 score**. Tomar múltiples negativos por query viola la independencia.

- 16 queries × 3.1 negativos/query = 50 scores
- **n efectivo = 16**, no 50
- Con n=16, α=0.10: k = ceil((16+1)(0.9))/16 = ceil(0.956) = 1
- **El cuantil es el mínimo alcanzable**, no un percentil útil

### 5. FP 0% con Wilson 95%: [0%, 8.8%]

"No vimos ninguno en 40" ≠ "es cero". El intervalo de confianza dice: con 95% de confianza, el FP real está entre 0% y 8.8%.

---

## Lo que SÍ es verdad ✅

Los fixes de código son correctos:

1. **Umbral eliminado de `buscar_por_frase`** — motor puro, sin filtro
2. **Umbral restringido a top-1** — en `buscar_con_calibracion` y MCP path
3. **Cold start eliminado** — sin calibración = sin filtro (antes 0.65 destrozaba R@5)
4. **23 tests pasando**

La arquitectura resultante es la correcta:
```
buscar_por_frase()       → SIN umbral (motor puro)
_recordar_impl()         → CON umbral conforme (decisión SI/NO)
buscar_con_calibracion() → CON umbral conforme (top-1 decide)
```

---

## Lo que falta medir (honestamente)

### Test 1: Efecto del umbral sobre R@5

Correr QA pasando por `_recordar_impl` (MCP path) y comparar con `buscar_por_frase` (motor puro). La diferencia SÍ sería el efecto del umbral.

### Test 2: Efecto del umbral sobre FP

Correr las 40 queries negativas del QA baseline pasando por `_recordar_impl` con umbral 0.63. Contar cuántas se abstiene.

### Test 3: Calibración con n efectivo

Usar **1 score por query** (el top-1), no múltiples. Con 16 queries efectivas, el mínimo alcanzable es α=1/17≈0.059. Necesitamos más queries para α=0.10.

---

## Medición correcta propuesta

```python
# Test 1: R@5 con umbral
import os
os.environ['BIORAG_CALIBRACION_ACTIVA'] = '1'

from core.memory_store import SQLiteMemoryBioRAG
ms = SQLiteMemoryBioRAG('MemoryBioRAG_Data/memory_biorag.db')

# Cargar calibración
ms._cargar_calibracion_persistida()

# Buscar por MCP path (con umbral)
for case in positive_cases:
    resultados, total = ms.buscar_por_frase(case['query'], limite=5)
    # Aplicar umbral como en MCP
    if resultados and not ms._debe_responder(resultados[0][4]):
        resultados = []  # abstención
    # Evaluar R@5...

# Test 2: FP con umbral
for case in negative_cases:
    resultados, total = ms.buscar_por_frase(case['query'], limite=5)
    if resultados and not ms._debe_responder(resultados[0][4]):
        fp_count += 1  # abstención = no FP
```

---

## Conclusión

**El código está bien. La tabla no medía lo que decía.**

- Fixes correctos: umbral al top-1, motor puro sin filtro, cold start eliminado
- QA confirma que **el motor no sufrió regresión** (R@5 96.37%)
- El efecto del umbral sobre FP **aún no está medido** — el QA no pasa por el path calibrado
- La calibración con 16 queries efectivas tiene poder estadístico limitado

**Siguiente paso:** crear `scripts/evaluar_qa_con_umbral.py` que pase por `_recordar_impl` y mida el efecto real del umbral.
