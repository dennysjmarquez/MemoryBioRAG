# EXPERIMENTS.md — Bitácora de Hipótesis Probadas y Descartadas

Este documento es el registro científico de BioRAG v25.x: qué se probó, qué se descartó, por qué, y con qué evidencia. La narrativa es honesta — incluye los experimentos que **no** funcionaron, porque son tan informativos como los que funcionaron.

**Regla de la bitácora:** un experimento que no muestra ganancia real sobre el baseline NO se integra al default. Se elimina quirúrgicamente, preservando los arreglos colaterales válidos ya commiteados.

---

## Resumen Ejecutivo

| Hipótesis | Versión | Veredicto | Evidencia clave |
|---|---|---|---|
| PPR (Diffusion of Heat, push-based) mejora el recall | v25.1 | **DESCARTADO** | 0% ganancia en evaluación honesta, +100–190ms latencia |
| FCA (Reticulados de Galois) como señal por_tema | v25.1 | **DESCARTADO** | Refutado en 3 capas (frecuencia ≠ semántica; sin clusters coherentes) |
| Boost dimensional adicional sobre el clasificador | v25.0–v25.1 | **DESCARTADO** | Toca techo estructural de discriminación (techo real < 2pp) |
| Fix de segmento SDM de dimensiones | v25.1 | **REVERTIDO** | Regresión de recall medido en la misma sesión |
| Signal #12 (Predicados SRL) sostiene +13.85pp | v23.1–v25.2 | **REFUTADO** | El +13.85pp histórico era un snapshot parcial; el backfill completo canibaliza la señal |
| Re-ranking jaccard léxico rescata candidatos hundidos | v25.2 | **GANADOR** | +13.85pp por_tema, +16.92pp R@1, holdout 50/50 sostiene, cero regresiones con protect-r0 |

---

## Metodología Común

Todas las evaluaciones usan:

- **921 casos QA** con 8 categorías de recuperación: `dormido`, `literal`, `typo`, `variante_gramatical`, `pregunta_natural`, `cruce_idioma`, `sinonimo`, `por_tema`.
- **Peso excluido del scoring** (`ignore_peso_sinaptico=True`) — campo de juego nivelado sin artefactos de umbral de ruido.
- **Holdout estricto 50/50 estratificado** por categoría, con **seed fija** (20260804): la mitad A ajusta hiperparámetros, la mitad B (que nunca vio el ajuste) valida la configuración elegida. Esto previene sobre-optimización.
- **Determinismo verificado**: 4 corridas consecutivas idénticas → misma tabla.

---

## Hipótesis Descartadas

### 1. PPR — Diffusion of Heat (v25.1) → DESCARTADO

**Hipótesis:** propagar calor sobre el grafo sináptico (APPR push-based) mejora el recall al alcanzar nodos no conectados textualmente.

**Lo que salió mal:** el benchmark que mostraba mejora tenía una **trampa**: los nodos dormidos se evaluaban como activos (estado no filtrado en el scoring), inflando los resultados.

**Evaluación limpia (estado filtrado):**
- **0% mejora** sobre el baseline de 12 señales + búsqueda profunda BFS.
- **+100–190ms de latencia** por query (inaceptable en el camino caliente).
- **100% de fallos** con evaluación honesta.

**Decisión:** eliminación quirúrgica del módulo PPR, sin revertir el repo entero. Se preservaron los arreglos colaterales ya commiteados (contrato de tupla `expandir_contexto_vecinos`, split BFS `_expandir_contexto_bfs`, cap `BIORAG_MAX_CONTEXTOS`, paginación). Red de seguridad: rama `backup_antes_limpieza_ppr_2026-08-02`.

**Lección de raíz:** un experimento que no muestra ganancia real sobre el baseline es ruido. El sistema que ya existía era el correcto.

---

### 2. FCA — Reticulados de Galois (v25.1) → DESCARTADO (refutado en 3 capas)

**Hipótesis:** las dimensiones semánticas pueden generar una señal `por_tema` vía Análisis Formal de Conceptos (reticulados de Galois).

**Refutación en 3 capas:**

1. **Sugeridor de dimensiones por frecuencia** (`lab_fca_chequeo_punto_entrada`, `lab_fca_sugeridor_dimensiones`): la frecuencia de aparición de una dimensión NO es señal semántica — las dimensiones "más usadas" son las genéricas (que todo nodo tiene), no las que discriminan. **Refutado**: frecuencia ≠ semántica.
2. **Retículo real** (`lab_fca_real.py`): 665 conceptos × 104 dimensiones → el retículo de Galois completo es estructuralmente gigantesco (explosión combinatoria) y el `impacto_atributo` muestra que ninguna dimensión individual sostiene la jerarquía. Los candidatos "triviales" (que aparecen poco) no son triviales estructuralmente: quitar cualquiera muta el retículo completo.
3. **Clusters semánticos** (`lab_fca_semantica.py`): los conceptos no-triviales del retículo (extensiones de 2..664 nodos) **no forman clusters temáticamente coherentes** — son intersecciones arbitrarias de dimensiones, no agrupaciones por tema. Ruido estructural.

