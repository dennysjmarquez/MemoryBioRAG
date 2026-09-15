# BioRAG — Definitive Agent Field Manual & Master Operating Instructions

> **To any agent reading this**: You are stepping into **MemoryBioRAG**, a bio-inspired, mathematically pure associative memory engine. It is engineered to surpass traditional vector RAG *without* pre-trained deep neural embeddings, *without* external API calls, *without* GPUs, and running 100% locally on CPU via graph theory, linear algebra, and hyperdimensional computing.
>
> Read this document completely before touching any code. It is designed so that you can achieve 100% operational mastery from your very first step.

---

## 1. System Thesis & Architectural Philosophy

MemoryBioRAG is **not** a wrapper around OpenAI, LangChain, or SentenceTransformers. It models biological neocortical and hippocampal memory dynamics:
- **Heptadic Multi-Signal Retrieval**: Combines exact/fuzzy lexical matching (FTS5 BM25), co-occurrence latent space (PPMI+SVD 100-dim), 13 topological semantic dimensions, hyperdimensional associative memory (SDM 2048-bit), and synaptic graph activation.
- **Epistemic Conformal Certainty (v28.1)**: Uses split conformal prediction (Vovk, 2005) to calibrate a mathematical false-positive (FP) guarantee as a dynamic percentile, not an arbitrary hardcoded threshold.
- **Autonomous Sleep Cycle & DMN**: Background daemons consolidate short-term memories into long-term structures, prune dead synapses, and form associative abstractions during idle periods (La Hormiguita).
- **Universal & Domain-Agnostic**: Designed for anyone (a physician, attorney, researcher, student) who downloads and runs it out-of-the-box without needing to be a software engineer.

---

## 2. Invariants & Operating Methodology (Arcadia Protocol)

These rules are **immutable** and must guide every decision you make:

### Invariant 1: UX-First Universal Design ("Antes de construir, justifica")
Before writing a single line of new code or proposing a feature, you must answer:
1. **Who uses it?** Assume the end-user is *not* a programmer. They will not edit code, tweak JSON files, or configure obscure environment variables. If a feature is "default-OFF" and invisible to a standard user, it provides zero real-world value.
2. **Does another natural path exist?** If the user's natural workflow (e.g. intuitive synonyms when saving a memory) or existing mechanisms solve the issue, **do not build new code**.
3. **Is it worth the technical weight?** All new code is debt.
4. **STRICT PROHIBITION**: **NEVER** hardcode domain vocabularies, dictionaries, or project-internal terms into the engine. The system must remain 100% domain-agnostic.

### Invariant 2: One Change at a Time (Rule 13)
Never test multiple hypotheses or changes simultaneously. Isolate each change, measure Before vs After, and record exact metrics. If any metric regresses: **IMMEDIATE REVERT**.

### Invariant 3: Visible Failures (Rule 12)
Missing data, unindexed tokens, or database discrepancies must fail visibly with clear exceptions and descriptive logs. **Never** return silent defaults (such as `0.0`, empty arrays, or fallback nulls) that can masquerade as valid zero-score results.

### Invariant 4: No Prose Without Concrete Output
Never report assumed, simulated, or expected numbers as verified facts. Every claim of success, improvement, or regression must be proven with verbatim command outputs (diffs, benchmark summaries, pytest runs).

### Invariant 5: Dual Verification Discipline
Verifying a fix against the frozen snapshot is **NOT** enough.
1. **Snapshot** (`snapshots/qa_escape_qcr_20260811.db`): Verifies mathematical regression against historical baselines.
2. **Live DB Copy** (via `sqlite3.backup()`): Verifies real-world resolution against the active, mutating production corpus.
*If a fix passes on the snapshot but fails on the live copy, it is NOT resolved.*

---

## 3. The Search Pipeline Anatomy (`core/memory_store.py`)

All retrieval through `buscar_por_frase` flows through three deterministic phases:

