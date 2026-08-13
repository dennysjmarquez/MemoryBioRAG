"""Reconstruye el índice ADN v29 únicamente para un ciclo de sueño controlado."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.adn_conceptual import ADNConceptualEngine

DB = Path(__file__).resolve().parent / "snapshot_prf_real.db"

if __name__ == "__main__":
    resultado = ADNConceptualEngine.reconstruir_indice_nocturno(str(DB))
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
