# H1 «ojos Unicode» en el nacimiento de sinapsis: resultados (2026-11-26)

[V] = verificado o medido aquí. [D] = deducción o propuesta, sin medir.

## 1. Para quien llega sin contexto
El motor crea sinapsis automáticas entre recuerdos que comparten palabras (`auto_vincular` al guardar y la
co-ocurrencia del sueño). En el Paso 2b, con las mismas ~839 frases reales en cuatro idiomas, nacieron 643 sinapsis en
español, 679 en inglés, **4 en chino y 0 en japonés**. Las dos reglas buscaban palabras con letras latinas
(`[a-zA-Záéíóúñ]{4,}`) o con `\w{4,}`, que en chino toma una frase entera como una sola «palabra». Para un usuario que
escribe en chino o japonés, el grafo de asociaciones estaba vacío.

## 2. El cambio (uno solo) [V]
- **Nuevo `core/cjk_unidades.py`**: parte las corridas de ideogramas y kana en bigramas de caracteres. Detecta la
  escritura por el nombre Unicode del carácter (sin listas de palabras ni diccionarios). Un bigrama solo de hiragana
  (した, ている) es gramática y no cuenta: es una regla de escritura, el equivalente de la regla latina «4 letras o
  más». El katakana de media anchura también cuenta (NFKC).
- **`core/sinapsis.py` `_tokenizar`**: suma esas unidades. La parte latina se lee con lo CJK cambiado por espacios
  («Python中文» ahora da «python»). `auto_vincular` pide candidatos al índice trigram también con subcadenas CJK de 3
  caracteres (como mucho 32).
- **`core/memory/consolidation.py` `_auto_generar_co_ocurrencia`**: la misma regla en sus dos puntos (sesión y
  mensajes).
- **Sin cambios** en umbrales, pesos, tipos, ranking, canal 1, `pmi_semantico` ni los enlaces manuales.
- **Fuera de CJK, idéntico por construcción**: si el texto no tiene ideogramas ni kana, `sin_cjk` devuelve el mismo
  texto y `unidades` devuelve vacío (lo comprueban los tests, y la medición N3 abajo).

## 3. Método [V]
Criterios fijados antes de medir en `CRITERIOS.md`. Mundo real UD PUD (es, en, zh, ja: las mismas frases), construido
con el motor real como en el Paso 2b (`guardar` del exp. 16, sueño cada 50 y al final, mismo entorno).
**Partición por documento**: desarrollo (166 documentos, 416 frases) para diseñar; **sellado** (231 documentos, 584
frases) medido una sola vez al final. Antes = commit `08e9825` en un `git worktree` aparte; Después = el mismo commit +
el cambio. La «relación real» solo se usa para auditar: dos frases del mismo documento.

## 4. Resultado en el mundo sellado [V]

| | es | en | zh | ja |
|---|---|---|---|---|
| sinapsis Antes | 367 | 532 | **4** | **0** |
| sinapsis Después | 367 (idéntico) | 532 (idéntico) | **406** | **736** |
| precisión: aristas del mismo documento | 20,5 % | 17,9 % | **40,9 %** | **27,9 %** |
| lift sobre el azar (0,37 %) | ×55 | ×48 | ×110 | ×75 |
| grado medio / máximo | 1,25 / 23 | 1,78 / 26 | 1,39 / 8 | 2,52 / 11 |
| recuerdos con alguna sinapsis | 219 | 284 | 364 | 468 |
| construcción | 23,2 s | 21,8 s | 9,4 s | 7,5 s |

| criterio | umbral | medido | ¿pasa? |
|---|---|---|---|
| N1 cobertura zh, ja | ≥ 50 % de la media es/en (449,5 → 225) | 406 y 736 | ✅ |
| N2 precisión zh, ja | ≥ 0,8 × 17,9 % = 14,3 % y lift ≥ 10 | 40,9 % / 27,9 %; ×110 / ×75 | ✅ |
| N3 identidad es, en (origen, destino, tipo, peso) | idéntica | 367/367 y 532/532 filas idénticas | ✅ |
| N4 hubs zh, ja | grado medio ≤ 3,56; máximo ≤ 52 | 1,39 / 2,52; 8 / 11 | ✅ |
| N5 coste zh, ja | ≤ 46,4 s | 9,4 s / 7,5 s | ✅ |

