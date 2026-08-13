"""Valida que el Neocórtex use pools precalculados, no un recorrido de todos los nodos."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.neocortex_teleologico import NeocortexTeleologico
from core.adn_conceptual import ADNConceptualEngine

BASE = Path(__file__).resolve().parent
DB = BASE / "snapshot_prf_real.db"
CASES = BASE / "casos_qa_baseline_v1.jsonl"

neocortex = NeocortexTeleologico(str(DB))
adn = ADNConceptualEngine(str(DB), indices=neocortex.indices)

casos = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
resultados = []
for caso in casos:
    if caso.get("concepto_esperado") is None:
        continue
    evaluacion = neocortex.evaluar_episteme(caso["query"])
    if evaluacion.get("confianza_epistemica", 0.0) >= 0.2:
        razonamiento = neocortex.razonar_por_significado(caso["query"], top_k=5)
        resultados.append({
            "id": caso["id"],
            "query": caso["query"],
            "esperado": caso["concepto_esperado"],
            "confianza_epistemica": evaluacion["confianza_epistemica"],
            "candidatos_precalculados": evaluacion["candidatos_precalculados"],
            "nodos_totales": len(neocortex.indices.vecs),
            "indice_nocturno_disponible": evaluacion["indice_nocturno_disponible"],
            "resultados": [r["concepto"] for r in razonamiento],
        })
    if len(resultados) >= 3:
        break

salida = {
    "indice_adn_listo": adn.indice_listo,
    "cromosomas_emergentes": len(adn.nombres_cromosomas),
    "nodos_totales": len(neocortex.indices.vecs),
    "casos_dirigidos": resultados,
    "veredicto": "ok" if resultados and all(r["candidatos_precalculados"] < r["nodos_totales"] for r in resultados) else "fallo",
}
print(json.dumps(salida, ensure_ascii=False, indent=2))
