# Independent-review follow-up: clean clone, Unicode keywords, and dependencies

This follow-up records a clean-clone reproduction of the reported suite mismatch and
fixes a separate, reproducible CLI validation bug. It does **not** claim to explain the
reviewer's 61 failures on Python 3.12.3; that exact interpreter was unavailable here.

## Fresh-clone test reproduction

- Cloned the published branch at `ddb32e65224941a180b7174a2f8c18ef0ded7894`
  into `/tmp/biorag-clean-review` (not a copy of the workspace), created a fresh
  virtual environment, and installed **only** `requirements.txt`.
- Environment: Python **3.11.2**, Unicode database **14.0.0**, pytest 9.1.1,
  NumPy 2.4.6. `scipy` was neither installed nor imported.
- Unmodified published clone: **999 passed, 18 skipped, 82 subtests passed**,
  exit 0; see [suite_before.txt](suite_before.txt).
- After the changes in this follow-up: **1001 passed, 18 skipped, 82 subtests
  passed**, exit 0 in 160.76 seconds; see [suite_after.txt](suite_after.txt). Two
  additional tests cover Unicode saving and assert that `buscar --todos` passes
  `limite=100` to the engine.
- The 20-help audit passes. The focused CLI tests pass (51 tests and 71 subtests).

The reported 61 failures on Python 3.12.3 were **not reproduced** in this Python 3.11.2
clean environment. Their cause remains undetermined; this run cannot establish whether
Python 3.12.3, its environment, or some other difference is responsible. Do not read the
clean 3.11 result as proof about 3.12.3.

## Confirmed `--todos` behavior

`cmd_buscar` has a dedicated `--todos` branch that passes `limite=100` to
`buscar_por_frase`. The search engine uses the requested `limite` to select the result
page; tie expansion is separately opt-in and defaults off. `--frase` and `--tokens`
are earlier, different routes, so they do not inherit this `--todos` request. The help
states this qualification. The new unit test checks the actual handler call argument;
no claim is made that every search corpus can produce 100 matches.

## Unicode keyword discrepancy fixed

The report's concrete `guardar ... --sustantivos-clave "海岸,mar"` mismatch was real:
CLI validation normalized the input but then applied an ASCII-only regular expression.
The MCP validator already accepted Unicode letters, marks, and numbers. CLI validation
now uses those same Unicode general categories (plus underscore), retains the existing
2–15-character and 1–5-term bounds, and still rejects punctuation/whitespace. Help now
spells out the allowed characters, and the affected help columns are aligned.

On the clean clone with its disposable `BIORAG_PATH`, the real command sequence
`guardar ... "海岸,mar"` → `sueno` → `buscar costas_test` exited successfully and returned
the saved content. The output is captured in
[unicode-cli-demo.txt](unicode-cli-demo.txt). No live database was accessed.

## SciPy and release text

- `requirements.txt` and the main `pyproject.toml` dependencies describe the app/test
  environment. The application `core/` has no SciPy import; the 3.11 fresh venv passed
  all tests without SciPy installed.
- SciPy imports do occur in standalone research/experiment scripts under `scripts/`,
  which are not included in the packaged application modules. Added the pinned optional
  `research` extra (`pip install .[research]`) for those scripts; SciPy is not imposed
  on normal app/test installs.
- The NumPy/SciPy phrase does occur in archived v1.0–v1.2 release documents. The current
  v36 release notes and core dependency metadata do not claim that SciPy is a runtime
  dependency. Those historic release documents were left intact.

The branch's pre-existing unrelated `.hormiguita.spawn.lock` remains untouched.
