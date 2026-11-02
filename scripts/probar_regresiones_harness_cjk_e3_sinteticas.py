#!/usr/bin/env python3
"""Pruebas sintéticas de desbordamiento de vecinos y fallo FTS registrado.

Construye una SQLite temporal con conceptos inventados. No usa las consultas
japonesas ni datos gold/privados. Los dos diagnósticos se guardan como JSON en
un directorio nuevo indicado por --salida; los parches solo se aplican al árbol
temporal de la prueba forzada, nunca al checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = [
    "core", "middleware", "config", "biorag.py",
    "scripts/evaluar_qa_multilingue_e3a.py",
    "scripts/casos_qa_multilingue_e3a.jsonl",
]
HARNESS = ROOT / "scripts/evaluar_controles_extendidos_cjk_e3.py"
PATCH_OR = ROOT / "docs/e3_cjk_trigram_propuesta_NO_APLICAR_20261101.patch"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True,
                        help="Directorio nuevo para las evidencias sintéticas")
    parser.add_argument("--vecinos", type=int, default=8,
                        help="Cantidad de vecinos sintéticos; debe ser > 5")
    return parser.parse_args()


def _create_fixture(path: Path, neighbor_count: int) -> None:
    from core.memory_service import aprender
    from core.memory_store import SQLiteMemoryBioRAG

    memory = SQLiteMemoryBioRAG(str(path))
    try:
        with patch("time.time", return_value=1_793_059_200.0):
            aprender(memory, "e3_anchor_quartz", "e3anchorquartz beacon for isolated context test", consolidar=True)
            for index in range(1, neighbor_count + 1):
                aprender(
                    memory,
                    f"e3_neighbor_{index:02d}",
                    f"synthetic neighbor payload number {index:02d} unrelated to anchor query",
                    consolidar=True,
                )
        memory.conn.commit()
        if memory.conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("La fixture sintética no pasó integrity_check")
        if memory.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] != 0:
            raise RuntimeError("No se pudo evacuar el WAL de la fixture sintética")
    finally:
        memory.cerrar_sistema()


def test_neighbor_overflow(source: Path, output: Path, neighbor_count: int) -> dict:
    from core.memory_store import SQLiteMemoryBioRAG
    from scripts.evaluar_controles_extendidos_cjk_e3 import _result_rows

    os.environ["BIORAG_MAX_CONTEXTOS"] = str(max(50, neighbor_count + 1))
    os.environ["BIORAG_MAX_VECINOS_POR_NODO"] = str(max(6, neighbor_count + 1))
    primary_copy = output / "neighbor_primary.db"
    context_copy = output / "neighbor_context.db"
    shutil.copyfile(source, primary_copy)
    shutil.copyfile(source, context_copy)
    primary = SQLiteMemoryBioRAG(str(primary_copy))
    context = SQLiteMemoryBioRAG(str(context_copy))
    try:
        with patch("time.time", return_value=1_793_059_200.0):
            primaries, total = primary.buscar_por_frase(
                "e3anchorquartz", profundidad="activos", limite=5,
                context_window=0, ignore_peso_sinaptico=True,
            )
        names = [row[0] for row in primaries]
        if names != ["e3_anchor_quartz"]:
            raise AssertionError(f"La búsqueda base no quedó aislada al ancla: {names}")
        # Los enlaces se añaden únicamente a la copia de contexto, después de
        # obtener los primarios limpios. Así se prueba la expansión explícita,
        # no un efecto de spreading activation sobre el ranking primario.
        with patch("time.time", return_value=1_793_059_200.0):
            for index in range(1, neighbor_count + 1):
                context.establecer_asociacion("e3_anchor_quartz", f"e3_neighbor_{index:02d}")
            expanded_primaries, neighbors = context.expandir_contexto_vecinos(
                primaries, depth=1, profundidad="activos", preview_chars=1500,
            )
        primary_rows = _result_rows(primaries)
        expanded_primary_rows = _result_rows(expanded_primaries)
        all_neighbor_rows = _result_rows(neighbors, limit=None)
        expected = [f"e3_neighbor_{index:02d}" for index in range(1, neighbor_count + 1)]
        actual = [row["concepto"] for row in all_neighbor_rows]
        if len(actual) <= 5 or set(actual) != set(expected) or len(actual) != neighbor_count:
            raise AssertionError(f"La expansión perdió vecinos: esperado={expected}, actual={actual}")
        record = {
            "test": "context_neighbor_overflow",
            "query_sha256": hashlib.sha256("e3anchorquartz".encode("utf-8")).hexdigest(),
            "primary_count": len(primary_rows),
            "primary_concepts": [row["concepto"] for row in primary_rows],
            "explicit_expansion_preserves_primary_rows": primary_rows == expanded_primary_rows,
            "expected_neighbor_count": neighbor_count,
            "observed_neighbor_count": len(all_neighbor_rows),
            "all_neighbors_recorded": all_neighbor_rows,
            "complete_neighbor_set_preserved": set(actual) == set(expected),
            "more_than_five_neighbors": len(actual) > 5,
            "total_motor": total,
            "passed": True,
        }
        (output / "context_neighbors_overflow.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return record
    finally:
        primary.cerrar_sistema()
        context.cerrar_sistema()
        primary_copy.unlink(missing_ok=True)
        context_copy.unlink(missing_ok=True)


def test_forced_fts_error(source: Path, output: Path) -> dict:
    import importlib.util

    spec = importlib.util.spec_from_file_location("e3_harness", HARNESS)
    harness = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(harness)

    temp_root = Path(tempfile.mkdtemp(prefix="e3_forced_fts_"))
    app = temp_root / "app"
    app.mkdir()
    archive_bytes = subprocess.check_output(["git", "archive", "HEAD", *SOURCE_FILES], cwd=ROOT)
    archive_path = temp_root / "app.tar"
    archive_path.write_bytes(archive_bytes)
    with tarfile.open(archive_path) as archive:
        archive.extractall(app)
    data_dir = app / "MemoryBioRAG_Data"
    data_dir.mkdir()
    (data_dir / "nltk_data").symlink_to(ROOT / "MemoryBioRAG_Data/nltk_data", target_is_directory=True)
    scripts_dir = app / "scripts"
    shutil.copy2(HARNESS, scripts_dir / HARNESS.name)
    patch_result = subprocess.run(
        ["patch", "--batch", "--forward", "-p1", "-i", str(PATCH_OR)],
        cwd=app, check=True, text=True, capture_output=True,
    )
    harness._instrument_cjk_error_capture(app)
    run_root = temp_root / "forced_run"
    result_path = output / "forced_fts_error.json"
    env = os.environ.copy()
    env.pop("BIORAG_PATH", None)
    env.update({
        "HOME": str(temp_root), "PYTHONHASHSEED": "0", "BIORAG_NEURONA": "0",
        "BIORAG_NO_LOG": "1", "NLTK_DATA": str(ROOT / "MemoryBioRAG_Data/nltk_data"),
        "PYTHONPATH": str(app), "BIORAG_DMN_ESTADO_PATH": str(temp_root / "dmn.json"),
    })
    try:
        completed = subprocess.run(
            [sys.executable, str(scripts_dir / HARNESS.name),
             "--salida", str(output), "--worker", "forced_fts",
             "--source", str(source), "--temp", str(run_root), "--result", str(result_path)],
            cwd=app, env=env, check=False, text=True, capture_output=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Forced FTS worker failed: {completed.stderr[-3000:]}")
        record = json.loads(result_path.read_text(encoding="utf-8"))
        if not record.get("injected_failure_triggered") or not record.get("injected_error_recorded"):
            raise AssertionError(f"No se registró el OperationalError inyectado: {record}")
        record["temporary_patch_applied"] = bool(patch_result.stdout)
        return record
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def main() -> int:
    args = parse_args()
    if args.vecinos <= 5:
        raise SystemExit("--vecinos debe ser mayor que cinco")
    output = args.salida.resolve()
    if output.exists():
        raise SystemExit(f"La salida ya existe; elija un directorio nuevo: {output}")
    output.mkdir(parents=True)
    if not PATCH_OR.is_file():
        raise SystemExit("Falta el parche OR NO APLICAR")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("Inicie con PYTHONHASHSEED=0 antes de crear el intérprete")
    os.environ.pop("BIORAG_PATH", None)
    os.environ.update({
        "BIORAG_NEURONA": "0", "BIORAG_NO_LOG": "1",
        "NLTK_DATA": str(ROOT / "MemoryBioRAG_Data/nltk_data"),
    })
    source = output / "synthetic_context_fixture.db"
    _create_fixture(source, args.vecinos)
    source_hash = sha256(source)
    context_record = test_neighbor_overflow(source, output, args.vecinos)
    forced_record = test_forced_fts_error(source, output)
    if sha256(source) != source_hash:
        raise RuntimeError("La DB fuente sintética cambió durante las pruebas")
    source.unlink()
    manifest = {
        "suite": "synthetic E3 CJK harness regressions",
        "audit_scope": ["retain all explicit neighbors beyond five", "record injected CJK FTS OperationalError"],
        "neighbor_test_passed": context_record["passed"],
        "forced_fts_error_recorded": forced_record["injected_error_recorded"],
        "synthetic_source_sha256": source_hash,
        "context_result_sha256": sha256(output / "context_neighbors_overflow.json"),
        "forced_error_result_sha256": sha256(output / "forced_fts_error.json"),
        "engine_checkout_sha256": sha256(ROOT / "core/memory/search.py"),
        "patch_applied_only_in_temporary_tree": True,
        "original_source_unchanged": True,
    }
    (output / "summary.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Synthetic regression evidence saved to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
