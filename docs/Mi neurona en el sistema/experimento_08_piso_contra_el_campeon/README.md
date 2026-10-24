# Experimento 08 — Piso contra el campeón

> **Pregunta (crítica de un agente auditor):** *"por_tema bajó de 80.00 (v4) a 73.85 (v5). El piso
> lo protege de hundirse, pero el retador ganó en global sacrificando esa categoría."*
>
> **Respuesta corta:** la crítica señalaba un hueco real en la **regla**, pero el caso que citaba no lo
> causaba ese hueco. Se cerró el hueco con una capa nueva y se midió con un A/B limpio.

## 0. En una línea por hallazgo

1. **El hueco existía:** el piso por categoría se comparaba solo contra la fórmula a mano. Un retador
   podía ganarle al campeón en total cediendo una categoría entera. Una prueba nueva lo demuestra:
   **con el código anterior, ese retador asciende**.
2. **La capa nueva:** un retador no asciende si, en alguna categoría y camino del examen, queda por
   debajo del campeón saliente en **más de 1 caso** (R@1, MRR y R@5).
   `BIORAG_NEURONA_TOL_CAMPEON` (por defecto 1).
3. **En los datos reales la regla nunca tuvo que actuar:** A (antes) y B (con la regla) son
   **idénticos ciclo a ciclo** en 500 ciclos (8 ascensos, mismos pesos finales, hash `085adece…`).
   Ningún ascenso real cedió más de un caso en ninguna categoría.
4. **El "80 → 73.85" era variación entre entrenamientos, no un trueque:** v4 y v5 son corridas
   distintas desde cero. El **mismo código** da por_tema 78.46 con el presupuesto de 3 s (despertar)
   y **84.62** sin corte de tiempo (corrida A). Con 65 preguntas, cada caso vale 1.54 puntos.
5. **τ = 1 es la tolerancia correcta, medido:** con τ = 0 (corrida C) la regla veta en el ciclo 95 un
   ascenso que cedía **un solo** caso, y la neurona termina con **4 ascensos y +8.4 puntos** de guardia,
   contra **8 ascensos y +14.3** con τ = 1. Ser más estricto que un caso frena el aprendizaje
   (el riesgo de estancamiento que señaló el auditor es real, pero solo con τ = 0).

## 1. El hueco, en el código

En `_calibrar` el retador debía: no perder casos de guardia, perder ≤ 5 % de lo que gana, no bajar el
top-5, **no bajar ninguna categoría respecto de la fórmula**, y superar al campeón en aciertos
totales. Faltaba: *no quitarle al campeón lo que ya lograba en una categoría*.

Ahora (`core/memory/neurona.py`):

