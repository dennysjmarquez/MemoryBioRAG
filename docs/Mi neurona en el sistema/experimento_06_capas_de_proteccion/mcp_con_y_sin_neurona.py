"""La neurona vista por un agente: herramienta MCP `recordar` con y sin neurona.

Para cada consulta: neurona apagada -> encendida -> apagada otra vez (si las dos
apagadas difieren es ruido del motor, p. ej. la ráfaga crea sinapsis, y se descuenta).

Invariantes que se exigen con la neurona encendida:
  1. mismos recuerdos en la respuesta (el top-10 que ve el agente);
  2. por POSICIÓN, los mismos números: score_hibrido, confianza_calibrada, nivel_certeza;
  3. mismas decisiones globales: total, trazabilidad (literal / paráfrasis / ráfaga / fallback).
Lo único que puede cambiar es QUÉ recuerdo ocupa cada uno de los 5 primeros puestos.

Uso (sobre una COPIA de una DB con campeón aprendido):
  BIORAG_PATH=/copia.db python mcp_con_y_sin_neurona.py --n 120 --salida res.json
"""
import argparse
import json
import os
import random
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
os.environ["BIORAG_NO_LOG"] = "1"


def sustantivos(q):
    ws = [w for w in re.findall(r"[a-z0-9_ñ]+", q.lower()) if 2 <= len(w) <= 15]
    from core.stopwords import STOPWORDS
    ws = [w for w in dict.fromkeys(ws) if w not in STOPWORDS]
    return ",".join(ws[:3])


def llamar(tools, q, sk, neurona):
    os.environ["BIORAG_NEURONA"] = neurona
    raw = tools["recordar"](query=q, sustantivos_clave=sk)
    d = json.loads(raw[raw.find("{"):])
    res = d.get("resultados", []) or []
    return dict(
        nombres=[r["concepto"] for r in res],
        por_posicion=[(r.get("score_hibrido"), r.get("confianza_calibrada"), r.get("nivel_certeza")) for r in res],
        globales=json.dumps({k: d.get(k) for k in ("total", "trazabilidad", "status", "mensaje")}, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--salida")
    a = ap.parse_args()
    casos = [json.loads(l) for l in open(os.path.join(REPO, "scripts", "casos_qa_baseline_v1.jsonl"), encoding="utf-8")]
    random.Random(7).shuffle(casos)
    import mcp_server as m
    tools = {t.name: t.fn for t in m._build_server()._tool_manager.list_tools()}
    from core.memory import neurona
    from core.memory_service import get_cerebro
    print("neurona:", json.dumps(neurona.resumen(get_cerebro()), default=str)[:200], flush=True)

    rep = dict(consultas=0, ruido=0, top5_cambiado=0, viol_nombres=0, viol_numeros=0, viol_globales=0, ejemplos=[])
    for c in casos:
        if rep["consultas"] >= a.n:
            break
        sk = sustantivos(c["query"])
        if not sk:
            continue
        off = llamar(tools, c["query"], sk, "0")
        on = llamar(tools, c["query"], sk, "1")
        off2 = llamar(tools, c["query"], sk, "0")
        rep["consultas"] += 1
        if off != off2:
            rep["ruido"] += 1
            continue
        if on["nombres"][:5] != off["nombres"][:5]:
            rep["top5_cambiado"] += 1
            if len(rep["ejemplos"]) < 5:
                rep["ejemplos"].append(dict(q=c["query"], cat=c["categoria"], esperado=c.get("concepto_esperado"),
                                            sin=off["nombres"][:5], con=on["nombres"][:5]))
        rep["viol_nombres"] += int(sorted(on["nombres"]) != sorted(off["nombres"]) or on["nombres"][5:] != off["nombres"][5:])
        rep["viol_numeros"] += int(on["por_posicion"] != off["por_posicion"])
        rep["viol_globales"] += int(on["globales"] != off["globales"])
    os.environ.pop("BIORAG_NEURONA", None)
    print(json.dumps({k: v for k, v in rep.items() if k != "ejemplos"}))
    for e in rep["ejemplos"]:
        print(json.dumps(e, ensure_ascii=False))
    if a.salida:
        json.dump(rep, open(a.salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
