MemoryBioRAG 1.1.0 — Architecture diagram expansion, calibrated precision claims, and installer safety

MemoryBioRAG 1.1.0 improves packaging documentation, deepens architectural transparency in the primary documentation, and hardens local installer safety across client environments.

Highlights of 1.1.0

- Architectural Documentation Expansion: The system architecture diagram now illustrates the full end-to-end cognitive retrieval pipeline, explicitly highlighting the QCR Escape zero-hit fallback, WordNet + Concept Hubs symbolic expansion, 2048-bit SDM hyperdimensional computing, and the guarded ranking neuron.
- Refined Epistemic Claims: Benchmarked precision statements, conformal calibration descriptions, and multi-signal retrieval terms have been calibrated to reflect exact empirical benchmark measurements with zero overpromising.
- Explicit Opt-In Maintenance: Background consolidation daemons and Default Mode Network (DMN) reflection are now explicitly labeled as opt-in throughout the documentation, schema overviews, and CLI reference.
- Installer Safety & Backup Deduplication: Hardened local configuration backup routines in `install.py`, preventing redundant backup file proliferation under `~/.biorag/backups/`.
- Unified Documentation Taxonomy: Normalized all references to use the official canonical name `MemoryBioRAG` across all guides, diagrams, and client integration instructions.
- Multi-Signal Hybrid Retrieval Clarification: Cleanly documented the multi-channel scoring balance across SQLite FTS5 BM25, 100-dimensional PPMI+SVD latent space, 13 semantic topological dimensions, and Hebbian synaptic graph activation.
- Synaptic Link Pre-Flight Validation: Hardened the `vincular` MCP tool to enforce existing node verification before creating associations, preventing dangling or orphan synapses in the connectome.
- Cross-Platform Daemon Hardening: Guarded `fcntl` file-locking mechanisms in `graph_maintenance_daemon.py` to prevent import crashes and ensure clean execution on Windows platforms.

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

Distribution Note

This release is published under the stable distribution channel: tag `v1.1` on `https://github.com/dennysjmarquez/MemoryBioRAG-Stable`.