$$
\forall\,\text{cat}\in\text{examen},\ \forall\,m\in\{\text{aciertos\#1},\ \textstyle\sum 1/\text{puesto},\ \text{aciertos top-5}\}:\quad
m_{\text{retador}}(\text{cat}) \;\ge\; m_{\text{campeón}}(\text{cat}) - \tau,\qquad \tau = 1
$$

Las categorías del examen ya separan los dos caminos (`por_tema@agente`, `por_tema@crudo`), así que la
regla también es por camino. El campeón se mide con su margen recalibrado en ese mismo ciclo, sobre el
mismo examen. Costo: una pasada más sobre las mismas tablas (constante).

**¿Por qué τ = 1 y no 0?** Con τ = 0 cualquier caso suelto que el retador ordene distinto veta el
ascenso: la neurona quedaría pegada al primer campeón por ruido de un caso. τ = 1 corta los trueques
reales (perder 2 o más en una categoría) y deja pasar el ruido. La corrida C mide qué pasa con τ = 0.

## 2. Pruebas (`tests/test_neurona.py`, 5 nuevas)

| Prueba | Qué demuestra | Con el código anterior |
|---|---|---|
| `test_cumple_campeon_tolera_exactamente_tol_casos` | la función tolera 1 y no 2, en las tres métricas | no existía |
| `test_retador_que_gana_en_total_cediendo_una_categoria_no_asciende` | el trueque exacto de la crítica: gana 250 casos en "a", cede los 75 de "c" → **no asciende** y queda el mismo campeón | **FALLA: asciende** |
| `test_sin_la_regla_ese_mismo_retador_ascendia` | control: con la regla apagada, el mismo caso asciende (el veto lo hace esta capa y no otra) | pasa |
| `test_ceder_un_solo_caso_se_tolera_con_tol_1[1]` | ceder 1 caso: asciende | pasa |
| `test_ceder_un_solo_caso_se_tolera_con_tol_1[0]` | con τ = 0, ese mismo caso se veta | **FALLA: asciende** |

Suite completa: **402 passed** (397 + 5).

## 3. El A/B (copias del snapshot canónico, `PYTHONHASHSEED=1`)

Para que A y B sean comparables, el presupuesto de tiempo por ciclo se puso en 1000 s: ninguna
pregunta se salta por velocidad de la máquina y la corrida es **determinista**. (Con el presupuesto
normal de 3 s, dos corridas del mismo código ya difieren: por eso el despertar del README da 94.06 y
la corrida A 95.43 con el mismo código.)

- **A** = árbol exacto de `HEAD` antes del cambio (`2d2f880`).
- **B** = el mismo árbol, con **solo** `core/memory/neurona.py` cambiado (`diff -rq` lo verifica).
- **C** = B con τ = 0 (solo práctica), para medir la sensibilidad.

### Práctica (500 ciclos)

| | ascensos (ciclos) | vetos | retiros | guardia: fórmula → campeón | margen final |
|---|---|---|---|---|---|
| **A** (antes) | 8 (86, 87, 95, 103, 208, 307, 407, 413) | — | 0 | 77.7 % → **92.0 %** (+14.3) | 1.0 |
| **B** (τ = 1) | 8 (los mismos ciclos) | **0** | 0 | 77.7 % → **92.0 %** (+14.3) | 1.0 |
| C (τ = 0) | 4 (86, 87, 97, 303) | 1 (ciclo 95) | 0 | 79.6 % → 88.0 % (+8.4) | 1.5 |

**Determinismo verificado:** A y B coinciden en los 500 ciclos en todos los campos (examen, fases,
guardias, margen) y el campeón final es el mismo byte a byte (hash `085adece94154b6b`). En C, A y C
coinciden hasta el ciclo 94; en el 95, el único veto. (Las guardias de C no son exactamente las mismas
de A desde ahí, porque el examen sigue otro camino: por eso se compara la subida, no el valor.)

### QA oficial (motor directo, 875 + 40 negativos)

| categoría (n) | piso R@1 | A: R@5 / R@1 / MRR | B: R@5 / R@1 / MRR |
|---|---|---|---|
| cruce_idioma (8) | 62.50 | 100 / 87.50 / .938 | 100 / 87.50 / .938 |
| dormido (65) | 100 | 100 / 100 / 1.000 | 100 / 100 / 1.000 |
| literal (487) | 99.59 | 100 / 99.59 / .998 | 100 / 99.59 / .998 |
| por_tema (65) | 63.08 | 100 / **84.62** / .913 | 100 / **84.62** / .913 |
| pregunta_natural (65) | 93.85 | 100 / 96.92 / .985 | 100 / 96.92 / .985 |
| sinonimo (55) | 56.36 | 100 / 60.00 / .735 | 100 / 60.00 / .735 |
| typo (65) | 87.69 | 100 / 98.46 / .992 | 100 / 98.46 / .992 |
| variante_gramatical (65) | 87.69 | 100 / 96.92 / .981 | 100 / 96.92 / .981 |
| **GLOBAL (875)** | 91.66 | **100 / 95.43 / .972** | **100 / 95.43 / .972** |

FP 0/40 y GATE OK en ambas. Salida textual: `resultados/qa_oficial_A.txt` y `qa_oficial_B.txt`.

### Camino del agente (`recordar` por MCP, 875)

| categoría (n) | A: R@5 / R@1 / MRR | B: R@5 / R@1 / MRR |
|---|---|---|
| cruce_idioma (8) | 100 / 100 / 1.000 | 100 / 100 / 1.000 |
| dormido (65) | 100 / 100 / 1.000 | 100 / 100 / 1.000 |
| literal (487) | 100 / 99.59 / .998 | 100 / 99.59 / .998 |
| por_tema (65) | 98.46 / 80.00 / .875 | 98.46 / 80.00 / .875 |
| pregunta_natural (65) | 100 / 96.92 / .985 | 100 / 96.92 / .985 |
| sinonimo (55) | 96.36 / 60.00 / .725 | 96.36 / 60.00 / .725 |
| typo (65) | 100 / 98.46 / .992 | 100 / 98.46 / .992 |
| variante_gramatical (65) | 100 / 95.38 / .973 | 100 / 95.38 / .973 |
| **GLOBAL (875)** | **99.66 / 95.09 / .969** | **99.66 / 95.09 / .969** |

Primer lugar de B frente a A: **+0 / −0**. (Referencia del camino del agente con la fórmula a mano,
experimento 07: R@1 92.34, R@5 99.09.) Comparación completa: `resultados/comparacion.txt`.

## 4. Lo que esto NO dice

- No dice que la regla "mejora" los números: en esta corrida **no cambió nada**, porque nada la
  violó. Es un seguro: impide un trueque que en estos datos no ocurrió, pero que la regla anterior
  permitía (lo demuestra la prueba).
- No elimina la variación entre entrenamientos distintos (v4 vs v5, o con y sin presupuesto de
  tiempo): dos campeones aprendidos por caminos distintos pueden diferir en algunos casos por
  categoría, siempre por encima del piso.
- La neurona sigue siendo un reordenador: no rescata recuerdos que la fórmula dejó fuera del top-10.
  Medido en el camino del agente: **1 caso de 875** (el 0516, por_tema) queda fuera del top-10; en la
  QA oficial, **0** quedan fuera del top-5.

## 5. Reproducir

```bash
cd "docs/Mi neurona en el sistema/experimento_08_piso_contra_el_campeon"
mkdir -p /tmp/q/e08/base && (cd /home/user/MemoryBioRAG && git archive 2d2f880 | tar -x -C /tmp/q/e08/base)
cp -r /home/user/MemoryBioRAG/MemoryBioRAG_Data/nltk_data /tmp/q/e08/base/MemoryBioRAG_Data/
cp -a /tmp/q/e08/base /tmp/q/e08/nuevo && cp /home/user/MemoryBioRAG/core/memory/neurona.py /tmp/q/e08/nuevo/core/memory/
bash ab.sh A /tmp/q/e08/base      # ~45 min: práctica + QA oficial + camino MCP
bash ab.sh B /tmp/q/e08/nuevo     # ~45 min (nunca a la vez que A)
python comparar_ab.py > resultados/comparacion.txt
```

## 6. Archivos

- `practicar_ab.py`: driver de práctica determinista, una línea JSONL por ciclo.
- `ab.sh`: una corrida completa (práctica, QA oficial y camino MCP) sobre una copia nueva.
- `comparar_ab.py`: determinismo hasta el primer veto, práctica, QA y MCP por categoría.
- `resultados/`: `curva_*.jsonl`, `practica_*.txt`, `qa_oficial_*.txt`, `mcp_*.json|txt`, `comparacion.txt`.
