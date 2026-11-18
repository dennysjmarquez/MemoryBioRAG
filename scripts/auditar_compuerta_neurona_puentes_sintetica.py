"""Caracterización aislada del hub, no una prueba de recall ni una aceptación.

Solo datos y parámetros fabricados, SQLite en memoria y parches de lectura.
No entrena, no consulta MCP, no modifica el motor ni accede a bases del usuario.
La aserción captura el comportamiento actual para investigarlo, NO lo declara
correcto: revisar esta caracterización si una corrección aprobada lo modifica.

Ejecutar: PYTHONPATH=. python scripts/auditar_compuerta_neurona_puentes_sintetica.py
"""
import os
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import core.concept_hub as hub
from core.memory import neurona_puentes as npu


def main():
    indice = SimpleNamespace(
        idf={"semilla": 1.0},
        idf_max=1.0,
        inv={"semilla": {0}},
        filas=[("hub_sintetico", {"semilla"}, 1.0, "ingenuo", "semilla")],
        nodos={"hub_sintetico": ["nodo_sintetico"]},
    )
    # Parámetros inventados, no proceden de una DB ni de entrenamiento.
    parametros = {
        "W": np.zeros((npu.N_OCULTAS, npu.N_ENTRADAS)),
        "b": np.ones(npu.N_OCULTAS),
        "v": np.ones(npu.N_OCULTAS),
    }
    assert npu._sano(parametros) and not npu.es_neutra(parametros)
    with (
        sqlite3.connect(":memory:") as conn,
        patch.dict(os.environ, {"BIORAG_PUENTES_SUELO": "0.5", "BIORAG_PUENTES_TECHO": "1.0"}),
        patch.object(hub, "_indice_bridges", return_value=indice),
        patch.object(hub, "_tokenizar_stems", return_value={"semilla"}),
        patch.object(hub, "_tokenizar", return_value=["semilla"]),
        patch.object(npu, "cargar", return_value=parametros),
    ):
        with patch.object(npu, "activa", return_value=False):
            base = hub._expandir_por_cobertura_idf("semilla", conn, threshold=0.55)
        with patch.object(npu, "activa", return_value=True):
            activa = hub._expandir_por_cobertura_idf("semilla", conn, threshold=0.55)
        assert base is not None and activa is None
    print("resultado=hub_devuelto_sin_neurona, hub_no_devuelto_con_neurona_simulada; "
          "gate_cobertura=aprobado_en_ambos")


if __name__ == "__main__":
    main()
