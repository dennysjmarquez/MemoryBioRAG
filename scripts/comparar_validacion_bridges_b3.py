#!/usr/bin/env python3
"""Reproduce sondas B2/B3 sin escribir el snapshot ni cambiar el motor.

B2 se carga desde el commit indicado y se verifica su SHA-256. Se ejecutan el
validador real de B2 y el del árbol actual con los mismos 5 ángulos. El examen
incluye 14 negativos ES/EN, 5 puentes reales y los 30 puentes del snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import types
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REFERENCIA = "88f71bbbee9e340511d777b1b56d5d7ee8139802"
SHA_B2 = "0c76c787346746a669f68a3609b01cdac36322ff4350bff15a7d8cd86eecdf4c"
SHA_SNAPSHOT = "104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796"
SNAPSHOT = ROOT / "snapshots" / "qa_escape_qcr_20260811.db"
SONDAS = ("바다 등대", "우산 가게", "海岸的灯塔", "灯塔", "海辺の灯台", "que con", "go to", "??? @@@", "once lunas")
NEGATIVOS = ("que con", "de la casa", "una casa", "un error", "solo", "el y", "lo de",
             "go to", "to be", "will be", "go cat", "no and", "the", "x q")
EXTRAS = ("１２３４", "哈哈哈哈", "1234 5678", "jaja jaja", "水", "문", "ガラス")
COMPLEMENTOS = ("corte red general", "apagar encender motor", "periodo trabajo rural", "sin luces visibles")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cargar_b2():
    src = subprocess.run(["git", "show", f"{REFERENCIA}:core/concept_hub.py"], cwd=ROOT,
                         check=True, stdout=subprocess.PIPE).stdout
    if hashlib.sha256(src).hexdigest() != SHA_B2:
        raise RuntimeError("El módulo B2 no coincide con su huella")
    modulo = types.ModuleType("concept_hub_b2_de_git")
    exec(compile(src, f"git:{REFERENCIA}:core/concept_hub.py", "exec"), modulo.__dict__)
    return modulo


def verificar(fn, angulos, texto, clave="farol_costero") -> dict:
    items = [{"text": t, "angle": a} for t, a in zip((texto, *COMPLEMENTOS), angulos)]
    validos, rechazados = fn(items, clave)
    if not all(any(v["text"] == t for v in validos) for t in COMPLEMENTOS):
        raise RuntimeError(f"Falló un puente de control: {texto!r}")
    return {"aceptado": any(v["text"] == texto for v in validos),
            "validos": len(validos), "rechazos": rechazados}


def comparar() -> dict:
    from core import concept_hub as b3

    b2 = cargar_b2()
    if b2.ANGULOS_OFICIALES != b3.ANGULOS_OFICIALES:
        raise RuntimeError("Los ángulos oficiales cambiaron")
    angulos = b2.ANGULOS_OFICIALES

    def fila(texto, clave="farol_costero"):
        return {"texto": texto, "clave": clave,
                "b2": verificar(b2.validar_bridges, angulos, texto, clave),
                "b3": verificar(b3.validar_bridges, angulos, texto, clave)}

    sondas = [fila(texto) for texto in SONDAS]
    negativos = [fila(texto) for texto in NEGATIVOS]
    extras = [fila(texto) for texto in EXTRAS]
    extras.append(fila(unicodedata.normalize("NFD", "ガラス")))
    extras.append(fila("海辺の灯台", "海辺の灯台"))

    if any(Path(str(SNAPSHOT) + sufijo).exists() for sufijo in ("-wal", "-shm")):
        raise RuntimeError("El snapshot tiene un archivo WAL/SHM; no se usa immutable")
    antes = sha256(SNAPSHOT)
    if antes != SHA_SNAPSHOT:
        raise RuntimeError("El snapshot no coincide con la huella acordada")
    with sqlite3.connect(SNAPSHOT.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as con:
        filas = con.execute("""SELECT h.hub_id,h.canonical_node,b.bridge_text,b.angle,b.weight
                               FROM concept_hubs h JOIN concept_hub_bridges b USING(hub_id)
                               ORDER BY h.hub_id,b.bridge_id""").fetchall()
    if sha256(SNAPSHOT) != antes:
        raise RuntimeError("El snapshot cambió durante la lectura")
    if len(filas) != 30 or len({r[0] for r in filas}) != 6:
        raise RuntimeError("El snapshot no contiene los 30 puentes esperados")
    diferencias, reales = [], []
    for hub in sorted({r[0] for r in filas}):
        grupo = [r for r in filas if r[0] == hub]
        items = [{"text": r[2], "angle": r[3], "weight": r[4]} for r in grupo]
        av, _ = b2.validar_bridges(items, hub.removeprefix("hub_"))
        bv, _ = b3.validar_bridges(items, hub.removeprefix("hub_"))
        for item in items:
            fue = any(v["text"] == item["text"] and v["angle"] == item["angle"] for v in av)
            es = any(v["text"] == item["text"] and v["angle"] == item["angle"] for v in bv)
            dato = {"hub": hub, "canonical": grupo[0][1], **item, "b2": fue, "b3": es}
            if fue != es:
                diferencias.append(dato)
            if hub == "hub_arquitectura_memoria":
                reales.append(dato)
    problemas = []
    if any(r["b2"]["aceptado"] or r["b3"]["aceptado"] for r in negativos):
        problemas.append("Al menos un negativo fue aceptado")
    if len(reales) != 5 or any(not (r["b2"] and r["b3"]) for r in reales):
        problemas.append("Los cinco puentes reales no se aceptaron en ambos brazos")
    if diferencias:
        problemas.append("Cambió la decisión sobre puentes del snapshot")
    return {"referencia_git_b2": REFERENCIA, "sha256_b2": SHA_B2,
            "sha256_b3": sha256(ROOT / "core" / "concept_hub.py"), "sha256_snapshot": antes,
            "unicode": unicodedata.unidata_version, "sondas": sondas, "negativos_es_en": negativos,
            "extras": extras, "puentes_qa_0593": reales,
            "snapshot": {"hubs": 6, "puentes": len(filas), "cambios": diferencias}, "problemas": problemas}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    resultado = comparar()
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Sonda | B2 | B3")
    for r in resultado["sondas"]:
        print(f"{r['texto']} | {'acepta' if r['b2']['aceptado'] else 'rechaza'} | {'acepta' if r['b3']['aceptado'] else 'rechaza'}")
    print("Negativos ES/EN rechazados en B2 y B3:", sum(not r["b2"]["aceptado"] and not r["b3"]["aceptado"] for r in resultado["negativos_es_en"]))
    print("Puentes reales QA aceptados en ambos:", sum(r["b2"] and r["b3"] for r in resultado["puentes_qa_0593"]))
    print("Snapshot:", resultado["snapshot"]["puentes"], "puentes; cambios:", len(resultado["snapshot"]["cambios"]))
    for p in resultado["problemas"]:
        print("-", p)
    return int(bool(resultado["problemas"]))


if __name__ == "__main__":
    sys.exit(main())
