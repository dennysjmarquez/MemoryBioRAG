#!/usr/bin/env python3
"""Compara las QA multilingües B1 con los resultados E3A, sin editar ninguna base.

python scripts/comparar_qa_multilingue_b1.py --salida docs/e3b1_comparacion_multilingue_20261027.json
La QA directa se compara caso a caso; en MCP se comparan íntegros los casos EN/ES,
se verifican las etiquetas y se identifican los rechazos «pendiente hueco 1».
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
HUECOS_ESPERADOS = {
    "zh-18", "ja-05", "ja-06", "ja-08", "ja-10", "ja-11", "ja-14",
    "ja-15", "ja-17", "ja-18", "ko-05", "ko-07", "ko-18", "ko-20",
}


def leer(nombre: str) -> dict:
    return json.loads((DOCS / nombre).read_text(encoding="utf-8"))


def casos_por_id(datos: list[dict]) -> dict[str, dict]:
    resultado = {caso["id"]: caso for caso in datos}
    if len(datos) != len(resultado):
        raise ValueError("IDs duplicados")
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    anterior = leer("e3a_multilingue_resultados_20261027.json")
    actual = leer("e3b1_directa_20261027.json")
    mcp_anterior = leer("e3a_mcp_resultados_20261027.json")
    mcp_actual = leer("e3b1_mcp_brazo_a_20261027.json")
    problemas = []

    if anterior["metadatos"]["gold_sha256"] != actual["metadatos"]["gold_sha256"]:
        problemas.append("La QA directa usa un gold distinto")
    casos_a = casos_por_id(anterior["casos"])
    casos_b = casos_por_id(actual["casos"])
    if set(casos_a) != set(casos_b) or len(casos_a) != 132:
        problemas.append("No coinciden los 132 IDs de la QA directa")
    distintos_directa = sorted(k for k in set(casos_a) & set(casos_b) if casos_a[k] != casos_b[k])
    if distintos_directa or anterior["metricas"] != actual["metricas"]:
        problemas.append(f"La QA directa cambió: {distintos_directa}")
    if actual["verificacion_orden_misma_base"]["diferentes"]:
        problemas.append("La QA directa depende del orden")

    met_a, met_b = mcp_anterior["metadatos"], mcp_actual["metadatos"]
    if met_a["gold_sha256"] != met_b["gold_sha256"] or met_a["sustantivos_sha256"] != met_b["sustantivos_sha256"]:
        problemas.append("La QA MCP usa gold o etiquetas distintos")
    a = mcp_anterior["recordar_sobre_base_directa"]
    b = mcp_actual["recordar_sobre_base_directa"]
    casos_a = casos_por_id(a["casos"])
    casos_b = casos_por_id(b["casos"])
    if set(casos_a) != set(casos_b) or len(casos_a) != 132:
        problemas.append("No coinciden los 132 IDs de MCP")
    en_es = {k for k in casos_a if casos_a[k]["idioma"] in ("en", "es")}
    diferentes_en_es = sorted(
        k for k in en_es & set(casos_b)
        if casos_a[k] != {campo: valor for campo, valor in casos_b[k].items() if campo != "marca_auditoria"}
    )
    if len(en_es) != 44 or diferentes_en_es:
        problemas.append(f"MCP EN/ES no coincide caso por caso: {diferentes_en_es}")
    if any(a["metricas"][lang] != b["metricas"][lang] for lang in ("en", "es")):
        problemas.append("Métricas MCP EN/ES distintas")
    for lang in ("zh", "ja", "ko", "ru", "en", "es"):
        anterior_lang, actual_lang = a["metricas"][lang], b["metricas"][lang]
        if anterior_lang["positivos"] != actual_lang["positivos"]:
            problemas.append(f"MCP {lang}: denominador positivo distinto")
        for campo in ("aciertos_r5", "aciertos_r1", "ejecutados_positivos"):
            if actual_lang[campo] < anterior_lang[campo]:
                problemas.append(f"MCP {lang}: bajó {campo}")
        if (anterior_lang["negativos_ejecutados"] == actual_lang["negativos_ejecutados"]
                and actual_lang["falsos_positivos"] > anterior_lang["falsos_positivos"]):
            problemas.append(f"MCP {lang}: aumentaron los falsos positivos")
    huecos = {k for k, c in casos_b.items() if c.get("marca_auditoria") == "pendiente hueco 1"}
    if huecos != HUECOS_ESPERADOS or b["pendiente_hueco_1"]["total"] != 14:
        problemas.append(f"Hueco 1 inesperado: {sorted(huecos)}")
    errores = {k for k, c in casos_b.items() if c["error"]}
    if errores != huecos:
        problemas.append(f"Rechazos distintos del hueco 1: {sorted(errores - huecos)}")
    if any(casos_b[k]["busqueda_ejecutada"] or casos_b[k]["falso_positivo"] is not None for k in huecos):
        problemas.append("Un rechazo se registró como búsqueda o abstención")
    if any(not c["busqueda_ejecutada"] for k, c in casos_b.items() if k not in huecos):
        problemas.append("Alguna consulta válida no llegó al motor")
    if b["verificacion_orden"]["diferentes"]:
        problemas.append("La QA MCP depende del orden")

    resultado = {"directa_casos_diferentes": distintos_directa,
                 "mcp_en_es_casos_diferentes": diferentes_en_es,
                 "pendiente_hueco_1": b["pendiente_hueco_1"],
                 "consultas_mcp_ejecutadas": sum(c["busqueda_ejecutada"] for c in casos_b.values()),
                 "mcp_metricas": b["metricas"], "problemas": problemas,
                 "cumple_multilingue": not problemas,
                 "solo_multilingue": True}
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("QA directa, casos diferentes:", len(distintos_directa))
    print("MCP EN/ES, respuestas diferentes:", len(diferentes_en_es))
    print("MCP consultas ejecutadas:", resultado["consultas_mcp_ejecutadas"], "/132")
    print("MCP pendiente hueco 1:", len(huecos), sorted(huecos))
    print("Comparación multilingüe:", "CUMPLE" if not problemas else "NO CUMPLE")
    for problema in problemas:
        print("-", problema)
    print("Las cuatro QA oficiales y pytest se validan aparte.")
    return int(bool(problemas))


if __name__ == "__main__":
    sys.exit(main())
