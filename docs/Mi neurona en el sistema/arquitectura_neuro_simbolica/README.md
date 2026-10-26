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
