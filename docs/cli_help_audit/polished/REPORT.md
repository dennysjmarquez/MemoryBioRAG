# Final help polish following independent review

Base commit: 054da69. This is a presentation-only follow-up to
[COMPLETION.md](../COMPLETION.md). Runtime/MCP translation remains unapproved and
unchanged. No new aliases or operational changes were introduced.

## Review items addressed

1. Root Examples now starts with a clearly labeled Quick start:
   guardar service_note → sueno → buscar service_note. It warns that these commands
   write to the selected database and asks the reader to choose a disposable copy.
   The exact three commands were extracted from root help and executed successfully
   in a new temporary database. Search returned the English content saved initially.
2. Memory-command options now use uniform two-space indentation, including the
   first line and wrapped continuations. Communication routing prose moved out of
   Options; that section now correctly says there are no additional options.
   Dashboard Examples starts with the actual safe --help command, not a warning;
   startup/install warnings remain in its explanatory prose.
3. Root update/recovery notes have a title and Options has a separating blank line.
4. Per-command domain glossary is a short bulleted list, not a semicolon sentence.
5. The 100-result request **does exist**: cmd_buscar's dedicated todos branch calls
   buscar_por_frase(..., limite=100). However, explicit --frase and --tokens select
   earlier routes. The help now states this qualification rather than implying
   that every flag combination requests 100 results.
6. Root and memory help now use lowercase usage:, matching native argparse.

## Evidence and verification limits

- 20/20 help invocations exit 0 and pass section-order, release-marker/allowlist
  and internal-name checks. Captures and results.json are in this directory.
- Three CLI test files: **54 passed, 71 subtests passed**, 8.39 seconds.
  Existing guarded tests now check quick-start ordering, root block separation,
  options indentation, glossary bullets and dashboard/communication layout.
  No tests were removed or renamed.
- Fresh full-suite baseline: **999 passed, 18 skipped, 82 subtests passed**,
  180.72 seconds, exit 0. See suite_before.log.
- Fresh full suite on final files: **999 passed, 18 skipped, 82 subtests passed**,
  180.35 seconds, exit 0. See suite_after.log. Totals are identical; timings are
  observations, not a performance claim. Configuration matches the prior audit:
  isolated source/snapshot copies, temporal prototype off, fixed hash seed, one
  BLAS thread, auto-download/update checks/daemon disabled.
- execution.json contains the real three-step temporary-database transcript and
  three **stub-engine routing argument probes** executing the unchanged handler:
  --todos requests limite=100; adding --frase omits that explicit limit; adding
  --tokens selects token search. These probes verify routing/call arguments only,
  **not** a real database returning 100 results. That large-result retrieval was
  not executed and is **not verified**.
- Function AST comparison confirms all biorag.py handlers are unchanged and only
  presentation functions changed in cli.py and cli_notes.py. The final tested
  source files were compared byte-for-byte with the workspace before commit.

No live memory, dashboard startup, installed update or live recovery was used.
Previously recorded platform/dependency limitations still apply. Runtime output
remains in its existing language; a separate translation decision is still needed.
