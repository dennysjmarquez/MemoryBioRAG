# Alerta: los 5 bugs se arreglaron sin la medición que los valida

**Fecha:** 2026-08-15
**Severidad:** alta — no porque los fixes sean malos, sino porque **no sabemos si lo son**.
**Acción recomendada:** no seguir con RRF hasta cerrar esto.

---

## Resumen en una frase

Los 5 fixes tocan directamente el **ranking**, y la evidencia presentada
(`16/16 tests`) es de una suite que **no mide ranking**. No hay ningún número de
recuperación antes/después. La regla del proyecto ("no modifico código que ya
funciona sin antes tener una forma de confirmar que sigue funcionando", y "un
cambio a la vez, medido con antes/después propio") no se cumplió.

Esto no dice que los fixes estén mal. Dice que **son indistinguibles de estar mal**
con la evidencia disponible.

---

## 1. `test_memory.py` no puede detectar una regresión de ranking

Verificado por búsqueda directa en el archivo: **cero ocurrencias** de `recall`,
`mrr`, `r@5`, `r@1` o `ndcg`.

| Suite | Qué mide | ¿Detecta regresión de ranking? |
|---|---|---|
| `test_memory.py` (16/16) | mecánica: LTP, sueño, SDM, inferencia, GABA | **no** |
| `scripts/evaluar_qa.py` | 921 casos, R@5, R@1, MRR, FP | **sí** — es el único |

Ahora crúzalo con lo que tocó cada fix:

| Bug | Qué cambia | Superficie de riesgo |
|---|---|---|
| 1.2 pesos suman 1.34 → renormalizados | **todos los scores** | ranking completo |
| 1.3 pisos `max(0.95,·)` → bonos en logit | **desempates del head** | R@1, MRR |
| 1.4 radio SDM → Hamming real | qué candidatos entran | recall |
| 1.5 `vector_query` fuera del loop | latencia | (bajo, si es equivalente) |
| 1.1 varianza explicada | métrica de diagnóstico | ninguna |

Los tres primeros son exactamente los que `test_memory.py` no ve. `16/16 PASS` es
verdadero y a la vez irrelevante como evidencia de no-regresión.

**Precedente en el propio repo:** `EXPERIMENTS.md` documenta que el PPR "mejoraba"
hasta que se evaluó bien y dio 0%. El proyecto ya aprendió esta lección una vez.

## 2. Cinco cambios simultáneos: la atribución es imposible

Aunque ahora se corra el benchmark, si R@5 se mueve no se sabrá cuál de los cinco
lo movió. Y pueden cancelarse entre sí: el 1.2 (renormalizar) y el 1.3 (quitar los
pisos) empujan el head en direcciones distintas. Un empate neto podría ocultar una
mejora grande y una regresión grande a la vez.

## 3. Los números de calibración son internamente contradictorios

Esto sí es un error demostrable, no una cuestión de proceso.

**a) El umbral 0.9633 es inalcanzable con el Platt reportado.**
Con `a=3.55, b=-1.11`, la probabilidad máxima que puede emitir el calibrador es
`sigmoide(3.55·1.0 − 1.11) = 0.9198`, para un score de entrada de 1.0 (el máximo,
porque `_calcular_score_hibrido` hace `min(1.0, ·)`).

```
score=0.0 -> p=0.2479
score=0.5 -> p=0.6604
score=1.0 -> p=0.9198   <-- techo
umbral    =   0.9633    <-- por encima del techo
```

Por construcción **nada puede superar el umbral**. De ahí el "filtra todo". No es
que el umbral sea "muy alto": es que se está comparando contra una escala en la que
no vive.

**b) "Todos los negativos ~0" y "umbral 0.9633" no pueden ser ambas ciertas.**
`UmbralConforme` toma el cuantil de los scores de los negativos. Verificado:

```
40 negativos en [0.00, 0.05] -> umbral = 0.0490
40 negativos en [0.90, 0.97] -> umbral = 0.9668
```

Si el umbral salió 0.9633, los negativos **no** estaban cerca de cero. El
diagnóstico del reporte contradice su propio número. Lo más probable: se calibró
el umbral sobre scores crudos y se aplicó sobre probabilidades de Platt (o al
revés). Son dos escalas distintas.

