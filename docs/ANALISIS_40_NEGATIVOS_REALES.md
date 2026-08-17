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

## Conclusiones

### 1. Los 40 "negativos reales" del dry-run son **solo reformulaciones** (señal A)

- Cero aprendizajes posteriores (señal B) — el benchmark no crea nodos, y el uso real no ha generado pares `buscar → 0 resultados → guardar nodo parecido` detectables con la ventana actual
- La señal B es la que detecta **ausencia real** (búsqueda sin respuesta → el agente la crea). Sin ella, no hay negativos de "no hay nada que devolver"

### 2. Los negativos reales (reformulaciones) puntúan **mucho más alto** que los sintéticos

```
Sintéticos:  media 0.458  |  máx 0.600
Reales (R):  media 0.800  |  máx 0.969
```

El umbral conforme calibrado con sintéticos (~0.60) **no protege** contra reformulaciones reales, que caen en 0.4-0.97.

### 3. La calibración conforme con 40 sintéticos **no valida la garantía real**

- FP held-out 0% con 20 muestras → Wilson 95% = **[0%, 16.1%]**
- **EXCEDE α=0.10** (no "dentro" como se reportó erróneamente)
- Sin poder estadístico para confirmar la garantía

### 4. El experimento clave ya se corrió y el resultado es: **umbrales idénticos**

```
Umbral con 40 sintéticos: ~0.60
Umbral con 40 reales:     0.6000
```

**No se movió.** Dos lecturas posibles:
- **(A)** Los sintéticos nunca estuvieron sesgados
- **(B)** Los 40 "reales" no son el mismo tipo de negativo (reformulación ≠ ausencia)

La evidencia apunta a **(B)**: reformulación = respuesta imprecisa; conforme = ausencia. Calibrar abstención con reformulaciones mide otra propiedad.

---

## Qué falta para garantía real

| Señal | Qué detecta | Estado |
|---|---|---|
| **A. Reformulación** | Respuesta imprecisa | ✅ 40 detectados, pero no calibra abstención |
| **B. Aprendizaje posterior** | Ausencia real (buscar → 0 → guardar) | ❌ 0 detectados — requiere tiempo real |
| **C. Silencio posterior** | Respuesta útil | Filtrada por riesgo asimétrico |

**La señal B es la única que da negativos de "no hay respuesta" para calibrar el umbral conforme.** Solo aparece con uso real acumulado (días/semanas con `BIORAG_NO_LOG=1`).

---

## Plan real (no bloqueante por merge)

1. **Merge a master** — el sistema funciona, ranking intacto (snapshot 50/50 = 100%), calibración conforme operativa con α configurable y guardas
2. **Dejar correr con `BIORAG_NO_LOG=1` en evaluaciones** — en días/semanas aparecerán pares `buscar → 0 → guardar` (señal B)
3. **Batch periódico de `feedback_implicito.py`** — acumular negativos reales de tipo B
4. **Recalibrar con negativos de tipo B** → comparar umbral nuevo vs 0.6000 → ese experimento sí valida (o no) la garantía real

---

## Corrección a documentación previa

- ❌ "Wilson dentro de α=0.10" → ✅ "Wilson 95% = [0%, 16.1%] EXCEDE α=0.10; consistente pero sin poder estadístico"
- ❌ "40 negativos reales" → ✅ "40 reformulaciones reales; 0 negativos de ausencia real (señal B)"
- ❌ "Garantía 6% validada" → ✅ "Garantía teórica sobre sintéticos; garantía real pendiente de señal B"

---

## Merge a master: decisión

**El merge NO debe bloquearse por esto.** El sistema cumple:
- ✅ Ranking intacto (snapshot 50/50 = 100%, live muestra que el problema del 80% FP era el umbral fijo 0.25, no el ranking)
- ✅ Calibración conforme operativa (percentil, α configurable, guarda 1/(n+1), recalibración por drift)
- ✅ Guarda degenerada conectada y verificada
- ✅ Bucle feedback cross-instance funcional
- ✅ `BIORAG_NO_LOG` evita contaminación futura del log

Lo que falta (señal B) es **datos, no código**. Los datos llegan solos dejando correr el sistema limpio.