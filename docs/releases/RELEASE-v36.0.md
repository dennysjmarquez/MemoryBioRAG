MemoryBioRAG v36.0 — Persistent associative memory engine on SQLite and CPU

BioRAG v36.0 delivers a bio-inspired cognitive memory engine for autonomous AI agents.
It operates 100% locally on CPU using SQLite FTS5, Hebbian synaptic graphs, 2048-bit 
Sparse Distributed Memory (SDM), and conformal prediction thresholds. No GPUs or external 
APIs are required in the retrieval path.

What changed:
- Search Engine: Gated BM25 ranking when scale helpers are deactivated, preserving zero-corpus invariance.
- Scoring & IDF: Restored FTS5 fallback when candidate texts are absent.
- Persistence: Hardened baseline rowid sanitation during database purges.
- Packaging: Clean zero-touch setup across OpenCode, Claude Code, and MCP-compatible agents.
- Verification: 100% pass rate across core biological memory test suites.

