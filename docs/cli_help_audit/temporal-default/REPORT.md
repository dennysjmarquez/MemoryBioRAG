# Temporal MCP prototype default: investigation and change

## What caused the red test in the terminal screenshot

At commit `8fe7d4e`, `core/mcp_server/search.py` treated an **unset**
`BIORAG_TEMPORAL_PROTOTYPE` as `'1'`. The prototype therefore required
`contexto_vigencia.mode` for each MCP `recordar`/`buscar` call. The extraction battery
saves and consolidates its synthetic cases, then calls `recordar` without that field.
The request is rejected early with `CONTEXTO_VIGENCIA_REQUERIDO`, before the search
engine or database query; the assertion expecting `resultados` fails. The red test in
the screenshot is this exact contract mismatch, not a Unicode, SciPy, or ranking error.

Reproduction on the pre-change code:

- With no variable: the end-to-end battery test fails with that exact error.
- With `BIORAG_TEMPORAL_PROTOTYPE=1`: same expected failure.
- With `BIORAG_TEMPORAL_PROTOTYPE=0`: the battery test passes.

A clean full-suite baseline on Python 3.11.2 with the variable unset produced **53
failed, 948 passed, 18 skipped, 82 subtests passed** (exit 1 in 134.42 seconds); full output
is [suite_before.log.gz](suite_before.log.gz). The 53 failures cluster in MCP callers across
nine files: Unicode recordar (20), sustantivos clave recordar (14), Unicode guardar
(8), identidad Unicode (5), auto-expansion (2), plus four single failures including
this extraction battery. The early mode gate preempts those callers, which is why
failures with Unicode-oriented test names misleadingly looked like Unicode bugs.
The external review's Python 3.12.3 counts differ slightly, but its reported gate-off
result agrees with the cause and fix. Python 3.12.3 was not available in this
environment, so that interpreter was not independently rerun here.

## Change made

To preserve backward compatibility for unconfigured MCP clients, the temporal
perspective experiment is now **opt-in**:

- Missing variable and `BIORAG_TEMPORAL_PROTOTYPE=0` preserve the prior MCP search
  contract; no mode is required and `contexto_vigencia` is ignored by the prototype.
- Explicit `BIORAG_TEMPORAL_PROTOTYPE=1` preserves the experimental contract:
  `recordar` and `buscar` require an explicit mode; no intent is inferred.
- `.env.example`, root README, MCP package README and prototype specification now
  document the off-by-default behavior. Both MCP tool schemas describe the default and
  opt-in switch. The server must be restarted after changing the setting.
- Existing explicit `=1` settings are not overwritten by this code change. In
  particular, `.env.example` is a template, not a migration of a user's `.env.local`;
  users who previously copied `=1` there must change it themselves to opt out.
- Tests now check default-off behavior and still check that explicit `=1` enforces the
  mode contract and advertises it in the tool schemas. The extraction end-to-end test
  passes without a hidden environment override.

## Verification

- Before/after full suites used the same fresh Python 3.11.2 venv installed from
  `requirements.txt`, fixed hash seed, one BLAS thread, isolated HOME, disabled update
  checks/daemon/automatic NLTK download, and **no** `BIORAG_TEMPORAL_PROTOTYPE` value.
- Before: **53 failed, 946 passed, 18 skipped, 82 subtests passed**.
- After: **1001 passed, 18 skipped, 82 subtests passed**, exit 0 in 161.76 seconds;
  see [suite_after.log.gz](suite_after.log.gz).
- Focused temporal-prototype plus extraction-battery tests: **41 passed**. This includes
  explicit-on enforcement and the screenshot's end-to-end case.
- CLI help audit: **20/20** pages pass; see this directory's captures and
  `results.json`.

No live database was accessed. The previous explicit-on behavior remains available for
prototype testing, but is no longer imposed on new or unconfigured users.
