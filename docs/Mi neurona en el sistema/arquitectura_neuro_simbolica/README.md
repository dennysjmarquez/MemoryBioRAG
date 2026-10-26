# Arquitectura Neuro-Simbólica Modular Distribuida — mapa y evaluación de la maquinaria

**Fecha:** 2026-10-26 · **Rol:** auditor (sesión `arena/6459e2d0`) · **Base de código:** master `f8c2b16`

## 1. El enfoque

BioRAG no apunta a una red neuronal grande que lo haga todo. Es un **motor simbólico
fijo** (SQLite + Python: índices, reglas, grafo, consolidación) con **micro-neuronas
especializadas** en los puntos donde una regla escrita a mano no alcanza.

- El motor **busca y ejecuta**. Cada neurona **decide en su punto** y nada más.
- Cada neurona tiene piso a mano, guardia, campeón/retador, techo y costo fijo
  (ver `GUIA_CREAR_UNA_NEURONA.md` y el experimento 10).
- Se puede encender, apagar o retirar sin tocar a las demás.

La familia de ideas existe: IA neuro-simbólica, la "sociedad de la mente" de Minsky,
las redes de expertos. Lo propio de BioRAG es el molde de cada neurona, que aprenda
en la base de cada persona y que no dependa de una red grande ni de embeddings.

## 2. Inventario de sistemas

Estado: **SANO** (medido y estable) · **REPARADO** (arreglo medido y en master) ·
**DÉBIL** (funciona pero hay fallos medidos) · **ROTO** · **NO EVALUADO** (no
auditado a fondo en esta pasada; no se afirma nada).

