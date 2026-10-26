#!/usr/bin/env python3
"""Construye copias del snapshot con UN HUB POR RECUERDO, como hace hoy `aprender`.

El snapshot oficial tiene 6 hubs / 30 puentes; una base real tiene ~1 hub por recuerdo
(la base viva de Dennys: 1086 hubs / 5025 puentes). Estas copias reproducen esa escala
para medir el concept hub en condiciones reales. El snapshot NO se toca: se copia.

  H-todos : cada recuerdo tiene su hub (usuario nuevo que empieza de cero con v35).
  H-mitad : solo la mitad MÁS NUEVA tiene hub (imita la historia de la base viva:
            los recuerdos viejos nacieron antes de que `aprender` exigiera puentes).

Los 5 puentes salen de los datos del propio recuerdo (aproximación honesta de lo que
escribe un agente): sinonimo = sus sinónimos; problema / solucion / ingenuo = frases de
su contenido; situacion = sus sustantivos clave (o una frase más). Determinista.

Uso: python3 construir_copias.py SNAPSHOT DESTINO_DIR
"""
import os
import re
import sqlite3
import sys
import time


def frases(texto):
    texto = re.sub(r"[#*`>|\[\]{}()]", " ", texto or "")
    partes = [p.strip() for p in re.split(r"(?<=[.!?:;])\s+|\n+", texto) if p.strip()]
    out = []
    for p in partes:
        palabras = re.findall(r"[\wáéíóúñü\-]+", p, flags=re.I)
        if len(palabras) >= 4:
            out.append(" ".join(palabras[:16]).lower())
    return out


def puentes_de(sinonimos, contenido, sustantivos):
    fr = frases(contenido)
    syn = " ".join(t.strip() for t in re.split(r"[,;]", sinonimos or "") if t.strip())
    syn = " ".join(syn.split()[:15])
    sus = " ".join(t.strip() for t in re.split(r"[,;]", sustantivos or "") if t.strip())
    cand = {
        "sinonimo": syn,
        "problema": fr[0] if len(fr) > 0 else "",
        "solucion": fr[1] if len(fr) > 1 else "",
        "situacion": sus or (fr[2] if len(fr) > 2 else ""),
        "ingenuo": fr[-1] if len(fr) > 3 else "",
    }
    return [(a, t) for a, t in cand.items() if len(t.split()) >= 1]


def construir(snapshot, destino, modo):
    src = sqlite3.connect(f"file:{snapshot}?mode=ro&immutable=1", uri=True)
    dst = sqlite3.connect(destino)
    src.backup(dst)
    src.close()
    filas = dst.execute(
        "SELECT concepto, sinonimos, contenido, sustantivos_clave, creado_en FROM largo_plazo "
        "ORDER BY creado_en, rowid").fetchall()
    if modo == "mitad":
        filas = filas[len(filas) // 2:]
    ya = {r[0] for r in dst.execute("SELECT canonical_node FROM concept_hubs")}
    n_h = n_b = 0
    for concepto, syn, cont, sus, _ in filas:
        if concepto in ya:
            continue
        hub = f"hub_{concepto}"
        dst.execute("INSERT OR IGNORE INTO concept_hubs (hub_id, canonical_node, description, created_at) "
                    "VALUES (?,?,?,?)", (hub, concepto, "Bridges obligatorios desde aprender", time.time()))
        dst.execute("INSERT OR IGNORE INTO concept_hub_nodes (hub_id, node_concepto, role) "
                    "VALUES (?,?,'canonical')", (hub, concepto))
        n_h += 1
        for angulo, texto in puentes_de(syn, cont, sus):
            cur = dst.execute("INSERT OR IGNORE INTO concept_hub_bridges (hub_id, bridge_text, angle, weight) "
                              "VALUES (?,?,?,1.0)", (hub, texto, angulo))
            n_b += cur.rowcount
    dst.commit()
    tot_h = dst.execute("SELECT COUNT(*) FROM concept_hubs").fetchone()[0]
    tot_b = dst.execute("SELECT COUNT(*) FROM concept_hub_bridges").fetchone()[0]
    ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
    dst.close()
    print(f"{os.path.basename(destino)}: +{n_h} hubs / +{n_b} puentes → total {tot_h} hubs / {tot_b} puentes | integridad {ok}")


if __name__ == "__main__":
    snap, carpeta = sys.argv[1], sys.argv[2]
    os.makedirs(carpeta, exist_ok=True)
    for modo in ("todos", "mitad"):
        ruta = os.path.join(carpeta, f"H_{modo}.db")
        if os.path.exists(ruta):
            os.remove(ruta)
        construir(snap, ruta, modo)
