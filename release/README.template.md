# MemoryBioRAG Stable

[![Release](https://img.shields.io/badge/release-{{VERSION}}-blue.svg?style=flat-square)](https://github.com/dennysjmarquez/MemoryBioRAG-Stable/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square)](https://python.org)
[![MCP](https://img.shields.io/badge/protocol-MCP%20stdio-orange?style=flat-square)](https://modelcontextprotocol.io)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey?style=flat-square)](https://github.com/dennysjmarquez/MemoryBioRAG-Stable)

**Local-first, bio-inspired associative memory engine for AI agents.**

MemoryBioRAG is a persistent memory engine that provides AI agents with durable episodic context, evolving associative knowledge graphs, and cross-session continuity—without hosted vector databases, without cloud embeddings APIs, and running 100% locally on CPU.

Rather than treating memory as flat text buffers or rigid vector lookups, MemoryBioRAG implements an engineering model inspired by neocortical memory dynamics: memories form synaptic associations through co-activation, consolidate during background rest cycles, and apply conformal prediction calibration to reduce false positives on evaluated benchmarks.

> **Language Note:** CLI commands (`buscar`, `guardar`, `asociar`, `estado`, `sueno`) and MCP tool names (`recordar`, `aprender`, `vincular`) use Spanish terminology reflecting the project's foundational cognitive taxonomy.

Interact with MemoryBioRAG through:
* **Model Context Protocol (MCP):** Connect any MCP-compatible agent (Claude Code, OpenCode, Cursor, Cline, Windsurf, or custom agent harnesses).
* **Local CLI (`biorag.py`):** Inspect, query, link, and awaken memories directly from your terminal.
* **Autonomous Daemons (opt-in):** Background consolidation and Default Mode Network (DMN) reflection.

```mermaid
flowchart LR
    Agent["🤖 AI Agent (Claude / OpenCode / Cursor)"] -->|MCP stdio| Engine["🧠 MemoryBioRAG Engine"]
    CLI["💻 Local CLI (biorag.py)"] --> Engine
    Engine --> FTS["⚡ SQLite FTS5 (Exact / BM25)"]
    Engine --> QCR["🔁 QCR Escape (zero-hit fallback & OR relaxation)"]
    Engine --> SYM["🔤 WordNet + Concept Hubs (symbolic expansion)"]
    Engine --> HEB["🕸️ Synaptic Connectome (Hebbian Graph)"]
    Engine --> PPMI["🧬 100-dim PPMI+SVD & 13 Semantic Axes"]
    Engine --> SDM["💠 SDM 2048-bit (HDC)"]
    Engine --> NEU["🎛️ Guarded Ranking Neuron (learns at consolidation)"]
    Engine --> CONF["🎯 Conformal Calibration"]
    Engine --> SLEEP["🌙 Sleep & Consolidation (opt-in)"]
```

## Quick Demonstration

```bash
# 1. Ingest a memory with thematic keywords (--sustantivos-clave anchors the conceptual core)
$ python biorag.py guardar arch_decision "Adopted Angular 19 signals and TailwindCSS for the client portal." \
    --sustantivos-clave "frontend,angular,arquitectura"
'arch_decision' guardado en corto plazo.

# 2. Consolidate working memory into the long-term connectome
$ python biorag.py sueno
[MemoryBioRAG] Proceso de consolidación y equilibrio sináptico completado con éxito.

# 3. Search memory across active nodes
$ python biorag.py buscar "client portal"
[MemoryBioRAG] 1 coincidencias encontradas:
--- #1: arch_decision (peso:0.98, estado:activo) ---
Adopted Angular 19 signals and TailwindCSS for the client portal.
```

When connected to an AI agent via MCP, the agent queries memory programmatically via `recordar` and receives epistemic certainty classifications (`evidencia_directa`, `relacionado_confianza_media`, `sin_evidencia_directa`).

---

## Feature Overview

| Capability | Description |
|---|---|
| **Associative Connectome** | Memories link to each other via Hebbian synaptic weights that strengthen through activation (LTP) and decay over time (LTD). |
| **Epistemic Conformal Certainty** | Split conformal prediction dynamically suppresses false positives—distinguishing direct evidence from lower-confidence associations on evaluated benchmarks. |
| **Local Multi-Signal Retrieval** | Multi-channel retrieval combining SQLite FTS5 BM25, 100-dim corpus-derived PPMI+SVD latent space, and 13 topological semantic dimensions. Zero GPUs and zero external API calls in the retrieval path. |
| **Autonomous Sleep Cycle & DMN (opt-in)** | Background daemons consolidate working memory into long-term structures, prune spurious connections, and detect cognitive gaps during idle periods. |
| **Fail-Fast Concept Hubs** | Multi-angle semantic bridge expansion resolving the "lexical abyss" problem where queries share zero literal tokens with stored knowledge. |
| **Zero-Touch Local Storage** | Pure local SQLite database at `~/.biorag/memory_biorag.db` (multiplatform). Zero telemetry, no external accounts, zero cloud lock-in. |
| **Universal MCP Interoperability** | Standard input/output (`stdio`) Model Context Protocol server compatible with Claude Code, OpenCode, Cursor, Cline, and any modern agent framework. |

---

## How MemoryBioRAG Compares to Traditional Vector RAG

| Dimension | Traditional Vector RAG | MemoryBioRAG |
|---|---|---|
| **Hardware Requirements** | GPU / Cloud Inference API | 100% Local CPU (ARM64 / x86_64) |
| **Embedding Cost** | Per-token API fees or massive model weights | Zero API calls in core retrieval path; internal corpus-derived PPMI+SVD |
| **Retrieval Mechanism** | Approximate Nearest Neighbors (ANN) cosine distance | Seven-signal hybrid retrieval: FTS5 BM25 + SVD + 13 Semantic Axes + Hebbian Graph |
| **Memory Relationships** | Unlinked points in embedding space | Explicit Hebbian synaptic connectome (LTP/LTD) |
| **Certainty Calibration** | Arbitrary similarity thresholds (e.g. `score > 0.75`) | Calibrated conformal prediction thresholds |
| **Memory Lifecycle** | Static records until manually reindexed | Sleep consolidation and associative pruning (opt-in DMN) |

---

## Benchmarked Performance (Internal Evaluation Suite)

Evaluated on the frozen 921-case BioRAG evaluation suite (875 gold retrieval queries, 40 negative controls for false-positive validation, and 6 ambiguous edge cases analyzed separately outside the global retrieval denominator):

| Metric | Result | Meaning |
|---|---|---|
| **Recall@5 (Global)** | **100.0% (875/875)** | 100% gold-memory retrieval rate within the agent's top-5 working window. |
| **Recall@1 (Top-1)** | **91.8% – 93.0%** | Over 9 out of 10 queries surface the exact target memory in first place. |
| **MRR (Mean Reciprocal Rank)** | **0.950 – 0.956** | High confidence density at the top of the ranked list. |
| **False Positive Rate** | **0.0% (0/40)** | Conformal prediction threshold successfully suppresses negative controls. |

*Note: Benchmarks measured on frozen reference snapshots under deterministic conditions. To inspect or run the complete evaluation suite, visit the [research repository](https://github.com/dennysjmarquez/MemoryBioRAG).*

---

## Quick start

### Requirements

- Python 3.11 or 3.12 (standard builds with SQLite FTS5 support)
- Git (or download source archive from GitHub Releases)

### Clone and install

```bash
git clone https://github.com/dennysjmarquez/MemoryBioRAG-Stable.git
cd MemoryBioRAG-Stable
python3 -m venv .venv
```

Activate the virtual environment and run the automated installer:

**Linux or macOS**

```bash
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python install.py
```

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python install.py
```

The installer verifies environment prerequisites, configures detected MCP clients (OpenCode, Claude Desktop, Cursor, Claude Code, Cline, etc.), and sets up canonical storage at `~/.biorag/`.

After installation, inspect your configuration with:

```bash
python install.py --status
python biorag.py help
```

To display configuration snippets for manual client setup, run `python install.py --show-config`.

---

## Connect an MCP client

MemoryBioRAG communicates with agents via the standard input/output (`stdio`) transport. The automated installer detects and patches client configuration files automatically.

### Supported Clients

* **Claude Code:** Configured in `~/.claude.json`
* **Claude Desktop:** Configured in `claude_desktop_config.json`
* **OpenCode:** Native MCP configuration + bundled reminder plugin
* **Cursor / VS Code:** Configured in `cursor.mcp.json` or `settings.json`
* **Cline / Windsurf / Custom Agents:** Standard `stdio` server entry point: `python path/to/mcp_server.py`

### Exposed MCP Tools

| Tool | Purpose |
|---|---|
| `recordar` | High-level recall with epistemic certainty classification and paraphrase expansion. |
| `buscar` | Multi-signal semantic search across active and dormant memories. |
| `aprender` | Durable memory ingestion with pre-flight search verification. |
| `vincular` | Explicit Hebbian synaptic association between two conceptual nodes. |
| `estado` | Health status, node count, and synaptic density diagnostics. |

---

## Command-line interface

MemoryBioRAG includes a full-featured CLI (`biorag.py`) for direct inspection and management from your terminal.

```bash
# Search memory across all active nodes
python biorag.py buscar "project decision" --todos

# Search including dormant memories (deep search)
python biorag.py buscar "architecture refactoring" --deep

# Store a durable memory with conceptual keywords (--sustantivos-clave defines thematic anchor)
python biorag.py guardar release_policy "Stable releases require verified test gates." --sustantivos-clave "stable,release,policy"

# Create a synaptic link between two concepts
python biorag.py asociar release_policy versioning_policy --tipo asociativa

# Inspect cortex health and statistics
python biorag.py estado

# Trigger a background consolidation cycle
python biorag.py sueno
```

Run `python biorag.py help` for the complete command reference.

---

## Bundled agent skill

The distribution bundles the `biorag-memory` skill at `skills/biorag-memory/SKILL.md`. The installer automatically deploys it to supported agent skill directories:
* `~/.claude/skills/biorag-memory/SKILL.md`
* `~/.config/opencode/skills/biorag-memory/SKILL.md`
* `~/.agents/skills/biorag-memory/SKILL.md`

---

## Data, configuration, and privacy

- **Default Storage:** SQLite database stored outside the repository at `~/.biorag/memory_biorag.db` (`%USERPROFILE%\.biorag\` on Windows).
- **Custom Location:** Set `BIORAG_PATH` to override the database path.
- **Privacy:** Core retrieval and storage are 100% local. MemoryBioRAG does not upload your database, memory contents, or telemetry.
- **Update Checker:** Checks public GitHub release tags every 24 hours (non-blocking). Disable anytime with `BIORAG_UPDATE_CHECK=0`.
- **Optional External Maintenance:** Background DMN reflection can optionally use Gemini API keys if explicitly configured; core search never requires external APIs.

---

## Repository Structure & Channels

* **Production / Distribution (`MemoryBioRAG-Stable`):** Official stable release channel. Contains clean, production-ready code, automated installer, and packaging metadata.
* **Research / Development (`MemoryBioRAG`):** Active research laboratory, historical benchmarks (921 QA suite), experimental scripts, and architectural exploration.

---

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
