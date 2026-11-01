# E3: dónde llegan las pérdidas chinas y japonesas — sonda sintética

## Pregunta y límites

En el control E3 actual faltan ocho consultas chinas y ocho japonesas del top 5. Se comprobó si el filtro final de una palabra las elimina en esas búsquedas. También se incluyeron los cinco aciertos de fragmento de cada idioma como control. Esto es búsqueda **directa**, no MCP ni prueba del agente completo. El gold y los recuerdos son sintéticos y no están validados por hablantes independientes. No se cambió el motor ni se propone quitar filtros; no es E1, QA oficial, ni medición de una base real.

## Ejecución

- Código de motor `6ea2387bfda92e29bbd811c9b398e9f9b0f3d504`; Python 3.11.2, SQLite 3.40.1, NumPy 2.4.6, NLTK 3.9.4.
- `scripts/auditar_perdidas_cjk_e3_sintetico.py` SHA-256 `d9b85708ad2c813b29712b012ce03a5a8b22c49d3a953d0ba7cd28cf386f0bf2`. Gold `scripts/casos_qa_multilingue_e3a.jsonl`, SHA-256 `d3665a8e895ba061354ddd7d9c4fe44614956ad79d663433c6ef70e59aa78a6a`.
- Se reconstruyeron 120 recuerdos en una base temporal nueva mediante el evaluador E3A; integridad OK, WAL vaciado, SHA de esa fuente `3e3022b439f967bde0390ca8b3add7da2c209d6bb5c0dce0c4c6d2258e9233a6`. Una copia limpia por búsqueda. Reloj fijo, `PYTHONHASHSEED=0`, `BIORAG_NEURONA=0`, `BIORAG_NO_LOG=1`, NLTK local; estado DMN separado por llamada. `profundidad=activos`, `limite=5`, `ignore_peso_sinaptico=True`. No se accedió a una base original ni se entrenó.
- Se observaron `zh-06` a `zh-18` y `ja-06` a `ja-18`. El observador de líneas solo leyó el pool justo antes del filtro final (`search.py:2081`) y justo después (`:2120`); no es una traza de todas las etapas. Cada caso se ejecutó también sin observador desde otra copia de la misma fuente: **26/26 listas, scores y totales idénticos**.
- Primer intento: abortó en `zh-06` sin generar resultados porque se apuntó a una línea `if (` sin evento de traza en Python 3.11. Se corrigió el punto a su primer operando y se repitió desde una base temporal nueva. El fallo fue del observador, no evidencia de comportamiento del motor; el log del intento quedó en `google_drive/auditoria_neuronas/e3_cjk_intento_fallido.log`.

Reproducir desde la raíz, con dependencias de `requirements.txt` instaladas y un nombre de salida nuevo:

```bash
env -i HOME="$HOME" PATH="$PATH" PYTHONHASHSEED=0 BIORAG_NEURONA=0 \
  BIORAG_NO_LOG=1 NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. \
  python scripts/auditar_perdidas_cjk_e3_sintetico.py --salida google_drive/auditoria_neuronas/e3_cjk_nueva.json
```

El script comprueba las instrucciones observadas y aborta si cambia la estructura o difiere el resultado con y sin observador. La huella SQLite de una base reconstruida puede variar; no se supone igualdad de bytes entre reconstrucciones.

## Resultado

| Casos | En top 5 | Esperado en pool antes del filtro | Esperado en pool después |
|---|---:|---:|---:|
| `zh-06`–`zh-10` | 5/5 | 5/5 | 5/5 |
| `zh-11`–`zh-18` | 0/8 | 0/8 | 0/8 |
| `ja-06`–`ja-10` | 5/5 | 5/5 | 5/5 |
| `ja-11`–`ja-18` | 0/8 | 0/8 | 0/8 |

En cada uno de los 16 fallos el pool completo ya estaba **vacío antes** de ese filtro, y el total devuelto fue 0. La expresión usada por el filtro trató cada pregunta de estos 16 casos como un solo token de tres o más caracteres. La observación **no demuestra que el filtro final sea la causa**: no tenía candidatos que filtrar en ese punto. Tampoco demuestra que el esperado nunca haya aparecido en etapas anteriores o explica exactamente dónde se pierde. Las sondas históricas con fragmentos en `docs/e3a_investigacion_multilingue_20261027.md` probaron otro caso; no deben generalizarse a estas preguntas completas.

La separación por espacios de varias rutas en `core/memory/search.py` merece investigación para escrituras sin espacios, pero el token observado no basta para demostrar causalidad ni para elegir un segmentador. Siguiente paso: rastrear creación y descarte de candidatos en las etapas anteriores, proteger pistas y usar controles de otros idiomas y ruido. Una propuesta de cambio requerirá diff y autorización, seguida de comparación aislada; no se ha corregido el problema.

## Evidencia

Detalle por caso, sin contenido de memorias reales: `google_drive/auditoria_neuronas/e3_cjk_trazas_6ea2387.json`, SHA-256 `3747488bb72a925979b9c6896ecd26064498167d2a5850e15bc926486072e96b`; copia privada Drive `1uoEVSdgsT8m6efH6hYB8gcxIyuzjOnH6`, checksum cotejado. Log de ejecución exitosa: `google_drive/auditoria_neuronas/e3_cjk_trazas_6ea2387.log`. E3 continúa abierto.
