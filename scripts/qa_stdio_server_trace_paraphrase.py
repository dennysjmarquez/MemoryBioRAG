#!/usr/bin/env python3
"""Launcher MCP stdio de diagnóstico con observación pasiva de búsqueda.

Solo para fixtures bajo BIORAG_QA_TEMP_ROOT. Envuelve temporalmente el método
público buscar_por_frase y el cursor SQLite de esa llamada, sin cambiar consultas,
parámetros, resultados ni efectos. Registra cada MATCH y las filas que esa consulta
real devuelve, además del pool final. La traza íntegra debe permanecer privada.
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


class _ObservedCursor:
    """Proxy transparente que observa las filas ya solicitadas por el motor."""

    def __init__(self, cursor, connection, statements, filter_statements, frase, parafrasis_list, modo_estricto):
        self._cursor = cursor
        self._connection = connection
        self._statements = statements
        self._filter_statements = filter_statements
        self._current = None
        self._parameters = ()
        self._expected_slots = {}
        for index, value in enumerate([frase] + list(parafrasis_list or [])):
            safe = " ".join(
                part for token in str(value).split()
                for part in re.split(r"-+", token) if part
            )
            if modo_estricto:
                if parafrasis_list:
                    expression = f"({ ' AND '.join(safe.split()) })" if safe else safe
                elif len(safe.split()) > 1:
                    expression = " ".join("+" + word for word in safe.split())
                else:
                    expression = safe
            else:
                expression = f'"{safe}"'
            slot = "query" if index == 0 else f"paraphrase_{index}"
            self._expected_slots.setdefault(expression, []).append(slot)

    @staticmethod
    def _split_top_level_or(expression):
        parts, start, depth, quoted, i = [], 0, 0, False, 0
        while i < len(expression):
            char = expression[i]
            if char == '"':
                if quoted and i + 1 < len(expression) and expression[i + 1] == '"':
                    i += 2
                    continue
                quoted = not quoted
            elif not quoted:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                elif depth == 0 and expression[i:i + 4].upper() == " OR ":
                    parts.append(expression[start:i].strip())
                    start = i + 4
                    i = start
                    continue
            i += 1
        if parts:
            parts.append(expression[start:].strip())
        return parts

    @classmethod
    def _strip_outer_parens(cls, expression):
        text = expression.strip()
        if not (text.startswith("(") and text.endswith(")")):
            return None
        depth, quoted = 0, False
        i = 0
        while i < len(text):
            char = text[i]
            if char == '"':
                if quoted and i + 1 < len(text) and text[i + 1] == '"':
                    i += 2
                    continue
                quoted = not quoted
            elif not quoted:
                depth += (char == "(") - (char == ")")
                if depth == 0 and i != len(text) - 1:
                    return None
            i += 1
        return text[1:-1].strip() if depth == 0 else None

    @classmethod
    def _probe_branches(cls, expression):
        branches = []
        def collect(text):
            text = text.strip()
            parts = cls._split_top_level_or(text)
            if len(parts) > 1:
                for part in parts:
                    collect(part)
                return
            inner = cls._strip_outer_parens(text)
            if inner is not None:
                collect(inner)
                return
            field = re.fullmatch(r"sustantivos_clave:\((.*)\)", text, flags=re.IGNORECASE)
            if field:
                terms = cls._split_top_level_or(field.group(1))
                if len(terms) > 1:
                    for term in terms:
                        branches.append(("field_boost", f"sustantivos_clave:({term})"))
                    return
                branches.append(("field_boost", text))
                return
            branches.append(("fts_branch", text))
        collect(expression)
        return branches

    def execute(self, sql, parameters=()):
        values = parameters if isinstance(parameters, (tuple, list)) else (parameters,)
        result = self._cursor.execute(sql, parameters)
        if re.search(r"\bMATCH\b", str(sql), flags=re.IGNORECASE):
            expression = next((value for value in values if isinstance(value, str)), None)
            self._current = {
                "statement_index": len(self._statements) + 1,
                "statement_kind": "fts_match",
                "sql_sha256": hashlib.sha256(str(sql).encode("utf-8")).hexdigest(),
                "sql": str(sql),
                "match_expression": expression,
                "rows_returned": 0,
                "count_value": None,
                "candidate_concepts": [],
                "variant_probes": [],
            }
            self._parameters = tuple(values)
            self._statements.append(self._current)
        elif "PALABRA_INICIO_ANCHO" in str(sql).upper():
            self._current = {
                "filter_index": len(self._filter_statements) + 1,
                "filter_kind": "single_word_prefix_guard",
                "sql_sha256": hashlib.sha256(str(sql).encode("utf-8")).hexdigest(),
                "sql": str(sql),
                "rows_returned": 0,
                "candidate_concepts": [],
                "input_candidates": list(values[4:]) if len(values) > 4 else [],
                "variant_probes": [],
            }
            self._parameters = tuple(values)
            self._filter_statements.append(self._current)
        else:
            self._current = None
            self._parameters = ()
        return self

    def executemany(self, sql, parameters):
        result = self._cursor.executemany(sql, parameters)
        self._current = None
        return self

    @staticmethod
    def _concept(row):
        if not row:
            return None
        # Búsquedas FTS normales devuelven rowid, concepto, ...; consultas de
        # puente/proyección pueden devolver solo concepto.
        value = row[1] if len(row) > 1 and isinstance(row[1], str) else row[0]
        return value if isinstance(value, str) else None

    def _record(self, rows):
        if self._current is not None:
            for row in rows:
                self._current["rows_returned"] += 1
                concept = self._concept(row)
                if concept is not None:
                    self._current["candidate_concepts"].append(concept)
            if "COUNT(" in self._current["sql"].upper() and rows:
                try:
                    self._current["count_value"] = rows[0][0]
                except (IndexError, TypeError):
                    pass
            if not self._current["variant_probes"]:
                expression = self._current.get("match_expression")
                branches = self._probe_branches(expression) if isinstance(expression, str) else []
                auxiliary_index = 0
                for branch_kind, branch_expression in branches:
                    if branch_kind == "field_boost":
                        label = "sustantivos_clave"
                    else:
                        normalized_branch = self._strip_outer_parens(branch_expression) or branch_expression
                        matched_slots = self._expected_slots.get(normalized_branch, [])
                        if matched_slots:
                            label = matched_slots[0] if len(matched_slots) == 1 else "ambiguous_duplicate_variant"
                        else:
                            auxiliary_index += 1
                            label = f"auxiliary_fts_branch_{auxiliary_index}"
                            matched_slots = []
                    probe = {
                        "source_slot": label,
                        "source_slots": matched_slots if branch_kind != "field_boost" else [label],
                        "branch_kind": branch_kind,
                        "match_expression": branch_expression,
                        "candidate_concepts": [],
                        "rows_returned": 0,
                        "count_value": None,
                    }
                    try:
                        cursor = self._connection.cursor()
                        params = (branch_expression,) + self._parameters[1:]
                        cursor.execute(self._current["sql"], params)
                        probe_rows = cursor.fetchall()
                        probe["rows_returned"] = len(probe_rows)
                        if "COUNT(" in self._current["sql"].upper() and probe_rows:
                            probe["count_value"] = probe_rows[0][0]
                        probe["candidate_concepts"] = [
                            concept for concept in (self._concept(row) for row in probe_rows)
                            if concept is not None
                        ]
                    except Exception as exc:
                        probe["probe_exception"] = type(exc).__name__
                    self._current["variant_probes"].append(probe)
        return rows

    def fetchall(self):
        return self._record(self._cursor.fetchall())

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is not None:
            self._record([row])
        return row

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany() if size is None else self._cursor.fetchmany(size)
        return self._record(rows)

    def __iter__(self):
        for row in self._cursor:
            self._record([row])
            yield row

    def __getattr__(self, name):
        return getattr(self._cursor, name)


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
        statements = []
        filter_statements = []
        original_cursor = self.cursor
        proxy = _ObservedCursor(
            original_cursor, self.conn, statements, filter_statements, frase,
            kwargs.get("parafrasis_list") or [], bool(kwargs.get("modo_estricto", False)),
        )
        error = None
        result = []
        total = None
        target_concept = os.environ.get("BIORAG_QA_TRACE_TARGET")
        search_stage_trace = []
        prior_trace = sys.gettrace()
        previous_presence = {}

        def trace_search(frame, event_name, arg):
            if (frame.f_code.co_name != "buscar_por_frase"
                    or not os.path.normpath(frame.f_code.co_filename).endswith(
                        os.path.join("core", "memory", "search.py")
                    )
                    or frame.f_locals.get("self") is not self):
                return None
            if event_name == "call":
                frame.f_trace_lines = True
                return trace_search
            if event_name == "line" and target_concept:
                local_vars = frame.f_locals
                for name in ("todos", "resultados_con_hibrido", "filtrados_qcr", "pagina_base", "pagina_resultados"):
                    rows = local_vars.get(name)
                    if not isinstance(rows, (list, tuple)):
                        continue
                    concept_index = 1 if name == "todos" else 0
                    found = [(i, row) for i, row in enumerate(rows)
                             if isinstance(row, (list, tuple)) and len(row) > concept_index
                             and row[concept_index] == target_concept]
                    present = bool(found)
                    key = (id(frame), name)
                    was_present = previous_presence.get(key, False)
                    if present != was_present and (present or was_present):
                        rank, row = found[0] if found else (None, None)
                        origin_map = local_vars.get("origen_scores", {})
                        origin = origin_map.get(target_concept) if isinstance(origin_map, dict) else None
                        search_stage_trace.append({
                            "stage": name,
                            "transition": "candidate_present" if present else "candidate_removed",
                            "line": frame.f_lineno,
                            "rank": rank,
                            "score": row[4] if row is not None and name != "todos" and len(row) > 4 else None,
                            "row_width": len(row) if row is not None else None,
                            "origin": origin[0] if isinstance(origin, (tuple, list)) and origin else None,
                        })
                    previous_presence[key] = present
            elif event_name == "return" and target_concept:
                returned_rows = arg[0] if isinstance(arg, tuple) and arg else arg
                returned_has_target = (
                    isinstance(returned_rows, (list, tuple))
                    and any(isinstance(row, (list, tuple)) and row and row[0] == target_concept
                            for row in returned_rows)
                )
                search_stage_trace.append({
                    "stage": "search_function_return",
                    "transition": "candidate_returned" if returned_has_target else "candidate_absent",
                    "line": frame.f_lineno,
                    "returned_total": arg[1] if isinstance(arg, tuple) and len(arg) > 1 else None,
                })
            return trace_search

        self.cursor = proxy
        sys.settrace(trace_search)
        try:
            result, total = original(self, frase, *args, **kwargs)
            return result, total
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)[:300]}
            raise
        finally:
            sys.settrace(prior_trace)
            self.cursor = original_cursor
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
                "fts_statements": statements,
                "post_search_filter_statements": filter_statements,
                "query_token_count": len(re.findall(r"\w{3,}", str(frase).lower())),
                "fts_match_expressions": [item.get("match_expression") for item in statements],
                "candidate_count": len(candidate_concepts),
                "candidate_concepts": candidate_concepts,
                "search_stage_trace": search_stage_trace,
                "engine_final_concepts": [
                    row[0] for row in (getattr(self, "last_pagina_resultados", []) or [])
                    if isinstance(row, (tuple, list)) and row
                ],
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
