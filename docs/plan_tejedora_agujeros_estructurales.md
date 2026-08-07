# Plan Tejedora — Detección y Tejido de Agujeros Estructurales

**Estado:** VALIDADO EMPÍRICAMENTE 2026-08-06 — Fase 2 (sweep) completada con pipeline real sobre 921 casos: tejido = **+0.000pp** (R@5 95.35% idéntico). Hipótesis refutada → el cableado estructural NO es el cuello de botella del recall. Decisión Dennys: valencia **removida totalmente** de la pipeline (4.1b, SUPERSEDE 4.1a). Proyecto cerrado como experimento (Fase 5-8 canceladas).

**Historial:** Validado por auditor técnico (Claude), 2 correcciones integradas. Ajuste de diseño 2026-08-06 (valencia → desempate, isla → degree ≤ 3, AA → 0.2) documentado en 4.1a. Presentación a Dennys 2026-08-06 02:00.
**Autor:** Athena-OEC
**Versión:** 1.0 (con correcciones del auditor técnico)

---

## 1. Contexto — ¿Por qué este experimento?

El sistema tiene **8,529 sinapsis latentes** detectadas pero **no conectadas**. El grafo tiene nodos huérfanos (grado 0-1) y regiones sin explorar. La hormiguita poda lo que hay, pero nadie **detecta lo que falta**.

**Gap real (verificado en código):**
- `_expandir_contexto_bfs` (memory_store.py:2919) expande contexto, no busca huecos
- `_context_window` (memory_store.py:143, deque maxlen=10) ya da bonus token-level, pero NO hay interferencia semántica entre queries recientes
- No existe detección de vacíos estructurales en el grafo

**Idea 2 del auditor técnico (2026-08-05):** detectar agujeros estructurales (nodos con degree 0-1, low clustering coefficient) y crear sinapsis nuevas para llenarlos, usando Adamic-Adar (no Jaccard) como métrica estructural.

**Lo que NO hace este experimento:**
- No emula el cerebro por emular
- No toma el camino fácil (ya hay bonus de tokens)
- No necesita LLM — es puramente estructural
- No toca producción (experimento aislado en scripts/)

---

## 2. Hipótesis

> **Tejer sinapsis estructurales (Adamic-Adar) entre nodos con degree bajo y dimensiones compartidas mejora el recall@5 en ≥2 puntos porcentuales sobre el baseline, sin degradar ninguna categoría.**

**Razón:** los nodos grado 0-1 son "islas" que la búsqueda nunca alcanza por sinapsis. Conectarlos con vecinos que comparten dimensiones semánticas amplía el alcance del grafo sin agregar ruido (porque el filtro dimensional garantiza coherencia semántica).

---

## 3. Métricas de Éxito y Fracaso

| Métrica | Umbral | Significado |
|---|---|---|
| **Éxito** | delta recall@5 ≥ +2 pp | Mejora medible y significativa |
| **Neutro** | 0 < delta < +2 pp | Mejora menor, no concluyente |
| **Fracaso** | delta ≤ 0 pp | No mejora o degrada |

**Secundario (monitoreo):**
- Ninguna categoría individual pierde >1 caso
- Latencia de búsqueda no aumenta >5ms
- Nodos nuevos no generan falsos positivos en la inspección manual

---

## 4. Parámetros del Experimento

### 4.1 Generación de Candidatos (Fase 1)

| Parámetro | Valor Inicial | Justificación |
|---|---|---|
| Métrica estructural | Adamic-Adar (AA) | Mide probabilidad de conexión por vecinos comunes; pondera por rareza de vecinos |
| Umbral AA mínimo | ≥ 0.2 | Ajustado 2026-08-06 (era ≥ 0.5): con 0.5 el pool real era de 2 pares — insuficiente para medir contra 921 casos. Con 0.2 + cap de saturación: 13 pares. Se sweep en Fase 2 |
| Dimensiones compartidas mínimas | ≥ 2 | Garantiza coherencia semántica (no conexión random) |
| Valencia somática | Desempate (NO filtro) | Ajustado 2026-08-06 — ver 4.1a |
| Máximo conexiones por nodo por ciclo | 3 | Evita saturación de un nodo |
| Grado máximo de isla | ≤ 3 | Ajustado 2026-08-06 (era ≤ 1): amplía la frontera sin perder coherencia |

### 4.1a Ajuste de Diseño — Valencia pasa de Filtro a Desempate (2026-08-06)

**Cambio:** `valencia_somatica` dejó de ser filtro de exclusión (≥ 0.3) y pasó a criterio de desempate/prioridad entre candidatos que ya pasaron AA + dimensiones compartidas.

