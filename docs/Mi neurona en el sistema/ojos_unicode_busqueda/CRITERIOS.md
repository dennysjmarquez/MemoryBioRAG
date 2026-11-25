# Paso 1 «ojos Unicode»: criterios fijados ANTES de medir (2026-11-25)

## Qué se arregla
En E1 (experimento 18) las palabras chinas o japonesas de 1–2 caracteres daban **0 resultados**
(`番茄`, `消防`, `足球`). La mayoría de las palabras chinas tienen 2 caracteres. Causa
(verificada leyendo el código y con FTS5 en una base temporal):
- el índice `trigram` no busca menos de 3 caracteres;
- `unicode61` toma una corrida CJK entera («炒蒜和番茄配米饭») como UNA palabra, así que el
  fallback de prefijo `番茄*` solo encuentra textos donde la corrida empieza por 番茄.

## El cambio (uno solo)
`core/memory/cjk_corto.py` + fallback 1.4b en `core/memory/search.py`: si la consulta trae una
corrida china/japonesa de 1–2 caracteres, se busca como subcadena (concepto, sinónimos,
sustantivos clave, contenido) y se puntúa con la misma fórmula de cobertura del ranker estable,
**usando solo la consulta y ese recuerdo** (sin estadísticas del corpus). Detección por nombre
Unicode (ideogramas, hiragana, katakana): sin listas de palabras ni diccionarios de idioma.
Sin corrida CJK corta en la consulta el código no se ejecuta.

## Criterios (todos deben cumplirse)
Medidos con `medir_ojos_unicode.py`, mundo sintético nuevo en una carpeta temporal, reloj fijo,
`PYTHONHASHSEED=0`, `BIORAG_NEURONA=0`, una copia de la base por consulta, `limite=5`.
No se abre la DB viva ni el snapshot para este experimento.

| id | criterio | umbral |
|---|---|---|
| U1 | Recall CJK corto: consultas zh/ja de 1–2 caracteres cuyo recuerdo objetivo está en el top-5 | ≥ 10 de 11 (Después) |
| U2 | Precisión: el distractor que comparte UN carácter (番薯 frente a 番茄, etc.) nunca queda por encima del objetivo | 0 casos |
| U3 | Falsos positivos: consultas CJK cortas sin ningún recuerdo que las contenga, con resultados | Después ≤ Antes y = 0 |
| U4 | Identidad fuera de CJK corto: consultas es/en/ko/ru y CJK de ≥ 3 caracteres, mismo top-5 y mismos scores Antes y Después | 100 % idénticas |
| U5 | Invariancia: añadir 40 recuerdos ajenos (que no contienen los términos) no cambia el top-5 de ninguna consulta U1 | 100 % idénticas (Después) |
| U6 | Partícula hiragana suelta (`の`) no activa el fallback | `terminos("の") == ()` |

## Puertas de regresión del motor (Antes = commit `3291338`, sin el cambio)
| puerta | criterio |
|---|---|
| `pytest tests` completo | mismos fallos/aprobados que Antes (ningún test nuevo en rojo) |
| `scripts/evaluar_qa.py` | R@5, R@1, MRR y FP exactamente iguales |
| `benchmark_abismo_lexico.py` | mismas cifras |
| `scripts/evaluar_qa_multilingue_e3a.py` (132 casos, 6 idiomas) | ninguna métrica baja en ningún idioma |

Si algún criterio falla, el cambio no se queda tal cual: se informa y se corrige o se revierte.