**c) α=0.05 con n=40 está en el límite del método.**
`ceil((40+1)·0.95) = 39`, o sea toma el penúltimo de 40: el umbral queda
determinado casi por el máximo de la muestra, que es el estadístico más inestable.
El α mínimo detectable con n=40 es 1/41 ≈ 0.024. Con 40 negativos, α=0.05 es el
suelo del método, no una elección cómoda.

**d) 50 casos de entrenamiento para Platt, y sin holdout.**
El reporte dice "entrenado con 50 casos QA". Platt tiene 2 parámetros, así que 50
no es absurdo, pero no se menciona ningún conjunto de validación separado. La regla
18 del manual (validación que el ajuste nunca toca) no se aplicó.

## 4. Una conclusión del reporte no se sostiene

> *"El problema del umbral alto revela que el feedback es extremadamente raro"*

El umbral conforme se calcula con los **scores de recuperación de consultas
negativas**. No toca `exitos_dopamina` ni el feedback en ningún punto. Son dos
subsistemas sin relación. P4 sí demostró que el feedback es raro — pero el umbral
de 0.9633 no es evidencia de eso.

---

## Qué hacer, en orden

### Paso 0 — Congelar (ahora)
No seguir con RRF. Añadir una señal nueva sobre una base sin medir multiplica el
problema de atribución en vez de resolverlo.

### Paso 1 — Establecer el "antes" (~30 min)
```bash
git stash            # o checkout del commit previo a los fixes
BIORAG_PATH=<db> python3 scripts/evaluar_qa.py > /tmp/eval_ANTES.txt
git stash pop
BIORAG_PATH=<db> python3 scripts/evaluar_qa.py > /tmp/eval_DESPUES.txt
diff /tmp/eval_ANTES.txt /tmp/eval_DESPUES.txt
```
Si no hay diferencia, los 5 fixes son neutros en calidad (siguen valiendo: 1.1 y
1.5 son correctitud y latencia). Si hay diferencia, ir al paso 2.

### Paso 2 — Desagregar (una tarde)
Cada fix detrás de su propio flag de entorno, y una corrida por fix:
`BIORAG_FIX_PESOS`, `BIORAG_FIX_PISOS`, `BIORAG_FIX_SDM`. Con el resultado, aplicar
McNemar pareado y Wilson (`scripts/evaluacion_estadistica.py`) para saber cuáles
mejoras son reales y cuáles son ruido.

### Paso 3 — Rehacer la calibración sobre una sola escala
- Decidir explícitamente si se calibra sobre `score_hibrido` **o** sobre `p_platt`,
  y usar la misma en `calibrar()` y en `responder()`.
- Reportar el umbral junto al rango observado de la escala, para que un umbral
  fuera de rango se vea de inmediato.
- Separar holdout para Platt.
- Con n=40 negativos, usar α≥0.10 o conseguir más negativos. Es barato: son
  consultas que no deben devolver nada.

**Guarda defensiva recomendada** en `UmbralConforme.calibrar()`: si el umbral
resultante supera el máximo score observado en los positivos, emitir un aviso
explícito. Un umbral que filtra el 100% debe gritar, no devolver silencio — es
justo el caso "resultado silencioso por defecto" que la regla 12 prohíbe.

### Paso 4 — Solo entonces, RRF
Y con el benchmark corriendo antes y después.

---

## Lo que sí está bien y hay que reconocer

- Los 5 diagnósticos de bug son correctos; los verifiqué en su momento.
- `eventos_refuerzo` está bien implementado: tabla propia, sin FK problemática,
  `try/except` que no puede tumbar el feedback. Ese parche esquivó los dos
  bloqueadores reales.
- P4 y P5 se ejecutaron con rigor y sus resultados son válidos.
- El autotest de termodinámica (0.015) es correcto, pero mide la teoría contra
  simulación — **no** valida ninguno de los 5 fixes.

El problema no es el trabajo. Es que se está declarando "verificado" con una
medición que no puede ver aquello que cambió.
