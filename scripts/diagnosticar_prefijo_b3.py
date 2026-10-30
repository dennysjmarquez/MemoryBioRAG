#!/usr/bin/env python3
"""Audita, sin alterar el motor, el filtrado de 33 frases zh/ja de B3.

Reproduce la condición de PALABRA_PREFIJO sobre los cuatro campos guardados en
la semilla sintética B3, y cruza las trazas FastMCP ya obtenidas con B2 y B3.
No demuestra semántica y no propone ni aplica una reparación.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def palabra_prefijo(token: str, texto: str | None) -> bool:
    # Mismo predicado que SQLiteMemoryBioRAG.__init__, sin modificarlo.
    if not token or not texto:
        return False
    token_norm = token.lower().replace("_", " ").replace("-", " ")
    texto_norm = texto.lower().replace("_", " ").replace("-", " ")
    return re.search(r"\b" + re.escape(token_norm), texto_norm) is not None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semilla", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    from core.memory.search import _ORIGENES_NO_LITERALES

    def leer(hub: str) -> dict:
        return json.loads((ROOT / "docs" / f"e3b3_busquedas_hub_{hub}_base_b3_20261028.json").read_text(encoding="utf-8"))
    b2, b3 = leer("b2"), leer("b3")
    esperado_sha = b3["metadatos"]["semilla"]["sha256"]
    if b2["metadatos"]["semilla"]["sha256"] != esperado_sha or sha256(args.semilla) != esperado_sha:
        raise RuntimeError("La semilla o las trazas no coinciden")
    if any(Path(str(args.semilla) + sufijo).exists() for sufijo in ("-wal", "-shm")):
        raise RuntimeError("La semilla tiene WAL/SHM: no se puede leer como immutable")
    indice_b2 = {(r["id"], r["tipo"]): r for r in b2["casos"]}
    filas = []
    with sqlite3.connect(args.semilla.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as con:
        for caso in b3["casos"]:
            if caso["idioma"] not in ("zh", "ja") or caso["tipo"] != "puente_completo":
                continue
            id_vista = (caso["id"], caso["tipo"])
            previo = indice_b2[id_vista]
            concepto = caso["concepto"].lower().replace(" ", "_").strip()
            campos = con.execute("SELECT concepto, contenido, sinonimos, sustantivos_clave FROM largo_plazo WHERE concepto=?",
                                 (concepto,)).fetchone()
            if campos is None:
                raise RuntimeError(f"No se encontró {concepto} en la semilla")
            actual = caso["on"]
            tokens = re.findall(r"\w{3,}", (actual["last_query_motor"] or "").lower())
            flags = [palabra_prefijo(tokens[0], campo) for campo in campos] if len(tokens) == 1 else []
            expansion = actual["last_hub_expansion"] or {}
            filas.append({"id": caso["id"], "idioma": caso["idioma"], "query": caso["query"],
                          "token_motor": tokens, "prefijo_en_concepto_contenido_sinonimos_sustantivos": flags,
                          "canonical_detectado": concepto in expansion.get("canonical_nodes", []),
                          "origen": actual["origen_esperado"], "top5": actual["top5"],
                          "respuesta_y_traza_identicas_a_b2": previo["on"] == actual})
    resultado = {
        "semilla_sha256": esperado_sha, "archivo_motor_sha256": sha256(ROOT / "core/memory/search.py"),
        "concept_hub_en_origenes_no_literales": "concept_hub" in _ORIGENES_NO_LITERALES,
        "casos": filas,
        "resumen": {"total": len(filas), "un_token": sum(len(r["token_motor"]) == 1 for r in filas),
                    "sin_prefijo_en_cuatro_campos": sum(len(r["prefijo_en_concepto_contenido_sinonimos_sustantivos"]) == 4 and not any(r["prefijo_en_concepto_contenido_sinonimos_sustantivos"]) for r in filas),
                    "canonical_detectado": sum(r["canonical_detectado"] for r in filas),
                    "origen_concept_hub": sum(bool(r["origen"] and r["origen"][0] == "concept_hub") for r in filas),
                    "sin_resultados": sum(not r["top5"] for r in filas),
                    "identicas_a_b2": sum(r["respuesta_y_traza_identicas_a_b2"] for r in filas)},
        "interpretacion": "La traza y el predicado son compatibles con el descarte por PALABRA_PREFIJO; no se instrumentó ni modificó el punto interno del descarte.",
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("concept_hub es origen no literal:", resultado["concept_hub_en_origenes_no_literales"])
    for nombre, valor in resultado["resumen"].items():
        print(f"{nombre}: {valor}")
    print(resultado["interpretacion"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
