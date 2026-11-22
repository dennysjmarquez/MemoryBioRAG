# CLI help audit — baseline and English-language pass

## Scope and status

The requested user-facing language is **English**, overriding the Spanish wording
and localization criteria in the supplied proposal. Existing command names,
flags, mode identifiers and stored data are not renamed. English is already the
native argparse heading/help language; adding a Spanish formatter would contradict
this requirement. No localization hacks or operational changes were introduced.

This pass completes the baseline and an English-language/purpose/safety pass.
It does **not** claim to finish every item of the proposed enterprise-help audit.

## Environment and method

- Fresh venv: `/tmp/biorag-help-validation`; requirements.txt plus scipy installed.
  Exact installed versions are recorded in environment.txt.
- Full tests ran against isolated source/snapshot copies, not the live database.
- Both full-suite runs used BIORAG_TEMPORAL_PROTOTYPE=0 for compatibility with
  legacy callers, NLTK auto-download off, daemon/update checks off, fixed hash seed
  and one BLAS thread. This does not certify the entire default-on MCP contract.
- Source before: ebe2f10. Captures: before/ and english/. Each has the root,
  16 primary commands and the three correcciones subcommands, with return codes.
  The proposal's root walker alone does not enumerate this grouped root help;
  the 16 primary names were taken from the root's GROUPS catalogue and captured
  explicitly. No command or failed help response was silently omitted.
- The new venv ran real CLI operations in a fresh synthetic database. Raw stdout,
  stderr and return codes are in synthetic_quickstart_before.json. These are not
  fabricated expected outputs or proof of a novice user study.

## Measured results

| Criterion | Before | English pass |
|---|---:|---:|
| Captured help entry points | 20 | 20 |
| Help exit code 0 | 20/20 | 20/20 |
| Purpose explanation | 19/20 | 20/20 |
| Examples section | 20/20 | 20/20 |
| Help entries containing internal agent names / OEC | 1 | 0 |
| Help entries with unverified 60/25/15 scoring formula | 1 | 0 |
| Repeated generic existing-node warning | 19 | 4 |
| Root glossary and BIORAG_PATH explanation | absent | present |
| update/recovery usage includes command name | no | yes |
| Private python -m core updater/recovery routes in help | present | absent |
| Full test suite passed | 999 | 999 |
| Full test suite skipped | 18 | 18 |
| Passed subtests | 82 | 82 |

Before: 168.97 seconds. Final English pass: 165.52 seconds. Timings are observations,
not a performance improvement claim. No tests were added or removed in this pass.

The first English full-suite attempt had **998 passed, 1 failed, 18 skipped,
82 subtests passed**, 168.77 seconds. A legacy help test required literal Spanish
pedagogical wording. Its presentation assertion was translated to the English
explanation of topic keywords, and that explanation was included explicitly.
The complete suite was then rerun successfully. The failed run log is preserved,
not replaced by the successful result.

## Source and execution findings

- guardar calls percibir_corto_plazo. The synthetic new concept was not returned
  by CLI buscar (exit 1) until sueno ran; after consolidation buscar returned it
  (exit 0). The glossary describes this CLI route, not every possible engine API.
- listar/corteza read largo_plazo. sustantivos and agregar_sustantivos also have
  working-memory fallbacks; their English descriptions explicitly say so.
- buscar_por_frase can record access/log/learning state and wakes returned dormant
  nodes for deep search. Help does not portray buscar as read-only or promise
  a fixed numerical ranking formula.
- leer_mensajes calls marcar_como_leido for displayed unread messages; help states
  that it changes read status.
- core.paths.resolve_db_path honors explicit path, BIORAG_PATH and canonical/legacy
  fallbacks. Memory CLI handlers share the resolved DB. update --db overrides that
  selection; recovery instead derives its source from the receipt/backup metadata.
  A database copy does not isolate dashboard dependency installations or Git/pip.
- dashboard can run uv sync or pip, npm ci/install, launch ports 8001/3000 and open
  a browser. Help warns about this; the example only requests dashboard --help.
  No dependency-install confirmation or configurable ports were added.
- The root explains MCP, daemon, clean checkout and external database. All operation
  handlers in biorag.py have identical ASTs before and after the module-docstring
  translation. Update/recovery changes are limited to argparse presentation.

## Important routing finding — decision required, not changed

core/memory/comms.py fixes supported recipients to athena, artemis, hermes and todos.
An unrecognized destination is converted to todos; an unsupported read filter is
ignored. A real synthetic `comunicar agent_b ...` invocation broadcast the message
instead of delivering privately. Help therefore does NOT claim arbitrary private
agent destinations; examples use explicit todos broadcasts and generic sender/
reader IDs through AGENT_NAME. No routing behavior was changed.

The scan also found internal names in historical README text, MCP communication
examples and functional shared query text. They were not globally replaced without
checking their callers/behavior. Zero names is certified for the **20 CLI help
outputs only**, not the entire README/MCP surface. In particular, removing the
legacy destination restriction would require a separate approved behavior change.

## Not verified / remaining work

- GNU/Linux `date -d '2026-01-01' +%s` returned 1767225600 in this environment.
  The macOS command failed here because GNU date does not support -j. Execution
  on macOS is **not verified**; no macOS conversion recipe was asserted as tested.
- Uniform section order (Usage, Summary, Why use it?, Before you start, Options,
  Examples, Expected output, See also) is **not completed**. Existing memory help
  still lists options before its purpose note. See-also sections are pending.
- Actual-output samples for every command are **not completed**. The synthetic
  transcript is real but has not been converted into examples in all help pages.
  Operational output remains in its existing language; translating it would exceed
  this help-only pass. No invented success output was inserted.
- The root and handler-mutating commands document BIORAG_PATH. Read handlers can
  still prepare schema during database initialization, as the root warns. Exhaustive
  per-command initialization side-effect verification, especially dashboard backend
  DB routing, is **not verified**. Recovery does not use BIORAG_PATH to override the
  receipt's database; do not claim that all 20 entries have identical path semantics.
- A fresh venv and synthetic save/search/consolidate/message flow were exercised,
  but an independent novice following the full README using only --help is
  **not verified**. Wheel installation, macOS and Windows usability are not certified.
- Uniform --db, ISO dates, dashboard install confirmation/ports and dashboard HTML
  export remain outside this change. No flags or command behavior were added.

No live database was opened, no release was published and no branch was switched.