**Decisión:** FCA no aporta señal de recuperación. Se descarta la línea completa.

---

### 3. Boost dimensional adicional (v25.0–v25.1) → DESCARTADO

**Hipótesis:** agregar más dimensiones al clasificador (13 ejes × 102 valores) mejora la discriminación de forma ilimitada.

**Hallazgo:** el clasificador dimensional tiene un **techo estructural de discriminación** — el techo real medido es inferior a 2pp de mejora adicional. El catálogo de 13 ejes ya cubre el espacio semántico que el sistema necesita; más dimensiones no discriminan mejor, solo agregan ruido de combinación.

**Decisión:** no se expande el catálogo más allá de los 13 ejes existentes sin nueva evidencia.

---

### 4. Fix de segmento SDM de dimensiones (v25.1) → REVERTIDO

**Hipótesis:** aplicar multi-proyección K (como en los otros segmentos SDM) al segmento de dimensiones mejora la representación.

**Resultado medido:** **regresión de recall** (54.3% → 43.1% en la métrica afectada). El segmento de dimensiones funciona mejor con ventana contigua que con bits dispersos.

**Decisión:** revertido en la misma sesión. Es la única excepción conocida donde la multi-proyección K NO aplica — documentado en el changelog v25.1.

---

### 5. Signal #12 — Predicados SRL (v23.1 → v25.2) → REFUTADO como ganancia real

**Hipótesis (v23.1):** los predicados SRL (keywords de contenido, peso 0.20) mejoran `por_tema` de 70.77% → 84.62% (+13.85pp).

**Refutación (v25.2):** el +13.85pp histórico correspondía a un **snapshot parcial** — backfill de predicados en 614 nodos con Signal #12 enganchada. El **backfill completo** sobre el corpus real canibaliza la señal (señales redundantes compitiendo por el mismo score), y medido sobre el baseline real de 921 casos la señal **no sostiene ganancia** (baseline real `por_tema`: 67.69%, no 84.62%).

**Decisión:** el peso 0.20 queda en `memory_store.py` con nota de canibalización; el backfill queda como capacidad disponible, **no enganchado**. La ganancia real de `por_tema` en v25.2 proviene del re-ranking jaccard.

---

## Hipótesis Ganadora

### 6. Re-ranking jaccard léxico (v25.2) → GANADOR

**Hipótesis de diseño (no parche):** los candidatos correctos existen en el pool de resultados pero quedan hundidos por señales ruidosas. El re-ranking jaccard léxico (coincidencia de tokens entre query y concepto, normalizado) es una señal de matching pura que puede rescatarlos.

**Implementación** (`core/memory_store.py`, Fase C): tras el ranking base, se re-ordena el head (`topk=20`) con `score + alpha × jaccard/max_j` (alpha=0.25), solo si el max jaccard de la ventana (50) supera el gate (0.04). **Protect-r0**: el ítem que ocupaba la posición 0 antes del re-ranking se restaura a la posición 0 — el re-ranking rescata hundidos, no hunde ganadores.

**Protocolo de validación (4 fases):**

- **Fase A** (`experimento_faseA_eval.py`): baseline real medido sobre corpus completo. `por_tema` baseline real: **67.69%** (R@5), **60.00%** (R@1).
- **Fase B — holdout 50/50** (`experimento_faseB_holdout.py`): ajuste de α/gate/topk en mitad A (criterio balanceado con restricción de no-daño); validación en mitad B. **La ventaja se sostiene en B** (la mitad que nunca vio el ajuste).
- **Fase B — protect-r0** (`experimento_faseB_protect_r0.py`): la variante "no demover rank 0" **elimina las regresiones R1** que la configuración sin protect-r0 introducía. Config ganadora final: α=0.25, gate=0.04, topk=20, window=50, protect-r0.
- **Fase C — fidelidad de réplica** (commit `275fc88`): la implementación en `memory_store.py` reproduce **921/921 rankings idénticos** al experimento. Señal completa (sin truncar) da el mismo +13.85pp. Cero daño en variante/PN/typo/literal. R@1 global intacto (86.38).

