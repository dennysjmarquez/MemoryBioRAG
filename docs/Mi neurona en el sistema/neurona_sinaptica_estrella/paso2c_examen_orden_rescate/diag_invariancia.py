"""Diagnóstico posterior del Paso 2c (sin puerta): ¿de dónde vienen los fallos de invariancia C2/O2?

Lee las bases y repasos de /tmp/paso2c (los deja `examen_orden_rescate.py`) y clasifica cada pista elegible cuyo top-5
cambia entre D y DI:
- entra_un_I: un recuerdo de I entra en el top-5 (el buscador es difuso, raíces y trigramas, y lo considera
  coincidencia aunque no contenga las unidades exactas de la pista);
- cambio_estado_D: algún recuerdo de D implicado cambió de estado (activo/dormido) al añadir I;
- mismo_conjunto_otro_orden / cambia_un_D_por_otro_D: el resto.
Mide además la invariancia como **orden relativo de los recuerdos de D** (la forma de la NORMA MÁXIMA que admite que un
recuerdo nuevo que sí coincide entre en la lista): el top de DI filtrado a D debe ser un prefijo del top de D.
Escribe resultados/diagnostico_invariancia.json.
"""
import json
import os

import examen_orden_rescate as e

AQUI = os.path.dirname(os.path.abspath(__file__))


def un(m, lg):
    d = os.path.join(e.TMP, m, lg)
    rD = json.load(open(os.path.join(d, "rep_D.json")))["registros"]
    rI = json.load(open(os.path.join(d, "rep_DI.json")))["registros"]
    vecD = json.load(open(os.path.join(d, "vec_D.json")))
    vecI = json.load(open(os.path.join(d, "vec_DI.json")))
    estD, estI = vecD["estado"], vecI["estado"]
    enD = set(estD)
    k = {(g["x"], g["pista"]): g for g in rD}
    cl = {"fallos": 0, "entra_un_I": 0, "cambio_estado_D": 0, "mismo_conjunto_otro_orden": 0,
          "cambia_un_D_por_otro_D": 0}
    rel_ok = 0
    for g in rI:
        a, bb = k[(g["x"], g["pista"])]["top"][:5], g["top"][:5]
        a6, b6 = k[(g["x"], g["pista"])]["top"][:6], [c for c in g["top"][:6] if c in enD]
        rel_ok += (a6[:len(b6)] == b6) if b6 else (len(a6) == 0)
        if a == bb:
            continue
        cl["fallos"] += 1
        if any(c not in enD for c in bb):
            cl["entra_un_I"] += 1
        elif any(estD.get(c) != estI.get(c) for c in set(a) | set(bb) | {g["x"]}):
            cl["cambio_estado_D"] += 1
        elif set(a) == set(bb):
            cl["mismo_conjunto_otro_orden"] += 1
        else:
            cl["cambia_un_D_por_otro_D"] += 1
    elD = [k[(g["x"], g["pista"])] for g in rI]
    QD, QI = e.preguntas_orden(elD, vecD, enD), e.preguntas_orden(rI, vecI, enD)
    solo = [kk for kk in QI if kk not in QD]
    return {
        "C2_clasificacion_de_fallos": cl,
        "C2_orden_relativo_D": "%d/%d" % (rel_ok, len(rI)),
        "C2_orden_relativo_D_frac": round(rel_ok / len(rI), 4),
        "O2_faltan_en_DI": sum(1 for kk in QD if kk not in QI),
        "O2_puesto_D_distinto": sum(1 for kk, q in QD.items() if kk in QI and QI[kk]["puesto_D"] != q["puesto_D"]),
        "O2_solo_en_DI": len(solo),
        "O2_solo_en_DI_con_A_de_I": sum(1 for kk in solo if kk[0] not in enD),
        "D_que_cambian_de_estado": sum(1 for c in enD if estD.get(c) != estI.get(c)),
    }


if __name__ == "__main__":
    out = {m: {lg: un(m, lg) for lg in e.b.IDIOMAS} for m in e.VARIANTES}
    json.dump(out, open(os.path.join(AQUI, "resultados", "diagnostico_invariancia.json"), "w"),
              ensure_ascii=False, indent=1)
    for m, v in out.items():
        for lg, r in v.items():
            print(m, lg, r["C2_orden_relativo_D"], r["C2_orden_relativo_D_frac"], r["C2_clasificacion_de_fallos"])
