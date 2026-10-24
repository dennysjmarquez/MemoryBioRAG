"""BioRAG — Despertar la neurona: N ciclos de práctica seguidos sobre los recuerdos que ya existen.

POR QUÉ EXISTE
    La neurona (core/memory/neurona.py) aprende sola cada vez que se consolida un
    recuerdo: dos recuerdos x dos preguntas por consolidación, costo fijo. En una
    memoria nueva eso alcanza. En una memoria que YA tiene cientos de recuerdos y
    recibe pocos nuevos, juntar el examen y ascender el primer campeón puede tardar
    semanas. Este script hace en minutos lo mismo que haría el uso:

        for i in range(ciclos):
            neurona.practicar(db, [])      # idéntico a lo que corre tras cada consolidación

    No es otro entrenamiento ni otra configuración: es la MISMA práctica, con las
    MISMAS capas (guardia del 20 % que nunca se estudia, piso por categoría y por
    camino, margen "primero no dañar", retiro del campeón si daña algo).

QUÉ ESCRIBE
    Solo la tabla `neurona_estado` (verificado: 40 ciclos sobre una copia del
    snapshot -> de 49 tablas cambia solo `neurona_estado`). Abrir la DB, como
    cualquier arranque de BioRAG, corre además el arranque normal del motor.
    Deshacer: `--olvidar` (borra lo aprendido; vuelven los pesos a mano).

DÓNDE CORRERLO
    Sobre la MISMA DB que vas a usar (lo aprendido es de esa memoria; un campeón
    entrenado en otra DB y copiado daña, y el piso lo retira). Primero, si querés,
    sobre una copia + tu QA; después sobre la real. El snapshot congelado oficial
    (snapshots/) se rechaza: es la referencia de la QA.

USO
    python3 scripts/despertar_neurona.py                      # DB de producción (o BIORAG_PATH)
    python3 scripts/despertar_neurona.py ruta/copia.db --ciclos 300
    python3 scripts/despertar_neurona.py --estado             # solo mirar, no escribe
    python3 scripts/despertar_neurona.py --olvidar --si       # volver a los pesos a mano
"""
import argparse
import json
import os
import sqlite3
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)


def _db_por_defecto():
    return os.environ.get("BIORAG_PATH") or os.path.join(REPO, "MemoryBioRAG_Data", "memory_biorag.db")


def _pct(x):
    return "—" if x is None else f"{100 * float(x):.1f} %"


def _linea(titulo, r):
    u = r.get("ultimo") or {}
    print(f"  {titulo}")
    print(f"    campeón activo ......... {'sí' if r.get('campeon') else 'no (motor = fórmula a mano)'}")
    print(f"    margen 'no dañar' ...... {r.get('margen', 0.0)}")
    print(f"    examen (estudio/guardia) {r.get('estudio', 0)} / {r.get('guardia', 0)}")
    print(f"    ciclos · ascensos · retiros  {r.get('ciclos', 0)} · {r.get('ascensos', 0)} · {r.get('retiros', 0)}")
    print(f"    fase ................... {'tranquila (techo)' if r.get('tranquila') else u.get('fase', '—')}")
    if u.get("guardia_mano") is not None:
        print(f"    guardia #1: fórmula {_pct(u.get('guardia_mano'))}  ->  neurona {_pct(u.get('guardia_campeon'))}")


def _respaldo(db_path):
    destino = f"{db_path}.antes_despertar_{time.strftime('%Y%m%d_%H%M%S')}.db"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(destino)
    src.backup(dst)  # API backup de SQLite: copia consistente aun en WAL (no usar cp)
    dst.close()
    src.close()
    return destino


