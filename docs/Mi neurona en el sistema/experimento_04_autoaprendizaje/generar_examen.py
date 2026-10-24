"""Paso 1 del experimento 04: la base se fabrica su propio examen ("tapar y adivinar").

Idea (aprendizaje autosupervisado): cada nodo ya trae su respuesta adentro.
Se "tapa" el nombre del nodo y se le pregunta a la búsqueda con otra forma de
pedirlo (typo, variante gramatical, sinónimo registrado, palabras de su
contenido, pregunta natural, cruce de idioma). Si la búsqueda no pone ese nodo
de #1, falló, y la base lo sabe sin que nadie se lo diga.

Reglas para que el experimento sea honesto:
- Se generan con las MISMAS funciones de `scripts/generar_casos_qa.py` (lo que
  cualquier base de un tercero podría hacer sola), pero con OTRA semilla.
- Se descarta toda pregunta que sea idéntica a una consulta del QA oficial
  (`scripts/casos_qa_baseline_v1.jsonl`): el QA hace de "búsquedas de la gente"
  y la neurona nunca debe ver sus respuestas.
- No se genera `literal` (sería la misma consulta que el QA) ni `dormido`.
- Solo lectura: abre el snapshot en modo `ro`.

Uso (desde la raíz del repo):
    python "docs/Mi neurona en el sistema/experimento_04_autoaprendizaje/generar_examen.py"
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from generar_casos_qa import generate_cases_for_node  # noqa: E402

SEMILLA = 2026
SNAP = REPO / "snapshots" / "qa_escape_qcr_20260811.db"
SALIDA = AQUI / "datos" / "examen_autogenerado.jsonl"

random.seed(SEMILLA)
qa = [json.loads(l) for l in open(REPO / "scripts" / "casos_qa_baseline_v1.jsonl", encoding="utf-8") if l.strip()]
consultas_qa = {c["query"].strip().lower() for c in qa}

con = sqlite3.connect(SNAP.resolve().as_uri() + "?mode=ro", uri=True)
filas = con.execute(
    "SELECT concepto, contenido, sinonimos, categoria FROM largo_plazo ORDER BY concepto").fetchall()
con.close()

examen, descartadas = [], 0
for concepto, contenido, sinonimos, _cat in filas:
    if not contenido or len(contenido) <= 50:
        continue
    nodo = {"concepto": concepto, "contenido": contenido, "sinonimos": sinonimos}
    casos = generate_cases_for_node(nodo, None, exclude_literal=True)
    nombre = concepto.replace("_", " ").strip().lower()
    for c in casos:
        if c["categoria"] == "dormido":
            continue
        q = c["query"].strip().lower()
        if q in consultas_qa or q == nombre or not q:
            descartadas += 1
            continue
        examen.append({"categoria": c["categoria"], "query": c["query"],
                       "concepto_esperado": concepto, "deep": False})

for i, c in enumerate(examen, 1):
    c["id"] = f"E{i:04d}"
SALIDA.parent.mkdir(parents=True, exist_ok=True)
with open(SALIDA, "w", encoding="utf-8") as f:
    for c in examen:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")

from collections import Counter  # noqa: E402
print(f"{len(examen)} preguntas ({descartadas} descartadas por coincidir con el QA o con el nombre)")
print(dict(Counter(c["categoria"] for c in examen)))
print(f"-> {SALIDA}")
