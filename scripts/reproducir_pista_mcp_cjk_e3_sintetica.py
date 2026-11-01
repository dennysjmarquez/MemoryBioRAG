#!/usr/bin/env python3
"""Prueba sintética mínima de recuperación por seed y seguimiento de arista MCP.

Crea y destruye una DB temporal con dos recuerdos japoneses inventados. Usa los
handlers MCP Python (_aprender_impl/_recordar_impl), no stdio ni una base viva.
No modifica el motor ni entrena neuronas.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch


def parse_final(raw: str) -> dict:
    starts = ([0] if raw.startswith("{") else []) + [
        i + 2 for i in range(len(raw)) if raw.startswith("\n\n{", i)
    ]
    for start in reversed(starts):
        try:
            obj = json.loads(raw[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("El handler MCP no devolvió un objeto JSON final")


def main() -> int:
    if os.environ.get("BIORAG_NEURONA") != "0":
        raise SystemExit("Fije BIORAG_NEURONA=0 antes de iniciar el proceso")
    if os.environ.get("BIORAG_PATH"):
        raise SystemExit("Quite BIORAG_PATH; esta prueba solo permite una DB temporal")

    from core.memory_store import SQLiteMemoryBioRAG
    from core.mcp_server import search, write
    from middleware.auto_guardado import buffer_global

    with tempfile.TemporaryDirectory(prefix="e3_mcp_cue_synthetic_") as tmp:
        db = Path(tmp) / "synthetic.db"
        memory = SQLiteMemoryBioRAG(str(db))
        memory._persistente = True
        try:
            with patch.object(write, "_get_cerebro", return_value=memory), \
                 patch.object(search, "_get_cerebro", return_value=memory):
                def preflight(query: str, terms: str) -> None:
                    result = parse_final(search._recordar_impl(
                        query=query, sustantivos_clave=terms, limite=5
                    ))
                    if result.get("status") == "error":
                        raise RuntimeError(f"Búsqueda previa sintética rechazada: {result}")

                def save(concept: str, content: str, terms: str, synonyms: str,
                         bridges: list[dict], link_to: str | None = None,
                         pre_terms: str | None = None) -> dict:
                    preflight(concept, pre_terms or terms)
                    result = parse_final(write._aprender_impl(
                        concepto=concept, contenido=content, bridges=bridges,
                        syn=synonyms, sustantivos_clave=terms,
                        busqueda_previa=True, vincular_con=link_to,
                    ))
                    if result.get("status") != "ok":
                        raise RuntimeError(f"Escritura MCP sintética falló: {result}")
                    if not memory.consolidar_concepto(concept):
                        raise RuntimeError(f"No se consolidó el registro temporal {concept}")
                    return result

                target_bridges = [
                    {"angle": "sinonimo", "text": "灯台警告 概念与别名线索"},
                    {"angle": "problema", "text": "灯台警告 困难情况与症状"},
                    {"angle": "solucion", "text": "灯台警告 可行办法和工具"},
                    {"angle": "situacion", "text": "灯台警告 实际场景和角色"},
                    {"angle": "ingenuo", "text": "灯台警告 新手自然提问"},
                ]
                save(
                    "灯台警告記録",
                    "灯台の黄色い光が三回点滅すると岩礁に注意する。",
                    "灯台,黄色,点滅,岩礁",
                    "黄色い閃光,沿岸の警告,夜間航行の注意,岩礁の危険,灯火信号",
                    target_bridges,
                )

                cue = "霧夜観測手掛かり"
                target = "灯台警告記録"
                seed_text = "濃霧の夜の船上では沿岸の光源を探し続ける。"
                free_query = "濃霧の夜に船上で光源の位置を見つけるには"
                query_terms = "濃霧,船上,光源,夜間"
                cue_bridges = [
                    {"angle": "sinonimo", "text": "深い霧の海上で方角を探す"},
                    {"angle": "problema", "text": "暗い海で位置を失う危険"},
                    {"angle": "solucion", "text": "沿岸の光を目印に進む"},
                    {"angle": "situacion", "text": "夜間航行の船員が使う"},
                    {"angle": "ingenuo", "text": "霧の夜に船から見える光は何"},
                ]
                save(
                    cue, seed_text, query_terms,
                    "濃霧,船上,沿岸の光,夜間の目印,航路確認",
                    cue_bridges, link_to=target,
                    pre_terms="霧夜,観測,手掛かり",
                )

                rows = list(memory.conn.execute(
                    "SELECT origen, destino, tipo, peso FROM sinapsis ORDER BY origen,destino"
                ))
                linked = any(cue in row[:2] and target in row[:2] for row in rows)
                if not linked:
                    raise RuntimeError("La arista sintética no quedó persistida")

                def search_case(query: str, terms: str) -> dict:
                    buffer_global.limpiar()
                    return parse_final(search._recordar_impl(
                        query=query, sustantivos_clave=terms, deep=False, limite=5,
                        context_window=1, completo=True, asociados=True,
                    ))

                free = search_case(free_query, query_terms)
                exact = search_case(seed_text, query_terms)
                primary_free = [r.get("concepto") for r in free.get("resultados", [])]
                primary_exact = [r.get("concepto") for r in exact.get("resultados", [])]
                context_exact = [r.get("concepto") for r in exact.get("contexto_expandido", [])]
                integrity = memory.conn.execute("PRAGMA integrity_check").fetchone()[0]
                result = {
                    "fixture": "synthetic_two_memory_japanese",
                    "database": "fresh_temporary_deleted_on_exit",
                    "transport": "direct MCP Python handlers; not stdio",
                    "synapses": [list(row) for row in rows],
                    "integrity_check": integrity,
                    "free_query_seed_hit": cue in primary_free,
                    "aligned_query_seed_hit": cue in primary_exact,
                    "aligned_query_target_in_expanded_context": target in context_exact,
                    "context_window": 1,
                    "interpretation": "single scripted path; not an independent agent evaluation",
                }
                buffer_global.limpiar()
                print(json.dumps(result, ensure_ascii=False, indent=2))
                if integrity != "ok" or cue in primary_free or cue not in primary_exact \
                        or target not in context_exact:
                    return 1
                return 0
        finally:
            buffer_global.limpiar()
            memory._persistente = False
            memory.cerrar_sistema()


if __name__ == "__main__":
    raise SystemExit(main())
