#!/usr/bin/env python3
"""Compara B2 con B1 en las QA directa, MCP y el intento de guardado nativo.

Las dos primeras comparan los 132 casos caso a caso, sobre el mismo gold y
parámetros respectivos. La tercera es otro experimento: 80 entradas de guardado
con cinco puentes sintéticos en idioma nativo, base temporal y búsqueda previa.
No se comparan porcentajes entre experimentos con corpus o parámetros distintos.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
HUECOS = {"zh-18", "ja-05", "ja-06", "ja-08", "ja-10", "ja-11", "ja-14",
          "ja-15", "ja-17", "ja-18", "ko-05", "ko-07", "ko-18", "ko-20"}
IDIOMAS = ("zh", "ja", "ko", "ru")


def leer(nombre: str) -> dict:
    return json.loads((DOCS / nombre).read_text(encoding="utf-8"))


def casos(datos: list[dict]) -> dict[str, dict]:
    por_id = {x["id"]: x for x in datos}
    if len(por_id) != len(datos):
        raise ValueError("IDs duplicados")
    return por_id


def comparar() -> dict:
    problemas = []
    da, db = leer("e3b1_directa_20261027.json"), leer("e3b2_directa_20261027.json")
    ma, mb = leer("e3b1_mcp_brazo_a_20261027.json"), leer("e3b2_mcp_brazo_a_20261027.json")
    ga, gb = leer("e3b2_guardado_referencia_b1_20261027.json"), leer("e3b2_guardado_nativo_20261027.json")
    for nombre, a, b, campos in (
        ("directa", da["metadatos"], db["metadatos"], ("gold_sha256", "profundidad", "limite", "ignore_peso_sinaptico", "biorag_neurona", "pythonhashseed", "reloj_fijo_unix")),
        ("MCP A", ma["metadatos"], mb["metadatos"], ("gold_sha256", "sustantivos_sha256", "profundidad", "limite_publico", "limite_interno_mcp", "ignore_peso_sinaptico", "biorag_neurona", "pythonhashseed", "reloj_fijo_unix")),
    ):
        if any(a[k] != b[k] for k in campos):
            problemas.append(f"{nombre}: gold, etiquetas o parámetros distintos")
    directos_a, directos_b = casos(da["casos"]), casos(db["casos"])
    if len(directos_a) != 132 or directos_a.keys() != directos_b.keys():
        problemas.append("Directa: no están los mismos 132 casos")
    diferentes_directa = sorted(k for k in directos_a.keys() & directos_b.keys() if directos_a[k] != directos_b[k])
    if diferentes_directa or da["metricas"] != db["metricas"] or db["verificacion_orden_misma_base"]["diferentes"]:
        problemas.append(f"Directa: diferencias {diferentes_directa}")
    mcp_a, mcp_b = ma["recordar_sobre_base_directa"], mb["recordar_sobre_base_directa"]
    mcp_ca, mcp_cb = casos(mcp_a["casos"]), casos(mcp_b["casos"])
    if len(mcp_ca) != 132 or mcp_ca.keys() != mcp_cb.keys():
        problemas.append("MCP A: no están los mismos 132 casos")
    diferentes_mcp = sorted(k for k in mcp_ca.keys() & mcp_cb.keys() if mcp_ca[k] != mcp_cb[k])
    if diferentes_mcp or mcp_a["metricas"] != mcp_b["metricas"] or mcp_b["verificacion_orden"]["diferentes"]:
        problemas.append(f"MCP A: diferencias {diferentes_mcp}")
    huecos = {k for k, c in mcp_cb.items() if c.get("marca_auditoria") == "pendiente hueco 1"}
    errores = {k for k, c in mcp_cb.items() if c["error"]}
    if huecos != HUECOS or errores != HUECOS:
        problemas.append(f"MCP A: clasificación de pendientes inesperada: {sorted(huecos)}")
    if any(mcp_cb[k]["busqueda_ejecutada"] or mcp_cb[k]["falso_positivo"] is not None for k in huecos):
        problemas.append("MCP A: un rechazo figura como búsqueda o abstención")

    if ga["metadatos"]["gold_guardado_sha256"] != gb["metadatos"]["gold_guardado_sha256"]:
        problemas.append("Guardado: entradas B1/B2 distintas")
    campos = ("id", "idioma", "concepto", "sustantivos_guardado_entrada", "sustantivo_busqueda_previa")
    gca, gcb = casos(ga["casos"]), casos(gb["casos"])
    if len(gca) != 80 or gca.keys() != gcb.keys():
        problemas.append("Guardado: no están los mismos 80 casos")
    if ga["integridad"] != "ok" or gb["integridad"] != "ok":
        problemas.append("Guardado: integridad SQLite falló")
    for k in sorted(gca.keys() & gcb.keys()):
        anterior, actual = gca[k], gcb[k]
        if any(anterior[c] != actual[c] for c in campos):
            problemas.append(f"{k}: entrada cambió")
        for version, r in (("B1", anterior), ("B2", actual)):
            if (not r["busqueda_previa_ejecutada"] or not r["busqueda_previa_confirmada"] or
                    "resultados" not in (r["busqueda_previa"] or {})):
                problemas.append(f"{k}: búsqueda previa {version} no verificada")
            if r["excepcion"] or r["error_consolidacion"]:
                problemas.append(f"{k}: excepción {version}")
            if r["guardado_en_db"] != r["confirmado_por_mcp"]:
                problemas.append(f"{k}: MCP y DB no coinciden en {version}")
            if r["guardado_en_db"]:
                if (r["primer_rechazo"] is not None or not r["consolidado"] or r["puentes_guardados"] != 5 or
                        r["sustantivos_en_db"] != r["sustantivos_normalizados"]):
                    problemas.append(f"{k}: persistencia {version} no verificada")
            elif not r["primer_rechazo"] or r["primer_rechazo"] != (r["respuesta_aprender"] or {}).get("codigo"):
                problemas.append(f"{k}: primer rechazo {version} sin verificar")
        if anterior["guardado_en_db"] and not actual["guardado_en_db"]:
            problemas.append(f"{k}: B1 guardaba y B2 no")
    por_idioma = {}
    for lang in IDIOMAS:
        ca, cb = [x for x in gca.values() if x["idioma"] == lang], [x for x in gcb.values() if x["idioma"] == lang]
        if len(ca) != 20 or len(cb) != 20:
            problemas.append(f"Guardado: no hay 20 intentos por idioma en {lang}")
        a, b = sum(x["guardado_en_db"] for x in ca), sum(x["guardado_en_db"] for x in cb)
        if b < a:
            problemas.append(f"Guardado: bajó {lang} {a}→{b}")
        por_idioma[lang] = {"intentos": len(cb), "guardados_b1": a, "guardados_b2": b,
                           "primeros_rechazos_b1": dict(Counter(x["primer_rechazo"] for x in ca if x["primer_rechazo"])),
                           "primeros_rechazos_b2": dict(Counter(x["primer_rechazo"] for x in cb if x["primer_rechazo"]))}
    return {"directa_diferentes": diferentes_directa, "mcp_a_diferentes": diferentes_mcp,
            "pendiente_hueco_1": sorted(huecos), "guardado": por_idioma,
            "problemas": problemas, "cumple_multilingue_y_guardado": not problemas,
            "las_cuatro_qa_y_pytest_se_validan_aparte": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    resultado = comparar()
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Directa: casos diferentes", len(resultado["directa_diferentes"]))
    print("MCP A: casos diferentes", len(resultado["mcp_a_diferentes"]))
    print("Pendiente hueco 1:", len(resultado["pendiente_hueco_1"]))
    for lang, r in resultado["guardado"].items():
        print(f"{lang}: guardados {r['guardados_b1']}→{r['guardados_b2']}/{r['intentos']}; rechazos B2 {r['primeros_rechazos_b2']}")
    for p in resultado["problemas"]:
        print("-", p)
    print("Multilingüe y guardado:", "CUMPLE" if not resultado["problemas"] else "NO CUMPLE")
    print("Las cuatro QA oficiales y pytest se validan aparte.")
    return int(bool(resultado["problemas"]))


if __name__ == "__main__":
    sys.exit(main())
