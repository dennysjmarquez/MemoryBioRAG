# Plan Técnico: Integración Temporal Knowledge Graph como Signal #14 / Capa 8 del Scoring Híbrido

**Fecha:** 2026-08-15  
**Autor:** Athena-OEC  
**Estado:** PROPUESTA TÉCNICA — Para revisión y aprobación de Dennys  
**Versión:** 1.0  
**Basado en:** Corrección de conceptos recibida (Graphiti ≡ grafo sinapsis BioRAG; SodaMem ≡ SDM 2048b) + análisis de código real (`core/memory_store.py`, `core/sdm.py`, `core/sinapsis.py`, `core/ppmi_vectorizer.py`)

---

## 1. RESUMEN EJECUTIVO

### 1.1 Qué se propone
Activar **Signal #14 (ADN Conceptual v29)** —actualmente instalado **APAGADO por defecto** (`BIORAG_ADN_RANKING_ENABLED=false`)— y fusionarlo con una **capa lógica temporal (Temporal Knowledge Graph)** que convierta las asociaciones del neocórtex en un **filtro activo de ordenamiento y validez histórica**, no solo un campo informativo adjunto.

### 1.2 Por qué es "Oportunidad de Oro"
- **Rendimiento actual brutal:** Global Recall@5 96.14%, Python puro + SQLite, ~20 MB RAM, 2.84 ms latencia
- **Gap crítico:** El sistema encuentra excelentemente por significado, pero **no razona el ciclo de vida del conocimiento** (anacronismo médico, protocolos superados, contradicciones temporales)
- **Ventaja competitiva:** Resolver nativamente validez temporal en CPU pura, sin embeddings densos comerciales, sin Neo4j externo, sin LLM para extracción

### 1.3 Alcance del plan
| Componente | Estado actual | Acción |
|---|---|---|
| `largo_plazo` tabla | `creado_en`, `ultimo_acceso` | **EXTENDER**: `occurrence_time`, `mention_time`, `validity_start`, `validity_end` |
| `sinapsis` tabla | Tipos: `pmi_hebbiano`, `co_ocurrencia`, `sinonimo_explicito`, `co_semantica`, `co_nombre`, `manual` | **EXTENDER**: Tipos `SUPERSEDES`, `CONTRADICTS`, `UPDATES` + `provenance_spans` |
| `_calcular_score_hibrido()` | 13 señales (hasta PPMI+SVD) | **AÑADIR Signal #14**: `temporal_kg_score` + `validity_gate` |
| `adn_firmas` / `hipotesis_teleologicas` | Existen, OFF por defecto | **ACTIVAR + INTEGRAR** con Temporal KG layer |
| Canal 2 (Halo Subconsciente) | Desacoplado del scoring principal | **UNIFICAR** como filtro temporal en Capa 8 |

---

## 2. ANÁLISIS DE CÓDIGO BASE — DÓNDE TOCAR

### 2.1 Esquema actual `largo_plazo` (líneas 405-418, 736-748)
```sql
CREATE TABLE largo_plazo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto TEXT UNIQUE NOT NULL,
    categoria INTEGER DEFAULT 1,
    contenido TEXT,
    peso_sinaptico REAL DEFAULT 1.0,
    estado TEXT DEFAULT 'activo',
    asociaciones TEXT DEFAULT '',
    ultimo_acceso REAL,
    sinonimos TEXT DEFAULT '',
    creado_en REAL DEFAULT 0,
    -- NUEVOS CAMPOS TEMPORALES:
    occurrence_time REAL DEFAULT NULL,  -- cuándo ocurrió el evento biológico/clínico en el mundo real
    mention_time REAL DEFAULT NULL,     -- cuándo lo procesó el agente
    validity_start REAL DEFAULT NULL,   -- inicio de vigencia del conocimiento
    validity_end REAL DEFAULT NULL,     -- fin de vigencia (NULL = vigente)
    FOREIGN KEY (categoria) REFERENCES categories(id)
)
```

