#!/usr/bin/env python3
"""Controles sintéticos pareados para CJK E3; no modifica el motor del checkout.

Crea una sola DB sintética, la copia antes de cada consulta y compara base,
OR CJK y umbral 2 en aplicaciones temporales obtenidas por git archive. Mide
casos mixtos, conectores, una consulta japonesa negativa, pistas/ranking y costo
local para longitudes crecientes. No es QA oficial ni evaluación de agente.

Los controles japoneses se suministran localmente por las variables
BIORAG_E3_JP_QUERY_A y BIORAG_E3_JP_QUERY_B. No guardes sus textos en el repo.
Ejemplo (el directorio de salida debe ser nuevo):
  env -u BIORAG_PATH PYTHONHASHSEED=0 BIORAG_NEURONA=0 BIORAG_NO_LOG=1 \
    NLTK_DATA="$PWD/MemoryBioRAG_Data/nltk_data" PYTHONPATH=. \
    python scripts/evaluar_controles_extendidos_cjk_e3.py \
    --salida /tmp/e3-controles-cjk-nuevos
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATCHES = {
    "or": ROOT / "docs/e3_cjk_trigram_propuesta_NO_APLICAR_20261101.patch",
    "umbral2": ROOT / "docs/e3_cjk_trigram_umbral2_DIAGNOSTICO_NO_APLICAR_20261101.patch",
}
SOURCE_FILES = [
    "core", "middleware", "config", "biorag.py",
    "scripts/evaluar_qa_multilingue_e3a.py",
    "scripts/casos_qa_multilingue_e3a.jsonl",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True,
                        help="Directorio nuevo que recibirá los resultados sintéticos")
    parser.add_argument("--worker", choices=("crear", "buscar"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--temp", type=Path)
    parser.add_argument("--expected-sha")
    return parser.parse_args()


def make_cases() -> list[dict]:
    # Supply the two Japanese control strings locally via environment; never
    # embed source query text, case IDs, labels, or a crosswalk in this script.
    japanese_a = os.environ.get("BIORAG_E3_JP_QUERY_A", "")
    japanese_b = os.environ.get("BIORAG_E3_JP_QUERY_B", "")
    if not japanese_a or not japanese_b:
        raise SystemExit("Set BIORAG_E3_JP_QUERY_A and BIORAG_E3_JP_QUERY_B locally")
    cases = [
        {"id": "jp_control_a", "query": japanese_a, "context_window": 1,
         "probe": "jp_control_a"},
        {"id": "jp_control_b", "query": japanese_b, "context_window": 1,
         "probe": "jp_control_b"},
        {"id": "mixed_latin_no_space", "query": "灯台ABC警告", "context_window": 1, "probe": "script_compaction"},
        {"id": "mixed_english_connector", "query": "灯台 and 警告", "context_window": 1, "probe": "latin_connector"},
        {"id": "mixed_punctuation", "query": "灯台—警告", "context_window": 1, "probe": "punctuation_boundary"},
        {"id": "japanese_particle_no", "query": "灯台の警告", "context_window": 1, "probe": "japanese_connector_preserved"},
        {"id": "mixed_hangul", "query": "灯台안전警告", "context_window": 1, "probe": "hangul_included_in_range"},
        {"id": "supplementary_han", "query": "𠀀灯台警告", "context_window": 1, "probe": "han_outside_bmp_range"},
        {"id": "cue_free_rephrase", "query": "濃霧の夜に船上で光源の位置を見つけるには", "context_window": 1, "probe": "free_rephrase"},
        {"id": "cue_aligned_seed", "query": "濃霧の夜の船上では沿岸の光源を探し続ける。", "context_window": 1, "probe": "aligned_seed_and_neighbor"},
    ]
    for n in (64, 128, 256, 500, 1000):
        filler = "".join(chr(0x4E00 + i) for i in range(n))
        cases.append({"id": f"long_cjk_{n}", "query": "灯台警告" + filler,
                      "context_window": 0,
                      "probe": "long_direct_engine_only" if n + 4 > 500 else "long_under_mcp_limit"})
    return cases


def worker_create(args: argparse.Namespace) -> None:
    sys.path.insert(0, str(ROOT))
    from scripts import evaluar_qa_multilingue_e3a as qa
    from core.memory_service import aprender
    from core.memory_store import SQLiteMemoryBioRAG

    cases = qa.cargar_gold()
    if args.source.exists():
        raise FileExistsError(args.source)
    with patch("time.time", return_value=qa.RELOJ_FIJO):
        base = qa.crear_base(args.source, cases)
    memory = SQLiteMemoryBioRAG(str(args.source))
    try:
        extras = [
            ("霧夜観測手掛かり", "濃霧の夜の船上では沿岸の光源を探し続ける。"),
            ("灯台警告記録", "灯台の黄色い光が三回点滅すると岩礁に注意する。"),
            ("方位磁針注意記録", "方位磁針の針は北を指す。"),
        ]
        for concept, content in extras:
            aprender(memory, concept, content, consolidar=True)
        memory.establecer_asociacion("霧夜観測手掛かり", "灯台警告記録")
        memory.establecer_asociacion("真鍮の方位磁針", "方位磁針注意記録")
        memory.conn.commit()
        integrity = memory.conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check={integrity}")
        if memory.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] != 0:
            raise RuntimeError("No se pudo evacuar WAL")
    finally:
        memory.cerrar_sistema()
    base.update({"sha256_sqlite": sha256(args.source), "extras_synthetic": 3,
                 "manual_links_synthetic": 2, "integrity_check": integrity})
    args.result.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _cjk_chars(text: str) -> list[str]:
    return [ch for ch in text if ("\u3400" <= ch <= "\u9fff")
            or ("\uf900" <= ch <= "\ufaff")
            or ("\u3040" <= ch <= "\u30ff")
            or ("\uac00" <= ch <= "\ud7af")]


def _trigrams(text: str) -> list[str]:
    chars = _cjk_chars(text)
    return sorted({"".join(chars[i:i + 3]) for i in range(len(chars) - 2)})


def raw_fts_probe(memory, query: str) -> dict:
    grams = _trigrams(query)
    if not grams:
        return {"query_trigram_count": 0, "fts_or_query_bytes": 0,
                "raw_fts_ms": 0.0, "raw_fts_candidates": 0, "fts_error": None,
                "overlap_with_compass_content": [], "overlap_by_candidate": [],
                "raw_top10": []}
    expr = " OR ".join('"' + gram.replace('"', '""') + '"' for gram in grams)
    t0 = time.perf_counter_ns()
    error = None
    rows = []
    try:
        memory.cursor.execute("""
            SELECT l.concepto, l.contenido,
                   bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) AS bm25_val
            FROM largo_plazo_fts f
            CROSS JOIN largo_plazo l ON l.rowid = f.rowid
            WHERE largo_plazo_fts MATCH ? AND l.estado='activo'
            ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0)
        """, (expr,))
        rows = memory.cursor.fetchall()
    except Exception as exc:  # report el error; no se convierte en resultado vacío exitoso
        error = f"{type(exc).__name__}: {exc}"
    elapsed = (time.perf_counter_ns() - t0) / 1_000_000
    compass = next((f"{r[0]} {r[1] or ''}" for r in rows if r[0] == "真鍮の方位磁針"), "")
    overlap = sorted(set(grams) & set(_trigrams(compass))) if compass else []
    return {"query_trigram_count": len(grams), "fts_or_query_bytes": len(expr.encode("utf-8")),
            "raw_fts_ms": round(elapsed, 3), "raw_fts_candidates": len(rows),
            "fts_error": error, "overlap_with_compass_content": overlap,
            "overlap_by_candidate": [
                {"concepto": r[0], "trigrams": sorted(set(grams) & set(_trigrams(f"{r[0]} {r[1] or ''}")))}
                for r in rows[:10]
            ],
            "raw_top10": [r[0] for r in rows[:10]]}


def worker_search(args: argparse.Namespace) -> None:
    sys.path.insert(0, str(ROOT))
    from core.memory_store import SQLiteMemoryBioRAG
    from scripts.evaluar_qa_multilingue_e3a import RELOJ_FIJO, sha256

    if sha256(args.source) != args.expected_sha:
        raise RuntimeError("La fuente pareada no coincide con la huella declarada")
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    outputs = []
    args.temp.mkdir(parents=True, exist_ok=True)
    before_source = sha256(args.source)
    for case in cases:
        timings, peaks, last = [], [], None
        repeats = 3
        for rep in range(repeats):
            folder = args.temp / f"{case['id']}_{rep}"
            folder.mkdir()
            copy = folder / "copy.db"
            shutil.copyfile(args.source, copy)
            memory = SQLiteMemoryBioRAG(str(copy))
            dmn = folder / "dmn_state.json"
            os.environ["BIORAG_DMN_ESTADO_PATH"] = str(dmn)
            try:
                raw_probe = raw_fts_probe(memory, case["query"])
                tracemalloc.start()
                tracemalloc.reset_peak()
                start_current, _ = tracemalloc.get_traced_memory()
                t0 = time.perf_counter_ns()
                with patch("time.time", return_value=RELOJ_FIJO):
                    primary_results, total = memory.buscar_por_frase(
                        case["query"], profundidad="activos", limite=5,
                        context_window=0, ignore_peso_sinaptico=True,
                    )
                timings.append((time.perf_counter_ns() - t0) / 1_000_000)
                _, peak = tracemalloc.get_traced_memory()
                peaks.append(max(0, peak - start_current) / 1024)
                context_t0 = time.perf_counter_ns()
                if case["context_window"]:
                    with patch("time.time", return_value=RELOJ_FIJO):
                        with_context, _ = memory.buscar_por_frase(
                            case["query"], profundidad="activos", limite=5,
                            context_window=case["context_window"], ignore_peso_sinaptico=True,
                        )
                    context_ms = (time.perf_counter_ns() - context_t0) / 1_000_000
                    primary_names = {r[0] for r in primary_results}
                    context = [r for r in with_context if r[0] not in primary_names]
                else:
                    context_ms = 0.0
                    context = []
                tracemalloc.stop()
                last = {
                    "total_motor": total,
                    "candidate_pool": len(getattr(memory, "last_todos", [])),
                    "cjk_origin_candidates": sum(
                        1 for v in getattr(memory, "last_origen_scores", {}).values()
                        if v and v[0] == "cjk_trigram_or_experimental"
                    ),
                    "results": [{"concepto": r[0], "score": float(r[4]),
                                 "asociaciones": r[5] or ""} for r in primary_results[:5]],
                    "expanded_context": [{"concepto": r[0], "score": float(r[4]),
                                          "asociaciones": r[5] or ""} for r in context],
                    "context_search_ms": round(context_ms, 3),
                    "raw_fts": raw_probe,
                }
            finally:
                if tracemalloc.is_tracing():
                    tracemalloc.stop()
                memory.cerrar_sistema()
        last["search_ms_median_three_runs"] = round(statistics.median(timings), 3)
        last["tracemalloc_peak_kb_median_three_runs"] = round(statistics.median(peaks), 1)
        last["query_chars"] = len(case["query"])
        last["probe"] = case["probe"]
        last["context_window"] = case["context_window"]
        outputs.append({"id": case["id"], **last})
        shutil.rmtree(args.temp / f"{case['id']}_0")
        shutil.rmtree(args.temp / f"{case['id']}_1")
    if sha256(args.source) != before_source:
        raise RuntimeError("La fuente pareada cambió durante las búsquedas")
    args.result.write_text(json.dumps({"source_sha256": before_source, "cases": outputs},
                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_worker(app: Path, args: list[str], env: dict[str, str]) -> None:
    subprocess.run([sys.executable, str(app / "scripts/evaluar_controles_extendidos_cjk_e3.py"),
                    *args], cwd=app, env=env, check=True)


def main() -> int:
    args = parse_args()
    if args.worker == "crear":
        worker_create(args)
        return 0
    if args.worker == "buscar":
        worker_search(args)
        return 0
    out = args.salida.resolve()
    if out.exists():
        raise SystemExit(f"La salida ya existe; use directorio nuevo: {out}")
    if any(not path.is_file() for path in PATCHES.values()):
        raise SystemExit("Falta uno de los parches diagnósticos")
    out.mkdir(parents=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    cases = make_cases()
    with tempfile.TemporaryDirectory(prefix="e3_extended_cjk_") as tmp:
        tmpdir = Path(tmp)
        cases_path = tmpdir / "cases.json"
        cases_path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        apps: dict[str, Path] = {}
        for name in ("baseline", "or", "umbral2"):
            app = tmpdir / name
            app.mkdir()
            archive = subprocess.check_output(["git", "archive", head, *SOURCE_FILES], cwd=ROOT)
            archive_path = tmpdir / f"{name}.tar"
            archive_path.write_bytes(archive)
            subprocess.run(["tar", "-xf", str(archive_path), "-C", str(app)], check=True)
            # Solo se enlaza el corpus NLTK de lectura; nunca la DB bajo MemoryBioRAG_Data.
            data_dir = app / "MemoryBioRAG_Data"
            data_dir.mkdir()
            (data_dir / "nltk_data").symlink_to(ROOT / "MemoryBioRAG_Data/nltk_data", target_is_directory=True)
            scripts_dir = app / "scripts"
            shutil.copy2(Path(__file__), scripts_dir / Path(__file__).name)
            if name in PATCHES:
                subprocess.run(["patch", "--batch", "--forward", "-p1", "-i", str(PATCHES[name])],
                               cwd=app, check=True)
            apps[name] = app
        source = tmpdir / "paired_synthetic.db"
        env_base = {
            "HOME": str(tmpdir), "PATH": os.environ.get("PATH", ""),
            "PYTHONHASHSEED": "0", "BIORAG_NEURONA": "0", "BIORAG_NO_LOG": "1",
            "NLTK_DATA": str(ROOT / "MemoryBioRAG_Data/nltk_data"),
        }
        base_env = {**env_base, "PYTHONPATH": str(apps["baseline"])}
        base_json = tmpdir / "base_meta.json"
        run_worker(apps["baseline"], ["--salida", str(out), "--worker", "crear",
                   "--source", str(source), "--result", str(base_json)], base_env)
        source_hash = sha256(source)
        if json.loads(base_json.read_text())["sha256_sqlite"] != source_hash:
            raise RuntimeError("Hash SQLite no coincide con metadatos de construcción")
        (out / "fuente_sintetica_metadata.json").write_text(
            json.dumps({**json.loads(base_json.read_text()),
                        "audit_head": head,
                        "query_count": len(cases), "repetitions_per_query": 3},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result_paths = {}
        for name, app in apps.items():
            env_child = {**env_base, "PYTHONPATH": str(app),
                         "BIORAG_DMN_ESTADO_PATH": str(tmpdir / f"dmn_{name}.json")}
            result = out / f"{name}.json"
            worker_tmp = tmpdir / f"work_{name}"
            run_worker(app, ["--salida", str(out), "--worker", "buscar",
                       "--source", str(source), "--cases", str(cases_path),
                       "--result", str(result), "--temp", str(worker_tmp),
                       "--expected-sha", source_hash], env_child)
            result_paths[name] = result
        arms = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in result_paths.items()}
        baseline = {row["id"]: row for row in arms["baseline"]["cases"]}
        for name in ("or", "umbral2"):
            for row in arms[name]["cases"]:
                prev = baseline[row["id"]]
                prev_names = [r["concepto"] for r in prev["results"]]
                now_names = [r["concepto"] for r in row["results"]]
                prev_ctx = [r["concepto"] for r in prev["expanded_context"]]
                now_ctx = [r["concepto"] for r in row["expanded_context"]]
                row["baseline_top5_missing"] = [x for x in prev_names if x not in now_names]
                row["baseline_context_missing"] = [x for x in prev_ctx if x not in now_ctx]
                row["top1_changed"] = bool(prev_names and now_names and prev_names[0] != now_names[0])
                row["score_deltas_for_shared"] = {
                    n: round(next(r["score"] for r in row["results"] if r["concepto"] == n)
                             - next(r["score"] for r in prev["results"] if r["concepto"] == n), 6)
                    for n in set(prev_names) & set(now_names)
                }
        summary = {
            "audit_head": head, "source_sha256": source_hash,
            "motor_sha256": hashlib.sha256((ROOT / "core/memory/search.py").read_bytes()).hexdigest(),
            "fixture_scope": "E3A inventada + tres recuerdos y dos enlaces manuales sintéticos",
            "paired_base": True, "source_unchanged_after_runs": sha256(source) == source_hash,
            "patches_unapplied_in_checkout": True,
            "arms": {name: {"median_search_ms": round(statistics.median(
                [c["search_ms_median_three_runs"] for c in arm["cases"]]), 3),
                "cases": len(arm["cases"])} for name, arm in arms.items()},
            "focus": "see per-case files for mixed alphabets, connectors, Japanese control, costs, ranking and context",
        }
        (out / "resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8")
    print(f"Paired synthetic controls saved to {out}")
    print("Three arms use copies of one source DB; OR and threshold patches were applied only under tempdir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
