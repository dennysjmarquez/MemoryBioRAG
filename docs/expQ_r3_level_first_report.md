# EXP-Q-R3: Level-First Ordering — Cambio Estructural del Cap

**Fecha**: 2026-09-09T07:35:01
**SHA estable**: ✅

## Hipótesis (Claude)

Ordenar contextos por `(nivel ASC, score DESC)` en vez de solo `score DESC`.
Un nodo más cercano en el grafo siempre gana a uno más lejano.
Cero hiperparámetros nuevos → cero riesgo de sobreajuste con n=2.

## Comparación Directa

| Caso | score_desc | level_first |
|:--|:--:|:--:|
| CASE_01 | NOT_FOUND | NOT_FOUND |
| CASE_02 | cw2:R23 | cw3:R38 |
| CASE_03 | NOT_FOUND | NOT_FOUND |
| CASE_04 | NOT_FOUND | NOT_FOUND |
| CASE_05 | cw1:R7 | cw1:R7, cw2:R7, cw3:R7 |

| **Generaciones** | 2 | 2 |
| **MonoViol** | 2 | 0 |
| **FP neg** | 0 | 0 |

## Veredicto

**LEVEL_FIRST_MEJORA_PARCIAL**

Level_first mejora monotonía (2→0) sin perder generaciones. Pero CASE_02 NO aparece en cw=2. Mejora sobre baseline pero no resuelve completamente el problema estructural.

---
*EXP-Q-R3 — core/ invariante — BFS con ordenamiento experimental*