### 2.2 Esquema actual `sinapsis` (líneas 32-48 en `core/sinapsis.py`)
```sql
CREATE TABLE sinapsis (
    origen TEXT NOT NULL,
    destino TEXT NOT NULL,
    peso REAL DEFAULT 0.5,
    tipo TEXT DEFAULT 'co_ocurrencia',  -- NUEVOS: 'SUPERSEDES', 'CONTRADICTS', 'UPDATES'
    creado_en REAL,
    ultimo_uso REAL,
    provenance_spans TEXT DEFAULT '',   -- JSON: spans del documento/fluente original
    PRIMARY KEY (origen, destino)
)
```

### 2.3 Scoring híbrido actual (líneas 3126-3174)
```python
def _calcular_score_hibrido(self, ..., ppmi_score: float = 0.0):
    # ... 13 señales actuales ...
    score = base_weight * (0.25*bm25 + 0.14*dim + ... + 0.20*pred_score) \
            + jsd_weight * jsd_score \
            + PPMI_VECTOR_WEIGHT * ppmi_score
    # NUEVO: + TEMPORAL_KG_WEIGHT * temporal_kg_score
```

### 2.4 Configuración Signal #14 actual (líneas 103-119)
```python
ADN_RANKING_ENABLED = os.environ.get('BIORAG_ADN_RANKING_ENABLED', 'false').lower() in ('1', 'true', 'yes')
ADN_PESO = float(os.environ.get('BIORAG_ADN_PESO', '0.15'))
ADN_MAX_EXPANSION = int(os.environ.get('BIORAG_ADN_MAX_EXPANSION', '24'))
ADN_UMBRAL_ASOCIACION = float(os.environ.get('BIORAG_ADN_UMBRAL_ASOCIACION', '0.35'))
# Fórmulas v29:
# S_final_directo    = 0.85 * S_base + 0.15 * S_adn
# S_final_asociativo = min(0.49, 0.70 * S_base + 0.30 * S_adn)
```

### 2.5 SDM (SodaMem) — Ya implementado en `core/sdm.py`
- 2048 bits, 5 segmentos, clusters Hebbianos + IDF ponderado
- HDC Context Binding (XOR determinista) v26.2
- Jaccard ponderado (dimensiones peso 2.5x)
- **No requiere cambios** — es la base biomimética del Temporal KG

---

## 3. DISEÑO TÉCNICO DETALLADO

### 3.1 Nuevas columnas en `largo_plazo` (Migración v30)

```python
# En _crear_estructura_cerebral() o migración ALTER TABLE
TEMPORAL_COLUMNS = [
    ("occurrence_time", "REAL DEFAULT NULL"),      -- Evento en mundo real (ej. publicación paper)
    ("mention_time", "REAL DEFAULT NULL"),         -- Procesamiento por agente
    ("validity_start", "REAL DEFAULT NULL"),       -- Vigencia inicio
    ("validity_end", "REAL DEFAULT NULL"),         -- Vigencia fin (NULL = actual)
    ("temporal_confidence", "REAL DEFAULT 1.0"),   -- Confianza en la validez temporal [0,1]
]

# Índices para queries temporales eficientes
CREATE INDEX IF NOT EXISTS idx_lp_validity ON largo_plazo (validity_start, validity_end);
CREATE INDEX IF NOT EXISTS idx_lp_occurrence ON largo_plazo (occurrence_time);
CREATE INDEX IF NOT EXISTS idx_lp_temporal_conf ON largo_plazo (temporal_confidence);
```

**Reglas de población:**
- `mention_time` = `time.time()` al crear/actualizar nodo (automático)
- `occurrence_time` = extraíble del contenido (fechas en paper, logs, logs clínicos) o = `mention_time` por defecto
- `validity_start` = `occurrence_time` por defecto
- `validity_end` = NULL (vigente) hasta que aparezca `SUPERSEDES`/`CONTRADICTS`

