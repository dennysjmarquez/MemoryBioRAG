# BioRAG — Agent Instructions

## Architecture Overview

**Single-file core**: `core/memory_store.py` (267KB) — class `SQLiteMemoryBioRAG` is the entire system. All MCP tools, search, consolidation, daemon logic live here. No package structure — flat modules in `core/`.

**Key modules**:
- `core/memory_store.py` — SQLite + FTS5 + 13-axis semantic dimensions + PPMI+SVD hybrid search + SDM/HDC + daemon state
- `core/sinapsis.py` — synaptic graph, propagation, triadic closure
- `core/ppmi_vectorizer.py` / `core/ppmi_hybrid_search.py` — PPMI+SVD factorization (100 dims), retrofitting, IDF-synonym scoring
- `core/sdm.py` — Sparse Distributed Memory (2048-bit), HDC binding
- `core/dmn_engine.py` / `core/dmn_reflexion.py` — Default Mode Network autonomous daemon (La Hormiguita)

**Daemons**: `graph_maintenance_daemon.py` (consolidation cycle), `sleep_cycle.py` (DMN reflection), `mcp_server.py` (MCP protocol)

**Installer**: `install.py` — cross-platform MCP setup (installs BioRAG, connects to OpenCode/Claude/VS Code/Cursor/Cline)

---

## Run Commands

| Task | Command |
|------|---------|
| **Full QA eval (921 cases, ~17 min)** | `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py` |
| **QA eval with custom cases** | `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py scripts/casos_qa.jsonl` |
| **Unit tests** | `python3 -m pytest tests/ -v` |
| **MCP server** | `python3 mcp_server.py` (stdio) |
| **Daemon (consolidation)** | `python3 graph_maintenance_daemon.py` |
| **DMN reflection (La Hormiguita)** | `python3 sleep_cycle.py` |
| **Install/verify** | `python3 install.py` |
| **Run QA suite wrapper** | `./scripts/run_qa_suite.sh` (loads `.env.local`, runs eval) |
| **Recalibrate FP guarantee (manual)** | MCP tool `calibrar` (alpha, n_negativos, forzar) — or `cerebro.calibrar_y_persistir()` |

**Critical**: Always use `BIORAG_PATH` pointing to a **snapshot** for reproducible eval. The live DB (`MemoryBioRAG_Data/memory_biorag.db`) is mutated by eval (temp copy) and daemons.

---

## Calibration (v28.1) — FP guarantee as a PERCENTILE

**Principle (Dennys, 2026-08-16)**: the corpus is not static — it grows or shrinks. A threshold calibrated against N nodes becomes invalid when the corpus changes size. So the FP threshold is a **percentile** (conformal prediction split, Vovk 2005), not an absolute number — like `width: 50%` in CSS, invariant to container size.

- `k = ceil((n+1)(1−alpha))/n` → the threshold is the score at that quantile of the negative queries' scores.
- **Guarantee is distribution-free**: assumes only that the calibration sample comes from the same population as production queries.
- When the corpus grows (more nodes → higher noise floor), the absolute value auto-recalculates; the percentile stays fixed.
- **Persistence**: table `calibracion_estado` (id=1) stores threshold, alpha, n_nodos_corpus, Platt a/b, date.
- **Drift detection**: `calibrar_y_persistir()` recalibrates automatically when corpus size changes >20% (second call = 0.0s reuse; first = ~35s / 40 searches).
- **MCP output**: each search result now carries `confianza_calibrada` + `nivel_certeza` (`evidencia_directa` / `relacionado_confianza_media` / `sin_evidencia_directa`) — the 3 Neocortex levels, without touching ranking (baseline preserved).

**Measured on live copy (918 nodes)**: fixed threshold 0.25 → FP 100% (32/32); conformal percentile → FP 6% (2/32).

Key methods in `core/memory_store.py`: `_contar_nodos_corpus`, `_cargar_calibracion_persistida`, `_persistir_calibracion`, `calibrar_y_persistir`, `nivel_certeza`, `confianza_calibrada`. Core math in `core/calibracion.py` (`UmbralConforme`, `CalibradorPlatt`). Tests: `tests/test_calibracion_conforme.py`.

---

## Evaluation & Snapshots

**Frozen snapshot for regression testing**: `snapshots/qa_escape_qcr_20260811.db` (49MB, 803 nodes, 921 QA cases)

**Baseline cases**: `scripts/casos_qa_baseline_v1.jsonl` (921 cases)

**Reference runs** (keep for comparison):
- `scripts/run_a_baseline_escape_binario.txt` — escape binario (pre-v26.4)
- `scripts/run_b_umbral_060.txt` — umbral capa 0.60 (v26.4 baseline)
- `scripts/run_c_gate_vacio.txt` — F1 gate_vacio experiment (regressed, kept as evidence)

**Current baseline (state B)**: `run_b_umbral_060.txt` — R@5 96.03%, R@1 88.76%, MRR 0.916, FP 25%

**To verify a change**: run eval against snapshot, compare R@5/R@1/MRR/FP to `run_b_umbral_060.txt`. Numbers must match or improve.

---

## Key Environment Variables (`.env.local`)

Copy `.env.example` → `.env.local` and uncomment. Key vars:

