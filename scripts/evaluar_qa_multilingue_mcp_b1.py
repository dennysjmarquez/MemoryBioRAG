#!/usr/bin/env python3
"""E3B1: ejecuta solo el brazo A de la QA MCP E3A, sin modificar el gold.

PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_multilingue_mcp_b1.py \
  --verificar-orden --salida docs/e3b1_mcp_brazo_a_20261027.json

Reutiliza las mismas funciones de E3A: 120 recuerdos guardados directamente,
sin sustantivos guardados, y 132 consultas a _recordar_impl sobre copias. No
simula guardado MCP multilingüe: eso corresponde a B2. No abre la base real.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unicodedata
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluar_qa_multilingue_e3a import IDIOMAS, RELOJ_FIJO, cargar_gold, crear_base, sha256
from scripts.evaluar_qa_multilingue_mcp_e3a import LABELS, cargar_sustantivos, ejecutar_brazo


def marcar_pendiente_hueco_1(brazo: dict) -> None:
    """Marca, sin convertirlos en aciertos, los rechazos por un único carácter."""
    marcados = []
    for caso in brazo["casos"]:
        termino = unicodedata.normalize("NFC", caso.get("termino_invalido") or "")
        es_hueco = (
            caso.get("error") == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"
            and len(termino) == 1
            and (unicodedata.category(termino)[0] in "LMN" or termino == "_")
        )
        caso["marca_auditoria"] = "pendiente hueco 1" if es_hueco else None
        if es_hueco:
            marcados.append(caso)
    brazo["pendiente_hueco_1"] = {
        "total": len(marcados),
        "por_idioma": {idioma: sum(c["idioma"] == idioma for c in marcados) for idioma in IDIOMAS},
        "ids": [c["id"] for c in marcados],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--verificar-orden", action="store_true")
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        parser.error("Inicia con PYTHONHASHSEED=0 BIORAG_NEURONA=0")
    casos = cargar_gold()
    labels = cargar_sustantivos(casos)
    inicio = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="biorag_e3b1_mcp_a_") as tmp:
        carpeta = Path(tmp)
        # Mismo entorno aislado que el brazo A del arnés E3A.
        env = {"BIORAG_PATH": str(carpeta / "acceso_auxiliar.db"),
               "BIORAG_AUTOGUARDADO_HEURISTICO": "0",
               "BIORAG_MCP_AUTO_PARAFRASIS": "0", "BIORAG_MCP_AUTO_DIMS": "0"}
        with patch.dict(os.environ, env), patch("time.time", return_value=RELOJ_FIJO):
            path = carpeta / "base_directa.db"
            base = crear_base(path, casos)
            print("Brazo A: 120 recuerdos directos, sin sustantivos guardados.", flush=True)
            brazo = ejecutar_brazo(path, casos, labels, carpeta, False, args.verificar_orden)
        marcar_pendiente_hueco_1(brazo)
        salida = {
            "metadatos": {"gold_sha256": sha256(ROOT / "scripts" / "casos_qa_multilingue_e3a.jsonl"),
                          "sustantivos_sha256": sha256(LABELS), "reloj_fijo_unix": RELOJ_FIJO,
                          "pythonhashseed": "0", "biorag_neurona": "0",
                          "profundidad": "activos", "limite_publico": 5, "limite_interno_mcp": 15,
                          "ignore_peso_sinaptico": "no expuesto por recordar; usa el default del motor",
                          "aislamiento": "base temporal; copia nueva por consulta; buffer limpio",
                          "sin_parafrasis_ni_rafaga_ni_dimensiones": True,
                          "duracion_s": round(time.perf_counter() - inicio, 2)},
            "base_directa": base, "recordar_sobre_base_directa": brazo,
        }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nidioma | positivos ejecutados | R@5 | R@1 | errores | FP/negativos ejecutados")
    for lang in IDIOMAS:
        s = brazo["metricas"][lang]
        print(f"{lang:6} | {s['ejecutados_positivos']:2}/{s['positivos']} | "
              f"{s['aciertos_r5']:2}/{s['positivos']} | {s['aciertos_r1']:2}/{s['positivos']} | "
              f"{s['rechazos_positivos']:2} | {s['falsos_positivos']}/{s['negativos_ejecutados']}")
    print("Pendiente hueco 1:", brazo["pendiente_hueco_1"]["total"],
          "casos:", ", ".join(brazo["pendiente_hueco_1"]["ids"]))
    print("Orden inverso, casos diferentes:", len(brazo["verificacion_orden"]["diferentes"]))
    print("Salida:", args.salida)
    return 1 if brazo["verificacion_orden"]["diferentes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