### 3.2 Nuevos tipos de arista en `sinapsis`

```python
# En init_sinapsis_table() + migración
TEMPORAL_EDGE_TYPES = {
    'SUPERSEDES':   "El nodo origen REEMPLAZA al destino (nuevo protocolo invalida viejo)",
    'CONTRADICTS':  "El nodo origen CONTRADICE al destino (evidencia opuesta)",
    'UPDATES':      "El nodo origen ACTUALIZA al destino (versión incremental)",
}

# provenance_spans: JSON array de spans
# [{"source_id": "doc_123", "start_char": 45, "end_char": 200, "doc_type": "paper|log|clinical_note"}]
```

**Reglas de propagación de validez:**
```
SUPERSEDES:  nodo_destino.validity_end = nodo_origen.mention_time
             nodo_destino.estado = 'superado' (nuevo estado)
CONTRADICTS: nodo_destino.temporal_confidence *= 0.5  (baja confianza)
             Alerta en planner-reader loop
UPDATES:     nodo_destino.validity_end = nodo_origen.mention_time
             nodo_origen.validity_start = nodo_destino.validity_start
             Hereda occurrence_time del original
```

### 3.3 Signal #14: `temporal_kg_score` — Cálculo

```python
def _calcular_temporal_kg_score(self, concepto: str, query_time: float = None) -> float:
    """
    Retorna score [0,1] que penaliza/boostea según validez temporal.
    Integrado en _calcular_score_hibrido como nueva señal.
    """
    if query_time is None:
        query_time = time.time()
    
    # 1. Validar vigencia del nodo
    row = self.cursor.execute("""
        SELECT validity_start, validity_end, temporal_confidence, occurrence_time
        FROM largo_plazo WHERE concepto = ?
    """, (concepto,)).fetchone()
    
    if not row:
        return 0.5  # neutral si no hay datos temporales
    
    v_start, v_end, temp_conf, occ_time = row
    
    # 2. Score de vigencia (1.0 = dentro de ventana, 0.0 = fuera)
    if v_start is not None and v_start > query_time:
        validity_score = 0.0  # futuro → no vigente aún
    elif v_end is not None and v_end < query_time:
        validity_score = 0.1  # expirado → penalización fuerte pero no cero (histórico)
    else:
        validity_score = 1.0  # vigente
    
    # 3. Boost por recencia del occurrence_time (conocimiento fresco)
    if occ_time is not None:
        age_days = (query_time - occ_time) / 86400
        if age_days < 30:
            recency_boost = 1.0
        elif age_days < 365:
            recency_boost = 0.8
        elif age_days < 1825:  # 5 años
            recency_boost = 0.5
        else:
            recency_boost = 0.2
    else:
        recency_boost = 0.5
    
    # 4. Penalización por aristas SUPERSEDES/CONTRADICTS activas
    contradiction_penalty = self._calcular_contradiction_penalty(concepto, query_time)
    
    # 5. Score final combinado
    temporal_kg_score = (
        0.50 * validity_score +
        0.30 * recency_boost +
        0.20 * temp_conf
    ) * (1.0 - contradiction_penalty)
    
    return round(max(0.0, min(1.0, temporal_kg_score)), 4)

def _calcular_contradiction_penalty(self, concepto: str, query_time: float) -> float:
    """Calcula penalización por aristas temporales contradictorias activas."""
    rows = self.cursor.execute("""
        SELECT tipo, peso, provenance_spans, creado_en
        FROM sinapsis
        WHERE (origen = ? OR destino = ?) 
        AND tipo IN ('SUPERSEDES', 'CONTRADICTS', 'UPDATES')
        AND creado_en <= ?
    """, (concepto, concepto, query_time)).fetchall()
    
    if not rows:
        return 0.0
    
    max_penalty = 0.0
    for tipo, peso, provenance, creado_en in rows:
        if tipo == 'SUPERSEDES':
            # Si YO soy el superado (destino), penalización total
            row = self.cursor.execute("""
                SELECT 1 FROM sinapsis WHERE destino = ? AND tipo = 'SUPERSEDES'
            """, (concepto,)).fetchone()
            if row:
                max_penalty = max(max_penalty, 0.9 * peso)  # casi elimina
        elif tipo == 'CONTRADICTS':
            max_penalty = max(max_penalty, 0.4 * peso)  # moderada
        elif tipo == 'UPDATES':
            max_penalty = max(max_penalty, 0.1 * peso)  # ligera
    
    return min(0.95, max_penalty)  # cap para no anular completamente
```