**Razón exacta (verificada en código, no opinión):** en el sistema, `valencia_somatica` se diseñó como escudo contra el olvido — los nodos con valencia ≥ 0.80 o categoría Principle/Protocol son inmunes al decaimiento pasivo LTD y a la poda (`core/memory_store.py:1904-2010`, todos los queries de decaimiento usan `AND COALESCE(valencia_somatica, 0.0) < 0.80`). **Nunca midió "disposición a conectar".** El plan original la reutilizó con un significado nuevo que el campo nunca tuvo.

**Evidencia empírica:** las islas (degree bajo) son por definición nodos que nadie reforzó → valencia 0.0. Verificado en snapshot Fase 0 (34/34 islas con valencia 0.0) y en la DB viva (de los 62 nodos con valencia ≥ 0.3, ninguno es isla). El filtro valencia ≥ 0.3 era estructuralmente incompatible con la propia definición de isla: pedir a un nodo frío que tenga "señal emocional" es una contradicción. Por eso Fase 1 produjo 0 candidatos con los parámetros originales.

**Qué NO cambia:** la protección contra el olvido sigue intacta en todo el sistema — ningún nodo pierde su inmunidad LTD. Este ajuste es SOLO del filtro nuevo de la Fase 1 del experimento, no del sistema de memoria.

**Nuevo rol de valencia:** si dos candidatos empatan en AA + dims compartidas, prioriza el de valencia más alta — su significado real (importancia protegida). Nunca excluye.

### 4.1b REMOCIÓN TOTAL DE VALENCIA — Decisión Dennys 2026-08-06 (SUPERSEDE 4.1a)

**Decisión de Dennys:** valencia NO participa en la pipeline de Tejedora ni como filtro ni como desempate. Desacople total entre la salvaguarda de olvido (valencia/LTD) y el tejido estructural.

**Por qué es correcto (evidencia):**
1. `valencia_somatica` mide inmunidad al olvido, NO "disposición a conectar" (ver 4.1a) — cualquier uso en Tejedora es reutilizar el campo con un significado que nunca tuvo.
2. Verificado empíricamente: la regeneración de candidatos SIN valencia produce **los mismos 13 pares** que con valencia como desempate (0.4s, 726 activos, 56 islas). La valencia era NO-OP en la práctica.
3. Desacoplar salvaguardas de señales de conexión elimina el riesgo de arrastrar basura protegida por valencia alta.

**Implementado:** `scripts/tejedora_generar_candidatos.py` — sin query de valencias, sin campos en el dict, sin sort por valencia. Keys: `['a', 'b', 'aa', 'dims_compartidas', 'degree_a', 'degree_b']`.

### 4.2 Cross-check contra Cuarentena (Catch #1 del auditor técnico)

> **Regla obligatoria:** Excluir de candidatos TODO par que tenga fila en `sinapsis_cuarentena` (en cualquier dirección: A→B o B→A).

**Razón:** la Hormiguita ya juzgó esos pares con juicio semántico real (Gemini) + motivo + confianza. Recrearlos a ciegas por criterio puramente estructural es contradicción entre mecanismos.

**Bonus — señal de calibración:** Si el inventario de candidatos tiene alta coincidencia con lo que la Hormiguita podó → señal de que el criterio estructural genera falsos positivos → ajustar umbral AA en Fase 2.

**Implementación:**
```sql
-- Excluir pares en cuarentena (bidireccional)
SELECT a.origen, a.destino
FROM candidatos a
WHERE NOT EXISTS (
    SELECT 1 FROM sinapsis_cuarentena c
    WHERE (c.origen = a.origen AND c.destino = a.destino)
       OR (c.origen = a.destino AND c.destino = a.origen)
);
```

### 4.3 Peso Inicial de la Sinapsis (Catch #2 del auditor técnico)

> **Parámetro del barrido:** el peso inicial de la sinapsis tejida NO es constante — se varía junto a AA, dims y valencia en Fase 2.

**Razón:** `peso_sinaptico` pesa 10% del score híbrido. Si el peso es demasiado bajo, la sinapsis tejida no mueve nada (mismo caso que tematico_score 0.08).

**Valores a barrer:** 0.3, 0.5, 0.7, 1.0

---

## 5. Protocolo — Fases 0-8

### Fase 0: Preparación

1. **Snapshot de la DB** antes de cualquier cambio (protocolo establecido)
2. **Holdout split 50/50** con seed fija (20260804), reusando protocolo de `experimento_faseB_holdout.py`
3. **Baseline** sobre los 921 casos (reutilizar `experimento_rr_pool.json`)