```
Query Entrada
    │
    ▼
[FASE 1: Generación de Candidatos]
    ├── 1.1 FTS5 Exacto (concepto + sinonimos)
    ├── 1.2 Escape QCR (si score < 0.60 o pool vacío → relajación OR)
    └── 1.3 Expansión Sináptica BFS (recorre aristas de `sinapsis` hasta N saltos)
    │
    ▼
[FASE 2: Scoring Híbrido Multi-Señal (_calcular_score_hibrido)]
    ├── BM25 / FTS Rank (~0.25)
    ├── PPMI + SVD 100-dim Cosine (~0.15)
    ├── 13 Ejes Semánticos / Jaccard dimensional (~0.14)
    ├── Peso Sináptico Hebbiano (~0.10)
    ├── Concepto & Sinónimos Ratios (~0.16)
    ├── SDM / HDC 2048-bit Overlap
    ├── Hub Matching & Predicados SRL
    └── Reranking Jaccard léxico final
    │
    ▼
[FASE 3: Calibración Conforme & Certeza Epistémica]
    ├── Umbral Conforme Dinámico (Percentil adaptativo según tamaño de corpus)
    └── Clasificación en 3 Niveles:
          • 'evidencia_directa' (Score ≥ umbral)
          • 'relacionado_confianza_media'
          • 'sin_evidencia_directa'
```

---

## 4. Codebase Navigation Map

The core engine is largely centralized in `core/memory_store.py` (~7,500 lines). Do not get lost; use this functional index:

| Component / Function | Line Range (Approx.) | Purpose |
|----------------------|----------------------|---------|
| `SQLiteMemoryBioRAG.__init__` | ~L150 - L450 | Database bootstrap, table schema creation, FTS5 virtual tables, PRAGMAs. |
| `guardar` / `aprender` | ~L1800 - L2150 | Memory ingestion: dimensional encoding, synonym storage, synaptic link triggers. |
| `vincular` / Hebbian updates | ~L2400 - L2700 | Graph edge creation, weight updates, reinforcement via activation. |
| `_calcular_score_hibrido` | ~L3660 - L3760 | The multi-signal scoring equation balancing BM25, PPMI, dimensions, and graph. |
| `nivel_certeza` & Calibración | ~L4200 - L4350 | Conformal prediction percentile, Platt scaling, Neocortex certainty labeling. |
| `buscar_por_frase` | ~L4770 - L5500 | Main retrieval pipeline: candidate generation, BFS graph expansion, ranking. |
| Daemons & Consolidation | ~L6000 - L7499 | Short-term to long-term memory consolidation, episodic cleanup, DMN hooks. |

### Auxiliary Core Modules (`core/`)
- `core/sinapsis.py`: Pure graph data structures, topological distance, triadic closure.
- `core/ppmi_vectorizer.py`: PPMI co-occurrence matrix generation, SVD dimensional reduction (100 dims), retrofitting.
- `core/ppmi_hybrid_search.py`: Fast cosine similarity on local latent space.
- `core/sdm.py`: Sparse Distributed Memory (Kanerva, 1988) with 2048-bit hyperdimensional binary vectors.
- `core/calibracion.py`: `UmbralConforme` and `CalibradorPlatt` statistical guarantees.
- `core/dmn_engine.py` & `core/dmn_reflexion.py`: Default Mode Network background sleep reflection.

---

## 5. Database Schema Reference (SQLite)

### Table: `largo_plazo` (Primary Long-Term Memory)
- `id` (INTEGER PRIMARY KEY)
- `concepto` (TEXT): Canonical identifier/title of the node.
- `contenido` (TEXT): Full memory content / descriptive payload.
- `peso_sinaptico` (REAL): Base Hebbian strength [0.0 - 1.0].
- `estado` (TEXT): `'activo'`, `'dormido'`, `'consolidado'`.
- `asociaciones` (TEXT): Comma-separated list of related concepts.
- `sinonimos` (TEXT): Comma-separated lexical equivalents.
- `dimensiones` (TEXT): Encoded semantic coordinate string (13 axes).
- `creado_en` (INTEGER/REAL): Timestamp.

### Table: `sinapsis` (Connectome Graph Edges)
- `id` (INTEGER PRIMARY KEY)
- `origen` (TEXT): Source node concept.
- `destino` (TEXT): Target node concept.
- `peso` (REAL): Synaptic connection strength [0.0 - 1.0].
- `tipo` (TEXT): Relation type (`'asociativa'`, `'causal'`, `'temporal'`).
- `ultima_activacion` (REAL): Timestamp for Hebbian decay calculation.