### 3.4 Integración en `_calcular_score_hibrido()` — Capa 8

```python
# Nueva constante configurable (línea ~100)
TEMPORAL_KG_WEIGHT = float(os.environ.get('BIORAG_TEMPORAL_KG_WEIGHT', '0.10'))
"""Peso Signal #14: Temporal KG validity score. Default 0.10 (conservador).
Override: export BIORAG_TEMPORAL_KG_WEIGHT=0.15"""

# En _calcular_score_hibrido() — agregar parámetro y cálculo
def _calcular_score_hibrido(self, ..., ppmi_score: float = 0.0,
                            temporal_kg_score: float = 0.0):
    # ... código existente ...
    
    score = (
        base_weight * (
            0.25 * bm25_norm +
            0.14 * dim_score +
            0.08 * concepto_ratio +
            0.08 * sinonimos_ratio +
            0.10 * peso_norm +
            0.10 * max(score_latente, score_cadena) +
            0.10 * grupo_score +
            0.08 * tematico_score +
            0.04 * temporal +
            0.02 * asoc_norm +
            0.20 * pred_score
        ) +
        jsd_weight * jsd_score +
        PPMI_VECTOR_WEIGHT * ppmi_score +
        TEMPORAL_KG_WEIGHT * temporal_kg_score   # ← NUEVA SEÑAL #14
    )
    
    # Validity Gate: si temporal_kg_score < 0.2, floor del score final
    # (conocimiento expirado/contradicho no debería rankear alto)
    if temporal_kg_score < 0.2 and not match_exacto:
        score = min(score, 0.25)  # cap duro
    
    # ... resto existente (match_exacto, sinonimos_ratio bonus) ...
```

### 3.5 Planner-Reader Loop (Nivel Agente — fuera de `memory_store.py`)