def main(argv=None):
    ap = argparse.ArgumentParser(description="Despertar la neurona de BioRAG (práctica acelerada).")
    ap.add_argument("db", nargs="?", default=None, help="ruta a la DB (default: BIORAG_PATH o la de producción)")
    ap.add_argument("--ciclos", type=int, default=500, help="ciclos de práctica (default 500, ~15 min con ~900 nodos)")
    ap.add_argument("--minutos", type=float, default=None, help="tope de tiempo; corta al cumplirse")
    ap.add_argument("--hasta-techo", action="store_true",
                    help="cortar en el primer techo (por defecto sigue: tras el techo puede despertar y ascender otra vez)")
    ap.add_argument("--sin-respaldo", action="store_true", help="no hacer copia de seguridad antes de escribir")
    ap.add_argument("--estado", action="store_true", help="solo mostrar el estado de la neurona (no escribe)")
    ap.add_argument("--olvidar", action="store_true", help="borrar lo aprendido (vuelven los pesos a mano)")
    ap.add_argument("--si", action="store_true", help="confirmar --olvidar")
    ap.add_argument("--cada", type=int, default=25, help="mostrar progreso cada N ciclos")
    a = ap.parse_args(argv)

    db_path = os.path.abspath(a.db or _db_por_defecto())
    if not os.path.isfile(db_path):
        print(f"[ERROR] Base de datos no encontrada: {db_path}")
        return 1
    if os.path.realpath(db_path).startswith(os.path.realpath(os.path.join(REPO, "snapshots")) + os.sep):
        print("[ERROR] Ese es el snapshot congelado oficial (referencia de la QA). Usá una copia.")
        return 1
    if os.environ.get("BIORAG_NEURONA", "1") == "0":
        print("[ERROR] BIORAG_NEURONA=0: la neurona está apagada en este entorno.")
        return 1
    if a.olvidar and not a.si:
        print("[ERROR] --olvidar borra lo aprendido. Confirmá con: --olvidar --si")
        return 1

    from core.memory_store import SQLiteMemoryBioRAG
    from core.memory import neurona

    print("=" * 80)
    print("BioRAG — Despertar la neurona")
    print("=" * 80)
    print(f"DB: {db_path}")

    respaldo = None
    if not (a.estado or a.sin_respaldo):
        respaldo = _respaldo(db_path)
        print(f"Respaldo: {respaldo}")

    db = SQLiteMemoryBioRAG(db_path=db_path)
    try:
        antes = neurona.resumen(db)
        print("")
        _linea("ANTES", antes)
        if a.estado:
            return 0
        if a.olvidar:
            neurona.olvidar(db)
            print("\nLo aprendido se borró: el motor vuelve a ser la fórmula a mano.")
            _linea("AHORA", neurona.resumen(db))
            return 0

        print(f"\nPracticando {a.ciclos} ciclos (cada ciclo = lo que corre tras una consolidación)...")
        t0 = time.time()
        r, hechos = {}, 0
        for i in range(a.ciclos):
            r = neurona.practicar(db, [])
            hechos = i + 1
            f = str(r.get("fase", ""))
            if f == "ascenso":
                print(f"  ciclo {hechos:4d}  ASCENSO  margen {r.get('margen')}  guardia #1 "
                      f"{_pct(r.get('guardia_mano'))} -> {_pct(r.get('guardia_campeon'))}")
            elif r.get("retiro"):
                print(f"  ciclo {hechos:4d}  retiro: el campeón dañaba algo; vuelve la fórmula a mano")
            elif hechos % a.cada == 0:
                print(f"  ciclo {hechos:4d}  {f:18s} examen {r.get('estudio', 0)}/{r.get('guardia', 0)}  "
                      f"{time.time() - t0:6.0f} s")
            if f in ("error", "apagada", "en pausa por fallas"):
                print(f"  la práctica se detuvo: {r}")
                break
            if a.hasta_techo and f.startswith("tranquila (techo)"):
                print(f"  ciclo {hechos:4d}  techo alcanzado")
                break
            if a.minutos is not None and time.time() - t0 > 60 * a.minutos:
                print(f"  ciclo {hechos:4d}  tope de {a.minutos} min")
                break

        despues = neurona.resumen(db)
        print("")
        _linea("DESPUÉS", despues)
        print(f"\n{hechos} ciclos en {time.time() - t0:.0f} s.")
        if not despues.get("campeon"):
            print("Sin campeón: con estos recuerdos la neurona todavía no encontró una mejora segura.\n"
                  "El motor queda exactamente igual a la fórmula a mano (nada se pierde). Seguirá\n"
                  "aprendiendo sola con el uso.")
        print("La 'guardia' es el examen propio de la neurona (20 % de recuerdos que nunca estudia),\n"
              "no la QA. Para medir con tu QA, corré esto sobre una copia y luego la suite sobre esa copia.")
        if respaldo:
            print(f"Deshacer: --olvidar --si   (o restaurar {os.path.basename(respaldo)})")
        print("=" * 80)
        return 0
    finally:
        try:
            db.cerrar_sistema()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