**Resultados finales sobre el corpus real (921 casos):**

| Métrica | Baseline | + Jaccard | Delta |
|---|---|---|---|
| `por_tema` R@5 | 67.69% | **81.54%** | **+13.85pp** |
| `por_tema` R@1 | 60.00% | **76.92%** | **+16.92pp** |
| `sinonimo` R@5 | — | 80.33% | sensibilidad residual: 1 caso (R@5) |

**Sensibilidad residual conocida:** `sinonimo` pierde 1 caso (id 0656, mitad A) — la única categoría con sensibilidad demostrada en toda la cadena de verificaciones.

**Activación gradual (por protocolo):** flag `BIORAG_RERANKING_JACCARD_ENABLED=1` (OFF por defecto en código). Monitoreo del benchmark con **atención específica a `sinonimo`** durante los primeros días. Si `sinonimo` se mantiene estable, se confirma el cierre definitivo del proyecto.

---

## Cómo Reproducir

```bash
# Baseline y re-ranking sobre el pool de 921 casos (Fase A)
python3 scripts/experimento_faseA_eval.py /tmp/salida_faseA.json

# Holdout estricto 50/50 con seed fija (Fase B)
python3 scripts/experimento_faseB_holdout.py

# Variante protect-r0 (Fase B)
python3 scripts/experimento_faseB_protect_r0.py

# Pool de casos y rankings (datos crudos)
scripts/experimento_rr_pool.json   # 921 casos: {id, categoria, expected, query, pool:[{concepto, score, jaccard}]}
scripts/experimento_faseA_pool.json

# Diagnósticos de posición y fallos por tema
python3 scripts/diagnostico_posicion_fallos_por_tema.py
python3 scripts/diagnostico_jaccard_fallos_por_tema.py
python3 scripts/diagnostico_tematico_jaccard_sinonimo.py
```

---

## Hipótesis Pendientes

### 7. Tejedora — Agujeros Estructurales (2026-08-05) → DESCARTADO

**Hipótesis:** tejer sinapsis estructurales (Adamic-Adar) entre nodos con degree bajo y dimensiones compartidas mejora el recall@5 en ≥+2pp sobre el baseline, sin degradar ninguna categoría.

**Estado:** **DESCARTADO EMPÍRICAMENTE 2026-08-06.** Aprobado por Dennys; valencia removida totalmente de la pipeline (desacople salvaguardas, decisión 2026-08-06); sweep Fase 2 ejecutado con pipeline real sobre los 921 casos.

**Evidencia del sweep (`scripts/tejedora_sweep.py`, snapshot aislado, 8 workers, `limite=5`):**
```
baseline_sin_tejido    95.35    +0.000pp
tejido_peso_0.6        95.35    +0.000pp
```
Las 13 sinapsis tejidas (`tejida_estructural`, peso 0.6) **no movieron ni un solo ranking** — R@5, R@1 y MRR idénticos. Confirmó el techo teórico pre-sweep (la red pesa ~2% en el score híbrido; solo 5 misses tenían respuesta-isla; las aristas conectan islas que no llegan al top-5).

**Lección:** el recall NO mejora tejiendo más sinapsis estructurales. El cuello de botella es el matching léxico/semántico (BM25 + dimensiones + PRF), no el cableado del grafo. Fases 3-8 canceladas.

**Historial:** plan validado por auditor técnico (Claude) con 2 correcciones (cross-check cuarentena + peso como parámetro del barrido). Documento completo: `docs/plan_tejedora_agujeros_estructurales.md`.

**Correcciones del auditor técnico integradas:**
1. Fase 1 excluye todo par con fila en `sinapsis_cuarentena` (bidireccional)
2. Peso inicial de sinapsis tejida = parámetro del barrido (0.3, 0.5, 0.7, 1.0)

**Semilla:** `core/dmn_engine.py` (durmiente, L130-215 muestreo resonante cortical).

---

## Changelog Científico (vs. Changelog Técnico)

| Versión | Hallazgo científico | Acción |
|---|---|---|
| v25.1 | PPR: 0% ganancia honesta, +100–190ms | Eliminado quirúrgicamente |
| v25.1 | FCA: frecuencia ≠ semántica, sin clusters | Línea descartada (3 capas) |
| v25.1 | SDM dimensiones: multi-proyección K regresa | Revertido en sesión |
| v25.2 | Signal #12: +13.85pp histórico = snapshot parcial; backfill completo canibaliza | Desenganchada (capacidad disponible) |
| v25.2 | Jaccard: +13.85pp por_tema, +16.92pp R@1, holdout sostiene | **Integrado** (Fase C, activación gradual) |
| v25.2+ | Tejedora: 13 sinapsis estructurales sobre 921 casos → +0.000pp | Descartado (Fases 3-8 canceladas) |
| v27.0 | Neocórtex de Sangre: ADN Conceptual + razonamiento por esencia + teleología | **PENDIENTE DE EVALUACIÓN** (blueprint, no integrado) |