```python
# Nuevo módulo: core/temporal_planner.py
class TemporalPlanner:
    """
    Orquesta evidence gathering → contradiction detection → temporal validation → reader.
    Se invoca desde mcp_server.py / agent loop ANTES de pasar contexto al LLM.
    """
    
    def __init__(self, cerebro: SQLiteMemoryBioRAG):
        self.cerebro = cerebro
    
    def plan_and_validate(self, query: str, candidatos: list[dict]) -> dict:
        """
        1. Detecta gaps temporales en candidatos top-k
        2. Navega aristas SUPERSEDES/CONTRADICTS/UPDATES
        3. Valida línea temporal coherente
        4. Retorna evidencia filtrada + metadata para Reader
        """
        query_time = time.time()
        evidencia_validada = []
        alertas_temporales = []
        
        for cand in candidatos[:10]:  # top-10 para planner
            concepto = cand['concepto']
            
            # A. Verificar vigencia
            temporal_score = self.cerebro._calcular_temporal_kg_score(concepto, query_time)
            if temporal_score < 0.3:
                alertas_temporales.append({
                    'concepto': concepto,
                    'tipo': 'EXPIRADO_O_CONTRADICHO',
                    'score': temporal_score,
                    'accion': 'EXCLUIR_O_MARCAR'
                })
                continue
            
            # B. Navegar aristas temporales (graph traversal)
            aristas_temp = self._obtener_aristas_temporales(concepto, query_time)
            for arista in aristas_temp:
                if arista['tipo'] == 'SUPERSEDES':
                    # El concepto actual está superado → seguir cadena
                    superseding = arista['origen'] if arista['destino'] == concepto else arista['destino']
                    alertas_temporales.append({
                        'concepto': concepto,
                        'tipo': 'SUPERSEDED_BY',
                        'superceded_by': superseding,
                        'provenance': arista['provenance_spans']
                    })
                    # Añadir el que supera a evidencia si no está
                    if superseding not in [e['concepto'] for e in evidencia_validada]:
                        sup_cand = self._get_candidato(superseding)
                        if sup_cand:
                            evidencia_validada.append(sup_cand)
                elif arista['tipo'] == 'CONTRADICTS':
                    alertas_temporales.append({
                        'concepto': concepto,
                        'tipo': 'CONTRADICTION_DETECTED',
                        'contra': arista['origen'] if arista['destino'] == concepto else arista['destino'],
                        'provenance': arista['provenance_spans']
                    })
        
        # C. Filtrar evidencia final (solo vigentes, priorizando los que superan)
        evidencia_final = [e for e in evidencia_validada 
                          if self.cerebro._calcular_temporal_kg_score(e['concepto'], query_time) >= 0.3]
        
        return {
            'evidencia': evidencia_final,
            'alertas_temporales': alertas_temporales,
            'query_time': query_time,
            'temporal_coherence': len(alertas_temporales) == 0
        }
    
    def _obtener_aristas_temporales(self, concepto: str, query_time: float) -> list[dict]:
        rows = self.cerebro.cursor.execute("""
            SELECT origen, destino, tipo, peso, provenance_spans, creado_en
            FROM sinapsis
            WHERE (origen = ? OR destino = ?)
            AND tipo IN ('SUPERSEDES', 'CONTRADICTS', 'UPDATES')
            AND creado_en <= ?
        """, (concepto, concepto, query_time)).fetchall()
        
        return [{
            'origen': r[0], 'destino': r[1], 'tipo': r[2],
            'peso': r[3], 'provenance_spans': r[4], 'creado_en': r[5]
        } for r in rows]
```

### 3.6 Episodios / Provenance Spans — Trazabilidad Ground Truth

```python
# Nueva tabla: episodios (provenance inmutable)
CREATE TABLE IF NOT EXISTS episodios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_tipo TEXT NOT NULL,        -- 'paper'|'clinical_note'|'log'|'api'|'manual'
    fuente_id TEXT NOT NULL,          -- DOI, PMID, log_id, url, etc.
    contenido_bruto TEXT,             -- Texto original (opcional, para auditoría)
    spans_json TEXT NOT NULL,         -- JSON: [{"start": 0, "end": 500, "conceptos": ["A", "B"]}]
    procesado_en REAL NOT NULL,
    agente TEXT DEFAULT 'sistema',
    hash_contenido TEXT               -- SHA256 para deduplicación
);

CREATE INDEX IF NOT EXISTS idx_ep_fuente ON episodios(fuente_tipo, fuente_id);
CREATE INDEX IF NOT EXISTS idx_ep_hash ON episodios(hash_contenido);

# Relación sinapsis → episodio (provenance_spans = JSON con episode_ids)
# Ejemplo provenance_spans:
# [{"episode_id": 42, "start_char": 100, "end_char": 350}, {"episode_id": 43, "start_char": 0, "end_char": 200}]
```

---

## 4. PLAN DE IMPLEMENTACIÓN POR FASES

### FASE 0: Preparación y Validación (Semana 1)
- [ ] Crear branch `feature/temporal-kg-signal14`
- [ ] Snapshot DB congelado para benchmark baseline (921 casos QA)
- [ ] Tests de regresión actuales pasando (pytest 16/16, QA eval)
- [ ] Documentar métricas baseline: GLOBAL R@5 96.14%, R@1 88.31%, MRR 0.910, FP 7.5%

