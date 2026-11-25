"""Traza paso a paso qué sinapsis crea el motor REAL al aprender y al consolidar.

Base nueva en /tmp (esquema del motor), recuerdos inventados de ejemplo; no abre ninguna base real
y no cambia el motor. Uso (desde la raíz del repo):
    PYTHONHASHSEED=1 HOME=/tmp/traza_home python "docs/Mi neurona en el sistema/estudio_nacimiento_aprender_consolidar/trazar.py"
"""
import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)

from core.memory_store import SQLiteMemoryBioRAG, normalizar_sustantivos_clave, normalizar_sustantivos_clave_exacto  # noqa
from core.mcp_server._shared import _resolver_dimensiones  # noqa
from core.sinapsis import auto_vincular, vincular_por_sinonimos  # noqa

D = {"entidad": ["objeto_fisico"], "intencion": ["intencion_documentar"]}
SESIONES = [
    [
        ("receta_salsa_tomate", "Salsa de tomate rojo maduro con ajo y albahaca, cocinar veinte minutos.",
         "salsa, tomate, receta italiana, rojo", "tomate,salsa,receta"),
        ("semaforo_rojo_transito", "El semaforo en rojo obliga a detenerse; pasarlo cuesta una multa.",
         "semaforo, luz roja, transito, rojo", "semaforo,transito,multa"),
        ("receta_pasta_tomate", "Pasta con salsa de tomate y queso parmesano rallado.",
         "pasta, tomate, receta", "pasta,tomate,queso"),
        ("configuracion_servidor_sistema", "Configuracion del sistema del servidor: version y protocolo de arranque.",
         "sistema, configuracion, servidor", "servidor,configuracion"),
    ],
    [
        ("sangre_donacion", "Donar sangre: los globulos rojos transportan oxigeno por el cuerpo.",
         "sangre, donacion, globulos rojos, rojo", "sangre,donacion,globulos"),
        ("sistema_backup", "Backup del sistema: version del protocolo de respaldo nocturno.",
         "sistema, backup, respaldo", "backup,respaldo"),
    ],
    [
        ("receta_pizza_tomate", "Pizza con salsa de tomate, queso y albahaca al horno.",
         "pizza, tomate, receta", "pizza,tomate,queso"),
        ("receta_tomate_frito", "Tomate frito casero: salsa de tomate con aceite y queso.",
         "tomate frito, salsa, receta", "tomate,salsa,aceite"),
    ],
]
# En la sesión 3, el agente pasa vincular_con: receta_tomate_frito -> receta_pizza_tomate (enlace manual).
VINCULAR_CON = {"receta_tomate_frito": "receta_pizza_tomate"}


def foto(con):
    return {(o, d): (round(p, 3), t, u is not None) for o, d, p, t, u in
            con.execute("SELECT origen, destino, peso, tipo, ultimo_uso FROM sinapsis")}


def diff(antes, despues):
    out = []
    for k, v in sorted(despues.items()):
        if k not in antes:
            out.append("  + %s -> %s  %s peso=%.2f%s" % (k[0], k[1], v[1], v[0], "  (ultimo_uso)" if v[2] else ""))
        elif antes[k] != v:
            out.append("  ~ %s -> %s  %s %.2f -> %s %.2f%s" % (k[0], k[1], antes[k][1], antes[k][0], v[1], v[0],
                                                             "  (ahora con ultimo_uso)" if v[2] and not antes[k][2] else ""))
    for k in sorted(set(antes) - set(despues)):
        out.append("  - %s -> %s  %s (borrada)" % (k[0], k[1], antes[k][1]))
    return out or ["  (nada)"]


def main():
    ruta = os.path.join(tempfile.mkdtemp(prefix="traza_", dir="/tmp"), "c.db")
    with contextlib.redirect_stdout(io.StringIO()):
        cer = SQLiteMemoryBioRAG(db_path=ruta)
    con = sqlite3.connect(ruta)
    print("Al abrir el cerebro (DMN del __init__):", len(foto(con)), "sinapsis")
    for n, ses in enumerate(SESIONES, 1):
        for concepto, contenido, syn, sk in ses:
            dims, _, err, _ = _resolver_dimensiones(cer, json.dumps(D))
            ex = normalizar_sustantivos_clave_exacto(sk)
            a = foto(con)
            with contextlib.redirect_stdout(io.StringIO()):
                cer.percibir_corto_plazo(concepto, contenido, syn, "General", dims, predicados=None,
                                         valencia_somatica=0.0, sustantivos_clave=normalizar_sustantivos_clave(ex),
                                         sustantivos_clave_exactos=ex)
                r1 = auto_vincular(cer, concepto, contenido)
                b = foto(con)
                r2 = vincular_por_sinonimos(cer, concepto, syn)
            c = foto(con)
            c_syn = c
            extra = None
            if concepto in VINCULAR_CON:
                cer.establecer_asociacion(concepto, VINCULAR_CON[concepto])
                cer.conn.commit()
                extra = diff(c, foto(con))
                c = foto(con)
            print("\n[sesión %d] aprender '%s'" % (n, concepto))
            print(" auto_vincular (el recuerdo está en corto_plazo; compara contra largo_plazo):")
            print("\n".join(diff(a, b)))
            print(" vincular_por_sinonimos:")
            print("\n".join(diff(b, c_syn)))
            if extra is not None:
                print(" vincular_con (establecer_asociacion):")
                print("\n".join(extra))
        a = foto(con)
        with contextlib.redirect_stdout(io.StringIO()):
            cer.ciclo_sueno_consolidacion()
        print("\n[sesión %d] consolidar (sueño):" % n)
        print("\n".join(diff(a, foto(con))))
        print(" estado:", dict(con.execute("SELECT estado, COUNT(*) FROM largo_plazo GROUP BY estado").fetchall()))
    print("\nTotal por tipo:", con.execute("SELECT tipo, COUNT(*) FROM sinapsis GROUP BY tipo").fetchall())
    print("\nSinapsis latentes (tabla aparte, se rehace entera en cada sueño):")
    for fila in con.execute("SELECT origen, destino, peso_atenuado, saltos, pmi_score, tiene_dim_comun "
                            "FROM sinapsis_latentes ORDER BY peso_atenuado DESC"):
        print("  %s ~> %s  peso=%.3f saltos=%d pmi=%.2f dim_comun=%d" % fila)


if __name__ == "__main__":
    main()
