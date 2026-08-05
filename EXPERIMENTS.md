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

### 7. Tejedora — Agujeros Estructurales (2026-08-05) → PENDIENTE

**Hipótesis:** tejer sinapsis estructurales (Adamic-Adar) entre nodos con degree bajo y dimensiones compartidas mejora el recall@5 en ≥+2pp sobre el baseline, sin degradar ninguna categoría.

**Estado:** plan validado por líder con 2 correcciones (cross-check cuarentena + peso como parámetro del barrido). Pendiente de ejecución. Documento completo: `docs/plan_tejedora_agujeros_estructurales.md`.

**Correcciones del líder integradas:**
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