### FASE 1: Esquema DB + Migración (Semana 2)
- [ ] **Migración `largo_plazo`**: 4 columnas temporales + índices (ALTER TABLE safe)
- [ ] **Migración `sinapsis`**: nuevos tipos + `provenance_spans` (TEXT JSON)
- [ ] **Nueva tabla `episodios`** + índices
- [ ] Script de migración idempotente (`scripts/migrar_temporal_kg_v30.py`)
- [ ] Verificar integridad: `PRAGMA integrity_check`, queries de prueba

### FASE 2: Signal #14 en Scoring (Semana 3)
- [ ] Implementar `_calcular_temporal_kg_score()` en `memory_store.py`
- [ ] Integrar en `_calcular_score_hibrido()` con `TEMPORAL_KG_WEIGHT`
- [ ] Agregar `BIORAG_TEMPORAL_KG_WEIGHT` en config (default 0.10)
- [ ] Implementar `_calcular_contradiction_penalty()`
- [ ] Unit tests: score temporal para casos (vigente, expirado, superado, contradictorio)

### FASE 3: ADN Conceptual + Temporal KG Fusion (Semana 4)
- [ ] Activar `ADN_RANKING_ENABLED=true` en config de prueba
- [ ] Fusionar `S_adn` con `temporal_kg_score`:
  ```python
  # Nueva fórmula combinada:
  S_temporal_adn = ADN_PESO * (0.7 * temporal_kg_score + 0.3 * adn_score)
  S_final_directo = (1 - ADN_PESO) * S_base + S_temporal_adn
  S_final_asociativo = min(0.49, 0.70 * S_base + 0.30 * adn_score)  # existente
  ```
- [ ] Validar que cota 0.49 asociativa se mantiene

### FASE 4: Planner-Reader Loop (Semana 5)
- [ ] Crear `core/temporal_planner.py`
- [ ] Integrar en `mcp_server.py` (endpoint `buscar_por_frase` → planner → reader)
- [ ] Implementar graph traversal para aristas temporales (BFS depth ≤ 2)
- [ ] Tests de integración: query con conocimiento superado → planner detecta y sustituye

### FASE 5: Población Automática de Campos Temporales (Semana 6)
- [ ] `mention_time` = auto en `aprender()` / `guardar()`
- [ ] `occurrence_time` = extracción heurística (regex fechas en contenido + NER básico)
- [ ] `validity_start` = `occurrence_time` por defecto
- [ ] Detección automática `SUPERSEDES`/`UPDATES`:
  - Si nuevo nodo comparte ≥80% tokens concepto + contenido semántico opuesto → `SUPERSEDES`
  - Si nueva versión de mismo concepto (similitud >0.9) → `UPDATES`
- [ ] `provenance_spans` = episode_id auto al ingestar documentos

### FASE 6: Benchmark + Validación OFF/ON (Semana 7-8)
- [ ] **Ablation OFF/ON** en snapshot congelado (921 casos QA):
  - Config A: `TEMPORAL_KG_WEIGHT=0.0`, `ADN_RANKING_ENABLED=false` (baseline v29)
  - Config B: `TEMPORAL_KG_WEIGHT=0.10`, `ADN_RANKING_ENABLED=true`
  - Config C: `TEMPORAL_KG_WEIGHT=0.15`, `ADN_RANKING_ENABLED=true`
- [ ] Métricas objetivo:
  - GLOBAL R@5 ≥ 96.5% (mejora ≥0.4pp)
  - por_tema R@5 ≥ 93.0% (mejora ≥0.7pp)
  - FP ≤ 6.0% (reducción ≥1.5pp)
  - Latencia ≤ 4ms (overhead ≤1.2ms)
- [ ] Diff caso-a-caso documentado (qué queries arregló, qué regressó)

