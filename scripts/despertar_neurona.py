"""BioRAG — Despertar la neurona: N ciclos de práctica seguidos sobre los recuerdos que ya existen.

POR QUÉ EXISTE
    La neurona (core/memory/neurona.py) aprende sola cada vez que se consolida la
    memoria: hasta 8 recuerdos x 7 preguntas por consolidación dentro de 3 s, costo
    fijo. En una memoria nueva eso alcanza. En una memoria que YA tiene cientos de recuerdos y
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


def _barra(n, meta, ancho=20):
    """Barra de avance legible: [██████░░░░]  n de meta."""
    meta = max(1, int(meta))
    lleno = min(ancho, int(ancho * min(n, meta) / meta))
    if n >= meta:
        return f"[{'█' * ancho}] {n:>4}  ✅ suficientes (necesitaba {meta})"
    return f"[{'█' * lleno}{'░' * (ancho - lleno)}] {n:>4} de {meta}"


def _hace(ts):
    """'hace 5 min', 'hace 3 h', 'hace 2 días' (o '—' si nunca)."""
    if not ts:
        return "— (todavía nunca)"
    s = max(0.0, time.time() - float(ts))
    if s < 90:
        return "hace un momento"
    if s < 3600:
        return f"hace {int(s // 60)} min"
    if s < 86400:
        return f"hace {int(s // 3600)} h"
    d = int(s // 86400)
    return f"hace {d} día{'s' if d != 1 else ''}"


def _ultima_practica(db_path):
    """Cuándo guardó la neurona por última vez lo aprendido (solo lectura; None si nunca)."""
    try:
        c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            fila = c.execute("SELECT actualizado FROM neurona_estado WHERE clave = 'pesos'").fetchone()
            return float(fila[0]) if fila and fila[0] else None
        finally:
            c.close()
    except sqlite3.Error:
        return None


def _etapa(r, metas):
    """(número, nombre, explicación) de la etapa en palabras de cualquier persona."""
    u = r.get("ultimo") or {}
    fase = str(u.get("fase", ""))
    if fase == "en pausa por fallas":
        return "!", "En pausa", "tuvo fallas seguidas y descansa una hora; tus búsquedas no se ven afectadas."
    if fase == "error":
        return "!", "Con un error", "la última práctica falló; tus búsquedas no se ven afectadas."
    if r.get("campeon"):
        if r.get("tranquila"):
            return 3, "Trabajando (en su mejor nivel)", "ya mejora tus búsquedas y llegó a su techo: ahora solo vigila."
        return 3, "Trabajando", "aprobó su examen y ya mejora tus búsquedas; sigue practicando para mejorar más."
    falta_e = max(0, metas[0] - int(r.get("estudio", 0)))
    falta_g = max(0, metas[1] - int(r.get("guardia", 0)))
    if falta_e or falta_g:
        return 1, "Juntando preguntas", "todavía no tiene suficientes preguntas para presentar su examen."
    if r.get("tranquila"):
        return 2, "Esperando más recuerdos", ("practicó mucho y no encontró una mejora segura; volverá a "
                                              "intentarlo cuando guardes más cosas.")
    return 2, "Presentando su examen", "ya tiene sus preguntas; solo empieza a trabajar si mejora sin dañar nada."


_FASE_CLARA = {
    "juntando examen": "juntando preguntas",
    "estudiando": "presentando examen",
    "ascenso": "aprobó",
    "tranquila": "en su mejor nivel",
    "tranquila (techo)": "en su mejor nivel",
}


def _linea(titulo, r, db_path=None):
    """Estado de la neurona explicado para cualquier persona (no hace falta saber de IA)."""
    from core.memory import neurona
    cfg = neurona._cfg()
    metas = (cfg["min_estudio"], cfg["min_guardia"])
    u = r.get("ultimo") or {}
    estudio, guardia = int(r.get("estudio", 0)), int(r.get("guardia", 0))
    ciclos, ascensos, retiros = int(r.get("ciclos", 0)), int(r.get("ascensos", 0)), int(r.get("retiros", 0))
    num, nombre, explica = _etapa(r, metas)
    ultima = _ultima_practica(db_path) if db_path else None

    print(f"  {titulo}")
    print("  " + "─" * 76)
    print(f"  ¿Está encendida?              {'✅ sí' if r.get('activa', True) else '⛔ no (BIORAG_NEURONA=0)'}")
    if r.get("campeon"):
        print("  ¿Ya mejora tus búsquedas?     🏆 sí, la neurona ordena tus resultados")
    else:
        print("  ¿Ya mejora tus búsquedas?     ⏳ todavía no: se usa la fórmula de siempre (fórmula a mano)")
    etapa_txt = f"{num} de 3 · {nombre}" if num != "!" else f"⚠️  {nombre}"
    print(f"  Etapa                         {etapa_txt}")
    print(f"                                {explica}")
    print("")
    print("  SU EXAMEN (preguntas que ella misma se hace con tus recuerdos)")
    print(f"    Para estudiar               {_barra(estudio, metas[0])}")
    print(f"    De control (nunca estudia)  {_barra(guardia, metas[1])}")
    print("")
    print("  SU HISTORIAL")
    print(f"    Veces que practicó          {ciclos:<6}(1 vez por cada consolidación de la memoria)")
    print(f"    Última práctica             {_hace(ultima) if db_path else '—'}")
    print(f"    Veces que aprobó            {ascensos}")
    aviso = "✅ bien" if retiros == 0 else "⚠️  la quitaron por empeorar algo; volvió sola a la fórmula"
    print(f"    Veces que la quitaron       {retiros:<6}{aviso}")
    if u.get("guardia_mano") is not None:
        print(f"    Aciertos en 1er lugar       fórmula {_pct(u.get('guardia_mano'))}  →  neurona "
              f"{_pct(u.get('guardia_campeon'))}   (en sus preguntas de control)")
    if r.get("campeon"):
        print(f"    Prudencia                   solo cambia el orden si está segura (margen {r.get('margen', 0.0)})")

    print("")
    if num == 1:
        faltan = []
        if estudio < metas[0]:
            faltan.append(f"{metas[0] - estudio} para estudiar")
        if guardia < metas[1]:
            faltan.append(f"{metas[1] - guardia} de control")
        print(f"  👉 En resumen: {'está viva y aprendiendo' if ciclos else 'todavía no ha practicado'}. "
              f"Le faltan {' y '.join(faltan)}.")
        print("     Practica unos segundos cada vez que se consolida la memoria (consolidar,")
        print("     dormir o cerrar sesión; guardar solo no basta). Para acelerar:")
        print("     ./scripts/despertar_neurona.sh --minutos 20")
    elif num == 2:
        print("  👉 En resumen: ya junta suficientes preguntas; ahora practica y se examina sola.")
        print("     Si nunca demuestra que mejora sin dañar nada, no se activa (y eso está bien).")
    elif num == 3:
        print("  👉 En resumen: la neurona está activa y mejorando tus búsquedas.")
    else:
        print("  👉 En resumen: tus búsquedas siguen funcionando normal con la fórmula de siempre.")
    print("  " + "─" * 76)


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
    ap.add_argument("--ciclos", type=int, default=500, help="ciclos de práctica (default 500, ~22 min con ~900 nodos)")
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
        if a.estado:
            _linea("ESTADO DE TU NEURONA", antes, db_path)
            return 0
        _linea("ANTES", antes, db_path)
        if a.olvidar:
            neurona.olvidar(db)
            print("\nLo aprendido se borró: el motor vuelve a ser la fórmula a mano.")
            _linea("AHORA", neurona.resumen(db), db_path)
            return 0

        print(f"\nPracticando hasta {a.ciclos} veces seguidas (cada una = lo que hace sola tras una consolidación)...")
        t0 = time.time()
        r, hechos = {}, 0
        for i in range(a.ciclos):
            r = neurona.practicar(db, [])
            hechos = i + 1
            f = str(r.get("fase", ""))
            if f == "ascenso":
                print(f"  práctica {hechos:4d}  🏆 APROBÓ: aciertos en 1er lugar (control) "
                      f"{_pct(r.get('guardia_mano'))} → {_pct(r.get('guardia_campeon'))}")
            elif r.get("retiro"):
                print(f"  práctica {hechos:4d}  ⚠️  la quitaron: empeoraba algo; vuelve la fórmula a mano")
            elif hechos % a.cada == 0:
                print(f"  práctica {hechos:4d}  {_FASE_CLARA.get(f, f):18s} para estudiar {r.get('estudio', 0):>4}  "
                      f"de control {r.get('guardia', 0):>3}  {time.time() - t0:6.0f} s")
            if f in ("error", "apagada", "en pausa por fallas"):
                print(f"  la práctica se detuvo: {r}")
                break
            if a.hasta_techo and f.startswith("tranquila (techo)"):
                print(f"  práctica {hechos:4d}  llegó a su mejor nivel (techo)")
                break
            if a.minutos is not None and time.time() - t0 > 60 * a.minutos:
                print(f"  práctica {hechos:4d}  se cumplieron los {a.minutos} min")
                break

        despues = neurona.resumen(db)
        print("")
        _linea("DESPUÉS", despues, db_path)
        print(f"\n{hechos} ciclos de práctica en {time.time() - t0:.0f} s.")
        if not despues.get("campeon"):
            print("Sin campeón: con estos recuerdos la neurona todavía no encontró una mejora segura.\n"
                  "El motor queda exactamente igual a la fórmula a mano (nada se pierde). Seguirá\n"
                  "aprendiendo sola con el uso.")
        print("Las preguntas 'de control' son el examen propio de la neurona (20 % de recuerdos que nunca\n"
              "estudia), no la QA. Para medir con tu QA, corré esto sobre una copia y luego la suite sobre esa copia.")
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
