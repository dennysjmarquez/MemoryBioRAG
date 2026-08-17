# Análisis: 40 negativos "reales" vs sintéticos — qué nos dice la calibración

**Fecha:** 2026-08-16  
**Estado:** Confirmado por auditoría externa y verificación empírica  

---

## Hallazgo central

| Tipo de negativo | N | Media | Mediana | Min | Max | Naturaleza |
|---|---|---|---|---|---|---|
| **Sintéticos (QA baseline)** | 40 | 0.458 | 0.450 | 0.340 | **0.600** | Escritas a mano para ser claramente ajenas |
| **Reales — reformulaciones (snapshot)** | 8 | 0.800 | 0.946 | 0.414 | 0.969 | El agente reformuló tras respuesta imprecisa |
| **Reales — reformulaciones (live)** | 1 | — | — | 0.967 | 0.967 | Idem |
| **Reales — aprendizaje posterior** | 0 | — | — | — | — | **No hay ninguna** en el log actual |

---

## Qué pasó con los "40 negativos reales"

El dry-run inicial reportó **40 negativos** con confianza ≥ 0.7. Tras análisis del auditor:

1. **Eran 40 reformulaciones** (señal A), **cero aprendizajes posteriores** (señal B)
2. El filtro de "profundización" (tokens X ⊂ X') ya estaba implementado y funcionando — descarta casos donde el agente *añade* especificidad a una búsqueda que ya funcionó (ej: "umbral conforme" → "umbral conforme calibracion alpha")
3. De los 40, **la mayoría son retries idénticos/quasi-idénticos** del agente (ej: "athena artemis" a 2s, sim=0.50) que puntean alto (mediana 0.946) porque **encontraron el nodo correcto** y el agente volvió a consultar
3. Solo **1 es una reformulación genuina** ("biorag v11 changelog completo" → reformulada en 3s, sim=0.50)

**Conclusión:** los 40 aplicados son **reformulaciones/retries detectados tras filtro de benchmark**, pero **no son negativos de ausencia** (señal B). La señal B (aprendizaje posterior) es la única que da negativos de "no hay respuesta" para calibrar el umbral conforme.

---

## Calibración conforme: qué valida y qué no

### Lo que SÍ valida
- **Umbral 0.6000** calibrado con 40 sintéticos → FP held-out 0% (Wilson [0%, 16.1%])
- **Wilson 95% para 0/20 = [0%, 16.1%]** → **EXCEDE α=0.10** (no "dentro" como se reportó erróneamente)
- Sin poder estadístico para confirmar la garantía con n=20

### Lo que NO valida
- Los negativos sintéticos (media 0.458) **no representan** las reformulaciones reales (media 0.800-0.967)
- El umbral 0.600 **no protege** contra reformulaciones reales que puntúan 0.4-0.97
- La garantía 6% es **teórica sobre sintéticos**; garantía real pendiente de señal B

---

## Qué falta para garantía real

| Señal | Qué detecta | Estado |
|---|---|---|
| **A. Reformulación** | Respuesta imprecisa / retry | ✅ 40 detectados, pero no calibran abstención |
| **B. Aprendizaje posterior** | Ausencia real (buscar → 0 → guardar) | ❌ 0 detectados — requiere tiempo real con uso limpio |
| **C. Silencio posterior** | Respuesta útil | Filtrada por riesgo asimétrico |

**La señal B es la única que da negativos de "no hay respuesta" para calibrar el umbral conforme.** Solo aparece con uso real acumulado (días/semanas con `BIORAG_NO_LOG=1`).

---

## Correcciones implementadas en esta sesión

1. **Filtro selectivo de ráfagas** (`feedback_implicito.py`): solo la señal A (reformulación) mira `es_rafaga`; la señal B (aprendizaje) queda intacta porque el benchmark nunca crea nodos
2. **Regla de profundización** (subset tokens): `tokens(X) ⊂ tokens(X')` → **profundización, no marcar** — evita LTD a nodos que sirvieron
3. **`BIORAG_NO_LOG=1`** en `evaluar_qa.py` + `buscar_por_frase`: evita contaminación futura del log con consultas de benchmark
4. **Guarda degenerada conectada** en `calibrar_umbral_conforme`: pasa positivos a `UmbralConforme.calibrar()` → dispara `*** UMBRAL DEGENERADO ***` si umbral > max positivo
4. **Feedback cross-instance** via `conceptos_top` en `log_busquedas`: funciona entre instancias MCP (caso B real)
5. **Wilson interval corrección**: 0/20 = [0%, 16.1%] **EXCEDE α=0.10** (no "dentro")

---

## Plan real (no bloqueante por merge)

1. **Merge a master** — el sistema cumple: ranking intacto (snapshot 20/20 = 100%), calibración conforme operativa (percentil, α configurable, guarda 1/(n+1), recalibración por drift), guarda degenerada, feedback cross-instance, `BIORAG_NO_LOG`
2. **Dejar correr con `BIORAG_NO_LOG=1`** — en días/semanas aparecerán pares `buscar → 0 → guardar` (señal B)
3. **Batch periódico de `feedback_implicito.py`** — acumular negativos reales de tipo B
4. **Recalibrar con negativos de tipo B** → comparar umbral nuevo vs 0.6000 → ese experimento sí valida (o no) la garantía real

---

## Merge a master: decisión

**El merge NO debe bloquearse.** El sistema cumple:
- ✅ Ranking intacto (snapshot 20/20 = 100%, live muestra que el problema del 80% FP era el umbral fijo 0.25, no el ranking)
- ✅ Calibración conforme operativa (percentil, α configurable, guarda 1/(n+1), recalibración por drift)
- ✅ Guarda degenerada conectada y verificada
- ✅ Bucle feedback cross-instance funcional
- ✅ `BIORAG_NO_LOG` evita contaminación futura del log

Lo que falta (señal B) es **datos, no código**. Los datos llegan solos dejando correr el sistema limpio.