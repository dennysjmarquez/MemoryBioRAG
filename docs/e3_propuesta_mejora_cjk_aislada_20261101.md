# E3 — propuesta CJK aislada para auditoría (NO APLICADA)

**Estado:** E3 continúa abierto. Este informe propone un cambio experimental de generación de candidatos; no lo aplica ni solicita cerrar E3. No avanzar a E4 hasta la auditoría de esta evidencia y autorización específica para cualquier cambio de motor.

## Base documental y aislamiento

Se leyeron los cuatro informes solicitados en `arena/6459e2d0-memorybiorag`, commit completo `5fcdac24a6cc7ab59d6987563cb62de7e95c92d4` (abreviado `5fcdac2`). El archivo de motor inspeccionado en esa referencia y en este checkout tiene el mismo SHA-256: `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6` (`core/memory/search.py`). El checkout local permaneció en la rama activa; no se cambió de rama.

Las ejecuciones de ranking usaron Python 3.11.2, SQLite 3.40.1, NumPy 2.4.6, NLTK 3.9.4, `PYTHONHASHSEED=0`, `BIORAG_NEURONA=0`, `BIORAG_NO_LOG=1`, reloj fijo, neurona de ranking apagada y la fixture E3A sintética de 120 recuerdos/132 consultas. SHA-256 de la fixture: `d3665a8e895ba061354ddd7d9c4fe44614956ad79d663433c6ef70e59aa78a6a`. No se abrió ni copió una base de usuario; cada ejecución creó su base temporal mediante la API y la eliminó al salir.

La referencia y los candidatos generaron sus bases por separado; sus hashes SQLite difieren. Por ello las cifras son una comparación descriptiva sobre la misma fixture y constructor, **no un A/B pareado sobre bytes idénticos**. En cada ejecución se repitieron las 132 consultas en orden inverso sobre su propia fuente: 0 diferencias dentro de la corrida para baseline y para el candidato amplio.

## Hallazgo y propuesta

Los informes previos encontraron que el OR crudo de trigramas CJK amplía el pool de 14 de 16 positivos fallidos (7/8 zh y 7/8 ja), pero también devuelve candidatos para 1/4 negativos CJK. El candidato adjunto explora ese canal como **adición** después de la generación existente: no sustituye resultados, no elimina recuerdos, no cambia el FTS principal, no toca asociaciones ni el filtro B4b descartado. Marca el origen como no literal para evitar que el filtro de prefijo de consulta de una palabra —que trata una cadena CJK como token único— descarte el resultado recién recuperado.

El diff exacto del candidato amplio, separado y no aplicado, está en [`e3_cjk_trigram_propuesta_NO_APLICAR_20261101.patch`](e3_cjk_trigram_propuesta_NO_APLICAR_20261101.patch). El experimento diagnóstico de umbral ≥2 tiene su propio diff igualmente no aplicado en [`e3_cjk_trigram_umbral2_DIAGNOSTICO_NO_APLICAR_20261101.patch`](e3_cjk_trigram_umbral2_DIAGNOSTICO_NO_APLICAR_20261101.patch); no forma parte de la propuesta principal. Ambos se ensayaron en copias aisladas de `core/memory/search.py`; el archivo rastreado del motor no fue editado. Ninguno está autorizado para aplicación.

La reproducción automatizada está en [`scripts/reproducir_medicion_cjk_aislada_e3.py`](../scripts/reproducir_medicion_cjk_aislada_e3.py) y usa el evaluador [`scripts/evaluar_qa_multilingue_e3a.py`](../scripts/evaluar_qa_multilingue_e3a.py) y la fixture sintética [`scripts/casos_qa_multilingue_e3a.jsonl`](../scripts/casos_qa_multilingue_e3a.jsonl). Con dependencias instaladas, ejecútese desde la raíz en un entorno limpio con `env -u BIORAG_PATH PYTHONHASHSEED=0 BIORAG_NEURONA=0 BIORAG_NO_LOG=1 NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. python scripts/reproducir_medicion_cjk_aislada_e3.py --salida /tmp/e3-cjk-repro-nueva`. El directorio de salida debe no existir; contiene tres JSON completos de la fixture inventada (baseline, OR y umbral 2). Se publican asimismo las salidas completas de la corrida: [`e3a_baseline_sintetico_20261101.json`](e3a_baseline_sintetico_20261101.json), [`e3a_candidato_or_sintetico_20261101.json`](e3a_candidato_or_sintetico_20261101.json) y [`e3a_umbral2_sintetico_20261101.json`](e3a_umbral2_sintetico_20261101.json). La prueba mínima de pista sináptica se recrea con `env -u BIORAG_PATH PYTHONHASHSEED=0 BIORAG_NEURONA=0 BIORAG_NO_LOG=1 NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. python scripts/reproducir_pista_mcp_cjk_e3_sintetica.py`; su resumen está en [`e3_pista_mcp_sintetica_resultado_20261101.json`](e3_pista_mcp_sintetica_resultado_20261101.json).

