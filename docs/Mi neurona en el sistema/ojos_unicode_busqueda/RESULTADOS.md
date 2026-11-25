# Paso 1 «ojos Unicode»: resultados (2026-11-25)

Criterios fijados antes de medir: `CRITERIOS.md`. Antes = commit `3291338`, en una copia aparte del repo
(`git worktree`). Después = el mismo commit + este cambio. [V] = medido, [D] = deducido.

## 1. Qué problema había (para alguien sin contexto)
Un recuerdo dice «今晚我炒蒜和番茄配米饭» («esta noche salteé ajo con **tomate** y arroz»). Buscar `番茄`
(tomate) devolvía **nada**. En chino casi todas las palabras tienen 2 caracteres, así que el motor era casi
ciego en chino y japonés para búsquedas de una palabra. Dos causas [V]:
1. El índice `trigram` necesita 3 caracteres como mínimo.
2. El índice `unicode61` separa palabras por espacios y puntuación; el chino no usa espacios, así que
   «今晚我炒蒜和番茄配米饭» es para él UNA sola palabra, y `番茄*` solo encuentra corridas que **empiezan** por 番茄.

## 2. El cambio (uno solo)
- `core/memory/cjk_corto.py` (nuevo): detecta en la consulta corridas chinas/japonesas de 1–2 caracteres
  (por el nombre Unicode del carácter, sin listas de palabras), las busca como subcadena en concepto,
  sinónimos, sustantivos clave y contenido, y puntúa cada recuerdo con la misma fórmula de cobertura del
  ranker estable (0,65 unión + 0,20 mejor campo + 0,15 ponderado), **solo con la consulta y ese recuerdo**.
- `core/memory/search.py`: fallback 1.4b justo después del fallback `unicode61`, con los mismos filtros
  (estado, categoría, fechas, corte estable de rowid) y la misma condición (pool < 3, sin modo estricto);
  y su gemelo en el overlay de altas nuevas.
- Una partícula hiragana suelta (の, は) no activa nada; un ideograma o katakana suelto sí (猫, 树).
- Sin corrida CJK corta en la consulta, el código nuevo no se ejecuta (lo comprueba un test).

## 3. Mundo sintético (U1–U6) [V]
`medir_ojos_unicode.py`, 22 recuerdos en zh/ja/ko/ru/es/en + 40 ajenos para invariancia; reloj fijo,
una copia por consulta. JSON: `resultados/antes.json`, `resultados/despues.json`.

| criterio | umbral | Antes | Después | |
|---|---|---|---|---|
| U1 recall CJK corto (top-5) | ≥ 10/11 | **0/11** | **11/11** (las 11 en top-1) | ✅ |
| U2 distractor de un carácter por encima | 0 | 0 | 0 (番薯, 消息, 足, 電話 nunca aparecen) | ✅ |
| U3 falsos positivos (钢琴, 鉛筆, 雪, ピザ) | Después ≤ Antes y = 0 | 0 | 0 | ✅ |
| U4 identidad fuera de CJK corto (12 consultas) | 100 % | — | 12/12 idénticas (top-5 y scores) | ✅ |
| U5 invariancia con 40 ajenos | 100 % | — | 11/11 idénticas | ✅ |
| U6 `terminos("の")` | `()` | — | `()` | ✅ |

Latencia por consulta en el mundo pequeño: mediana 2,9 → 2,5 ms, máximo 13,0 → 8,5 ms (ruido; sin coste visible).
Dato correcto, no ruido: `猫` (gato) trae también el recuerdo chino «三只猫», porque el carácter es el mismo.

## 4. Puertas de regresión del motor [V]
| puerta | Antes | Después |
|---|---|---|
| `pytest tests` | 1123 passed, 18 skipped | 1123 passed, 18 skipped (+16 tests nuevos aparte, en verde) |
| `scripts/evaluar_qa.py` (875 + 40 negativos) | R@5 100 %, R@1 93,03 %, MRR 0,957, FP 0/40, GATE OK | **idéntico**, todas las categorías |
| `benchmark_abismo_lexico.py` | S3 R@1 1,00 · R@5 1,00 · MRR 1,000 | **idéntico** |
| `evaluar_qa_multilingue_e3a.py` (132 casos) | zh 12/12/0,6 · ja 12/12/0,6 · ko 18/19 · ru 19/20 · en 20/20 · es 20/20 | **idéntico** caso por caso |

Notas: la QA midió una copia temporal del snapshot como puerta de regresión (sha256 `104dd290…` igual antes y
después). Los JSON de la QA difieren solo en dos metadatos de procedencia (`origen_es_snapshot`, `referencia`),
porque el Antes corrió desde la copia del repo, donde el snapshot no existe; las métricas son idénticas.
El sistema S4 del abismo no se pudo medir en ninguno de los dos lados (falta `sklearn` en el entorno).
`pytest` debe correrse sin `BIORAG_WORDNET_ENABLED=0`: con esa variable falla
`test_typo_de_verdad_sigue_teniendo_parecido_difuso` también en el commit base (es del entorno, no del cambio).

## 5. Lo que este cambio NO arregla (hallazgos para ciclos aparte)
1. **Coreano de 2 sílabas** [V]: `사과` y `영화` dan 0 resultados antes y después. Causa (leída en el código):
   `_agregar_prefix_wildcards` (`core/memory/scoring.py` L67) no pone `*` a términos de < 3 caracteres, y el
   coreano pega las partículas a la palabra (`사과를`). Propuesta: un cambio igual de pequeño, en su propio ciclo.
2. **Preguntas enteras en chino/japonés** [V]: zh-11…zh-18 (y sus equivalentes en japonés) siguen en 0: la
   pregunta es una corrida larga sin espacios. Es otro problema (segmentar la consulta, p. ej. con bigramas) y
   toca más el ranking; necesita su propio ciclo y criterios.
3. [D] El fallback solo actúa si el pool tiene < 3 resultados (la misma regla que el fallback `unicode61`). En
   un corpus chino grande, si ya hay ≥ 3 recuerdos que *empiezan* por la palabra, los que la tienen en medio no
   se añaden. No se observó en las mediciones; queda anotado.
4. [D] El gemelo en el overlay de altas nuevas está cubierto por la suite general pero no tiene un test propio.

## 6. Reproducir
```
PYTHONHASHSEED=0 BIORAG_NEURONA=0 python "docs/Mi neurona en el sistema/ojos_unicode_busqueda/medir_ojos_unicode.py" --repo . --salida /tmp/despues.json
python -m pytest -q tests/test_ojos_unicode_cjk_corto.py
```
