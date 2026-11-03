#!/usr/bin/env python3
"""Launcher MCP stdio de diagnóstico con observación pasiva de búsqueda.

Solo para fixtures bajo BIORAG_QA_TEMP_ROOT. Envuelve temporalmente el método
público buscar_por_frase para registrar parámetros, SQL MATCH ejecutado y
candidatos/orígenes devueltos, sin cambiar sus argumentos, retorno o efectos.
La traza JSONL debe guardarse bajo la copia temporal y no publicarse.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    db_value = os.environ.get("BIORAG_PATH")
    temp_value = os.environ.get("BIORAG_QA_TEMP_ROOT")
    trace_value = os.environ.get("BIORAG_QA_TRACE_PATH")
    if not db_value or not temp_value or not trace_value:
        raise SystemExit("Se requieren BIORAG_PATH, BIORAG_QA_TEMP_ROOT y BIORAG_QA_TRACE_PATH")
    db_path = Path(db_value).resolve()
    temp_root = Path(temp_value).resolve()
    trace_path = Path(trace_value).resolve()
    for label, path in (("DB", db_path), ("traza", trace_path)):
        try:
            path.relative_to(temp_root)
        except ValueError as exc:
            raise SystemExit(f"Guardrail: {label} fuera del temporal QA") from exc
    trace_path.parent.mkdir(parents=True, exist_ok=True)

    fixed_time = float(os.environ.get("BIORAG_QA_RELOJ_FIJO", "1793059200.0"))
    time.time = lambda: fixed_time

    from core.memory_store import SQLiteMemoryBioRAG

    original = SQLiteMemoryBioRAG.buscar_por_frase
    sequence = 0

    def observed(self, frase, *args, **kwargs):
        nonlocal sequence
        sequence += 1
        fts_sql = []
        callback = self.conn.set_trace_callback

        def capture_sql(statement: str) -> None:
            if re.search(r"largo_plazo_fts\s+MATCH", statement, flags=re.IGNORECASE):
                match = re.search(
                    r"largo_plazo_fts\s+MATCH\s+'((?:[^']|'')*)'",
                    statement,
                    flags=re.IGNORECASE,
                )
                fts_sql.append(match.group(1).replace("''", "'") if match else "<MATCH statement; expression parse unavailable>")

        callback(capture_sql)
        error = None
        try:
            result, total = original(self, frase, *args, **kwargs)
            return result, total
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)[:300]}
            raise
        finally:
            callback(None)
            pool = getattr(self, "last_todos", []) or []
            origins = getattr(self, "last_origen_scores", {}) or {}
            candidate_concepts = [row[1] for row in pool if len(row) > 1 and row[1]]
            event = {
                "search_call_index": sequence,
                "query_sha256": hashlib.sha256(str(frase).encode("utf-8")).hexdigest(),
                "paraphrase_sha256": [
                    hashlib.sha256(str(value).encode("utf-8")).hexdigest()
                    for value in (kwargs.get("parafrasis_list") or [])
                ],
                "modo_estricto": bool(kwargs.get("modo_estricto", False)),
                "fts_match_expressions": fts_sql,
                "candidate_count": len(candidate_concepts),
                "candidate_concepts": candidate_concepts,
                "candidate_origins": {
                    name: {"origin": value[0], "score": value[1]}
                    for name, value in origins.items()
                    if isinstance(value, (tuple, list)) and len(value) >= 2
                },
                "returned_concepts": [row[0] for row in result] if error is None else [],
                "returned_scores": {row[0]: row[4] for row in result} if error is None else {},
                "reported_total": total if error is None else None,
                "exception": error,
            }
            with trace_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()

    SQLiteMemoryBioRAG.buscar_por_frase = observed

    from core.mcp_server.server import _build_server, _proteger_canal_stdio

    _proteger_canal_stdio()
    app = _build_server()
    app.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
