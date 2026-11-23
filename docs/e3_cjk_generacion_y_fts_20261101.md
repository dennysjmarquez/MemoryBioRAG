# E3: generación de candidatos CJK y sonda de índice

## Propósito

Continuación de `e3_trazas_perdidas_cjk_20261101.md`: observar etapas anteriores de búsqueda y distinguir ausencia de candidatos de descarte final. Pruebas sintéticas locales **directas**, no MCP, ni evaluación del agente, ni campaña E1. No se modificó motor, base original o neuronas. El conjunto de 20 recuerdos por idioma es pequeño y no tiene validación independiente de hablantes.

## 1. Trazas de generación

Código `70e42df8e3642f6aacad475cb344cdaf566e2d0a`. Entorno Python 3.11.2, SQLite 3.40.1, NumPy 2.4.6 y NLTK 3.9.4; gold SHA-256 `d3665a8e895ba061354ddd7d9c4fe44614956ad79d663433c6ef70e59aa78a6a`. Base temporal de 120 recuerdos, integridad comprobada, SHA `588dffc9febc8ac78fc71843220b487d84fd398f549f17e6dd93cdd76dcc08f4`, una copia por consulta. Reloj fijo, `PYTHONHASHSEED=0`, neurona de ranking apagada, `BIORAG_NO_LOG=1`, estado DMN individual, activos, límite 5 y peso sináptico ignorado.

`rastrear_generacion_cjk_e3_sintetico.py` observó 26 casos, `zh-06`–`zh-18` y `ja-06`–`ja-18`. Para cada uno comparó otra copia limpia sin observador: **26/26 salidas y scores iguales**. No registró información de una base viva.

| Punto observado en `core/memory/search.py` | 10 aciertos `06`–`10` de ambos idiomas | 16 fallos `11`–`18` de ambos idiomas |
|---|---:|---:|
| FTS principal, después del primer bloque (`:557`) | esperado presente 10/10 | pool vacío 16/16 |
| Después de los rescates previos al merge de concepto (`:1071`) | esperado presente 10/10 | pool vacío 16/16 |
| Final del bloque de generación, antes de normalización BM25 (`:1433`) | esperado presente 10/10 | pool vacío 16/16 |
| Después de construir scores, antes de ordenar (`:1875`) | esperado presente 10/10 | pool vacío 16/16 |
| Antes del filtro final (`:2081`) | esperado presente 10/10 | pool vacío 16/16 |

Estos son **puntos observados**, no una grabación de cada operación intermedia: no se puede afirmar que nunca haya existido un candidato entre dos puntos. En esta fixture y configuración, sin dimensiones o paráfrasis proporcionadas por un agente, los 16 fallos no tienen candidatos al terminar la generación; no basta con reajustar el orden de una lista vacía. Tampoco se prueba qué ruta anterior exacta debió aportar una pista.

## 2. Experimento aparte: FTS crudo con trigramas de la consulta

Para examinar el índice sin modificar la búsqueda del motor, se construyó **otra** base sintética nueva, SHA `96fc9281dd8067d1e2e26427da478618b4a520441b6760af483f779285511484`. Se consultó SQLite FTS directamente, sin límite ni ranking del motor, para los mismos 26 positivos y cuatro negativos `zh`/`ja`.

- Primer brazo: expresión completa limpiada. En los 26 positivos se comprobó que coincide con la expresión FTS registrada por la traza y que la presencia del esperado coincide con aquella observación; las bases fueron reconstruidas por separado, no son un A/B de bytes idénticos.
- Segundo brazo: **todos** los trigramas consecutivos únicos de la pregunta limpiada unidos con OR, sin mirar el recuerdo esperado para elegirlos ni descartar tokens. El índice devuelve candidatos, no respuestas finales.

| Conjunto | Expresión completa: esperado en FTS | OR de trigramas: esperado en FTS |
|---|---:|---:|
| `zh-11`–`zh-18` | 0/8 | 7/8 (`zh-18` no aparece) |
| `ja-11`–`ja-18` | 0/8 | 7/8 (`ja-17` no aparece) |
| Controles positivos `zh/ja-06`–`10` | 10/10 | 10/10 |

En los cuatro negativos, la expresión completa no encontró candidatos; el OR de trigramas encontró candidatos en **1/2 japoneses y 0/2 chinos**. También produjo dos candidatos en `ja-14` y `ja-16`. Son hallazgos del índice crudo: **no son FP finales ni R@5 del motor**, porque no se ejecutó con esa alternativa el pipeline completo. Los datos muestran que esta simplificación puede ampliar pistas y también traer candidatos en un negativo; por sí solos no permiten elegir una solución, medir precisión general, probar escalabilidad ni justificar el cambio de motor. Tampoco es un segmentador lingüístico ni demuestra comprensión.

## Evidencia y reproducción

Además, `tests/test_qa_multilingue_e3a.py` y `tests/test_comparar_qa_multilingue_b3.py` pasaron **9/9** en este entorno. Son pruebas focales del evaluador/comparador, no una suite completa ni validan el experimento OR como cambio de motor.

Scripts exactos y sus hashes:

- `scripts/rastrear_generacion_cjk_e3_sintetico.py`: `79c83b99cdfcc8bf5c56298493f007b01d7090ea3faa9c309c0d43ef828cdc73`.
- `scripts/sondear_fts_trigramas_cjk_e3_sintetico.py`: `e95cc01fe046fb2a43bb973adaee001f5426ff5640dd70deb365d2fc7d9705da`.

Desde la raíz, con `requirements.txt` instalado y nombres de salida que no existan:

```bash
mkdir -p google_drive/auditoria_neuronas
env -i HOME="$HOME" PATH="$PATH" PYTHONHASHSEED=0 BIORAG_NEURONA=0 BIORAG_NO_LOG=1 \
 NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. python \
 scripts/rastrear_generacion_cjk_e3_sintetico.py --salida google_drive/auditoria_neuronas/traza_nueva.json
env -i HOME="$HOME" PATH="$PATH" PYTHONHASHSEED=0 BIORAG_NEURONA=0 BIORAG_NO_LOG=1 \
 NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. python \
 scripts/sondear_fts_trigramas_cjk_e3_sintetico.py \
 --traza google_drive/auditoria_neuronas/traza_nueva.json --salida google_drive/auditoria_neuronas/fts_nuevo.json
```

Archivos de esta ejecución, también conservados en Drive privado y con checksums cotejados:

- `google_drive/auditoria_neuronas/e3_generacion_cjk_70e42df.json`: `02666f53796f0ed5876539a8fa6e6854736c3abfcb79b5e751f09270c22ff3f6`, Drive `1Y_ISZdIM-v0caUzR2IJNeNvLGkQb1-ap`.
- `google_drive/auditoria_neuronas/e3_fts_trigramas_70e42df.json`: `1728fd84db63afa664a12bf569efc8e5acc3663fef7f109e554b1cfe45e2dcfa`, Drive `1vea76SJU29C7fQRylHw57lwioxVHKUfK`.

## Pendiente

Investigar cómo el agente puede usar pistas y reformular mediante MCP con casos sintéticos y sin mirar respuestas, incluyendo las consultas no resueltas y controles negativos. Después corresponderían controles multilingües y de ruido más amplios antes de proponer cualquier cambio. No aplicar OR de trigramas ni quitar filtros como arreglo: exige diff, autorización y medición de recall, pistas, FP y costo. E3 sigue abierto; E4, fase 2 y v36 no quedan cerrados por estas sondas.
