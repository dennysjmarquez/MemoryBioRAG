# Completed English CLI help audit

> Subsequent formatting/quick-start polish and fresh validation:
> [final polish report](polished/REPORT.md).

This report supersedes the remaining-work list in REPORT.md for CLI presentation.
REPORT.md and its captures/logs remain the historical record of the first pass.

## Delivered

- Root, 16 primary commands and three correction subcommands: **20 help pages**.
- Ordered Usage, Summary, What is it for?, Before you start when applicable,
  Options, Examples, Expected output and See also sections. Argparse retains its
  native lowercase usage/options labels. Its real parser supplies all option and
  subcommand definitions; the new HelpParser changes only help composition.
- Root descriptions for every command; Key concepts glossary for working memory,
  permanent cortex, consolidation, topic keywords and dormant nodes. Relevant
  per-command domain glosses use code formatting and the same English definitions.
- Crosslinks between save/search/consolidate/list and other related commands.
- English example content, English path/digest placeholders, unchanged public
  commands/flags and existing illustrative keys.
- Explicit list of allowed public identifiers/example keys; release manifest
  Spanish-marker lint reused. All 20 completed pages have zero marker hits after
  allowlisting. Manual capture review also found no Spanish prose. This is not a
  claim of exhaustive automatic natural-language detection.
- Safety notes for mutators, search access/log/learning writes, deep-search wakeup,
  message read marking, database-copy selection and update/recovery limitations.
  Recovery correctly says BIORAG_PATH does not override the receipt's source.
- English expected-output descriptions derived from real synthetic operations,
  without inserting Spanish runtime prose into English help. Full **verbatim**
  outputs are retained separately, not replaced with invented English transcripts.
- README entry note, future help-maintenance contract in AGENTS.md, and a separate
  MCP/runtime language inventory and proposal. Runtime/MCP translations and English
  aliases were **not** implemented.

## Real execution evidence

[completion_runtime.json](completion_runtime.json) records 19 invocations on a
fresh temporary database using the previously created fresh validation venv.
The first CLI call initialized that database; no live memory was accessed.

| Operation | Observed result |
|---|---|
| Save earlier and replacement facts | Both exit 0; working-memory confirmations |
| Search before consolidation | Exit 1; no match |
| Consolidate | Exit 0; two nodes reindexed |
| Search after consolidation | Exit 0; replacement content and earlier history returned |
| List / cortex / status | Exit 0; two active nodes, zero working-memory items |
| Familiarity / inspect keywords | Exit 0; concept recognized, service/port keywords |
| Assign keywords / associate | Exit 0; keyword update and association confirmations |
| Broadcast / read unread | Exit 0; agent_a → todos message shown |
| Register correction | Exit 0; status pending_confirmation, confirmed false |
| Review correction | Exit 0; digest and evidence returned |
| Confirm with actual returned digest | Exit 0; status approved |
| Recovery plan on synthetic backup receipt | Exit 0; automatic_restore_allowed false |
| Stage recovery on that fixture | Exit 0; separate snapshots, live_database_unchanged true |

These are real shortened observations, not verbatim English translations. For
example, an **abbreviated verbatim fragment** from search/list output is:

```text
The test service uses port 8443
```

An **abbreviated verbatim fragment** from registration JSON is:

```json
{
  "status": "pending_confirmation",
  "id": "cambio-puerto-001",
  "confirmed": false,
  "receipt": null
}
```

Full raw output, including existing Spanish runtime messages, variable timing,
scores, digest, timestamps and temporary paths, is in the JSON artifact. Sandbox
runtime timestamps are preserved as observed, not asserted as a verified wall clock.

### Quickstart sticking points found

- A newly saved fact is not returned by the default CLI search until consolidation.
  The help now connects guardar → sueno → buscar explicitly.
- Private message IDs are not arbitrary: an unknown recipient broadcasts instead.
  Examples use explicit todos broadcasts and AGENT_NAME; routing was not changed.
- Help is English while many runtime messages and MCP descriptions remain Spanish.
  This is stated plainly; translating those is a separate approval-gated phase.
- Corrections require existing nodes, structured fields, Unix seconds, the real
  review digest and a stable confirmation request ID. The synthetic flow exercised
  the published examples with explicit database/node substitutions.
- The existing example test substituted Spanish path/digest placeholders. After
  changing those placeholders to English, that fixture mapping also needed updating.
  The initial focused run caught this (11 passed / 1 failed); the mapping was fixed,
  then all 12 focused tests passed. No test count was reduced.

## Reproduction and acceptance

```bash
python scripts/audit_cli_help.py
python -m pytest tests/test_cli_help.py tests/test_corrections_cli.py -q
```

The audit captures help with `python -S` to exclude optional site packages. Existing
guarded tests exercise both entry points and aliases while rejecting database,
network and engine imports during help. They now also enforce section order and
release-marker checks, including a negative Spanish fixture that must be rejected.

| Criterion | Original audit | Completed |
|---|---:|---:|
| Help exit 0 | 20/20 | 20/20 |
| Purpose section | 19/20 | 20/20 |
| Examples | 20/20 | 20/20 |
| Ordered standard sections | Not originally measured | 20/20 |
| Expected-output / See-also sections | Absent | 20/20 |
| Internal agent names in CLI help | 1 page | 0 pages |
| Unverified numeric ranking formula | 1 page | 0 pages |
| Spanish-marker hits after explicit allowlist | Not originally measured | 0 |

Fresh full-suite results on isolated source/snapshot copies:

| Full regression | Passed | Skipped | Passed subtests | Time |
|---|---:|---:|---:|---:|
| Before completion changes | 999 | 18 | 82 | 171.94 s |
| Final completed sources | 999 | 18 | 82 | 176.75 s |

Both exited 0. Exact logs: suite_completion_before.log and
suite_completion_after.log. Test totals are identical; no tests were removed.
Timing differences are observations, not a performance claim. An intermediate
regression was deliberately stopped after a final no-match wording correction;
the recorded final run started again against the final source files.

AST comparison also confirmed unchanged non-entry-point operational functions in
biorag.py, core/updater.py and core/recovery.py. Parser changes are help composition
and displayed metavars only; existing argument destinations, types, defaults,
required flags and execution branches remain unchanged.
No claim is made that historical QA benchmarks were rerun in this help-only task.

## Explicitly not verified or not performed

- Dashboard startup/install/browser behavior was source-reviewed, **not verified**
  by launching dependency installers or servers. Its safe help was executed.
- Applying a real Git/pip/database update was **not verified**. No installed update
  or live recovery was performed. Recovery was verified only on a synthetic backup.
- macOS date execution, Windows behavior, wheel installation and an independent
  novice usability study remain **not verified**. This was a fresh-venv synthetic
  rehearsal, not certification of every README installation path.
- No guarantee of global Git/pip/SQLite atomicity or compatibility of an older
  program with later memories is made.
- Full-suite configuration retains the baseline's temporal-prototype-off setting;
  it does not certify all default-on MCP perspectives in this run.
- Exhaustive dependency/OS errors and dashboard backend database routing are
  **not verified**. Root help warns schema preparation can occur on database open.

See [LANGUAGE_REVIEW.md](LANGUAGE_REVIEW.md) for the MCP language findings,
191-template runtime inventory, alias proposal and behavior-change boundaries.
No release, merge, tag, new branch, forced push, live-data access or operational
routing/ranking change is part of this work.
