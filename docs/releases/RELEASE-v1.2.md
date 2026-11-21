MemoryBioRAG 1.2.0 — Connectome link validation and cross-platform daemon compatibility

MemoryBioRAG 1.2.0 delivers hardening improvements for synaptic link integrity and cross-platform execution on Windows environments.

Highlights of 1.2.0

- Synaptic Link Validation: The `vincular` MCP tool now enforces strict pre-flight existence checks on both nodes before establishing associations. If either node has not been saved, the tool returns an informative error rather than creating hanging or orphan synapses in the connectome.
- Cross-Platform Daemon Hardening: Guarded Unix-specific `fcntl` file-locking mechanisms in `graph_maintenance_daemon.py`, preventing import crashes and ensuring clean execution across Windows and non-POSIX platforms.
- Regression Test Coverage: Added dedicated automated test suites covering node-existence validation for graph linking (`tests/test_vincular_validacion.py`).
- Full Suite Verification: All 895+ core tests pass with zero regressions and verified corpus growth invariance.

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

This release is published under the stable distribution channel: tag `v1.2` on `https://github.com/dennysjmarquez/MemoryBioRAG-Stable`.