**Pasa 5 de 5.** En desarrollo (donde se diseñó) salió lo mismo: zh 0 → 247 (45,8 %), ja 0 → 502 (29,1 %).

**Ablación hecha en desarrollo, antes de mirar el sellado** [V]: sin la regla «bigrama solo de hiragana no cuenta»,
el japonés da 1434 sinapsis con un 15,8 % de precisión y grado medio 6,9 (hubs de gramática). Con la regla: 502,
29,1 % y 2,4. Por eso se quedó.

## 5. Puertas de regresión del motor [V]
El «Antes» de las puertas es la medición del Paso 1 (`../../ojos_unicode_busqueda/resultados/puerta_*_despues.json`):
`git diff 11e25c4 08e9825 -- core scripts tests snapshots benchmark_abismo_lexico.py` está vacío, así que es el mismo
motor.

| puerta | Antes | Después |
|---|---|---|
| `pytest tests` | 1123 + 16 del Paso 1 = 1139 passed, 18 skipped | **1157 passed, 18 skipped** (= 1139 + 18 tests nuevos de H1) |
| `scripts/evaluar_qa.py` (921 casos, snapshot) | R@5 100 %, R@1 93,03 %, MRR 0,957, FP 0/40 | **idéntico** (solo cambian metadatos de procedencia y duración) |
| `benchmark_abismo_lexico.py` | S3 R@1 1,00 · R@5 1,00 · MRR 1,000 | **idéntico**, caso por caso |
| `evaluar_qa_multilingue_e3a.py` (132 casos) | zh 12/20 · ja 12/20 · … | **idéntico** caso por caso; solo cambia el sha de la base temporal (ahora nacen sinapsis en zh/ja) |
| `tests/test_ojos_unicode_cjk_corto.py` | verde | verde |

El snapshot no se tocó (sha256 `104dd2902aaf24c3…` antes y después).

## 6. Qué se ve en las aristas nuevas (lectura de ejemplos) [V] y lo que queda [D]
- Las aristas del mismo documento son buenas: «女兒 / 殺死 / 試圖» unen dos frases de la misma noticia.
- Muchas aristas «de otro documento» son **puentes temáticos legítimos** (p. ej. «政權轉移», la transición de poder,
  aparece en dos noticias distintas). La métrica del mismo documento las cuenta como error: la precisión real es
  mayor que la medida.
- Ruido que queda [D]: bigramas que cruzan la frontera entre un kanji y una partícula («の移», «が大», «女は») y el
  doble conteo de los bigramas solapados (una palabra de 3 caracteres comparte 2 bigramas). Posible mejora en otro
  ciclo, con criterios propios. No se ajustó aquí para no diseñar mirando el sellado.
- **`pmi_hebbiano` sigue sin ver CJK**: `core/pmi_semantico.py` solo tokeniza letras latinas y también lo usa el
  ranking. Todas las sinapsis nuevas de zh/ja son `co_ocurrencia`. Ciclo aparte.
- La pasada 2 de `auto_vincular` (por nombre de concepto) sigue con la regex latina; en PUD no aplica (los nombres
  son ids). Ciclo aparte si los nombres de concepto vienen en CJK.
- El coreano (hangul) no entra en este cambio: separa las palabras con espacios, pero pega las partículas. Ciclo aparte.

## 7. Reproducir
```
cd "docs/Mi neurona en el sistema/neurona_sinaptica_estrella/h1_nacimiento_cjk"
git worktree add --detach /tmp/h1_antes 08e9825
python medir_nacimiento.py medir /tmp/h1_antes antes sellado
python medir_nacimiento.py medir <repo> despues sellado
python -m pytest -q tests/test_h1_nacimiento_cjk.py tests/test_ojos_unicode_cjk_corto.py
```
Archivos: `CRITERIOS.md`, `medir_nacimiento.py`, `resultados/*.json` (con la tabla de sinapsis completa de cada mundo).
