#!/usr/bin/env python3
"""BioRAG CLI — Puente para que los agentes OEC (Athena, Artemis, Hermes)
interactúen con la corteza cerebral compartida desde la terminal.

Uso desde el agente:
  python3 biorag.py buscar <concepto> [--deep]
  python3 biorag.py guardar <clave> <contenido>
  python3 biorag.py asociar <a> <b>
  python3 biorag.py comunicar <destino> <mensaje>
  python3 biorag.py leer_mensajes [--no-leidos] [--ultimos N] [--para <agente>]
  python3 biorag.py sueno [limite_energia]
  python3 biorag.py corteza
  python3 biorag.py familiaridad <texto>
  python3 biorag.py estado
"""
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG

DB_PATH = "/mnt/recursos_compartidos_y_otros/MemoryBioRAG/MemoryBioRAG_Data/memory_biorag.db"


def cmd_buscar(cerebro, args):
    if not args:
        print("Especifica un concepto. Ej: biorag.py buscar san_cayetano")
        print("  --deep   Buscar tambien en memoria dormida (despierta el nodo)")
        return 1
    deep = False
    if "--deep" in args:
        deep = True
        args = [a for a in args if a != "--deep"]
    if not args:
        print("Especifica un concepto.")
        return 1
    concepto = " ".join(args)
    if deep:
        resultado = cerebro.buscar_recuerdo_profundo(concepto)
    else:
        resultado = cerebro.buscar_recuerdo_microsegundos(concepto)
    if resultado:
        print(resultado)
        return 0
    print(f"No se encontro '{concepto}' en la corteza.")
    return 1


def cmd_guardar(cerebro, args):
    if len(args) < 2:
        print("Uso: biorag.py guardar <clave> <contenido>")
        return 1
    clave = args[0].lower().replace(" ", "_")
    contenido = " ".join(args[1:])
    cerebro.percibir_corto_plazo(clave, contenido)
    print(f"'{clave}' guardado en corto plazo. Consolidalo con 'sueno' para hacerlo permanente.")
    return 0


def cmd_asociar(cerebro, args):
    if len(args) < 2:
        print("Uso: biorag.py asociar <concepto_a> <concepto_b>")
        return 1
    cerebro.establecer_asociacion(args[0], args[1])
    return 0


def cmd_sueno(cerebro, args):
    limite = float(args[0]) if args else 10.0
    cerebro.ciclo_sueno_consolidacion(limite_energia=limite)
    return 0


def cmd_corteza(cerebro, args):
    cerebro.cursor.execute(
        "SELECT concepto, categoria, peso_sinaptico, estado, asociaciones "
        "FROM largo_plazo ORDER BY peso_sinaptico DESC, estado ASC"
    )
    filas = cerebro.cursor.fetchall()
    if not filas:
        print("La corteza esta vacia.")
        return 0

    print(f"{'CONCEPTO':<25} {'CATEGORIA':<15} {'PESO':<8} {'ESTADO':<10} {'ASOCIACIONES'}")
    print("-" * 80)
    for c, cat, peso, est, asoc in filas:
        print(f"{c:<25} {cat:<15} {peso:<8} {est:<10} {asoc}")
    print("-" * 80)
    print(f"Total: {len(filas)} nodos corticales.")
    return 0


def cmd_estado(cerebro, args):
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
    activos = cerebro.cursor.fetchone()[0]
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'")
    dormidos = cerebro.cursor.fetchone()[0]
    cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo")
    corto = cerebro.cursor.fetchone()[0]
    cerebro.cursor.execute("SELECT ROUND(SUM(peso_sinaptico), 2) FROM largo_plazo WHERE estado = 'activo'")
    energia = cerebro.cursor.fetchone()[0] or 0.0

    print(f"Nodos activos:      {activos}")
    print(f"Nodos dormidos:     {dormidos}")
    print(f"Memoria de trabajo: {corto} items")
    print(f"Energia sinaptica:  {energia}")
    return 0


def cmd_comunicar(cerebro, args):
    if len(args) < 2:
        print("Uso: biorag.py comunicar <destino> <mensaje>")
        print("  destino: athena, artemis, hermes, todos")
        print("  Identificate con env AGENT_NAME=athena|artemis|hermes")
        return 1
    origen = os.environ.get("AGENT_NAME", "desconocido")
    destino = args[0]
    mensaje = " ".join(args[1:])
    cerebro.enviar_comunicado(origen, destino, mensaje)
    return 0


def cmd_leer_mensajes(cerebro, args):
    solo_no_leidos = "--no-leidos" in args
    ultimos = 10
    destino = None
    args_limpios = [a for a in args if a != "--no-leidos"]
    for i, a in enumerate(args_limpios):
        if a == "--ultimos" and i + 1 < len(args_limpios):
            try:
                ultimos = int(args_limpios[i + 1])
            except ValueError:
                pass
        if a == "--para" and i + 1 < len(args_limpios):
            destino = args_limpios[i + 1]
    mensajes = cerebro.leer_comunicados(destino=destino, solo_no_leidos=solo_no_leidos, ultimos=ultimos)
    if not mensajes:
        print("No hay mensajes.")
        return 0
    ids_a_marcar = []
    for msg_id, origen, dest, contenido, ts, leido in reversed(mensajes):
        marca = "[NO LEIDO]" if not leido else "          "
        fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        print(f"{marca} #{msg_id} {fecha} | {origen} -> {dest}")
        print(f"         {contenido}")
        print()
        if not leido:
            ids_a_marcar.append(msg_id)
    if ids_a_marcar:
        cerebro.marcar_como_leido(ids_a_marcar)
    return 0


def cmd_familiaridad(cerebro, args):
    from middleware.interceptor import escanear_familiaridad
    texto = " ".join(args)
    if not texto:
        print("Uso: biorag.py familiaridad <texto a escanear>")
        return 1
    conceptos = escanear_familiaridad(texto, cerebro)
    if conceptos:
        for c in conceptos:
            print(f"[Nota de Familiaridad: Te resulta familiar el concepto \"{c}\"]")
        return 0
    print("Sin coincidencias de familiaridad.")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    comando = sys.argv[1]
    args = sys.argv[2:]

    cerebro = SQLiteMemoryBioRAG(db_path=DB_PATH)

    comandos = {
        "buscar": cmd_buscar,
        "guardar": cmd_guardar,
        "asociar": cmd_asociar,
        "sueno": cmd_sueno,
        "corteza": cmd_corteza,
        "estado": cmd_estado,
        "familiaridad": cmd_familiaridad,
        "comunicar": cmd_comunicar,
        "leer_mensajes": cmd_leer_mensajes,
    }

    if comando not in comandos:
        print(f"Comando desconocido: {comando}")
        print(__doc__)
        cerebro.cerrar_sistema()
        return 1

    try:
        resultado = comandos[comando](cerebro, args)
        cerebro.cerrar_sistema()
        return resultado
    except Exception as e:
        print(f"Error: {e}")
        cerebro.cerrar_sistema()
        return 1


if __name__ == "__main__":
    sys.exit(main())