---

## Hipótesis en Evaluación

### 8. Neocórtex de Sangre — ADN Conceptual y Razonamiento por Esencia (v27.0) → PENDIENTE DE EVALUACIÓN

**Hipótesis:** si cada recuerdo se describe por su *esencia* (una firma genética de genes mecánicos/abstractos, en vez de por su vocabulario), el sistema puede relacionar conceptos que no comparten palabras ("un error de código" con "frustración" o "entropía") y razonar por esencia en vez de por coincidencia textual.

**Estado:** **EN EVALUACIÓN — no presentado a nadie todavía.** Es un **blueprint congelado**, no una implementación integrada. La decisión de integración al core NO se ha tomado; aún no se ha discutido con ningún auditor ni par.

**Dónde vive:**
- Blueprint completo (código de referencia + demos + tests + documentación + presentación): `docs/¿Cuál es la Meta Final del Proyecto_Neocortex_nivel_2/`
- Variante experimental del core: `docs/.../memory_store.py` (5229 líneas, +75 vs core) — fork con init de `NeocortexTeleologico` + `ADNConceptualEngine`, métodos `_cargar_firmas_adn()` / `_persistir_firma_adn()`, tabla `adn_firmas`.
- Motor de ADN: `docs/.../adn_conceptual.py` — infiere la firma genética (esencia) de un concepto.
- Razonamiento teleológico: `docs/.../neocortex_teleologico.py` + `docs/.../hipotesis_teleologica.py` — vinculación por esencia y generación proactiva de hipótesis por "gaps genéticos".
- DMN evolucionada: `docs/.../dmn_engine.py` (variante modificada con curiosidad teleológica).
- Módulos de apoyo (copias o variantes): `auto_clustering.py`, `clasificador_wordnet.py`, `stemmer_es.py`, `ppmi_hybrid_search.py`, `dmn_reflexion.py`.
- Demos y tests: `demo_vivo_neocortex.py`, `run_adn_test.py`, `run_neocortex_test.py`, `run_teleology_test.py`, `test_neocortex_teleologico.py`, `test_sdm_completo.py`.
- Arquitectura y narrativa: `info.md`, `teoria_de_ejes_semanticos.md`, `slide_content.md`, 4 docs de briefing/arquitectura, presentación `Neocórtex de Sangre: La Evolución Genética de BioRAG.pptx`.

**Las 3 promesas del experimento (a validar empíricamente):**
1. **Intuición Sintética:** relacionar un error de código con una emoción de frustración o el concepto de "entropía" sin que nadie lo haya explicado, solo porque sus genes mecánicos/abstractos coinciden.
2. **Verdad Absoluta (cero alucinación):** un motor de incertidumbre como "filtro de realidad" — si el ADN de la consulta no encaja en el mapa, el sistema se detiene en vez de adivinar.
3. **Evolución Proactiva:** la memoria "sueña"; al detectar datos sobre "Gatos" y "Autonomía" pero ninguno sobre "Libertad", el motor teleológico marca el hueco para que el sistema busque activamente esa conexión.

**Qué falta para pasar de blueprint a experimento medido:**
- Decidir si la integración se hace sobre `core/memory_store.py` o como capa independiente.
- Medir impacto real sobre los 921 casos QA (recuperación, FP, latencia) con protocolo de ablación como los experimentos previos.
- Definir umbrales de afinidad y honestidad epistémica con evidencia, no por diseño.
- Evaluar la relación costo/beneficio de persistir firmas ADN por nodo en el ciclo de sueño.

**Lección de proceso que ya dejó:** documentar como blueprint ANTES de integrar evita que una idea sin evidencia contamine el core — el experimento se evalúa con datos, no por entusiasmo.

---

## Sesión 2026-08-15 — Diagnóstico del FP 80% en live DB

Registro de una sesión completa de depuración estadística. Se incluye porque las
hipótesis **refutadas** son la parte más útil: evitan repetir el mismo camino.

### Resumen ejecutivo

