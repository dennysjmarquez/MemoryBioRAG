# E3: control multilingüe sintético actual — 2026-11-01

## Propósito y límites

Se retomó el plan de limpieza del motor hacia v36, usando la batería multilingüe E3A ya existente como **control diagnóstico sintético**, no como campaña E1, prueba MCP ni evaluación de la memoria real. El gold contiene 120 recuerdos inventados, 132 consultas (20 positivos y dos negativos por idioma); no se validó como muestra representativa ni equivale a las cuatro QA oficiales. No se entrenó ninguna neurona ni se cambió el motor. La neurona de ranking se apagó explícitamente; no se afirma que esto apague todos los mecanismos neuronales.

Código `ef3dad87c840bb289a623aa092287ddca4acc30e`. El SHA-256 del gold fue `d3665a8e895ba061354ddd7d9c4fe44614956ad79d663433c6ef70e59aa78a6a`. El evaluador creó una base temporal nueva, con sus 120 recuerdos, comprobó integridad, vació WAL antes de copiar y utilizó una copia diferente por consulta. El reloj se fijó como en el experimento previo; la fuente sintética no cambió durante las búsquedas. Sin base de usuario ni snapshot.

## Ejecución

Python 3.11.2, SQLite 3.40.1, NumPy 2.4.6, NLTK 3.9.4; `PYTHONHASHSEED=0`, `BIORAG_NEURONA=0`, `BIORAG_PATH` ausente, datos NLTK del repositorio y estado auxiliar temporal separado. Profundidad `activos`, límite 5, peso sináptico ignorado. Se repitieron las 132 consultas en orden inverso, cada una desde copia limpia de la misma base sintética; **0 diferencias** en listas y puntuaciones dentro de esta corrida.

```bash
env -u BIORAG_PATH PYTHONHASHSEED=0 BIORAG_NEURONA=0 \
  BIORAG_DMN_ESTADO_PATH=/tmp/biorag-e3-control-dmn.json \
  NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. \
  /tmp/biorag-neuron-audit-env/bin/python scripts/evaluar_qa_multilingue_e3a.py \
  --verificar-orden --salida google_drive/auditoria_neuronas/e3a_actual.json
```

Salida **código 0**, duración 11,66 s en este entorno. El archivo completo sintético, con las consultas y resultados por caso, se guardó en Drive privado como `e3a_control_actual_ef3dad8.json` (`1tkdA3iUtKjO81zGOtrrfOjOj81Lu3BzC`): SHA-256 local y devuelto por Drive `6094828d5d4270c4eaae55e0db83f7800e0565c8bb81af66187dcb84f2a36e30`. No contiene recuerdos vivos. No entregarlo como paquete ciego E1.

## Resultados literales de la ejecución

```text
Comparación sobre la misma base: 0 casos diferentes

Idioma | R@5 | R@1 | MRR@5 | FP
zh     | 12/20 ( 60.00%) | 12/20 ( 60.00%) | 0.6000 | 0/2
ja     | 12/20 ( 60.00%) | 12/20 ( 60.00%) | 0.6000 | 0/2
ko     | 19/20 ( 95.00%) | 18/20 ( 90.00%) | 0.9250 | 0/2
ru     | 20/20 (100.00%) | 19/20 ( 95.00%) | 0.9750 | 0/2
en     | 20/20 (100.00%) | 20/20 (100.00%) | 1.0000 | 2/2
es     | 20/20 (100.00%) | 20/20 (100.00%) | 1.0000 | 0/2
```

Estos dos falsos positivos ingleses son los dos controles de esta batería, **no** los 40 controles de la QA oficial. Los ocho casos fuera del top 5 de chino y de japonés se mantienen visibles: no presentar sus aciertos como cobertura general del idioma.

## Comparación descriptiva con B3

Contra `docs/e3b3_directa_20261028.json`, mismo hash de gold y 132 IDs: 10 casos mejoran de posición o entran en el top 5 (`ja-06`–`ja-10`, `zh-06`–`zh-10`), cero bajan y cero controles negativos cambian su estado de FP. Las listas de resultados difieren en esos mismos 10 casos. Esto reproduce el patrón reportado en la auditoría histórica de Cambio 2 (`6986ecb`).

**Límite esencial:** la base sintética histórica y la actual se construyeron por separado y sus hashes SQLite difieren; la comparación de ejecuciones no es un A/B pareado en la misma copia, ni demuestra por sí sola la causa de las diferencias. La prueba de orden sí usó la misma base dentro de la corrida actual. No extrapolar el resultado a otras memorias, MCP o a v36 completa.

## Siguiente trabajo

Mantener abiertos los dos FP ingleses y las pérdidas multilingües: investigar el canal que realmente recupera cada caso, conservar pistas y no revivir el filtro B4b ya descartado por pérdida en ruso. El hallazgo del filtro de hub de una palabra (`auditoria_busqueda_hub_filtro_una_palabra_20261101.md`) se estudia por separado; ninguna de estas evidencias autoriza un cambio del motor. Antes de una propuesta, baseline y diff aislado, pruebas en copias y controles de recall/pistas, con medición del agente más BioRAG por MCP donde corresponda.
