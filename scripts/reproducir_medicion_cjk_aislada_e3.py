#!/usr/bin/env python3
"""Reproduce baseline y dos candidatos CJK de E3A en copias aisladas.

Requiere dependencias de requirements.txt y `patch`. No modifica core/: los dos
parches se aplican únicamente a copias temporales. `--salida` debe ser un
subdirectorio nuevo que recibirá baseline.json, candidato_or.json y umbral2.json.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import argparse

ROOT = Path(__file__).resolve().parents[1]
EVALUADOR = ROOT / "scripts" / "evaluar_qa_multilingue_e3a.py"
FIXTURE = ROOT / "scripts" / "casos_qa_multilingue_e3a.jsonl"
PATCHES = {
    "candidato_or": ROOT / "docs" / "e3_cjk_trigram_propuesta_NO_APLICAR_20261101.patch",
    "umbral2": ROOT / "docs" / "e3_cjk_trigram_umbral2_DIAGNOSTICO_NO_APLICAR_20261101.patch",
}


def ejecutar(cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def preparar_copia(candidate_root: Path) -> Path:
    shutil.copytree(ROOT / "core", candidate_root / "core")
    scripts = candidate_root / "scripts"
    scripts.mkdir()
    shutil.copy2(EVALUADOR, scripts / EVALUADOR.name)
    shutil.copy2(FIXTURE, scripts / FIXTURE.name)
    for name in ("config", "middleware", "MemoryBioRAG_Data"):
        (candidate_root / name).symlink_to(ROOT / name, target_is_directory=True)
    (candidate_root / "biorag.py").symlink_to(ROOT / "biorag.py")
    return scripts


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", type=Path, required=True,
                   help="Directorio nuevo para los JSON completos (sintéticos)")
    args = p.parse_args()
    out = args.salida.resolve()
    if out.exists():
        p.error(f"La salida ya existe; use una ruta nueva: {out}")
    if not EVALUADOR.is_file() or not FIXTURE.is_file() or any(not x.is_file() for x in PATCHES.values()):
        p.error("Falta el evaluador, la fixture sintética o uno de los parches de diagnóstico")
    out.mkdir(parents=True)

    env = os.environ.copy()
    env.pop("BIORAG_PATH", None)
    env.update({
        "PYTHONHASHSEED": "0",
        "BIORAG_NEURONA": "0",
        "BIORAG_NO_LOG": "1",
        "NLTK_DATA": str(ROOT / "MemoryBioRAG_Data" / "nltk_data"),
        "PYTHONPATH": str(ROOT),
    })
    ejecutar([sys.executable, str(EVALUADOR), "--verificar-orden",
              "--salida", str(out / "baseline.json")], ROOT, env)

    for variant, patch_path in PATCHES.items():
        with tempfile.TemporaryDirectory(prefix=f"e3_cjk_{variant}_") as tmp:
            candidate_root = Path(tmp)
            scripts = preparar_copia(candidate_root)
            ejecutar(["patch", "--batch", "-p1", "-i", str(patch_path)], candidate_root, env)
            env_candidate = env.copy()
            env_candidate["PYTHONPATH"] = str(candidate_root)
            ejecutar([sys.executable, str(scripts / EVALUADOR.name), "--verificar-orden",
                      "--salida", str(out / f"{variant}.json")], candidate_root, env_candidate)

    print(f"Listo. Resultados sintéticos completos: {out}")
    print("Las copias con parche se destruyen al terminar; core/ del checkout no se modifica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
