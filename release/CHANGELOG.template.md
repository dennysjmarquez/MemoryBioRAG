# Changelog

All notable changes to the MemoryBioRAG Stable distribution are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## {{VERSION}} (2026-11-20)

### Added
- Strict pre-flight node existence validation in the `vincular` MCP tool, preventing orphan or dangling synapses in the connectome.
- Cross-platform file locking guards for `fcntl` in `graph_maintenance_daemon.py`, preventing import errors on Windows.
- Dedicated regression test suite covering graph association validation (`tests/test_vincular_validacion.py`).

## v1.1 (2026-11-20)

### Added
- Expanded architectural overview diagram illustrating the complete cognitive pipeline (QCR Escape, Concept Hubs, 2048-bit SDM, and the Guarded Ranking Neuron).

### Changed
- Calibrated conformal prediction precision claims and multi-signal hybrid retrieval definitions to match verified benchmark baselines.
- Explicitly documented background consolidation daemons and Default Mode Network (DMN) reflection as opt-in.
- Hardened local backup management in `install.py` to prevent redundant backup file accumulation under `~/.biorag/backups/`.
- Unified branding and taxonomy to canonical `MemoryBioRAG` across all guides and templates.

## v1.0 (2026-11-20)

### Added
- Initial official stable release of MemoryBioRAG, a local-first persistent associative memory engine for AI agents.
- Multi-signal hybrid retrieval unifying SQLite FTS5 BM25, 100-dim corpus-derived PPMI+SVD latent space, and 13 topological semantic dimensions.
- Explicit Hebbian synaptic connectome linking related memories through co-activation (LTP/LTD).
- Model Context Protocol (MCP) stdio server exposing 5 core cognitive tools (`recordar`, `buscar`, `aprender`, `vincular`, `estado`).
- Automated zero-touch installer (`install.py`) with automatic client configuration and 100% install/uninstall symmetry.
- 100% local CPU execution with zero external embeddings APIs, zero telemetry, and zero GPU requirements.
