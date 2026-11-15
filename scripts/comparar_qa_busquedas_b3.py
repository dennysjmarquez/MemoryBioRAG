#!/usr/bin/env python3
"""Compara búsquedas FastMCP B2/B3 con controles de base y hub ON/OFF.

En cada semilla B2 y B3 compara dos motores sobre las mismas copias byte a
byte. Además informa pérdidas de R@5/R@1 entre las dos semillas para los 36
casos guardados en ambos brazos; el crecimiento cambia el corpus, por lo que
esa segunda comparación no aísla el efecto de la validación. Los fragmentos
sin nombre son genéricos, repetidos en cada idioma y no identifican un nodo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
HUB_B2 = "0c76c787346746a669f68a3609b01cdac36322ff4350bff15a7d8cd86eecdf4c"
HUB_B3 = "50cdced5342eb255abcd1ea9ab0781ab677ec518b173bc3855a32c0be9b618cf"
CORPUS = "fed44d525fe037a4ffd596a5b5bda24129ca22727474518b5425dd805954c35c"
TIPOS = ("nombre", "puente_completo", "fragmento_sin_nombre")
IDIOMAS = ("zh", "ja", "ko", "ru")


def por_vista(datos: dict) -> dict[tuple[str, str], dict]:
    filas = datos["casos"]
    resultado = {(r["id"], r["tipo"]): r for r in filas}
    if len(filas) != len(resultado):
        raise ValueError("Búsquedas duplicadas")
    return resultado


def comparar_misma_base(b2: dict, b3: dict) -> tuple[dict, list[str]]:
    problemas = []
    ma, mb = b2["metadatos"], b3["metadatos"]
    if ma["semilla"] != mb["semilla"]:
        problemas.append("Las dos versiones no usan exactamente la misma semilla")
    for key in ("corpus_sha256", "reloj_fijo_unix", "pythonhashseed", "biorag_neurona", "profundidad",
                "limite_publico", "limite_interno_mcp", "ignore_peso_sinaptico", "control_hub"):
        if ma[key] != mb[key]:
            problemas.append(f"Parámetro distinto: {key}")
    if ma["hub_sha256"] != HUB_B2 or mb["hub_sha256"] != HUB_B3 or ma["corpus_sha256"] != CORPUS:
        problemas.append("Huella de código o del corpus incorrecta")
    a, b = por_vista(b2), por_vista(b3)
    if a.keys() != b.keys():
        problemas.append("No coinciden los casos y las vistas de consulta")
    diferentes = []
    for key in sorted(a.keys() & b.keys()):
        x, y = a[key], b[key]
        if any(x[k] != y[k] for k in ("query", "sustantivos_clave", "contiene_nombre", "concepto")):
            problemas.append(f"{key}: consulta o entrada distinta")
        if bool(x["contiene_nombre"]) != (x["tipo"] != "fragmento_sin_nombre"):
            problemas.append(f"{key}: marca de nombre incorrecta")
        for modo in ("on", "off"):
            if x[modo] != y[modo]:
                diferentes.append({"id": key[0], "tipo": key[1], "hub": modo})
            if modo == "off" and (x[modo]["last_hub_expansion"] or y[modo]["last_hub_expansion"]):
                problemas.append(f"{key}: hay expansión con el hub apagado")
    if diferentes:
        problemas.append(f"Las respuestas o las trazas difieren en {len(diferentes)} llamadas")
    return {"sha256_semilla": ma["semilla"]["sha256"], "vistas_comparadas": len(a),
            "llamadas_comparadas_por_version": len(a) * 2,
            "respuestas_o_trazas_diferentes": diferentes}, problemas


def comparar_crecimiento(antes: dict, despues: dict) -> dict:
    a, b = por_vista(antes), por_vista(despues)
    comunes = a.keys() & b.keys()
    if len(comunes) != len(a):
        raise ValueError("La base nueva no conserva todas las vistas previamente guardadas")
    campos = {}
    for modo in ("on", "off"):
        for metrica in ("acierto_r5", "acierto_r1"):
            perdidas = [{"id": k[0], "tipo": k[1]} for k in sorted(comunes)
                        if a[k][modo][metrica] and not b[k][modo][metrica]]
            ganancias = [{"id": k[0], "tipo": k[1]} for k in sorted(comunes)
                         if not a[k][modo][metrica] and b[k][modo][metrica]]
            campos[f"{modo}_{metrica}"] = {"perdidas": perdidas, "ganancias": ganancias}
    return {"vistas_comunes": len(comunes), "casos_comunes": len({k[0] for k in comunes}),
            "metricas": campos,
            "nota": "las semillas tienen distinta cantidad de recuerdos; no es comparación de código aislado"}


def resumen_expansiones_cjk(datos: dict) -> dict:
    grupo = [r for r in datos["casos"] if r["idioma"] in ("zh", "ja") and r["tipo"] == "puente_completo"]
    hub_correcto = 0
    origen_hub = 0
    sin_entrega = 0
    for row in grupo:
        esperado = row["concepto"].lower().replace(" ", "_").strip()
        expansion = row["on"]["last_hub_expansion"] or {}
        hub_correcto += esperado in expansion.get("canonical_nodes", [])
        origen = row["on"]["origen_esperado"] or []
        origen_hub += bool(origen and origen[0] == "concept_hub")
        sin_entrega += not row["on"]["acierto_r5"]
    return {"puentes_chino_japones": len(grupo), "expansion_al_nodo_correcto": hub_correcto,
            "origen_esperado_concept_hub": origen_hub, "sin_nodo_en_top5": sin_entrega,
            "nota": "la expansión y el origen son trazas internas, no equivalen a un resultado entregado"}


def tabla_busquedas(resumen: dict) -> str:
    lines = ["# E3B3 — búsquedas MCP posteriores", "",
             "Cada celda muestra aciertos R@5 con hub **ON / OFF**. Son copias de la misma base B3.",
             "El puente completo contiene el nombre; el fragmento sin nombre es genérico y repetido.", "",
             "| Idioma | Guardados buscados | Nombre ON/OFF | Puente completo ON/OFF | Fragmento sin nombre ON/OFF |",
             "|---|---:|---:|---:|---:|"]
    for idioma in IDIOMAS:
        r = resumen[idioma]
        n = r["nombre"]["casos"]
        cells = [f"{r[t]['on_r5']}/{r[t]['off_r5']}" for t in TIPOS]
        lines.append(f"| {idioma} | {n} | " + " | ".join(cells) + " |")
    lines += ["", "Un hallazgo por nombre o por una frase que contiene el nombre no demuestra recuperación independiente por puente.",
              "Las consultas sin nombre son iguales para muchos nodos y no constituyen una prueba semántica concluyente.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--tabla", type=Path)
    args = parser.parse_args()
    datos = {}
    for base in ("b2", "b3"):
        for hub in ("b2", "b3"):
            path = DOCS / f"e3b3_busquedas_hub_{hub}_base_{base}_20261028.json"
            datos[(hub, base)] = json.loads(path.read_text(encoding="utf-8"))
    comparaciones, problemas = {}, []
    for base in ("b2", "b3"):
        r, p = comparar_misma_base(datos[("b2", base)], datos[("b3", base)])
        comparaciones[base] = r
        problemas.extend(f"base {base}: {x}" for x in p)
    crecimiento = comparar_crecimiento(datos[("b2", "b2")], datos[("b3", "b3")])
    for metrica, valor in crecimiento["metricas"].items():
        if valor["perdidas"]:
            problemas.append(f"{metrica}: pérdidas en base crecida {valor['perdidas']}")
    actual = datos[("b3", "b3")]
    resultado = {
        "misma_base_b2_vs_b3": comparaciones, "comparacion_base_crecida": crecimiento,
        "b3_por_idioma_y_tipo": actual["resumen"]["por_idioma"],
        "b3_expansion_chino_japones": resumen_expansiones_cjk(actual),
        "consultas_mcp_totales": sum(d["resumen"]["consultas_mcp"] for d in datos.values()),
        "sin_regresion_detectada": not problemas, "problemas": problemas,
        "limitaciones": "FastMCP en proceso; frases sintéticas, nombre dentro del puente completo, fragmentos genéricos.",
    }
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.tabla:
        args.tabla.parent.mkdir(parents=True, exist_ok=True)
        args.tabla.write_text(tabla_busquedas(resultado["b3_por_idioma_y_tipo"]), encoding="utf-8")
    print("Consultas MCP totales:", resultado["consultas_mcp_totales"])
    for base, c in comparaciones.items():
        print(f"Misma base {base}: {c['llamadas_comparadas_por_version']} llamadas por versión; "
              f"respuestas o trazas diferentes {len(c['respuestas_o_trazas_diferentes'])}")
    print("Base crecida: casos comunes", crecimiento["casos_comunes"])
    for idioma in IDIOMAS:
        r = resultado["b3_por_idioma_y_tipo"][idioma]
        print(idioma, "; ".join(f"{t} ON/OFF {r[t]['on_r5']}/{r[t]['off_r5']}/{r[t]['casos']}" for t in TIPOS))
    print("Chino/japonés:", resultado["b3_expansion_chino_japones"])
    for problema in problemas:
        print("-", problema)
    print("Sin regresión en búsquedas medidas:", resultado["sin_regresion_detectada"])
    return int(bool(problemas))


if __name__ == "__main__":
    sys.exit(main())
