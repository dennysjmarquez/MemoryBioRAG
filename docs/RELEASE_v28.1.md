# v28.1 — Auditoría matemática, corrección de scoring e instrumentación

> **Versión:** v28.1 — Agosto 2026
> **Tipo:** release de correctitud e instrumentación. **No cambia métricas de recuperación.**
> **Base:** v28.0 (`5a306fa`)

---

## Por qué v28.1 y no v29

v29 debería reservarse para un cambio de capacidad (el ADN Conceptual ya tiene ese
número asignado en el roadmap). Esta release **no añade capacidades ni mueve las
métricas**: corrige errores, añade instrumentación y crea las herramientas de
medición que no existían.

Semánticamente es una release *patch/minor* de infraestructura. Llamarla v29 daría
a entender un salto funcional que no ocurrió.

---

## Qué cambia

### 1. Cinco bugs de scoring corregidos

| # | Dónde | Qué estaba mal | Efecto |
|---|---|---|---|
| 1.1 | `ppmi_vectorizer.py` | `varianza_explicada` siempre devolvía 1.0 (truncaba `S` antes de calcular el total) | la métrica no informaba nada; imposible elegir `dim` con criterio |
| 1.2 | `memory_store.py` | los pesos sumaban 1.34 y el score saturaba en `min(1.0, ·)` | pérdida de resolución en el head del ranking |
| 1.3 | `memory_store.py` | `max(0.95, score)` empataba resultados | el desempate lo decidía el orden del `SELECT` |
| 1.4 | `sdm.py` | el radio comparaba `(1-Jaccard)*2048` contra una escala Hamming | el radio o no filtraba nada o lo filtraba todo |
| 1.5 | `ppmi_hybrid_search.py` | `vector_query` se recalculaba por candidato | O(N·\|q\|) evitable |

Más **dos bugs introducidos por los propios fixes** y corregidos después: la suma
`1.19` hardcodeada (bug 1.2 en otra forma) y una rama de sinónimos que usaba
`max(logit, target)` y aplastaba cinco scores distintos al mismo 0.70.

### 2. Instrumentación del refuerzo (lo más importante a medio plazo)

Nueva tabla `eventos_refuerzo`: registra cada refuerzo dopaminérgico con
`peso_anterior`, `peso_nuevo`, `delta`, `exitos_previos` y timestamp.

**Antes de esto, el LTP no dejaba rastro.** Era la única regla de actualización de
peso sin historial persistente, lo que la hacía imposible de validar. El logging va
dentro de un `try/except` deliberado: perder telemetría es aceptable, romper el
bucle de feedback no.

### 3. Herramientas de medición

| Script | Para qué |
|---|---|
| `test_regresion_scoring.py` | 4 tests de propiedades del scoring. Validado contra las versiones con bug (falla) y sin bug (pasa) |
| `test_h_corpus_umbral.py` | AUC positivos vs negativos, barrido de umbral, coste de abstenerse |
| `medir_ratio_produccion.py` | ratio real de consultas con/sin respuesta en `log_busquedas` |
| `evaluacion_estadistica.py` | Wilson, McNemar pareado, macro vs micro, corrección BH |
| `test_p4_feedback.py` | ¿el olvido discrimina por valor o por falta de feedback? |
| `test_p5_que_sostiene_activos.py` | qué mantiene vivos a los nodos activos |
| `test_p6_inmortales_por_null.py` | nodos inmortales por `categoria IS NULL` |
| `termodinamica_cortical.py` | ley de supervivencia cortical (teoría + autotest) |
| `calibracion.py` | RRF, Platt, isotónica, umbral conforme, MMR, Dunning LLR |

`BIORAG_FP_THRESHOLD` hace configurable el umbral de falso positivo, antes
hardcodeado en 0.25.

---

## Qué NO cambia

**Las métricas de recuperación.** Con honestidad:

| Métrica | v28.0 | v28.1 | En casos | Significancia |
|---|---|---|---|---|
| R@5 (snapshot) | 96.14% | 96.25% | +1 de 881 | McNemar p=1.00 |
| R@1 (snapshot) | 88.76% | 88.76% | 0 | — |
| FP (snapshot) | 25.0% | 17.5% | −3 de 40 | p=0.25 |

Ninguna diferencia es estadísticamente distinguible de cero. **El valor de esta
release es de correctitud, latencia y capacidad de medir — no de métrica.**

Se documenta así a propósito: llamar "driver principal" a una mejora de un caso
convierte ruido en narrativa.

---

## Hallazgos de diagnóstico (ver `EXPERIMENTS.md`)

1. **El FP del 80% en live DB es preexistente**, no lo causaron los fixes ni el
   daemon. Matriz 2×2 completa con `baseline@live` medido.
2. **El ranking funciona**: AUC entre positivos y negativos = **0.914**, R@5 en live
   96.37%. El problema no es la fusión de señales.
3. **El problema es el umbral absoluto**: 0.25 se eligió para un corpus de ~800
   nodos; en un corpus mayor los scores basales suben y el listón se queda corto.
4. **El olvido no discrimina por valor**: 154 nodos dormidos, **100% con
   `exitos_dopamina = 0`**, y 97 de ellos con grado sináptico ≥10 (puentes
   estructurales). No mueren por inútiles: mueren porque nadie cierra el bucle de
   feedback.
5. **Bug latente detectado, no corregido**: un nodo con `categoria IS NULL` nunca
   recibe LTD (por la lógica ternaria de SQL: `NULL NOT IN (...)` evalúa a NULL).
   Es inmortal de facto. Ver `docs/HALLAZGO_H5_INMORTALES.md` — **no aplicar el fix
   sin medir primero cuántos nodos afecta**: activaría el decaimiento sobre una
   población que nunca ha decaído.

---

## Pendientes al cierre de v28.1

| # | Acción | Bloquea a |
|---|---|---|
| 1 | Medir ratio real en `log_busquedas` | la elección del umbral |
| 2 | Barrido H-corpus verificando monotonía | idem |
| 3 | Barrido de `dim` ∈ {25,50,75,100,150} | cobra el fix 1.1 |
| 4 | Calibración + umbral en escala de score crudo | resuelve el FP |
| 5 | Medir H5 (`test_p6`) antes de tocar el LTD | seguridad de datos |

**El paso 1 decide el resto.** Con ratio 881:32 el óptimo de `TP−FP` es 0.25; con
1.6:1 salía 0.78. Mismo método, conclusión opuesta: el ratio decide, no el método.

---

## Nota de rumbo

El objetivo declarado del proyecto es recuperar **por significado, no por léxico**.
Los datos de esta auditoría lo sostienen: la señal semántica existe y es fuerte
(AUC 0.914, 105 islas semánticas auto-organizadas, PPMI modular y no degenerada).

Lo que falta no es más señal semántica — es **decidir cuándo esa señal es
suficiente para responder y cuándo toca decir "no lo sé"**. Ese es un problema de
calibración, no de representación.

Y el hallazgo del feedback (punto 4) apunta a lo mismo desde el otro lado: el
sistema tiene una economía de memoria real —nace, se refuerza, compite, muere— pero
el circuito de recompensa casi nunca se cierra, así que el olvido está siendo
gobernado por el silencio en vez de por el valor.