| Hipótesis | Veredicto | Evidencia clave |
|---|---|---|
| El daemon de mantenimiento causa el FP 80% | **DESCARTADA** | daemon OFF → sigue 80% |
| El fix 1.2 (renormalización) causó el FP 80% | **DESCARTADA** | baseline@live = 80% sin los fixes |
| La fusión lineal está rota (→ usar RRF) | **DESCARTADA** | AUC=0.914 y R@5 live 96.37%: el ranking funciona |
| RRF resuelve el FP | **DESCARTADA** | RRF es invariante a la magnitud; el FP es decidir *si* responder |
| Escenario B: discriminación colapsada | **DESCARTADA** | AUC=0.914 (umbral A: separación excelente) |
| H-corpus: el umbral absoluto no escala con el corpus | **CONFIRMADA** | negativos en [0.3,0.5] contra umbral fijo 0.25 |

### La matriz 2×2 que cerró la atribución

|  | SNAPSHOT | LIVE DB |
|---|---|---|
| Baseline (`5a306fa`) | 25% FP | **80% FP** |
| Con 5 fixes | 17.5% FP | 80% FP |

Medir `baseline@live` fue la corrida decisiva: **el 80% es preexistente**. Sin esa
celda, entre "snapshot+baseline" y "live+fixes" cambiaban dos variables a la vez y
no había atribución posible.

### Bugs corregidos (7)

Cinco iniciales (varianza explicada siempre 1.0; pesos sumando 1.34 con saturación;
pisos `max(0.95,·)` que empataban el head; radio SDM comparando Jaccard contra una
escala Hamming; `vector_query` recalculado por candidato) más **dos introducidos por
los propios fixes**: la suma `1.19` hardcodeada y una rama de sinónimos que usaba
`max(logit, target)` y aplastaba cinco scores distintos al mismo 0.70.

### Lecciones de método

1. **`16/16 tests` no era evidencia de no-regresión.** `test_memory.py` verifica
   mecánica (LTP, sueño, SDM), no propiedades del scoring: cero ocurrencias de
   `recall`/`mrr`. Los dos bugs introducidos pasaron en verde. Se añadió
   `scripts/test_regresion_scoring.py`, validado contra las versiones con bug
   (falla) y sin bug (pasa) — un test que solo pasa no demuestra nada.

2. **Un umbral absoluto invalida comparaciones históricas.** El FP se medía contra
   `score >= 0.25` hardcodeado. Cualquier reescalado del scoring cambia lo que ese
   0.25 significa. Ahora es `BIORAG_FP_THRESHOLD`.

3. **Truncar la clase mayoritaria sesga el punto de operación.** Un
   `limite_casos=120` recortaba los positivos pero no los negativos, distorsionando
   el ratio de ~22:1 a ~1.6:1. El "umbral óptimo 0.78" derivado de ahí era artefacto:
   con el ratio real el óptimo de `TP−FP` es 0.25.

4. **Calibrar y medir sobre los mismos datos da un resultado tautológico.** Un
   `FP=6.2%` que era, por definición del cuantil 90, aritmética y no medición.
   Corregido con partición calibración/validación.

5. **Los deltas hay que traducirlos a casos.** `+0.11pp R@5` = **1 caso de 881**
   (McNemar p=1.00); `−7.5pp FP` = **3 casos de 40** (p=0.25). Ninguno significativo.
   Con 881 casos hacen falta ~782 pareados para detectar +2pp con potencia 80%.

6. **La monotonía es un test gratuito de sanidad.** Una tabla mostraba FP y recall
   subiendo *a la vez* al subir el umbral — imposible. Detectó un error de medición
   que ningún test funcional habría visto.

### Estado al cierre

**Resuelto:** 7 bugs con tests de regresión; instrumentación del LTP (tabla
`eventos_refuerzo`, antes no había rastro persistente del refuerzo dopaminérgico);
umbral de FP parametrizable.

**Sin resolver:** el FP del 80% en live sigue idéntico. Lo que cambió es que está
localizado: umbral absoluto que no escala, en un sistema cuyo ranking funciona bien.

**Pendiente que bloquea la decisión:** medir el ratio real de consultas con y sin
respuesta en `log_busquedas` (`scripts/medir_ratio_produccion.py`). De ese ratio
depende el umbral: con 881:32 el óptimo de `TP−FP` es 0.25; con 1.6:1 salía 0.78.
Mismo método, conclusión opuesta — **el ratio decide, no el método**. Si sale alto,
la vía no es un corte binario sino abstención graduada, que además encaja con el
filtro de honestidad epistémica que el proyecto ya declara.

---

## Hipótesis E — Sinónimo, calibración, y auditoría inicial de mecanismos (18-ago-2026)

### Contexto
`sinonimo` es la categoría más débil del benchmark de 921 casos (top5 2/14 en el
sub-proyecto aislado PPMI+SVD, 77% en el benchmark completo). Se probaron dos
vías para cerrarla, ninguna lista para producción, y se auditó el cableado real
de 4 mecanismos existentes contra el mismo benchmark.

