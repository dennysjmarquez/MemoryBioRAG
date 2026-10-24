"""Lee la hoja ya marcada por Dennys y dice qué tan bien acierta la neurona.

Uso:  python medir_hoja.py
Respuestas válidas: si / no / momento / contradicen / nose (vacío = no contestada).
"momento" (son del mismo momento o proyecto) cuenta como "sí tienen que ver".
"contradicen" se cuenta aparte: dice si hace falta la capa de contradicción.
"""
import csv
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
VALIDAS = {"si", "sí", "no", "momento", "contradicen", "nose", "no se", "no sé"}


def main():
    clave = json.load(open(os.path.join(AQUI, "clave_no_mirar.json"), encoding="utf-8"))["pares"]
    resp = {}
    with open(os.path.join(AQUI, "hoja_para_dennys.csv"), encoding="utf-8-sig") as fh:
        for fila in csv.reader(fh):
            if not fila or fila[0] == "id":
                continue
            r = fila[5].strip().lower()
            if r in VALIDAS:
                resp[fila[0]] = "si" if r in ("si", "sí", "momento") else ("nose" if r.startswith("no s") else r)
    grupos = {"A": "existen hoy y la neurona las CONSERVA", "B": "existen hoy y la neurona las SOLTARÍA",
              "C": "Gemini las sacó, la neurona les da fuerza alta", "D": "no existen; la neurona las PROPONDRÍA"}
    print(f"Contestadas: {len(resp)} de {len(clave)}\n")
    for g, txt in grupos.items():
        ids = [i for i, v in clave.items() if v["grupo"] == g and i in resp]
        n = len(ids)
        si = sum(resp[i] == "si" for i in ids)
        no = sum(resp[i] == "no" for i in ids)
        co = sum(resp[i] == "contradicen" for i in ids)
        if not n:
            print(f"{g} ({txt}): sin respuestas")
            continue
        print(f"{g} ({txt}): {n} contestadas · sí {si} ({100 * si / n:.0f} %) · no {no} · contradicen {co}")
    print("\nCómo leerlo:")
    print("  A alto en 'sí'  = lo que la neurona conserva es bueno (precisión).")
    print("  B alto en 'no'  = lo que soltaría de verdad sobraba. Cada 'sí' en B es algo que perderías.")
    print("  C: 'sí' = tenía razón la neurona; 'no' = tenía razón Gemini.")
    print("  D alto en 'sí'  = vale la pena que la neurona proponga conexiones nuevas.")


if __name__ == "__main__":
    main()