### Fase 1: Generación de Candidatos

1. Calcular degree de cada nodo activo en el grafo de sinapsis
2. Identificar nodos con degree ≤ 3 (candidatos a "isla" — ajustado desde ≤ 1, ver 4.1a)
3. Para cada par de candidatos, calcular Adamic-Adar
4. Filtrar por AA ≥ umbral + dims compartidas ≥ 2 (valencia NO filtra — es desempate)
5. **Excluir** todo par con fila en `sinapsis_cuarentena` (cross-check bidireccional)
6. **Registrar** cuántos candidatos coinciden con cuarentena (señal de calibración)
7. **Output:** `scripts/tejedora_candidatos.json` — lista de pares candidatos con scores

### Fase 2: Sweep de Parámetros

Barrido grid-search sobre mitad A del holdout:

| Parámetro | Valores | Total combinaciones |
|---|---|---|
| Umbral AA | 0.2, 0.3, 0.5, 0.7 | 4 (ajustado: se agregó 0.2) |
| Dims mínimas | 2, 3 | 2 |
| Valencia | Desempate (no se barre como filtro) | — |
| Peso inicial | 0.3, 0.5, 0.7, 1.0 | 4 |
| **Total** | | **32 configs** |

Cada config: crear sinapsis tejidas en mitad A → medir recall@5 → seleccionar mejor config.

**Criterio de selección:** mayor recall@5 sin degradar ninguna categoría >1 caso.

### Fase 2 RESULTADO — Sweep ejecutado 2026-08-06 (pipelline real, 8 workers)

**Setup real ejecutado:** `scripts/tejedora_sweep.py` — mismo snapshot de Fase 0, mismo holdout (921 casos), `buscar_por_frase` real de `core/memory_store.py:3079`, `limite=5`, inyección de aristas con tipo `tejida_estructural` (rechaza aristas existentes), jaccard sobre tokens stopwords. Baseline vs config con las 13 aristas tejidas (peso 0.6).

```
baseline_sin_tejido    95.35    +0.000pp
tejido_peso_0.6        95.35    +0.000pp
```

| Métrica | baseline | tejido | delta |
|---|---|---|---|
| R@5 global | 95.35% | 95.35% | **0.000pp** |
| R@1 global | 86.27% | 86.27% | 0.000pp |
| MRR | 0.8983 | 0.8983 | 0.000 |
| por_tema R@5 | 78.46% | 78.46% | 0.000pp |
| sinonimo R@5 | 75.41% | 75.41% | 0.000pp |

**VEREDICTO: la hipótesis está REFUTADA con la pipeline real.** Las 13 sinapsis tejidas no movieron NI UN SOLO ranking de los 921 casos. Confirmado el techo teórico calculado antes del sweep (la red pesa ~2% en el score híbrido; las aristas conectan islas que de todos modos no llegan al top-5; solo 5 misses tenían respuesta-isla, y ninguna se salvó).

**Implicación:** el recall de BioRAG NO mejora tejiendo más sinapsis estructurales. El cuello de botella es el matching léxico/semántico (BM25 + dimensiones + PRF), no el cableado del grafo. Las sinapsis existentes ya cubren la vía de propagación; agregar aristas no cambia el ranking porque el peso de la red en el scoring es marginal. Fases 3-8 CANCELADAS.

### Fase 3: Tejido de Sinapsis

Con la mejor config de Fase 2:

1. Crear sinapsis tejidas en DB de experimentación (copia aislada)
2. Tipo: `tejida_estructural` (nuevo, no confundir con `latente_confirmada`)
3. Peso: valor seleccionado en sweep
4. Sync CSV de asociaciones (lesson: `leccion_hormiguita_sincronizar_cache_asociaciones_podar`)
5. Registrar cada sinapsis tejida con trazabilidad completa

### Fase 4: Evaluación

1. Medir recall@5 sobre mitad B (nunca vio el ajuste)
2. Comparar contra baseline de mitad B
3. Verificar que ninguna categoría pierde >1 caso
4. Medir latencia (no >5ms adicional)

### Fase 5: Integración en Daemon

Si Fase 4 aprueba (delta ≥ +2pp):

1. Agregar detección de agujeros estructurales al daemon (`graph_maintenance_daemon.py`)
2. Ejecutar tejido en cada ciclo (junto a poda)
3. Flag `BIORAG_TEJEDORA_ENABLED` (OFF por defecto)
4. Monitoreo: nodos tejidos, candidatos descartados por cuarentena