### 1. Calibración conforme — activada
`BIORAG_CALIBRACION_ACTIVA` estaba OFF por default, sin documentar en
`.env.example`, con calibración guardada (`metodo=cost_sensitive_optimal`,
`umbral=0.53`, `n_positivos=0` — nunca verificada contra positivos reales).
Medido en vivo contra DB real: sin activar, FP=80% (32/40); activada, FP=2.5%
(1/40), a costa de R@5 91.4%→70.7%. **No existe umbral que dé R@5>90% y FP<5%
a la vez** (probado 0.25/0.53/0.60/0.63). Decisión: activar 0.53 en producción.
`.env.example` actualizado con el trade-off documentado.

### 2. Retrofitting de vectores (Faruqui et al. 2015) — descartado en esta forma
`scripts/retrofit_ppmi_svd.py`. Grafo `sinapsis(tipo=sinonimo_explicito)`,
7685 edges. 8 configuraciones probadas (alpha 0.05–1.0, iters 3–10, con/sin
normalización por grado, filtro de peso 0–0.9). **Ninguna mejoró `sinonimo`
top5 sobre el baseline (2/14); la mayoría empeoró, y `por_tema` degradó en
casi todas.** Causa raíz verificada: el grafo tiene nodos-hub de hasta 305
vecinos (mediana 9, p99 129) — muy distinto a un lexicon WordNet-style de
pocos sinónimos por nodo, para el que está diseñada la fórmula de Faruqui.
Con alpha fijo, un hub de 305 vecinos reduce el vector original a ~0.4% del
resultado. Diagnóstico adicional: las 14 queries de `sinonimo` son palabras
sueltas comparadas contra vectores de documento promediados de un modelo con
varianza explicada 33% — el retrofitting mueve el destino (documento), pero
el punto de partida (la palabra suelta) ya viene mal representado; no ataca
la causa.

### 3. Expansión de query por grafo (1 salto) — señal real, no lista para producción
`scripts/expansion_grafo_sinonimo.py`. En vez de mover vectores, expande la
query a nivel léxico: conceptos-semilla (contienen la palabra literal) →
boost a vecinos por `sinonimo_explicito`. Primera versión (boost=SUMA) explotó
por el mismo problema de hub (`identidad` acumuló boost=29.7 en un candidato
irrelevante). Corregido a boost=MAX (un concepto gana por su mejor camino,
no por cantidad de caminos débiles). Resultado con w=0.5: `sinonimo` 2/14→3/14
(+1 caso real), pero `por_tema` 13/21→1/21 (colapso). Detalle caso por caso:
3/14 casos tenían camino de grafo y mejoraron mucho (rank 34→9, 88→6, 38→5);
11/14 no tenían ningún camino (cobertura incompleta); daño colateral confirmado
en 1 caso que ya estaba bien (rank 4→16, sin recibir boost él mismo — lo
desplazaron competidores boosteados). Ganancia y pérdida se cancelan en el
agregado. Un solo peso global no puede servir a las dos categorías —
necesita ruteo por tipo de query, no mezcla aditiva.

### 4. Ablación de 4 mecanismos existentes (GABA, DMN, PPMI+SVD, Jaccard)
`scripts/ablacion_mecanismos.py` (ya existente, cableado verificado real).
Snapshot congelado por config (bug propio corregido: la primera corrida
reusó el mismo archivo de DB mutable entre configs — la búsqueda despierta
nodos dormidos como efecto secundario, contaminando comparaciones
posteriores; detectado porque GABA-off y DMN-off dieron idéntico hasta el
decimal, estadísticamente imposible si fueran mecanismos independientes).
Repetido con copia fresca por config:
- **PPMI+SVD OFF**: R@5 91.4%→90.8% (−0.57pp), concentrado 100% en
  `sinonimo` (−4.9pp) y `por_tema` (−3.1pp), cero impacto en las otras 6
  categorías. Bien cableado, aporta lo esperado de un mecanismo de peso 0.15.
- **GABA OFF**: idéntico al baseline en las 8 categorías. Solo se activa si
  top-1 ≥0.80; puede estar disparando pero sin cruzar el umbral binario top-5
  en ningún caso de este dataset — no confirmado si realmente no aporta o si
  el benchmark no es sensible a su efecto.
