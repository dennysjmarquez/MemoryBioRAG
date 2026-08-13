"""Traza causal de la consulta 'redes neuronales' contra un snapshot SQLite dado."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.neocortex_teleologico import NeocortexTeleologico
from core.ppmi_hybrid_search import _tokenizar

DB = "/home/ubuntu/MemoryBioRAG/scripts/snapshot_prf_real.db"
QUERY = "redes neuronales"

neocortex = NeocortexTeleologico(DB)
indices = neocortex.indices
procesados = neocortex._tokenizar_profundo(QUERY)
vector = indices.vector_query(procesados)

salida = {
    "query": QUERY,
    "tokens_ppmi": _tokenizar(QUERY),
    "tokens_neocortex": procesados,
    "tokens_disponibles": sorted(indices.token_vecs.keys()),
    "tokens_conocidos": [t for t in procesados if t in indices.token_vecs],
    "norma_vector_query": float((vector @ vector) ** 0.5) if vector is not None else None,
    "evaluacion_epistemica": neocortex.evaluar_episteme(QUERY),
}
print(json.dumps(salida, ensure_ascii=False, indent=2))
