# Language and compatibility review

## Public CLI help policy

All help prose is English. Public Spanish command/flag identifiers remain unchanged.
The explicit identifier/example-key allowlist is in
[scripts/audit_cli_help.py](../../scripts/audit_cli_help.py), with a machine-readable
copy beside the completed help captures. Existing illustrative proposal and node
keys are retained; only path and digest placeholders were changed to English.
No English command aliases were added.

The audit reuses `[language].spanish_markers` from `release_manifest.toml`.
It removes only allowlisted tokens before scanning. It does not disable the
release lint or whitelist whole output lines. The marker check is a heuristic:
it cannot prove the absence of every Spanish word. Manual review of all 20
captures supplements it. Argparse's native English headings remain unchanged.

## MCP review — reported, not translated

| Tool | Description / parameter prose | Error / response prose | Source |
|---|---|---|---|
| `recordar` | Spanish | Spanish, plus stable error codes and some English validation exceptions | `core/mcp_server/search.py` |
| `buscar` | Spanish legacy-alias description | Delegates to the same search implementation | `core/mcp_server/search.py` |
| `aprender` | Spanish | Spanish, with structured JSON identifiers | `core/mcp_server/write.py` |
| `vincular` | Spanish | Spanish missing-node and success messages | `core/mcp_server/synapses.py` |
| `estado` | Spanish legacy-alias description | Structured counts; no local human-readable error branch in its alias body; propagated errors not exhaustively exercised | `core/mcp_server/introspection.py` |

Examples inspected directly: invalid date messages, invalid search limit/window,
missing keyword guidance, write validation responses and missing association nodes.
No remote MCP session was exercised: **not verified**. Tool descriptions, error
messages, JSON field names, modes and authorization rules were not changed.

## Runtime message inventory and proposed later phase

[message_inventory.json](message_inventory.json) inventories 191 source templates:
CLI print calls and literal response/error fields in the inspected CLI/MCP modules.
It records source file/line/text, not invented runtime results. This is bounded to
those modules; dependency, SQLite, Python and OS errors are not exhaustively inventoried.
[completion_runtime.json](completion_runtime.json) contains actual synthetic runs.

Representative existing messages (unchanged):

- Save: `'servicio_puerto_actual' guardado en corto plazo.`
- Search miss: `No se encontraron coincidencias para la frase.`
- Keywords: `Sustantivos clave de ...`
- Status: `Nodos activos`, `Nodos dormidos`, `Memoria de trabajo`.
- Association: `Sinapsis establecida`.
- Message registration: `Mensaje de ... para todos registrado ...`.
- Message reads: `[NO LEIDO]`.
- MCP search: `Fecha 'desde' inválida`, invalid limit/context-window guidance.
- MCP linking: `No se pueden vincular: nodo(s) ... no existen ...`.
- Recovery: Spanish `reason` and `next` values within English-keyed JSON.

Proposed separate, approval-gated phase: translate human-readable success/error
prose together with README transcripts and MCP parameter/tool descriptions; retain
public identifiers, persisted values, structured JSON keys, stable error codes,
agent-authored memory text and message content. First audit text-sensitive clients
and tests. Do not combine this with a storage migration or ranking change.

Optional aliases (`save`, `search`, `sleep`) are a proposal only. They would require
an explicit compatibility decision, collision checks, documentation, dispatcher
and alias parity tests. None were implemented.

## Known behavior decisions not made here

Private destination routing is hardcoded. Unknown recipient IDs silently broadcast
to `todos`; unknown destination filters are ignored. This is why generic examples
use explicit broadcasts and AGENT_NAME, not fictional private destinations.
The README's recipient list and MCP's supported-recipient description were retained
because they reflect that operational restriction. Historical README release notes
and third-party product names were not rewritten. Their presence is not evidence
of a CLI-help lint failure.

No uniform --db, ISO-date parsing, dashboard installation prompt/port option or
HTML export was added. macOS date conversion is **not verified** on macOS.
