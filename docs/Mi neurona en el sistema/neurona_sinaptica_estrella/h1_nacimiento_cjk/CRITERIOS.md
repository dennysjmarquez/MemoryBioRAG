# H1 «ojos Unicode» en el nacimiento de sinapsis: criterios fijados ANTES de medir (2026-11-25)

## Problema (verificado leyendo el código y medido en el Paso 2b)
Con 839 frases reales por idioma y sin estructura declarada, el motor creó **es 643, en 679, zh 4, ja 0** filas de
sinapsis. Las dos reglas automáticas de nacimiento no ven chino ni japonés:
- `core/sinapsis.py` `_tokenizar` (lo usa `auto_vincular`): `\b[a-zA-Záéíóúñ]{4,}\b`, solo letras latinas;
- `core/memory/consolidation.py` `_auto_generar_co_ocurrencia` (sueño): `\w{4,}`, que en CJK toma una corrida entera
  («今晚我炒蒜和番茄配米饭») como una sola palabra.
Además, `auto_vincular` busca candidatos con el índice trigram, y los términos de menos de 3 caracteres no entran.

## El cambio (uno solo: «las reglas de nacimiento ven CJK»)
Un módulo `core/cjk_unidades.py` con las unidades de la escritura sin espacios (bigramas de cada corrida de
ideogramas y kana; un ideograma o katakana suelto es una unidad), detectadas por el nombre Unicode del carácter, sin
listas. Se usa en los dos puntos de nacimiento, y para generar candidatos con trigramas CJK en el índice trigram.
**En un texto sin caracteres CJK, todo queda exactamente igual que antes** (por construcción y comprobado).
No se tocan umbrales, pesos, tipos ni `pmi_semantico` (ese tokenizador también lo usa el ranking: queda para otro
ciclo). No se toca el ranking.

## Datos y método (buenas prácticas)
- Mundo real UD PUD (es, en, zh, ja; mismas frases), construido con el motor real como en el Paso 2b (`guardar` del
  exp. 16 copiado en el script, sueño cada 50 y al final, misma semilla y entorno).
- **Partición por documento:** desarrollo = `sha256("h1|"+doc) % 5 < 2` (~40 %); **sellado** = el resto (~60 %).
  El diseño solo se mira y ajusta en desarrollo. El sellado se mide **una vez**, al final, Antes y Después.
- Antes = commit `08e9825` en una copia aparte (`git worktree`). Después = el mismo commit + el cambio.
- Relación real (solo para auditar): dos frases del mismo documento.

## Criterios en el mundo sellado (todos deben cumplirse)
| id | qué | umbral |
|---|---|---|
| N1 | Cobertura: filas de sinapsis en zh y en ja | ≥ 50 % de la media de es y en (Después) |
| N2 | Precisión: fracción de aristas entre frases del mismo documento, en zh y en ja | ≥ 0,8 × la menor de es y en (Después), y ≥ 10 × la tasa al azar |
| N3 | Identidad fuera de CJK: tabla de sinapsis de es y en (origen, destino, tipo, peso) | idéntica Antes y Después |
| N4 | Hubs: grado medio y grado máximo en zh y ja | ≤ 2 × el de es/en (el mayor de los dos) |
| N5 | Coste: tiempo de construcción de zh y ja | ≤ 2 × el mayor de es/en |

## Puertas de regresión del motor (Antes frente a Después)
| puerta | criterio |
|---|---|
| `pytest tests` completo | mismos aprobados y saltados (más los tests nuevos en verde) |
| `scripts/evaluar_qa.py` | R@5, R@1, MRR y FP idénticos |
| `benchmark_abismo_lexico.py` | idéntico |
| `scripts/evaluar_qa_multilingue_e3a.py` | ninguna métrica baja en ningún idioma (aquí el cambio sí puede crear sinapsis en zh/ja) |
| `tests/test_ojos_unicode_cjk_corto.py` | en verde |

Si algún criterio falla en el sellado, no se ajusta el diseño mirando el sellado: se informa tal cual.
