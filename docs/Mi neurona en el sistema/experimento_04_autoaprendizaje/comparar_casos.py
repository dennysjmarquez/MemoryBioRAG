"""Compara caso a caso dos corridas de `qa_con_neurona.py` (registro *_top.jsonl).

Uso:  python comparar_casos.py base top5_A_R2_s7
Cuenta, para cada categoría, cuántos casos GANA (pasa a #1) y PIERDE (deja de
ser #1) la segunda corrida frente a la primera, y si alguno sale del top-5.
Los casos van en el mismo orden que scripts/casos_qa_baseline_v1.jsonl (una
búsqueda por caso), así que se alinean por posición.
"""
import collections
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[2]
a, b = sys.argv[1], sys.argv[2]
casos = [json.loads(l) for l in open(REPO / "scripts" / "casos_qa_baseline_v1.jsonl", encoding="utf-8") if l.strip()]
A = [json.loads(l) for l in open(AQUI / "resultados" / f"qa_motor_{a}_top.jsonl", encoding="utf-8")]
B = [json.loads(l) for l in open(AQUI / "resultados" / f"qa_motor_{b}_top.jsonl", encoding="utf-8")]
assert len(casos) == len(A) == len(B), (len(casos), len(A), len(B))

gana, pierde, sale5, entra5 = collections.defaultdict(list), collections.defaultdict(list), [], []
for c, ra, rb in zip(casos, A, B):
    assert c["query"] == ra["q"] == rb["q"], c["id"]
    e = c.get("concepto_esperado")
    if not e:
        continue
    a1, b1 = ra["top"][:1] == [e], rb["top"][:1] == [e]
    if b1 and not a1:
        gana[c["categoria"]].append(c["id"])
    if a1 and not b1:
        pierde[c["categoria"]].append(c["id"])
    if e in ra["top"][:5] and e not in rb["top"][:5]:
        sale5.append(c["id"])
    if e not in ra["top"][:5] and e in rb["top"][:5]:
        entra5.append(c["id"])

print(f"{b} frente a {a}  (incluye los 6 'ambiguo', que el informe oficial saca del global)")
for cat in sorted(set(gana) | set(pierde)):
    print(f"  {cat:22s} gana {len(gana[cat]):3d}   pierde {len(pierde[cat]):3d}   {pierde[cat] if pierde[cat] else ''}")
print(f"  TOTAL                  gana {sum(map(len, gana.values())):3d}   pierde {sum(map(len, pierde.values())):3d}")
print(f"  salen del top-5: {len(sale5)} {sale5}   entran al top-5: {len(entra5)} {entra5}")
