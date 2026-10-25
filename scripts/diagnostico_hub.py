#!/usr/bin/env python3
"""Diagnóstico del concept hub: ¿contra quién compite una pregunta?

SOLO LECTURA. Copia tu base (API de backup de SQLite) a una carpeta temporal y trabaja
sobre ESA copia, igual que hace el test de generalización: crea las tablas del hub y
carga los hubs curados (HUBS_INICIALES). Tu base original no se modifica.

Para cada pregunta muestra:
  - qué decide el hub NUEVO (v35.2) y qué decidía el hub VIEJO (BIORAG_HUB_ESCALA=0)
  - los recuerdos que compiten en el hub nuevo: parecido, porción de la ventaja
    y el puente que coincidió
  - el top 5 de la búsqueda completa con cada hub

Uso:
  BIORAG_PATH=<tu_base.db> python3 scripts/diagnostico_hub.py              (5 preguntas del test)
  BIORAG_PATH=<tu_base.db> python3 scripts/diagnostico_hub.py "pregunta"   (las que quieras)
  Opcional: --json salida.json   guarda todo para compartirlo.
"""
import json
import math
import os
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

PREGUNTAS_TEST = [
    ("qué hacía antes de ser programador", "historia_tasajera_fumigador_rufino", "trabajo_previo"),
    ("cómo sobrevivía económicamente antes de la tecnología", "historia_tasajera_fumigador_rufino", "trabajo_previo"),
    ("metí un cambio y todo se rompió", "leccion_control_flujo_codigo_preexistente", "control_flujo"),
    ("toqué algo que andaba bien y dejó de andar", "leccion_control_flujo_codigo_preexistente", "control_flujo"),
    ("dos modelos de IA que no están de acuerdo, ¿cómo resuelvo?",
     "resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad", "consenso_multi_modelo"),
]
CUANTOS = 10


def copia_segura(origen, destino):
    src = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    dst = sqlite3.connect(destino)
    src.backup(dst)
    dst.close()
    src.close()


def con_modo(escala, funcion):
    anterior = os.environ.get("BIORAG_HUB_ESCALA")
    os.environ["BIORAG_HUB_ESCALA"] = "1" if escala else "0"
    try:
        return funcion()
    finally:
        if anterior is None:
            os.environ.pop("BIORAG_HUB_ESCALA", None)
        else:
            os.environ["BIORAG_HUB_ESCALA"] = anterior