| # | Sistema (analogía) | Dónde | Qué decide | Estado | Evidencia | ¿Lugar para neurona? |
|---|---|---|---|---|---|---|
| 1 | Entrada léxica (reconocer palabras) | `core/memory/search.py` fallbacks 1.0–2.0 (FTS5, trigramas, prefijos) | qué recuerdos entran como candidatos | SANO | QA snapshot R@5 100 %, 0 fallos (`d776a49`) | no |
| 2 | Léxico mental (sinónimos externos) | `core/fallback_simbolico.py` `expandir_palabra_wordnet` (~171); `core/lexical_learning.py` | ampliar la búsqueda cuando la pregunta usa otras palabras | **DÉBIL** | WordNet no lematiza ni restaura tildes. Cobertura sobre las 921 consultas: WordNet ES 32,2 %, RLA-ES 36,9 % (rama operario `96bbe74`). EXP-Q en la base viva: 0/3 en top-5 | **sí**: neurona de sinónimos, cerrada de fábrica (guía, anexo F1) |
| 3 | Integración (fórmula de puntaje) | `core/memory/scoring.py:295` | cuánto vale cada candidato | **DÉBIL** con bases grandes | 14 pesos fijos + pisos en logit. El piso de sinónimos es binario (1.0 o 0): en la base viva una mediana de 16 recuerdos declara la misma palabra y empata. Dos intentos de graduarlo fueron negativos y se revirtieron (`6e62e9a`, `d724c33`) | sí, pero solo como **dato nuevo para la neurona de ranking** y solo tras diagnosticar el puesto real (§4, P1) |
| 4 | Hub de conceptos | `core/concept_hub.py` | traducir la pregunta al concepto canónico | REPARADO | v35.2/v35.3 + ingenuo ×1.0. Confianza viva 0.67. QA snapshot, H_mitad y H_todos: 0 fallos | no por ahora |
| 5 | Invariancia de escala | `core/memory/escala.py` (v35.1) | que el tamaño de la base no cambie decisiones internas | REPARADO | experimento `escala_recall_20261025` | no |
| 6 | Memoria asociativa (grafo, evocación por cadena) | `core/memory/synapses.py:164` y `:255` | qué recuerdos vecinos se traen por enlaces | **DÉBIL** | EXP-Q: el recuerdo correcto está en el grafo pero en el puesto #33 y #91 en la base viva. Los nodos correctos tienen 101–167 enlaces; el efecto *fan* es suave (`1/log(e+grado−1)`). Reordenar por convergencia (tipo PPR) es un callejón sin salida medido | más adelante: neurona de saltos del grafo, después de limpiar enlaces |
| 7 | Convergencia de evidencia y desempate Jaccard | `core/memory/evidence_convergence.py`; `scoring.py:388` | reordenar con pruebas de varios campos | SANO | dentro de la QA oficial | no |
| 8 | Neurona de ranking (viva) | `core/memory/neurona.py` | orden final del top-5 | SANO | QA: R@1 91,89 → 94,97, MRR .950 → .970. **Solo reordena el top-5, así que no puede cambiar el R@5** | ya existe |
| 9 | Saber que no sabe (umbral conforme) | `core/memory/umbral.py` | responder o abstenerse | SANO | ya se calibra por base; FP 0/40 | no: ya aprende de cada base |
| 10 | Consolidación (sueño: co-ocurrencia automática) | `core/memory/consolidation.py:47` | qué enlaces nuevos crea el sueño | SANO / mejorable | exp13: sin enlaces automáticos hay 5 fallos (el "ruido" ayuda). Canal 2 hoy: 5 buenos / 8 malos; con neurona ≥ .50: 9 buenos / 1 malo | **sí**: filtro del canal 2 |
| 11 | Mantenimiento del grafo (hormiguita) | `core/daemon_lifecycle.py`, `core/mcp_server/daemon.py` | qué enlaces reforzar o proponer | pendiente de reemplazo | la neurona asociativa está construida, es cerrada y está en escala 0, pero **sin cablear al motor** | **sí**: `core/neurona_asociativa.py` (pendiente de cablear) |
| 12 | Red por defecto y reflexión (DMN, vacíos) | `core/dmn_engine.py`, `core/dmn_reflexion.py`, `core/sueno_vacios.py` (vía `sleep_cycle.py`) | hipótesis en reposo | NO EVALUADO | — | — |
| 13 | Metacognición (métricas del sueño) | `core/mcp_server/introspection.py` tool `metricas_historial` | mostrar el historial de ciclos | **ROTO → REPARADO en esta rama** | pedía la columna `categoria_dominante`, que no existe (es `categoria_dominante_id`). Fallaba en toda base con al menos un ciclo | no |
| 14 | Señales semánticas (PPMI/SVD, SDM, ADN, temática, inferencia transitiva) | `core/ppmi_*`, `core/sdm.py`, `core/adn_conceptual.py`, `core/tematica.py`, `core/inferencia_transitiva.py` | aportan puntos a la fórmula (#3) | NO EVALUADO una por una | se miden solo en conjunto dentro de la QA | — |

**Código sin conectar al motor** (lo decide Dennys; no se borra nada sin su OK):
- `core/rrf_fusion.py`: 0 usos.
- `core/feedback_implicito.py`: solo lo usa un script. Además choca con la norma "sin sistemas de feedback".
- `core/memory/neurona_puentes.py`: está en la rama del operario, apagado. Aprende peor que la regla sola (AUC .814 vs .922).
- `core/calibracion.py` está **a medias** (revisado 2026-10-26, pregunta de Dennys):
  - **En uso** (vía `core/memory/umbral.py` → MCP `buscar` y `calibrar`): `UmbralConforme`,
    `CalibradorPlatt`, `calibracion_isotonica`. Son el sistema "saber que no sabe"
    (FP 0/40) y la confianza que ve el agente.
  - **Importadas pero nunca llamadas** (`search.py:34`, `memory_store.py:13`):
    `zscore_por_query`, `fusion_rrf`, `FusionLogistica`, `mmr`.
  - **Sin importar en ningún lado** (ni en `core/`, ni en `scripts/`, ni en `tests/`):
    `dunning_llr`, `retrofit_normalizado`, `energia_dirichlet`.
  - Tres de las que no se usan sirven a hallazgos de esta auditoría, sin conectarlas a
    ciegas:
    - `FusionLogistica` como **herramienta de diagnóstico** (no para reemplazar
      pesos, porque los pesos a mano son el piso): dice qué señal de la fórmula no
      se distingue de cero (E4).
    - `dunning_llr` como criterio para que nazca un enlace (§6.1).
    - `retrofit_normalizado` contra el arrastre de los nodos con cientos de enlaces
      por alias en los vectores PPMI (§6.1).

## 3. Por qué el resultado varía según la base: tres mecanismos medidos

1. **Señales binarias que empatan.** Un "sí/no" (por ejemplo, "este recuerdo declara
   la palabra como sinónimo") no distingue entre los que dicen que sí. Con más
   recuerdos hay más empates, y el desempate queda en manos de otra señal que premia
   otra cosa (BM25 premia el nombre). Medido: mediana de 16 empatados en la base viva.
2. **Topes fijos con números absolutos.** Ejemplo: `asoc_norm = min(1, asoc_count/20)`
   en `scoring.py:318`. El tope 20 es igual con 100 recuerdos que con 10.000. Su peso
   es pequeño (0,02), pero el patrón se repite: hay 414 decimales escritos a mano en
   `core/` (sin contar 0, 0,5 y 1). No todos son un problema; sirve como mapa para
   revisarlos.
3. **El grado del grafo crece con la base.** Los nodos muy conectados atraen la
   búsqueda por enlaces y un efecto *fan* suave no los frena (EXP-Q, sistema #6).

Además, el **contenido** pesa tanto o más que el tamaño. Con 150 recuerdos la base
viva ya falla 13 de 61 casos de sinónimos porque sus recuerdos se parecen mucho entre
sí. Esta cifra viene del script del operario, que no mide igual que la QA oficial, así
que hay que confirmarla con la QA.

## 4. Plan priorizado

El operario ejecuta, el auditor da el veredicto. Una cosa por entrega.

| P | Qué | Tipo | Estado |
|---|---|---|---|
| P0 | Arreglar `metricas_historial` | reparación simbólica | **hecho en esta rama**, con prueba |
| P1 | Diagnosticar los 6 fallos de sinónimos en la base viva: puesto real del recuerdo correcto sin neurona, con la QA oficial | diagnóstico | en curso (operario) |
| P2 | Léxico mental, paso 1: WordNet con lematización y tildes | reparación simbólica | propuesto; falta OK |
| P3 | Léxico mental, paso 2: tesauro RLA-ES (3 MB, LGPL) | dato externo | propuesto; falta OK de Dennys por la licencia y el tamaño |
| P4 | Grafo: efecto *fan* relativo al grado típico de cada base | reparación simbólica a medir | candidato; medir con EXP-Q y la QA |
| P5 | Topes fijos (§3.2): pasar de números absolutos a relativos a la base | reparación simbólica a medir | candidato; uno por uno |
| P6 | Cablear la neurona asociativa en lugar de la hormiguita | neurona cerrada | pendiente desde v35 |
| P7 | Neurona filtro del canal 2 de consolidación | neurona nueva | candidata (exp13) |
| P8 | Decidir qué hacer con el código sin conectar | limpieza | decisión de Dennys |

**Regla para elegir entre símbolo y neurona:**
- Si es un error o una normalización universal, se arregla con símbolo (código).
- Si depende del contenido de cada memoria, va una neurona viva con piso.
- Si es conocimiento universal del idioma, va una neurona cerrada de fábrica.

**Compuerta de cada entrega:**
- QA oficial antes y después, sin bajar el recall (R@5, R@1 y fallos);
- FP 0/40;
- todas las pruebas en verde;
- huella del snapshot `104dd2902aaf` intacta;
- interruptor para apagar el cambio;
- ninguna base de datos en el commit.

## 5. Verificación de P0 (esta rama)

```
# antes del arreglo
tests/test_metricas_historial.py  -> 1 failed, 1 passed
  sqlite3.OperationalError: no such column: categoria_dominante
# después del arreglo
pytest tests/ -> 505 passed
sha256 snapshots/qa_escape_qcr_20260811.db -> 104dd2902aaf (intacto)
```

## 6. ¿Dónde hace falta criterio neuronal? (investigación 2026-10-26)

Pregunta de Dennys: ¿en qué puntos del motor una regla fija decide mal y haría falta
criterio? Solo se mide, no se cambia nada. Las mediciones son de solo lectura sobre el
snapshot y sobre una copia de la base viva (1357 recuerdos, fuera del repo).
Script reproducible: `scripts/experimentos/criterio_neuronal_20261026/medir.py`.

### 6.1 Hallazgo principal: los enlaces por alias se crean sin ningún criterio

Al guardar un recuerdo con alias, `core/sinapsis.py:440` (`vincular_por_sinonimos`)
crea un enlace **fuerte (0.9) y protegido** hacia **todo** recuerdo cuyo nombre o alias
**contiene** ese texto (`LIKE %alias%`). El alias `ia` "está" en `memoria`, `guia` y
`dennys_identidad`.

| | snapshot (866) | base viva (1357) |
|---|---:|---:|
| enlaces por alias | 5.863 (42,2 % del grafo) | **15.219 (45,5 %)** |
| con un extremo que ya no existe | 0 | **738** |
| creados por un alias de ≤ 3 letras | 383 | **3.148** |
| creados por un alias que alcanza ≥ 20 recuerdos | 3.098 | **9.167** |
| el alias coincide como palabra entera | 4.171 | 8.093 |
| enlaces por recuerdo: mediana / máximo | 24 / 270 | 35 / **633** |
| alcance de `ia` / `id` | 395 / 386 | **718 / 661** |

- Los recuerdos crecieron ×1,6 y los enlaces por alias ×2,6. Los creados por alias
  cortos crecieron ×8. **El grafo crece más rápido que la memoria**: es una causa
  concreta del mecanismo 3 de §3 y de los nodos muy conectados que tapan al correcto
  en EXP-Q.
- Estos enlaces también sirven de "diccionario de sinónimos" para otros procesos
  (`scripts/retrofit_ppmi_svd.py`, `core/inferencia_transitiva.py`), así que el ruido
  se propaga.
- Dos capas:
  - **Error de código** (universal): comparar por "contiene" en vez de por alias o
    palabra entera, y los enlaces que quedan colgando de recuerdos que ya no existen.
    Se arregla con código.
  - **Criterio** (depende del contenido): aun con palabra entera, `leccion` une 72
    recuerdos. Si dos recuerdos que comparten un alias de verdad tienen que ver, lo
    decide la **neurona asociativa**, que ya está construida y cerrada pero sin
    cablear. Este es su primer punto natural de enganche.
- Cuidado (exp13): parte del "ruido" ayuda a buscar; sin enlaces automáticos había 5
  fallos. No se borra nada. Primero se cambia cómo nacen los enlaces nuevos, y se mide
  con la QA en copias.

### 6.2 Vigencia: "¿cuál es la última versión de X?" (Reto 1)

La base viva tiene más de 13 recuerdos con versiones de BioRAG (v10.3 … v34.0, y
`version_actual_biorag` dice v35.0). El motor no sabe que uno **reemplaza** a otro:
decide solo por palabras, y la recencia pesa 0,04.

```
>> ¿cuál es la última versión de biorag?
   1. 0.934  2026-10-04  ultima_version_biorag          (dice v32.3: VIEJO)
   2. 0.767  2026-10-07  version_actual_biorag_v32_4_20261007
   3. 0.753  2026-07-08  biorag_v14_0_estado
   4. 0.749  2026-10-14  version_actual_biorag          (dice v35.0: el correcto)
>> biorag latest version
   1. 0.718  2026-07-08  biorag_v14_0_estado            (julio)
```

Hacen falta dos habilidades:
1. **Intención**: la pregunta pide lo más reciente ("última", "actual", "ahora",
   "latest"). El piso es una lista de palabras ES/EN; la neurona aprende las demás
   formas de pedirlo.
2. **Familia en el tiempo**: estos recuerdos hablan de lo mismo en distintos momentos.
   La verdad para entrenar sale gratis de la propia base: hay 183 recuerdos con versión
   en el nombre y familias con fechas (v26.2 < v26.3 < v26.4).

Piso: el comportamiento de hoy. La neurona solo sube al más reciente de la familia
**dentro del top-5**, nunca saca al resto.

### 6.3 Ranking de lugares para criterio neuronal

| # | Punto | Qué decide hoy una regla fija | Evidencia | Verdad para entrenar | Tipo |
|---|---|---|---|---|---|
| 1 | Nacimiento de enlaces por alias (`sinapsis.py:440`) | "contiene el texto → enlace 0.9" | §6.1 | pares de la neurona asociativa (ya calibrada) | arreglo de código + neurona **cerrada** (asociativa) |
| 2 | Vigencia en la búsqueda | nada (recencia 0,04) | §6.2 | familias con versión y fecha de la propia base | intención **cerrada** + familia **viva** con piso |
| 3 | Filtro del canal 2 del sueño | todo enlace del canal 2 entra | exp13: 5 buenos / 8 malos → 9 / 1 | exp13 | neurona cerrada (asociativa) |
| 4 | ¿Recuerdo nuevo o actualización? (al guardar) | similitud ≥ 0,05 fija, top-3 (`write.py:35`) | más de 9 copias `version_actual_biorag*` | las mismas familias de #2 | viva, solo propone; nunca borra ni fusiona |
| 5 | Saltos del grafo | BFS con *fan* suave | EXP-Q #33 / #91 | — | **esperar**: medir de nuevo después de #1 |
| — | Olvido / dormir | ACT-R con umbrales fijos | 0734 (una regla) dormido | **no hay** sin feedback, y feedback está prohibido | **no** poner neurona |
| — | Umbral conforme, hub, entrada léxica | — | sanos o reparados | — | no hace falta |

**Orden recomendado:** primero el arreglo de código de #1 (y medir cuánto mejora el
grafo solo con eso). Después, la neurona asociativa como juez de #1 y #3 (la misma
neurona en dos puntos). Luego #2, que es el Reto 1.