### Table: `calibracion_estado` (Conformal Predictor State)
- `id` (INTEGER PRIMARY KEY, always 1)
- `umbral` (REAL): Currently calibrated FP threshold.
- `alpha` (REAL): Target significance level (e.g. 0.05 for 95% confidence).
- `n_nodos_corpus` (INTEGER): Node count at calibration time (triggers re-calibration if drift > 20%).
- `platt_a`, `platt_b` (REAL): Platt scaling calibration coefficients.

---

## 6. Curated Deep-Dive Documentation Index (`docs/`)

The `docs/` folder contains extensive research artifacts. Do not read them all at once to preserve context window. Consult them on demand:

- **For Semantic Dimensions Theory**: `docs/teoria_de_ejes_semanticos.md`
- **For PPMI+SVD Mathematical Formulation**: `docs/LEEME_ppmi_svd.md`
- **For Conformal Calibration Deep-Dive**: `docs/AUDITORIA_CALIBRACION_v28.1.md`
- **For the Lexical Abyss Challenge (EXP-Q)**: `docs/INFORME_ABISMO_LEXICO_EXPQ_v31.3.md` and `docs/analisis_pilares_abismo_lexico.md`
- **For Background Daemon & Graph Maintenance**: `docs/plan_hormiguita_mantenimiento_grafo.md`
- **For Master Project Vision & History**: `Building Human-Like Persistent Memory.md` and `docs/PLAN_MAESTRO_BIORAG_UNICO_EN_EL_PLANETA.md`

---

## 7. Execution & Benchmark Commands

Always run these commands from the repository root:

```bash
# 1. Full QA Evaluation Suite (921 frozen cases — Primary Gate):
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py

# 2. Comprehensive Unit Test Suite:
python3 -m pytest tests/ -v

# 3. Lexical Abyss Challenge (Zero lexical overlap test):
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/test_abismo_lexico.py

# 4. Safe Live DB Copy for Dual Verification:
python3 -c "import sqlite3; src=sqlite3.connect('MemoryBioRAG_Data/memory_biorag.db'); dst=sqlite3.connect('/tmp/live_copy.db'); src.backup(dst); dst.close(); src.close()"

# 5. MCP Server (Stdio communication):
python3 mcp_server.py

# 6. Background Consolidation Daemon:
python3 graph_maintenance_daemon.py
```

### Official Baseline Target (v31.3 / State B):
- **Global Recall@5**: ≥ 96.03% (Gate threshold: ≥ 97.0%)
- **Global Recall@1**: ≥ 88.76%
- **Global MRR**: ≥ 0.916
- **False Positive Rate**: Target 0.0% on negative controls

---

## 8. Common Pitfalls & How to Avoid Them

| Pitfall | Cause | Remediation |
|---------|-------|-------------|
| **Evaluating against Live DB directly** | Daemons and test scripts write to the DB. | **Always** use `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db` for official benchmarks. |
| **Solving snapshot without live verification** | Snapshot population (851 active) differs from production. | Run Dual Verification via temporary SQLite backup. |
| **Omitting `parafrasis` in searches** | Single queries lose ~60% recall on complex queries. | Always generate 3–5 diverse paraphrases in MCP search tools. |
| **Hardcoding domain terms** | Temptation to patch a single test case with a lookup dict. | **STRICTLY FORBIDDEN**. Must be resolved via graph topology, PPMI, or universal heuristics. |
| **Modifying scoring weights arbitrarily** | `_calcular_score_hibrido` weights are tightly normalized. | Re-normalize weights so total equals `1.0 - jsd_weight`; verify with complete QA eval. |
| **Committing `.db` or `.env.local` files** | Repository hygiene. | Check `git status` before finishing any task. |

---

## 9. Onboarding Checklist for Incoming Agents

Before claiming readiness to tackle any new feature or fix:
1. [ ] Confirm you have read this `AGENTS.md` file.
2. [ ] Run `pytest tests/ -v` and confirm all tests pass.
3. [ ] Run `scripts/evaluar_qa.py` against the snapshot and record your baseline metrics.
4. [ ] State clearly the hypothesis and isolated change you intend to make (One change at a time).
5. [ ] Ensure your proposed solution adheres to the **"Antes de construir, justifica"** UX-first rule.
