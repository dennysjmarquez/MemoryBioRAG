#!/usr/bin/env python3
"""Compara B3 con B2: directa, MCP A y los mismos 80 guardados.

Distingue la ausencia de regresiones de la expectativa adicional de aumento
por cada idioma zh/ja/ko. Las cuatro QA oficiales y las búsquedas posteriores
se comparan por separado.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
IDIOMAS = ("zh", "ja", "ko", "ru")


def cargar(nombre: str) -> dict:
    return json.loads((DOCS / nombre).read_text(encoding="utf-8"))


def por_id(filas: list[dict]) -> dict[str, dict]:
    resultado = {fila["id"]: fila for fila in filas}
    if len(resultado) != len(filas):
        raise ValueError("IDs duplicados")
    return resultado


def comparar_guardados(a: dict, b: dict) -> tuple[dict, list[str], list[str]]:
    problemas: list[str] = []
    expectativas: list[str] = []
    campos = ("gold_guardado_sha256", "write_sha256", "pythonhashseed", "biorag_neurona", "reloj_fijo_unix")
    if any(a["metadatos"][c] != b["metadatos"][c] for c in campos):
        problemas.append("Guardados: corpus, escritura o parámetros diferentes")
    if a["integridad"] != "ok" or b["integridad"] != "ok":
        problemas.append("Guardados: SQLite no pasó integrity_check")
    aa, bb = por_id(a["casos"]), por_id(b["casos"])
    if len(aa) != 80 or aa.keys() != bb.keys():
        problemas.append("Guardados: IDs distintos o no son 80")
    entrada = ("id", "idioma", "concepto", "sustantivos_guardado_entrada", "sustantivo_busqueda_previa")
    for key in sorted(aa.keys() & bb.keys()):
        x, y = aa[key], bb[key]
        if any(x[c] != y[c] for c in entrada):
            problemas.append(f"{key}: entrada cambió")
        for version, r in (("B2", x), ("B3", y)):
            if not r["busqueda_previa_ejecutada"] or not r["busqueda_previa_confirmada"]:
                problemas.append(f"{key}: búsqueda previa {version} no confirmada")
            if r["excepcion"] or r["error_consolidacion"] or r["guardado_en_db"] != r["confirmado_por_mcp"]:
                problemas.append(f"{key}: excepción o discrepancia MCP/SQLite en {version}")
            if r["guardado_en_db"] and (
                r["primer_rechazo"] is not None or not r["consolidado"] or r["puentes_guardados"] != 5
                or r["sustantivos_en_db"] != r["sustantivos_normalizados"]
            ):
                problemas.append(f"{key}: guardado {version} sin las cinco verificaciones")
            if not r["guardado_en_db"] and r["primer_rechazo"] != (r["respuesta_aprender"] or {}).get("codigo"):
                problemas.append(f"{key}: primer rechazo {version} no coincide")
        if x["guardado_en_db"] and not y["guardado_en_db"]:
            problemas.append(f"{key}: se guardó en B2 y no en B3")
    resultado = {}
    for idioma in IDIOMAS:
        ca = [r for r in aa.values() if r["idioma"] == idioma]
        cb = [r for r in bb.values() if r["idioma"] == idioma]
        if len(ca) != 20 or len(cb) != 20:
            problemas.append(f"{idioma}: no son 20 entradas en cada brazo")
        prev = sum(r["guardado_en_db"] for r in ca)
        actual = sum(r["guardado_en_db"] for r in cb)
        if actual < prev:
            problemas.append(f"{idioma}: guardados bajaron {prev}→{actual}")
        if idioma in ("zh", "ja", "ko") and actual <= prev:
            expectativas.append(f"{idioma}: no aumentaron los guardados ({prev}→{actual})")
        rechazos = []
        for r in cb:
            if not r["guardado_en_db"]:
                valor = (r["respuesta_aprender"] or {}).get("termino_invalido")
                rechazos.append({"id": r["id"], "codigo": r["primer_rechazo"],
                                 "termino_nfc": unicodedata.normalize("NFC", valor) if isinstance(valor, str) else None})
        ids_previos = {r["id"] for r in ca if r["guardado_en_db"]}
        ids_actuales = {r["id"] for r in cb if r["guardado_en_db"]}
        resultado[idioma] = {
            "intentos": len(cb), "guardados_b2": prev, "guardados_b3": actual,
            "ids_ganados": sorted(ids_actuales - ids_previos),
            "ids_perdidos": sorted(ids_previos - ids_actuales),
            "primeros_rechazos_b2": dict(Counter(r["primer_rechazo"] for r in ca if r["primer_rechazo"])),
            "primeros_rechazos_b3": dict(Counter(r["primer_rechazo"] for r in cb if r["primer_rechazo"])),
            "rechazos_b3": rechazos,
        }
    return resultado, problemas, expectativas


def comparar() -> dict:
    problemas = []
    directa_b2, directa_b3 = cargar("e3b2_directa_20261027.json"), cargar("e3b3_directa_20261028.json")
    mcp_b2, mcp_b3 = cargar("e3b2_mcp_brazo_a_20261027.json"), cargar("e3b3_mcp_brazo_a_20261028.json")
    guardado_b2, guardado_b3 = cargar("e3b2_guardado_nativo_20261027.json"), cargar("e3b3_guardado_nativo_20261028.json")
    parametros_directa = ("gold_sha256", "profundidad", "limite", "ignore_peso_sinaptico",
                          "biorag_neurona", "pythonhashseed", "reloj_fijo_unix")
    parametros_mcp = ("gold_sha256", "sustantivos_sha256", "profundidad", "limite_publico",
                      "limite_interno_mcp", "ignore_peso_sinaptico", "biorag_neurona", "pythonhashseed", "reloj_fijo_unix")
    for nombre, a, b, campos in (("directa", directa_b2, directa_b3, parametros_directa),
                                  ("MCP A", mcp_b2, mcp_b3, parametros_mcp)):
        if any(a["metadatos"][c] != b["metadatos"][c] for c in campos):
            problemas.append(f"{nombre}: corpus o parámetros diferentes")
    da, db = por_id(directa_b2["casos"]), por_id(directa_b3["casos"])
    ma, mb = mcp_b2["recordar_sobre_base_directa"], mcp_b3["recordar_sobre_base_directa"]
    ca, cb = por_id(ma["casos"]), por_id(mb["casos"])
    if len(da) != 132 or da.keys() != db.keys() or len(ca) != 132 or ca.keys() != cb.keys():
        problemas.append("No coinciden los 132 IDs en directa o MCP")
    diferentes_directa = sorted(k for k in da.keys() & db.keys() if da[k] != db[k])
    diferentes_mcp = sorted(k for k in ca.keys() & cb.keys() if ca[k] != cb[k])
    if diferentes_directa or directa_b2["metricas"] != directa_b3["metricas"]:
        problemas.append(f"Directa: diferencias por caso o métricas: {diferentes_directa}")
    if diferentes_mcp or ma["metricas"] != mb["metricas"]:
        problemas.append(f"MCP A: diferencias por caso o métricas: {diferentes_mcp}")
    if directa_b3["verificacion_orden_misma_base"]["diferentes"] or mb["verificacion_orden"]["diferentes"]:
        problemas.append("El orden inverso produce diferencias")
    huecos_b2 = {k for k, c in ca.items() if c.get("marca_auditoria") == "pendiente hueco 1"}
    huecos_b3 = {k for k, c in cb.items() if c.get("marca_auditoria") == "pendiente hueco 1"}
    if len(huecos_b3) != 14 or huecos_b2 != huecos_b3:
        problemas.append("Cambió el conjunto de 14 pendientes hueco 1")
    guardados, fallos_guardado, expectativas = comparar_guardados(guardado_b2, guardado_b3)
    problemas.extend(fallos_guardado)
    return {"directa_casos_diferentes": diferentes_directa, "mcp_a_casos_diferentes": diferentes_mcp,
            "pendiente_hueco_1": sorted(huecos_b3), "guardados": guardados,
            "problemas_de_regresion_o_metodo": problemas, "expectativas_de_aumento_no_cumplidas": expectativas,
            "sin_regresiones_en_estas_mediciones": not problemas,
            "aumento_zh_ja_ko_en_los_guardados": not expectativas,
            "qa_oficial_y_busquedas_posteriores_se_miden_aparte": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    resultado = comparar()
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Directa, casos diferentes:", len(resultado["directa_casos_diferentes"]))
    print("MCP A, casos diferentes:", len(resultado["mcp_a_casos_diferentes"]))
    print("Pendiente hueco 1:", len(resultado["pendiente_hueco_1"]))
    for lang, r in resultado["guardados"].items():
        print(f"{lang}: guardados {r['guardados_b2']}→{r['guardados_b3']}/{r['intentos']}; "
              f"ganados {len(r['ids_ganados'])}; perdidos {len(r['ids_perdidos'])}; rechazos B3 {r['primeros_rechazos_b3']}")
    for p in resultado["problemas_de_regresion_o_metodo"]:
        print("REGRESIÓN O MÉTODO:", p)
    for p in resultado["expectativas_de_aumento_no_cumplidas"]:
        print("EXPECTATIVA NO CUMPLIDA:", p)
    print("Sin regresión en estas mediciones:", resultado["sin_regresiones_en_estas_mediciones"])
    print("Aumento en zh/ja/ko:", resultado["aumento_zh_ja_ko_en_los_guardados"])
    print("QA oficiales y búsquedas posteriores se validan por separado.")
    return int(not resultado["sin_regresiones_en_estas_mediciones"] or not resultado["aumento_zh_ja_ko_en_los_guardados"])


if __name__ == "__main__":
    sys.exit(main())
