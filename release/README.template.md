# MemoryBioRAG Stable

**Persistent, local-first memory for AI agents.**

`{{VERSION}}` · Python 3.11–3.12 · Apache-2.0 · Model Context Protocol (MCP)

MemoryBioRAG (BioRAG) is a persistent memory engine that an AI agent can use through an MCP server or a command-line interface. It stores and retrieves durable context; the host agent's language model remains responsible for reasoning and generating user-facing responses. BioRAG does not bundle a generative LLM. An optional, explicitly configured Gemini-backed maintenance path is separate from core retrieval and is not required to use BioRAG.

## What makes BioRAG different

BioRAG is designed around a local SQLite database and an associative memory graph rather than requiring a hosted vector database or a pretrained embedding API for core retrieval.

- **Hybrid retrieval:** SQLite FTS5/BM25 is combined with query, concept, and relationship signals.
- **Associative memory:** weighted links connect related memories and can be strengthened by feedback.
- **Neural-inspired lifecycle:** consolidation, reinforcement, decay, and dormant memories are inspired by cognitive mechanisms. This is an engineering model, not a biological-brain simulation.
- **Local statistical representations:** the codebase also includes corpus-derived PPMI/SVD signals and sparse distributed memory. It would be inaccurate to describe BioRAG as “vector-free”; it does not require a pretrained neural embedding model for its core retrieval path.
- **Agent interoperability:** MCP exposes memory operations to compatible clients; the CLI provides a direct, inspectable fallback.

These are design choices, not a claim that BioRAG outperforms other memory systems. Compare systems on the same dataset and workload before making performance claims.

## Quick start

### Requirements

- Python 3.11 or 3.12
- SQLite built with FTS5 support
- Git if you choose to clone the source repository instead of downloading its archive

### Clone and install

```bash
git clone https://github.com/dennysjmarquez/MemoryBioRAG-Stable.git
cd MemoryBioRAG-Stable
python3 -m venv .venv
```

You can also download and extract the source ZIP from a Stable GitHub Release, then run the remaining commands from the extracted project directory.

Activate the environment and install the pinned dependencies.

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

The installer checks the environment, configures detected MCP-compatible clients, and copies the bundled BioRAG skill to supported agent skill directories. It may download NLTK WordNet and Open Multilingual Wordnet data to the user's data directory; these dictionaries are not bundled in the repository.

After installation, restart the configured agent and inspect the setup with:

```bash
python install.py --status
python biorag.py help
```

To print configuration snippets for manual setup, run `python install.py --show-config`.

## Connect an MCP client

The MCP server uses the standard input/output (`stdio`) transport when launched by an agent. The installer can configure supported clients, including OpenCode, Claude Code, Claude Desktop, VS Code, Cursor, Cline, and other clients detected by this installer. Restart the client after configuration so that it discovers the BioRAG tools. Current MCP tool names include `recordar` and `buscar` for retrieval, `aprender` for explicit durable writes, `vincular` for associations, and `estado` for status; inspect each tool's schema for its arguments.

OpenCode uses MCP for core memory operations. When the installer configures OpenCode, it detects the available plugin API (V1 or V2) and copies the matching bundled reminder plugin. The plugin injects BioRAG usage reminders on selected turns; MCP remains usable if the plugin is removed or unavailable. The V2 plugin's desktop notification is best-effort and may require the host's `notify-send` command. The current plugin also attempts to write reminder counts and operational errors to `/tmp/opencode/biorag-remember.log`; inspect that diagnostic file before sharing logs.

## Command-line interface

Run `python biorag.py help` for the complete command reference. The current CLI command names and built-in help text are in Spanish; the examples below show the exact command names. Common operations include:

| Task | Command |
|---|---|
| Search memory | `python biorag.py buscar "project decision" --todos` |
| Include dormant memories in search | `python biorag.py buscar "project decision" --deep` |
| Store a durable memory | `python biorag.py guardar release_policy "Stable artifacts require review." --sustantivos-clave "stable,release,policy"` |
| Create an association | `python biorag.py asociar release_policy versioning_policy` |
| Check memory status | `python biorag.py estado` |
| Consolidate working memory | `python biorag.py sueno` |

Use `guardar` only for information the user wants retained. `sueno` runs the consolidation lifecycle; it is not required after every search.

## Bundled agent skill

The Stable source archive includes the English `biorag-memory` skill at `skills/biorag-memory/SKILL.md`. When `install.py` runs from that source checkout, it copies the skill into supported agent skill folders. A wheel-only installation does not currently bundle the skill; use the source archive to install it. Common locations are:

- Claude Code: `~/.claude/skills/biorag-memory/SKILL.md`
- OpenCode: `~/.config/opencode/skills/biorag-memory/SKILL.md` or `~/.opencode/skills/biorag-memory/SKILL.md`
- Shared agent skills: `~/.agents/skills/biorag-memory/SKILL.md`

The skill is an instruction file, not an executable plugin. Its source remains in the cloned repository if you need to inspect or copy it manually. The installer leaves a pre-existing skill with the same name untouched; uninstall removes only an unchanged bundled copy and preserves other or locally edited skills. Development-only skills are not part of Stable.

## Troubleshooting

- **The MCP client shows no BioRAG tools:** Run `python install.py --status` and `python install.py --show-config`. Confirm that the configured command uses the intended Python environment and points to this source checkout, then restart the client. The MCP server uses stdio when launched by a client; do not configure it as an HTTP URL unless you deliberately set up the optional SSE transport.
- **SQLite reports that FTS5 is unavailable:** Check the Python-linked SQLite build with:

  ```bash
  python -c 'import sqlite3; c=sqlite3.connect(":memory:"); c.execute("CREATE VIRTUAL TABLE fts_check USING fts5(text)"); print(sqlite3.sqlite_version)'
  ```

  Use a Python distribution whose SQLite library includes FTS5 if that command fails.