- **DMN OFF**: idéntico al baseline. **Test estructuralmente inválido** — DMN
  vive en `core/dmn_engine.py`, corre en inactividad/consolidación, nunca es
  invocado por `buscar_por_frase`. Ejemplo real de "tecnología correcta,
  aplicada donde no corresponde medirla": no es un bug de cableado, es medir
  el mecanismo equivocado con el benchmark equivocado.
  Jaccard no se re-probó: su config de ablación fuerza el mismo valor que ya
  es default (OFF), sería una comparación contra sí mismo.

### Lecciones metodológicas de hoy
1. `buscar_por_frase` no es una función pura — despierta nodos dormidos como
   efecto secundario. Cualquier comparación entre configs necesita una copia
   de DB fresca por config, nunca reusar un archivo mutable entre corridas.
2. Un resultado "idéntico hasta el decimal" entre dos configs que deberían
   ser independientes es señal de contaminación, no de que ninguna aporte —
   investigar antes de reportar.
3. Auditar "¿está bien cableado?" y auditar "¿el benchmark puede medir este
   mecanismo?" son preguntas distintas — un mecanismo puede pasar la primera
   y fallar la segunda sin estar roto (caso DMN).
4. No existe un techo de "recall perfecto en todo" — cada categoría semántica
   tiene un techo real medido (ver arriba), y el trade-off recall/FP es
   matemático, no un bug.

### Pendiente — auditoría de los ~22 mecanismos restantes del catálogo de 26
Documento de referencia: catálogo completo con mecanismo → fundamento
científico → archivo → para qué se usa. Verificados hoy contra código real:
PPMI/SVD, GABA, DMN, escalado sináptico homeostático, separación de patrones
hipocampal (los 2 últimos solo spot-check de existencia, no de comportamiento
en benchmark). Criterio para seguir: mismo estándar que arriba — no basta con
"existe en el código", hay que (a) confirmar que el camino de código que dice
usarlo realmente lo invoca, (b) medir su efecto real contra los 921 casos con
DB fresca por config, (c) si da nulo, verificar primero si el benchmark puede
medirlo (caso DMN) antes de concluir que no aporta.

### Corrección de marco (18-ago-2026, mismo día): "2/14" no es el número de producción

El sub-proyecto aislado PPMI+SVD (`ppmi-svd-semantico.md`) mide el componente
vectorial SOLO, por diseño ("sin complejidad del pipeline"). Comparando las
mismas queries contra `buscar_por_frase` real (con Capa 4: WordNet +
columna `sinonimos`, 96.9% de nodos poblados): `perfil` rank 34→**4**,
`regla` 66→**5**, `memory` 68→**2**, `agentes` 38→**3**. La Capa 4 ya rescata
la mayoría de estos casos en producción. El número real de producción para
`sinonimo` es el 77% del benchmark de 921 casos, no el 2/14 aislado.

Investigados los 7 casos que SÍ fallan en producción real (found_rank=None
en el benchmark de 921): en los 3 auditados a fondo (`dimensiones`,
`familia`, `buscar`) el concepto esperado **tiene la palabra literal en su
campo `sinonimos`**, está `activo`, y SÍ es encontrado por el motor — solo
que compite contra 10-20 candidatos igual de plausibles que también
mencionan la misma palabra, y pierde la competencia por score (ranks 8, 11,
21 respectivamente). **No es un bug de cableado — es el techo inherente de
una consulta de una palabra contra un corpus de conceptos densamente
relacionados.** No se investigaron los 4 casos restantes (`boost`, `memoria`,
`dsl`) con este mismo nivel de detalle — mismo patrón esperado pero sin
confirmar.

**Conclusión de toda la sesión de auditoría:** de todo lo revisado hoy
(calibración, PPMI+SVD, GABA, DMN, retrofitting, expansión de grafo, Capa 4
WordNet/sinónimos, escalado homeostático, separación de patrones), **no se
encontró ningún mecanismo genuinamente mal cableado.** Los hallazgos reales
fueron: (a) mecanismos correctos pero apagados por default sin documentar
(calibración, Jaccard), (b) un mecanismo correcto probado con el benchmark
equivocado (DMN), (c) un problema real sin resolver que no es de cableado
sino de ambigüedad semántica inherente en queries de una palabra.

### Reversión de la decisión de calibración (18-ago-2026, mismo día)

`scripts/medir_ratio_produccion.py` (ya existía, nunca se había corrido) midió
el ratio real contra `log_busquedas`: **15-36:1** (con:sin respuesta) en 6134
consultas reales — muy por encima del 22:1 sintético del benchmark de 921
casos. Las dos copias de DB disponibles dieron números distintos entre sí
(15.1:1 vs 36.4:1; rangos de fecha de `log_busquedas` no anidados entre las
dos copias, causa no determinada — posible retención/poda en la DB viva,
sin confirmar). Ambas apuntan en la misma dirección cualitativa: muy por
encima del punto de quiebre (1.6:1) que hubiera justificado un umbral alto.