## Medición de ranking

R@5 y falsos positivos (FP) de la batería sintética E3A:

| Idioma / control | Baseline | Candidato OR CJK amplio | Cambio observado |
|---|---:|---:|---:|
| zh positivos | 12/20 (60%) | 19/20 (95%) | +7 recuperados; zh-18 sigue sin aparecer |
| ja positivos | 12/20 (60%) | 19/20 (95%) | +7 recuperados; ja-17 sigue sin aparecer |
| zh negativos | 0/2 FP | 0/2 FP | sin cambio en esta fixture |
| ja negativos | 0/2 FP | 1/2 FP | aparece un FP nuevo (ja-n01) |
| en negativos | 2/2 FP | 2/2 FP | FP ingleses previos persisten; no mejora |
| ko / ru / es | baseline sin cambio | mismas métricas | sin cambio en esta fixture |

Los casos que entraron con el candidato quedaron en rango 1 en estos positivos; esta fixture pequeña no prueba ranking en corpus poblados. También hubo distractores en el top-5 japonés de ja-14 y ja-16; el caso negativo ja-n01 devolvió `真鍮の方位磁針`. No interpretar el 1/2 japonés como una tasa general: son solo dos controles negativos por idioma.

Como análisis de sensibilidad adicional, se probó en otra copia exigir al menos dos trigramas compartidos antes de añadir un candidato OR. Dio zh 17/20, ja 19/20 y 0/4 FP CJK, pero descartó dos recuperaciones chinas que solo compartían un trigrama (zh-11 y zh-14). **Ese filtro no está en el parche ni se recomienda como decisión**: muestra el intercambio recall/FP y no debe usarse para eliminar pistas sin más evidencia. No se usó B4b.

## Pista sináptica: prueba mínima por handlers MCP

Para abordar la carencia de la exploración previa, se creó otra base temporal, fresca y totalmente sintética con dos recuerdos japoneses. Se escribió por los handlers de MCP `_aprender_impl`, se creó un enlace bidireccional explícito `manual` mediante `vincular_con` (peso 0.5) y se consultó por `_recordar_impl` con `context_window=1`. Integridad SQLite final: `ok`.

- Con una paráfrasis más libre, el seed no apareció: **0/1** en esa consulta.
- Con la consulta del caso alineada con el texto del seed, MCP devolvió el seed como resultado primario y el recuerdo conectado en `contexto_expandido`: **seguimiento de pista 1/1** en ese trayecto sintético.
- El destino no apareció como primario en esa búsqueda; fue recuperado como vecino del seed. La traza muestra una arista manual real en la base temporal, no una asociación inventada en la respuesta.

Es una comprobación de que el transporte de contexto puede exponer un vecino sináptico cuando existe una arista y se pide ventana de contexto; **no** prueba que un agente descubra la pista por sí mismo, que reformule de manera general, ni que el grafo esté poblado de forma representativa. Se llamaron directamente los handlers Python del servidor MCP; no se midió aquí el protocolo stdio ni se probaron negativos para el seguimiento. La prueba es exploratoria, pequeña y diseñada con conocimiento de la fixture.

## Límites, riesgos y decisión solicitada a auditoría

1. El OR de trigramas puede crear FP y candidatos distractores, como demostró ja-n01. No debe desplegarse ni extrapolarse desde esta batería.
2. Los dos FP ingleses de la batería continúan; este parche no aborda esa causa.
3. Los dos positivos CJK sin recuperación (`zh-18`, `ja-17`) siguen abiertos. Tampoco se ha probado la recuperación de las 16 pérdidas del informe anterior mediante un agente independiente.
4. El test de sinapsis confirma una ruta técnica mínima, no una mejora general del recall por pistas.
5. Solicito auditoría de la propuesta y de estos límites antes de E4. No apliqué el parche, no modifiqué el motor/base original/manifiesto, no descarté asociaciones, no ejecuté E1, no entrené neuronas ni autoricé campaña.

**Conclusión provisional:** el canal CJK por OR de trigramas es un candidato de recuperación con aumento visible de recall sintético, pero su falso positivo japonés y la fixture limitada impiden recomendar su adopción. E3 sigue abierto; la decisión de aplicación queda reservada a Dennys tras auditoría.
