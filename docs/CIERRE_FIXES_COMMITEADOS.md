# Cierre: todo commiteado y verificado independientemente

**Fecha:** 2026-08-15
**Rama:** `origin/fix-by-fix-measurement` @ `3aa7638`
**Veredicto:** los entregables pendientes están commiteados y verificados. Esta
línea de trabajo se puede cerrar. Queda **una** afirmación por corregir y **un**
archivo por commitear.

---

## 1. Verificado contra el remoto ✅

Lo comprobé con `git ls-tree` y ejecutando el código, no leyendo el reporte:

| Entregable | Estado |
|---|---|
| `scripts/test_regresion_scoring.py` | ✅ commiteado en `7fb8d97`, **byte a byte idéntico** al propuesto |
| `eventos_refuerzo` (tabla) | ✅ 4 ocurrencias en `memory_store.py`, esquema correcto |
| Logging del LTP | ✅ dentro de `try/except`, no puede tumbar el feedback |
| `BIORAG_FP_THRESHOLD` | ✅ en `evaluar_qa.py` |
| Fixes 1.1–1.5 | ✅ correctos |

**Detalle menor:** el reporte dice "1. `3aa7638` — 2 archivos cambiados". En
realidad son **dos commits**: `7fb8d97` (el test) y `3aa7638` (tabla + doc). El
resumen atribuye a uno solo el trabajo de ambos. No es un problema — el trabajo está
—, pero el registro no coincide con el historial.

### Verificación independiente del test

Ejecuté **mi** copia del test contra **su** código commiteado: pasa los 4 tests.
Y previamente lo había validado contra las versiones con bugs (`master` y `573fd49`),
donde falla correctamente. Es una red de seguridad real, no un test que solo pasa.

### El logging del LTP está bien resuelto

```python
try:
    delta = round(nuevo_peso - peso_actual, 4)
    self.cursor.execute("INSERT INTO eventos_refuerzo ...")
except Exception as e:
    print(f"[BioRAG] aviso: no se pudo registrar evento_refuerzo para '{key}': {e}")
```

El `delta` se recalcula desde los pesos reales en vez de reutilizar la variable
local (que vale cosas distintas en la rama de éxito y en la de fallo). Correcto, y
además hace que **P3-ter sea medible por fin**: con esta tabla se puede validar
Δw = 0.15(1−0.3w) por medición directa en vez de inferencia.

---

## 2. Lo que queda pendiente

### a) `scripts/test_h_corpus_umbral.py` no está commiteado

Es el único entregable que falta. Contiene las dos correcciones que hicieron falta
tras los sesgos detectados (partición calibración/validación, y `limite_casos=0` por
defecto) más el barrido multi-coste. Sin él, la próxima corrida del barrido volvería
a usar la versión sesgada.

### b) La afirmación del umbral sigue igual

El resumen mantiene:

> *"H-corpus live DB: AUC=0.914, óptimo=0.78 (net=40)"*

El `net=40` proviene de la corrida con `limite_casos=120` (~51 positivos frente a 32
negativos, ratio ~1.6:1). Con el ratio real del benchmark (881:32):

| umbral | Recall | FP | net real |
|---|---|---|---|
| **0.25** | 100% | 100% | **849** |
| 0.78 | 78% | 0% | **687** |

Con el ratio real, `TP − FP` favorece **0.25**, no 0.78. Y ni uno ni otro es "el
óptimo": el 881:32 es un artefacto del diseño del benchmark, no la carga de
producción.

**Sigue sin hacerse lo que desbloquea esto:**
- rehacer el barrido con el script corregido y **verificar la monotonía** (la tabla
  previa tenía una fila imposible en 0.80, con FP y recall subiendo a la vez);
- medir el ratio real en `log_busquedas`.

Mientras no se hagan, "Calibración resuelve FP 80%" es una intención, no un plan:
no hay un umbral objetivo ni un criterio para elegirlo.

### c) El fix 1.1 sigue sin cobrarse

`varianza_explicada = 0.10` está bien medido ahora. Pero el propósito del fix era
**elegir `dim` con criterio**, y `dim=100` sobre ~900 documentos sigue sin
justificar. El barrido cuesta una tarde (7.2s por reindexado × 5 valores + 5
corridas de benchmark) y es independiente de todo lo demás.

---

## 3. Estado real del proyecto tras esta sesión

**Resuelto:**
- 7 bugs reales corregidos (5 iniciales + 2 introducidos por los fixes)
- Tests de regresión que impiden que los dos peores vuelvan
- Instrumentación del LTP, que era invisible
- Umbral de FP parametrizable

**Descartado con evidencia:**
- el daemon como causa del FP 80%
- el fix 1.2 como causa del FP 80%
- la fusión lineal como causa (R@5 en live es 96.37%)
- RRF como solución al FP
- el escenario B (discriminación rota): AUC=0.914 lo refuta

**Sin resolver:**
- **el FP del 80% en live está exactamente igual que al principio.**

Eso último conviene decirlo sin adornos. La sesión produjo mucho conocimiento y
código correcto, pero el problema que la originó sigue abierto. Lo que cambió es que
ahora se sabe **qué no es** y **dónde está**: un umbral absoluto que no escala con
el tamaño del corpus, en un sistema cuyo ranking funciona bien (AUC 0.914).

---

## 4. Siguientes pasos

| # | Acción | Coste |
|---|---|---|
| 1 | Commitear `scripts/test_h_corpus_umbral.py` | 1 min |
| 2 | Rehacer barrido con el script corregido; **verificar monotonía** | 1 corrida |
| 3 | Medir ratio real positivos:negativos en `log_busquedas` | 1 consulta |
| 4 | Barrido de `dim` (cobrar el fix 1.1) | 1 tarde |
| 5 | Elegir umbral con el coste relativo escrito; aplicar con benchmark A/B | — |
| 6 | RRF / retrofitting, como mejoras de **ranking** | — |

Y una recomendación de registro: volcar esta sesión en `EXPERIMENTS.md`. Cinco
hipótesis refutadas con evidencia y una matriz 2×2 completa es exactamente el tipo
de material que ese documento existe para conservar — y que evita que dentro de seis
meses alguien vuelva a proponer RRF para arreglar el FP.