### FASE 7: Documentación + Deploy Gradual (Semana 9)
- [ ] Actualizar `README.md` sección "Temporal Knowledge Graph"
- [ ] Documentar variables de entorno nuevas
- [ ] Guía de migración para usuarios existentes
- [ ] Deploy canary → monitoreo 48h → rollout completo

---

## 5. VARIABLES DE ENTORNO NUEVAS

```bash
# Temporal KG (Signal #14)
BIORAG_TEMPORAL_KG_WEIGHT=0.10          # Peso en scoring híbrido (default 0.10)
BIORAG_TEMPORAL_VALIDITY_GATE=0.20      # Floor score si temporal_kg_score < gate (default 0.20)
BIORAG_TEMPORAL_CONTRADICTION_CAP=0.95  # Cap penalización contradicción (default 0.95)

# ADN Conceptual (v29) — existentes, ahora ACTIVADOS
BIORAG_ADN_RANKING_ENABLED=true
BIORAG_ADN_PESO=0.15
BIORAG_ADN_MAX_EXPANSION=24
BIORAG_ADN_UMBRAL_ASOCIACION=0.35

# Episodios / Provenance
BIORAG_EPISODIOS_ENABLED=true
BIORAG_EPISODIOS_MAX_CHARS=50000        # Límite contenido_bruto por episodio
```

---

## 6. MIGRACIÓN DE DATOS EXISTENTES

```python
# scripts/migrar_temporal_kg_v30.py
def migrar_largo_plazo_temporal(con):
    """Puebla campos temporales en nodos existentes."""
    ahora = time.time()
    con.execute("""
        UPDATE largo_plazo SET
            mention_time = COALESCE(mention_time, ultimo_acceso, creado_en, ?),
            occurrence_time = COALESCE(occurrence_time, mention_time),
            validity_start = COALESCE(validity_start, occurrence_time),
            validity_end = CASE 
                WHEN estado = 'superado' THEN mention_time 
                ELSE NULL 
            END,
            temporal_confidence = CASE
                WHEN estado IN ('activo', 'dormido') THEN 1.0
                WHEN estado = 'cuarentena' THEN 0.5
                WHEN estado = 'superado' THEN 0.2
                ELSE 0.8
            END
    """, (ahora,))
    con.commit()

def migrar_sinapsis_provenance(con):
    """Inicializa provenance_spans vacío en aristas existentes."""
    con.execute("""
        ALTER TABLE sinapsis ADD COLUMN provenance_spans TEXT DEFAULT '[]'
    """)
    con.commit()
```

---

## 7. RIESGOS Y MITIGACIONES

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| **Overhead latencia** (cálculo temporal + planner) | Media | Alto | Lazy-load: solo calcular `temporal_kg_score` para top-50 candidatos; planner opcional via flag |
| **Regresión por_tema/sinonimo** | Media | Alto | Ablation OFF/ON obligatoria en snapshot congelado; rollback inmediato si FP > 10% |
| **Migración DB falla** | Baja | Crítico | Migración idempotente, backup automático, `PRAGMA integrity_check` pre/post |
| **Falsos SUPERSEDES automáticos** | Alta | Medio | Umbral conservador (similitud >0.9 + oposición semántica); revisión manual en dashboard |
| **Planner-reader loop rompe API actual** | Baja | Medio | Feature flag `BIORAG_PLANNER_ENABLED`; mantener path legacy |

---

## 8. MÉTRICAS DE ÉXITO (KPIs)

| Métrica | Baseline v29 | Objetivo v30 | Método |
|---|---|---|---|
| **GLOBAL R@5** | 96.14% | ≥ 96.5% | 921 casos QA, snapshot congelado, 4 corridas |
| **por_tema R@5** | 92.31% | ≥ 93.0% | Idem |
| **sinonimo R@5** | 78.69% | ≥ 80.0% | Idem |
| **Falsos Positivos** | 7.5% | ≤ 6.0% | 40 controles negativos |
| **Latencia p50** | 2.84 ms | ≤ 4.0 ms | `benchmark.py` 100 queries |
| **Memoria RAM** | ~20 MB | ≤ 30 MB | `psutil` en benchmark |
| **Temporal coherence** | N/A | ≥ 95% | Planner detecta contradicciones en test set curado |