- **The CLI and MCP server show different memories:** Check that both use the same `BIORAG_PATH`. Run `python biorag.py estado` from the source checkout to inspect the local database and status.
- **WordNet-based expansion is unavailable:** Confirm that NLTK data was downloaded during setup and that `BIORAG_NLTK_DATA`, if set, points to that data directory. Core local storage and FTS5 search do not require the optional Gemini maintenance feature.
- **The OpenCode reminder is not installed:** Check `~/.config/opencode/plugins/opencode-biorag-remember-plugin.ts` and rerun `python install.py` from the Stable source checkout. The installer detects V1 or V2 and preserves an existing customized plugin rather than overwriting it. MCP memory tools remain available without the reminder plugin.
- **You need an offline startup:** Set `BIORAG_UPDATE_CHECK=0` to disable the non-blocking GitHub version check. Optional token translation and Gemini maintenance also require external network access and are described in the privacy section.

## Dashboard and optional plugins

The Neuro-Visor dashboard product is not part of this Stable distribution: its web UI, backend, and Node assets are excluded. Stable omits the dashboard help entry and does not register a `dashboard` CLI command, but retains the underlying handler as dormant code for possible reactivation. The handler's required dashboard assets are not included. The development source is not deleted or rewritten, and the MCP server and CLI do not depend on the dashboard.

The OpenCode reminder plugin is included separately from MCP and is installed automatically when the installer configures OpenCode. It selects the bundled V1 or V2 implementation based on the detected plugin API. Removing the plugin does not disable MCP memory operations.

## Data, configuration, and privacy

- The default SQLite database is stored outside the source checkout at `~/.biorag/memory_biorag.db` (or the equivalent home directory on Windows).
- Set `BIORAG_PATH` to use a different database location. The installer can also place NLTK data under `~/.biorag/nltk_data`; set `BIORAG_NLTK_DATA` to override that location.
- The source archive contains no user database, memory contents, credentials, or private evaluation data.
- Core memory search and storage use the local SQLite database; no hosted LLM or vector database is required. BioRAG does not upload the database as a whole.
- The update check is enabled by default and reads public Stable version metadata from GitHub. Set `BIORAG_UPDATE_CHECK=0` to disable it; this check does not send memory contents.
- Optional token translation is disabled by default. If `deep-translator` is installed and `BIORAG_TRADUCCION_ACTIVA=1` is set, query tokens may be sent to Google Translate for translation.
- Optional Gemini-backed reflective maintenance is separate from core retrieval. If you configure `GEMINI_API_KEYS` or `GEMINI_API_KEY` and invoke the corresponding maintenance operation, the memory content used for that reflection request is sent to the external Gemini API. The continuous daemon is disabled by default; do not configure this feature if external processing is not acceptable.
- Installation may download NLTK WordNet and Open Multilingual Wordnet data. These dictionary downloads are described above; memory records are not part of those downloads.
- Protect the database as user data. Do not commit `.env` files, databases, private datasets, credentials, or evaluation outputs.

## Distribution and releases

**Recommended first channel: GitHub Releases.** GitHub describes releases as a way to package software with release notes and downloadable assets, and automatically provides source archives for the tagged revision ([release overview](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases), [release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)). The local release preparer creates a source ZIP, a Python wheel, and a release manifest containing SHA-256 digests. The source ZIP is the full installer distribution, including the agent skill and both OpenCode plugin versions; the wheel currently omits those non-Python integration assets. Attach only reviewed artifacts and release notes; nothing is uploaded by these local tools.

**Possible later channel: PyPI.** Consider this only after package metadata, wheel inclusion of the skill and OpenCode plugin, install compatibility, and the publishing workflow have been reviewed. PyPI's publishing guide describes packaging prerequisites and recommends Trusted Publishing (OIDC) where supported ([PyPI publishing guide](https://docs.pypi.org/publishing/publishing-to-pypi/)). This local preparation does not configure or publish to PyPI. GitHub Packages documents registries for formats including npm, RubyGems, Maven/Gradle, NuGet, and containers, but does not list a native Python package registry ([supported registry formats](https://docs.github.com/en/packages/learn-github-packages/introduction-to-github-packages#support-for-package-registries)).

Stable versions use canonical tags of the form `vX.X`; prereleases are not part of this channel. Local packaging tools create reviewable artifacts only. Uploading, tagging, or publishing is a separate action and requires explicit release approval. Reaching potential adopters, including companies such as Google, is a long-term goal—not evidence of contact, evaluation, adoption, endorsement, or partnership.

## Design context

Persistent-memory projects make different trade-offs. [Mem0](https://github.com/mem0ai/mem0) documents configurable LLM and embedding-model options; [Graphiti](https://github.com/getzep/graphiti) focuses on temporal context graphs and documents configurable graph-database, LLM, and embedder components; the [MCP reference servers](https://github.com/modelcontextprotocol/servers) include a graph-based memory example. [Obsidian](https://obsidian.md/help/data-storage) stores notes as Markdown files in local vaults and supports [internal links](https://obsidian.md/help/links), a human-managed note-taking model distinct from BioRAG's agent-facing memory interface. These are architectural references, not like-for-like performance baselines. BioRAG makes no superiority claim without a reproducible, public comparison.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
