# Plan Tejedora — Detección y Tejido de Agujeros Estructurales

**Estado:** Validado por líder, 2 correcciones integradas. Pendiente de presentación (2026-08-05 16:00).
**Autor:** Athena-OEC
**Versión:** 1.0 (con correcciones del líder)

---

## 1. Contexto — ¿Por qué este experimento?

El sistema tiene **8,529 sinapsis latentes** detectadas pero **no conectadas**. El grafo tiene nodos huérfanos (grado 0-1) y regiones sin explorar. La hormiguita poda lo que hay, pero nadie **detecta lo que falta**.

**Gap real (verificado en código):**
- `_expandir_contexto_bfs` (memory_store.py:2919) expande contexto, no busca huecos
- `_context_window` (memory_store.py:143, deque maxlen=10) ya da bonus token-level, pero NO hay interferencia semántica entre queries recientes
- No existe detección de vacíos estructurales en el grafo

**Idea 2 del líder (2026-08-05):** detectar agujeros estructurales (nodos con degree 0-1, low clustering coefficient) y crear sinapsis nuevas para llenarlos, usando Adamic-Adar (no Jaccard) como métrica estructural.

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
| Umbral AA mínimo | ≥ 0.5 | Criterio inicial conservador; se sweep en Fase 2 |
| Dimensiones compartidas mínimas | ≥ 2 | Garantiza coherencia semántica (no conexión random) |
| Valencia somática mínima | ≥ 0.3 | Excluye nodos "fríos" sin señal emocional |
| Máximo conexiones por nodo por ciclo | 3 | Evita saturación de un nodo |

### 4.2 Cross-check contra Cuarentena (Catch #1 del líder)

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

### 4.3 Peso Inicial de la Sinapsis (Catch #2 del líder)

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
2. Identificar nodos con degree ≤ 1 (candidatos a "isla")
3. Para cada par de candidatos, calcular Adamic-Adar
4. Filtrar por AA ≥ umbral + dims compartidas ≥ 2 + valencia ≥ 0.3
5. **Excluir** todo par con fila en `sinapsis_cuarentena` (cross-check bidireccional)
6. **Registrar** cuántos candidatos coinciden con cuarentena (señal de calibración)
7. **Output:** `scripts/tejedora_candidatos.json` — lista de pares candidatos con scores

### Fase 2: Sweep de Parámetros

Barrido grid-search sobre mitad A del holdout:

| Parámetro | Valores | Total combinaciones |
|---|---|---|
| Umbral AA | 0.3, 0.5, 0.7 | 3 |
| Dims mínimas | 2, 3 | 2 |
| Valencia mínima | 0.3, 0.5 | 2 |
| Peso inicial | 0.3, 0.5, 0.7, 1.0 | 4 |
| **Total** | | **48 configs** |

Cada config: crear sinapsis tejidas en mitad A → medir recall@5 → seleccionar mejor config.

**Criterio de selección:** mayor recall@5 sin degradar ninguna categoría >1 caso.

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

- **Líder validó:** "mismo rigor que todo lo demás — snapshot, holdout seed fija, criterio de éxito explícito"
- **Catch #1:** cross-check contra `sinapsis_cuarentena` (evitar reconectar lo que la Hormiguita juzgó)
- **Catch #2:** peso inicial como parámetro del barrido (no constante)
- **Grid Cells:** confirmado como NO necesario ahora (fronteras ya cubiertas por degree 0-1)
- **HDC binding:** no se toca (experimento independiente, 38/38 validados)
- **principio_purga_nivel_db_triggers:** la DB se auto-limpia, no depende de daemon/dashboard
- **principio_cableado_completo_todos_los_caminos:** este plan cubre daemon/on-demand/startup/endpoint

---

## 10. Cronograma

| Fase | Tiempo estimado | Dependencias |
|---|---|---|
| Fase 0 | 30 min | Snapshot + split + baseline |
| Fase 1 | 1-2 horas | Grafo real, cuarentena |
| Fase 2 | 2-4 horas | 48 configs × mitad A |
| Fase 3 | 30 min | Mejor config |
| Fase 4 | 30 min | Mitad B |
| Fase 5 | 1-2 horas | Si Fase 4 aprueba |
| Fase 6 | 1 hora | 921 casos completos |
| Fase 7-8 | 1 hora | Documentación + commit |
| **Total** | **6-10 horas** | |

---

*Documento generado por Athena-OEC. Pendiente de presentación al líder (2026-08-05 16:00).*
