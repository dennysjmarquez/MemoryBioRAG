MemoryBioRAG v1.0 — Initial official release of the persistent associative memory engine

BioRAG v1.0 is the first official release of the bio-inspired cognitive memory engine for AI agents.
It operates 100% locally on CPU using SQLite FTS5, Hebbian synaptic graphs, 2048-bit 
Sparse Distributed Memory (SDM), and conformal prediction thresholds. No GPUs or external 
APIs are required in the core retrieval path.

Highlights:
- Pure local retrieval: SQLite FTS5 BM25 combined with 100-dim PPMI+SVD and 13 semantic dimensions.
- Associative connectome: Hebbian synaptic graph linking related memories through experience.
- Epistemic certainty: Dynamic conformal calibration guarantees false-positive boundaries.
- Autonomous maintenance: Built-in background daemons for consolidation and sleep reflection.
- Universal MCP & CLI: Out-of-the-box support for OpenCode, Claude Code, and MCP-compatible agents.
- 100% clean production source with zero external runtime dependencies beyond core requirements.