---

## 9. ARQUITECTURA FINAL — CAPAS DE SCORING (v30)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SCORING HÍBRIDO v30 (14 SEÑALES)                  │
├─────────────────────────────────────────────────────────────────────┤
│  Capa 1  Lexical:        BM25 (FTS5 trigram)          peso 0.25     │
│  Capa 2  Semántico:      Dimensiones (13 ejes)       peso 0.14     │
│  Capa 3  Concepto:       Match nombre exacto         peso 0.08     │
│  Capa 4  Sinónimos:      Match sinónimos declarados  peso 0.08     │
│  Capa 5  Sináptico:      Peso sinapsis + GABA        peso 0.10     │
│  Capa 6  Asociativo:     Jaccard / Cadena evocación  peso 0.10     │
│  Capa 7  Grupal:         WordNet semantic grouping   peso 0.10     │
│  Capa 8  Temático:       Ausencia/presencia dims IDF peso 0.08     │
│  Capa 9  Temporal:       Recencia simple             peso 0.04     │
│  Capa 10 Asociaciones:   Conteo vecinos              peso 0.02     │
│  Capa 11 Causal:         Predicados SRL              peso 0.20     │
│  Capa 12 Distribucional: JSD overlap                 peso JSD_W   │
│  Capa 13 Vectorial:      PPMI+SVD (100d ortogonales)  peso 0.15   │
│  Capa 14 TEMPORAL KG:    Validity + Contradicciones  peso 0.10   │ ← NUEVA
├─────────────────────────────────────────────────────────────────────┤
│  FUSIÓN ADN (Signal #14 v29):                                        │
│    S_final_directo    = 0.85 * S_base + 0.15 * (0.7*TKG + 0.3*ADN)  │
│    S_final_asociativo = min(0.49, 0.70*S_base + 0.30*ADN)           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 10. PRÓXIMOS PASOS INMEDIATOS (Para Dennys)

1. **Revisar este plan** — ¿Aprobar alcance y prioridades?
2. **Confirmar variables de entorno defaults** — ¿`TEMPORAL_KG_WEIGHT=0.10` OK?
3. **Decidir feature flags** — `BIORAG_PLANNER_ENABLED` por defecto ON u OFF?
4. **Autorizar branch y Fase 0** — Crear `feature/temporal-kg-signal14` y snapshot DB
5. **Definir test set temporal** — Casos curados de conocimiento médico superado/contradicho para validar planner

---

## 11. REFERENCIAS DE CÓDIGO CLAVE

| Archivo | Líneas relevantes | Qué tocar |
|---|---|---|
| `core/memory_store.py` | 405-418, 736-748, 3126-3174 | Esquema `largo_plazo`, `_calcular_score_hibrido` |
| `core/sinapsis.py` | 32-48, 104-166 | Esquema `sinapsis`, `auto_vincular` (nuevos tipos) |
| `core/sdm.py` | 169-242, 272-320 | SDM (base biomimética — NO tocar) |
| `core/ppmi_vectorizer.py` | 69-122, 298-360 | PPMI+SVD (Signal #13 — NO tocar) |
| `core/adn_conceptual.py` | 1-350 | ADN Conceptual v29 (activar + fusionar) |
| `mcp_server.py` | Endpoints `buscar_por_frase` | Inyectar Planner-Reader loop |
| `scripts/migrar_temporal_kg_v30.py` | **NUEVO** | Migración idempotente |

---

**Firma:** Athena-OEC  
**Fecha:** 2026-08-15  
**Estado:** Listo para revisión de Dennys → Aprobación → Fase 0