| Variable | Purpose | Default |
|----------|---------|---------|
| `BIORAG_PATH` | DB path for eval/daemons | `MemoryBioRAG_Data/memory_biorag.db` |
| `BIORAG_QCR_ESCAPE_CAPA_MIN` | QCR gate layer escape threshold | `0.60` |
| `BIORAG_QCR_ACTIVO` | Enable/disable QCR gate | `1` |
| `BIORAG_PPMI_WEIGHT` | PPMI hybrid search weight | `0.15` |
| `BIORAG_RERANKING_JACCARD_ENABLED` | Jaccard re-ranking (Fase C) | `1` |
| `BIORAG_LIMITE_MCP` | MCP search default limit | `10` |
| `BIORAG_RAFTAGA_ACTIVA` | Enable reminiscence burst | `true` |
| `GEMINI_API_KEYS` | Comma-separated keys for DMN daemon | — |
| `BIORAG_DAEMON_LOG_ENABLED` | Enable daemon logging | `0` |

**.env.local is gitignored**. Never commit secrets. `.env.example` documents all options.

---

## Snapshot Discipline

- **Never eval against live DB directly** — `evaluar_qa.py` copies to temp but daemons mutate live DB
- **Always use `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db`** for regression testing
- **Snapshot creation**: `python3 scripts/generar_snapshot.py` (creates timestamped .db in `snapshots/`)
- **Never commit .db files** — `.gitignore` covers `MemoryBioRAG_Data/**/*.db` and `snapshots/`
- **Live-DB copies**: `python3 -c "import sqlite3; src=sqlite3.connect('MemoryBioRAG_Data/memory_biorag.db'); dst=sqlite3.connect('/tmp/opencode/live_copy.db'); src.backup(dst); dst.close(); src.close()"` — consistent snapshot even with daemons running.

## Dual Verification (MANDATORY since 2026-08-14)

**Verifying a fix against the frozen snapshot is NOT sufficient** — the live DB has a different node population (906 total / 481 active vs snapshot 866/851). Proof: fix `d6678b3` "rescued" case 0757 in the snapshot (rank 5) but **still fails in production** (rank 9, tie at 0.7000). The MCP runs against the live DB, so a fix that only works on the snapshot fixes nothing for the real user.

Every fix must be verified **BOTH** ways:
1. **Snapshot** (`snapshots/qa_escape_qcr_20260811.db`) — reproducible regression comparison against `run_b_umbral_060.txt`.
2. **Live-DB copy** (via `sqlite backup()` above) — to confirm the fix actually rescues the case in production.

If a fix passes the snapshot but fails on the live copy, report it as **NOT resolved in production** — never claim "rescatado" without the production re-check.

---

## QA Eval Details

`scripts/evaluar_qa.py`:
- Loads cases from `scripts/casos_qa_baseline_v1.jsonl` (or arg)
- Copies source DB → temp → runs eval → writes `scripts/casos_fallidos.jsonl`
- FP threshold: score ≥ 0.25 on negative-category queries
- Categories: `literal`, `sinonimo`, `por_tema`, `pregunta_natural`, `typo`, `variante_gramatical`, `cruce_idioma`, `dormido`, `negativo`
- Output: table with R@5, R@1, MRR, errors/FPs per category + global summary

**Gates for "PASA"**: `por_tema` R@5 ≥ 10/21, `sinonimo` R@5 ≥ 6/14, `sinonimia limpia` ≥ 1

---

## MCP Tools (via `mcp_server.py`)

Primary tools agents use:
- `biorag_recordar` (née `buscar`) — semantic search with dimensions, paraphrase, burst
- `biorag_aprender` (née `guardar`) — store memory with dimensions + synonyms
- `biorag_vincular` — connect two nodes
- `biorag_consolidar` — commit short-term → long-term (sleep cycle)
- `biorag_oraculo_inicio` / `biorag_oraculo_preguntar` — NotebookLM oracle
- `biorag_contexto_inicio` / `biorag_contexto_fin` — session tracking for auto-learn

**Always**: `asociados=true`, `parafrasis` (5 levels), `dias=7` for recent, `forzar_rafaga` with 15 words if primary search fails.

---

## Common Pitfalls

| Pitfall | Avoid |
|---------|-------|
| Editing `memory_store.py` without running eval | Always run eval against snapshot after core changes |
| Using live DB for eval | Use `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db` |
| Forgetting `parafrasis` in search | Loses ~60% recall — always provide 5-level paraphrases |
| Committing .db files | `.gitignore` covers them; don't force |
| Changing gate logic without evidence | Reverting F1 showed: evidence present > future projection |
| Hardcoding FP threshold 0.25 | Formalize as constant if touched (see `evaluar_qa.py:107`) |

---

## Key Files Reference

| File | Role |
|------|------|
| `core/memory_store.py` | Main class `SQLiteMemoryBioRAG` — all search, storage, daemon logic |
| `scripts/evaluar_qa.py` | QA evaluation runner (main verification) |
| `scripts/casos_qa_baseline_v1.jsonl` | 921 frozen test cases |
| `snapshots/qa_escape_qcr_20260811.db` | Frozen snapshot for reproducible eval |
| `scripts/run_qa_suite.sh` | Wrapper (loads `.env.local`, runs eval) |
| `.env.local` | Local overrides (gitignored) |
| `requirements.txt` | `numpy`, `pytest`, `fastapi`, `uvicorn` |

---

## Version / Release

- `VERSION` file: `v29.1`
- `CHANGELOG.md` — detailed history with metrics
- Version bump: update `VERSION`, `CHANGELOG.md`, tag commit

---

## Quick Verification Checklist

Before claiming "done" on any core change:

1. `python3 -m pytest tests/ -v` — unit tests pass
2. `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py` — numbers match `run_b_umbral_060.txt` (R@5 96.03%, R@1 88.76%, MRR 0.916, FP 25%)
3. **Live-DB re-check (Dual Verification)**: copy live DB via `sqlite backup()` and re-verify the specific rescued cases against that copy — a snapshot rescue is NOT a production rescue (proof: 0757, fix `d6678b3`)
4. No new .db files committed (check `git status`)
5. `.env.local` not committed (check `git status`)