### Fase 6: Validación Final

1. Evaluar sobre 921 casos completos (no solo mitad B)
2. Verificar categorías individualmente
3. Inspección manual de sinapsis tejidas (muestra de 20)
4. Documentar hallazgos en EXPERIMENTS.md

### Fase 7: Documentación

1. Actualizar EXPERIMENTS.md con resultados
2. Actualizar CHANGELOG.md
3. Actualizar README.md si aplica
4. Guardar nodo en BioRAG con dimensiones y sinónimos

### Fase 8: Commit

1. Commit con mensaje descriptivo
2. Tag si es release
3. Backup de DB post-experimento

---

## 6. Archivos Involucrados

| Archivo | Rol |
|---|---|
| `scripts/tejedora_generar_candidatos.py` | Fase 1: genera candidatos con AA |
| `scripts/tejedora_sweep.py` | Fase 2: barrido de parámetros |
| `scripts/tejedora_tejer.py` | Fase 3: crea sinapsis tejidas |
| `scripts/tejedora_evaluar.py` | Fase 4: evalúa recall@5 |
| `core/dmn_engine.py` | Semilla: muestreo resonante cortical (L130-215) |
| `core/memory_store.py` | Tablas: sinapsis, sinapsis_latentes, sinapsis_cuarentena, largo_plazo |
| `core/dmn_reflexion.py` | Hormiguita: cross-check cuarentena |
| `scripts/experimento_faseB_holdout.py` | Protocolo de split 50/50 (reusar) |
| `scripts/experimento_rr_pool.json` | Holdout 921 casos |
| `scripts/casos_qa_baseline_v1.jsonl` | Benchmark gate |

---

## 7. Semilla Técnica — dmn_engine.py

El experimento se basa en la idea dormida de `core/dmn_engine.py` (256 líneas, del 2026-07-26):

**Mecanismo existente (L130-215):**
1. Tomar nodo ancla (valencia ≥0.3 o peso ≥0.5)
2. Buscar nodo resonante que comparta dimensión semántica
3. Si no hay arista directa → crear sinapsis latente nueva

**Lo que le falta (lo que este experimento agrega):**
- Medición de impacto (recall@5 delta)
- Criterio de calidad (cross-check cuarentena)
- Integración con daemon (Fase 5)
- Peso como parámetro (Catch #2)

**Decisión 2026-07-27:** dmn_engine.py quedó dormido deliberadamente (no se arranca en prod). Este experimento lo usa como base técnica sin activarlo — crea las sinapsis en una DB de experimentación, no en la DB viva.

---

## 8. Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| Sobresaturación de un nodo | Max 3 conexiones/nodo/ciclo |
| Falsos positivos estructurales | Cross-check cuarentena + inspección manual |
| Degradación de categorías | Monitoreo por categoría; protect-r0 |
| Latencia adicional | Sinapsis tejidas se indexan normalmente; overhead ~0 |
| DB crece demasiado | Triggers de purga (ya implementados en P1) |

---

## 9. Referencias

- **Auditor técnico validó:** "mismo rigor que todo lo demás — snapshot, holdout seed fija, criterio de éxito explícito"
- **Catch #1:** cross-check contra `sinapsis_cuarentena` (evitar reconectar lo que la Hormiguita juzgó)
- **Catch #2:** peso inicial como parámetro del barrido (no constante)
- **Grid Cells:** confirmado como NO necesario ahora (fronteras ya cubiertas por islas de degree ≤ 3)
- **HDC binding:** no se toca (experimento independiente, 38/38 validados)
- **principio_purga_nivel_db_triggers:** la DB se auto-limpia, no depende de daemon/dashboard
- **principio_cableado_completo_todos_los_caminos:** este plan cubre daemon/on-demand/startup/endpoint

---

## 10. Cronograma

| Fase | Tiempo estimado | Dependencias |
|---|---|---|
| Fase 0 | 30 min | Snapshot + split + baseline |
| Fase 1 | 1-2 horas | Grafo real, cuarentena |
| Fase 2 | 2-4 horas | 32 configs × mitad A |
| Fase 3 | 30 min | Mejor config |
| Fase 4 | 30 min | Mitad B |
| Fase 5 | 1-2 horas | Si Fase 4 aprueba |
| Fase 6 | 1 hora | 921 casos completos |
| Fase 7-8 | 1 hora | Documentación + commit |
| **Total** | **6-10 horas** | |

---

*Documento generado por Athena-OEC. Pendiente de aprobación de negocio (Dennys) — presentación 2026-08-06 02:00.*
