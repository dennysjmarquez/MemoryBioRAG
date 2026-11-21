MemoryBioRAG 1.0.0 — Zero-cloud associative memory engine, Hebbian connectome, and local MCP agent integration

MemoryBioRAG 1.0.0 is the first stable release in the Stable distribution channel of the local-first, bio-inspired persistent associative memory engine for AI agents and engineering workflows. MemoryBioRAG runs 100% locally on CPU, without hosted embedding APIs, external vector databases, or GPU requirements. It does use its own local vector machinery — PPMI+SVD and SDM — trained and stored on your machine.

Highlights of 1.0.0

- 100% Local CPU Architecture: Built on standard SQLite FTS5 and optimized linear algebra (NumPy/SciPy). No external API calls, telemetry, or cloud lock-in in the core memory retrieval path.
- Multi-Signal Associative Engine: Unifies lexical BM25 matching, a 100-dimensional PPMI+SVD co-occurrence latent space, 13 semantic dimensions, Hebbian synaptic graph activation, and 2048-bit Sparse Distributed Memory (SDM) hyperdimensional computing.
- Conformal Calibration: Percentile-based thresholds calibrated on negative controls to reduce false positives on evaluated benchmarks, instead of relying on arbitrary fixed similarity cutoffs.
- Hebbian Synaptic Connectome: Dynamic graph edges form and strengthen between memories through co-activation, modeling biological neural association and structural continuity across sessions.
- Sleep & Consolidation (DMN): Consolidation cycles move short-term working memories into permanent long-term storage, prune stale synapses, and perform episodic reflection via a local Default Mode Network. Background maintenance is opt-in and disabled by default.
- Guarded Ranking Neuron: A small ranking neuron learns only during consolidation and can only reorder results within safeguards; the hand-tuned formula remains the floor.
- Model Context Protocol (MCP) Integration: MCP stdio server exposing the core cognitive tools (`recordar`, `buscar`, `aprender`, `vincular`, `estado`) for Claude Code, OpenCode, Cursor, Cline, Windsurf, and custom agent architectures.
- User-Space Install & Symmetric Operations: `install.py` sets up local data under `~/.biorag/` and MCP client configuration, with symmetric uninstall. This release does not install a systemd `--user` service or background daemon by default.
- Scale-Aware Retrieval: Intra-query normalization reduces recall drift as the corpus grows on evaluated benchmarks, so adding same-topic memories does not collapse retrieval quality.

Requirements

- Python >= 3.11
- SQLite with FTS5 (bundled with standard Python builds)
- NumPy / SciPy

Installation & Quick Start

```bash
# Clone the stable repository
git clone https://github.com/dennysjmarquez/MemoryBioRAG-Stable.git
cd MemoryBioRAG-Stable

# Run the automated installer
python3 install.py
```

Quick Verification

```bash
# 1. Ingest a memory with key thematic anchors
$ python biorag.py guardar arch_decision "Adopted Angular 19 signals and TailwindCSS for the client portal." \
    --sustantivos-clave "frontend,angular,arquitectura"
'arch_decision' guardado en corto plazo.

# 2. Consolidate working memory into the long-term connectome
$ python biorag.py sueno
[MemoryBioRAG] Proceso de consolidación y equilibrio sináptico completado con éxito.

# 3. Query associative memory
$ python biorag.py buscar "client portal"
[MemoryBioRAG] 1 coincidencias encontradas:
--- #1: arch_decision (peso:0.98, estado:activo) ---
Adopted Angular 19 signals and TailwindCSS for the client portal.
```

Known Limitations

- Evaluated on Spanish/English corpora; ranking ties can still occur on very short queries.
- Conformal thresholds depend on the calibration set and are not a universal guarantee.
- The associative neuron is built and evaluated, but does not yet decide inside the engine.

Distribution Note

This is the first general-availability release under the stable distribution channel: tag `v1.0.0` on `https://github.com/dennysjmarquez/MemoryBioRAG-Stable`.