Con la regla de decisión del propio script (`neto = recall − fp/ratio`), un
ratio de 15-36:1 favorece un umbral BAJO: activar 0.53 destruye más recall
del que protege de FP en tráfico real. **Se revirtió la decisión de activar
`BIORAG_CALIBRACION_ACTIVA` tomada horas antes en esta misma sesión** —
`.env.example` actualizado, default vuelve a ser desactivada.

Nota aparte, sin resolver: de 6134 consultas, solo 38 (0.6%) tienen feedback
explícito (`util`), y las 38 son `util=0` — nunca se registró un `util=1` en
esta DB. El mecanismo de feedback (dopamina/RPE, `biorag_feedback()`) existe
y está cableado, pero no se está usando en la práctica — no se investigó por
qué hoy.

### Auditoría de GABA con tráfico real (18-ago-2026, mismo día)

Se midió, contra `log_busquedas` (6134 consultas reales), cuántas veces se
cumple la condición de disparo de GABA (top1 ≥0.80): **64.7%** (3861/5970
con `top_score` registrado) — se dispara constantemente, no es un caso raro.

Sin embargo, cruzando con la ablación del benchmark de 921: de los 579 casos
donde la condición se cumple, **0 cambiaron de rank al desactivar GABA**
(no solo el agregado — caso por caso, ninguno). Causa verificada en el
código (`core/memory_store.py`, bloque GABA): solo atenúa candidatos con
`score < top_score * 0.70`. Para que eso mueva el top-5 hace falta que un
candidato ya claramente inferior al líder esté además compitiendo justo en
el borde del corte top-5 — combinación que no ocurrió ni una vez en 6134
consultas reales + 921 del benchmark.

**No es un mecanismo mal cableado ni con bug — es un mecanismo de cola que,
con los datos actuales, no tiene ningún caso donde aplique de forma
observable.** Puede que sea necesario para escenarios que este corpus
todavía no tiene (documentos casi-duplicados compitiendo cerca del líder),
o puede ser candidato a simplificar. No se decidió qué hacer con esto hoy.

### JSD (Jensen-Shannon Divergence) — mismo patrón de peso 0.0 por default, sin caso claro para activar

`BIORAG_JSD_WEIGHT` default `'0.0'` — se calcula (`_calcular_jsd`) en cada
búsqueda pero no aporta al score final salvo activación explícita. Mismo
patrón que calibración/Jaccard (mecanismo real, apagado por default, sin
documentar el trade-off). Probado con `BIORAG_JSD_WEIGHT=0.05` (valor
sugerido en el propio código) contra los 921 casos: R@5 91.37%→91.37%
(sin cambio), R@1 +0.11pp, FP sin cambio. Por categoría: `por_tema` +1.5pp,
`sinonimo` −1.6pp — se cancelan casi exacto. **No hay caso claro para
activarlo con este peso** — no se probaron otros pesos por tiempo.

### Cambio real implementado: ampliación de ventana por empate (18-ago-2026)

`core/memory_store.py::buscar_por_frase()`, antes de la paginación final.
Para queries ≤2 palabras (página 1), si hay candidatos justo debajo del
corte de `limite` con score ≥90% del último incluido, se amplía la ventana
devuelta (tope +10). Motivación: casos reales (`dimensiones`, `familia`,
`buscar` — ver más arriba) donde el concepto correcto SÍ se encuentra pero
pierde una competencia legítima contra candidatos igual de plausibles justo
debajo del top-5.

**Medido correctamente (no con R@5 — ese nunca fue el objetivo del cambio):**
de los casos que antes NO devolvían el concepto esperado en absoluto
(found_rank=null), **7 ahora sí lo devuelven** en algún lugar de la ventana
ampliada (posiciones 6-11). **0 regresiones**: ningún caso que antes se
encontraba se rompió, ningún negativo empezó a devolver falsos positivos
nuevos. Nota metodológica propia: el primer intento de medir esto con R@5
agregado dio "0.00pp cambio" — error de métrica (R@5 no puede detectar un
candidato que aparece en posición 6-11), no de código. Corregido comparando
found_rank null→no-null directamente.

Límite conocido: el tope +10 es arbitrario: rescata casos con rank real
≤15, no rescata casos más profundos (ej. "buscar", rank real 21, no
resuelto). Subir el tope rescataría más casos a costa de ventanas de
respuesta más grandes — no evaluado el trade-off de subirlo más.