def corto(texto, n=60):
    texto = (texto or "").replace("\n", " ")
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def main():
    args = sys.argv[1:]
    salida_json = None
    if "--json" in args:
        i = args.index("--json")
        salida_json = args[i + 1]
        del args[i:i + 2]
    preguntas = [(q, None, None) for q in args] or PREGUNTAS_TEST

    origen = os.environ.get("BIORAG_PATH")
    if not origen or not os.path.exists(origen):
        print("Falta BIORAG_PATH=<ruta de tu base .db>")
        sys.exit(1)

    tmp = tempfile.mkdtemp(prefix="diag_hub_")
    copia = os.path.join(tmp, "copia.db")
    try:
        print(f"Copiando tu base a una carpeta temporal (el original no se toca)…")
        copia_segura(origen, copia)
        from core.memory_store import SQLiteMemoryBioRAG
        import core.concept_hub as ch
        cerebro = SQLiteMemoryBioRAG(copia)
        ch.crear_tablas(cerebro.conn)
        ch.cargar_hubs_iniciales(cerebro.conn)
        conn = cerebro.conn
        n_hubs = conn.execute("SELECT COUNT(*) FROM concept_hubs").fetchone()[0]
        n_puentes = conn.execute("SELECT COUNT(*) FROM concept_hub_bridges").fetchone()[0]
        print(f"Hubs en la copia: {n_hubs}   puentes: {n_puentes}\n")

        informe = []
        for query, esperado, hub_esperado in preguntas:
            nuevo = con_modo(True, lambda: ch.expandir_query_con_hub(query, conn))
            viejo = con_modo(False, lambda: ch.expandir_query_con_hub(query, conn))
            puntajes, idx = con_modo(True, lambda: ch._puntajes_por_recuerdo(query, conn))
            T = ch.HUB_TEMPERATURA if ch.HUB_TEMPERATURA > 0 else 0.10
            s_top = puntajes[0][0] if puntajes else 0.0
            pesos = [math.exp((s - s_top) / T) for s, _, _ in puntajes]
            total = sum(pesos) or 1.0
            top5_nuevo = [r[0] for r in con_modo(True, lambda: cerebro.buscar_por_frase(query, limite=5))[0]]
            top5_viejo = [r[0] for r in con_modo(False, lambda: cerebro.buscar_por_frase(query, limite=5))[0]]

            print("=" * 100)
            print(f"PREGUNTA: {query}")
            if esperado:
                print(f"  Se espera el recuerdo: {esperado}   (hub: {hub_esperado})")

            def decision(r):
                if not r:
                    return "no se decide por ningún recuerdo"
                return f"{r['hub_id']}  (confianza {r['hub_confidence']:.2f})"
            print(f"  Hub NUEVO decide: {decision(nuevo)}")
            print(f"  Hub VIEJO decidía: {decision(viejo)}")
            print(f"\n  Recuerdos que compiten en el hub nuevo ({len(puntajes)} activados; se muestran {min(CUANTOS, len(puntajes))}):")
            print(f"  {'#':>2}  {'parecido':>8}  {'porción':>7}  {'nodos':>5}  hub  →  puente que coincidió")
            filas = []
            for i, ((s, hub_id, matcheados), p) in enumerate(zip(puntajes, pesos), 1):
                d = idx["hubs"][hub_id]
                fila = {"puesto": i, "hub": hub_id, "recuerdo": d["canonical"], "parecido": round(s, 4),
                        "porcion": round(p / total, 4), "nodos": len(d["nodos"]), "puentes": matcheados[:3]}
                filas.append(fila)
                if i <= CUANTOS:
                    marca = " ←esperado" if hub_esperado and hub_id == hub_esperado else ""
                    print(f"  {i:>2}  {s:8.3f}  {p / total:7.1%}  {len(d['nodos']):>5}  {hub_id}{marca}")
                    print(f"  {'':>30}→ {corto(matcheados[0] if matcheados else '', 64)}")
            if hub_esperado and hub_esperado not in [f["hub"] for f in filas[:CUANTOS]]:
                pos = next((f for f in filas if f["hub"] == hub_esperado), None)
                print(f"  (hub esperado {hub_esperado}: " +
                      (f"puesto {pos['puesto']}, parecido {pos['parecido']:.3f})" if pos else "no se activó)"))

            def marca5(lista):
                return "  ".join(("✔" if esperado and c == esperado else "") + corto(c, 45) for c in lista)
            print(f"\n  Top 5 con hub NUEVO: {marca5(top5_nuevo)}")
            print(f"  Top 5 con hub VIEJO: {marca5(top5_viejo)}")
            if esperado:
                print(f"  ¿Esperado en top 5?  nuevo: {'sí' if esperado in top5_nuevo else 'NO'}   "
                      f"viejo: {'sí' if esperado in top5_viejo else 'NO'}")
            print()
            informe.append({"query": query, "esperado": esperado, "hub_esperado": hub_esperado,
                            "nuevo": nuevo and {k: nuevo[k] for k in ("hub_id", "hub_confidence", "hub_parecido", "hub_ventaja")},
                            "viejo": viejo and {k: viejo[k] for k in ("hub_id", "hub_confidence")},
                            "competidores": filas[:25], "top5_nuevo": top5_nuevo, "top5_viejo": top5_viejo})
        cerebro.cerrar_sistema()
        if salida_json:
            with open(salida_json, "w", encoding="utf-8") as f:
                json.dump(informe, f, ensure_ascii=False, indent=1)
            print(f"Guardado: {salida_json}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
