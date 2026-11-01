"""Auditar rutas del Concept Hub con fixture sintética en SQLite en memoria.

Ejecutar: PYTHONPATH=. python scripts/auditar_rutas_neurona_puentes_sintetica.py
No consulta datos privados ni MCP; no entrena, guarda pesos o cambia el motor.
Los parámetros fabricados solo existen en memoria y no se muestran en pantalla.
Caracteriza el comportamiento actual, no declara aceptable ninguna pérdida.
"""
import os
import sqlite3
from unittest.mock import patch

import numpy as np

from core import concept_hub as hub
from core.memory import neurona_puentes as neurona


def main():
    parametros = {
        "W": np.zeros((neurona.N_OCULTAS, neurona.N_ENTRADAS)),
        "b": np.ones(neurona.N_OCULTAS),
        "v": np.ones(neurona.N_OCULTAS),
    }
    assert neurona._sano(parametros) and not neurona.es_neutra(parametros)
    puentes = [
        {"text": "origen nectar", "angle": "sinonimo"},
        {"text": "oscuro sendero", "angle": "problema"},
        {"text": "velero distante", "angle": "solucion"},
        {"text": "calendario urbano", "angle": "situacion"},
        {"text": "semilla alborada", "angle": "ingenuo"},
    ]
    # Ambas condiciones usan la misma fixture y el mismo índice real. Solo se
    # inyecta el estado neuronal fabricado; la tokenización y el índice no se
    # sustituyen. La ruta escala se comprueba mediante el punto de entrada real.
    with sqlite3.connect(":memory:") as conn:
        hub.crear_tablas(conn)
        hub.crear_hub(conn, "hub_demo", "nodo_demo", validar_existencia=False)
        hub.agregar_bridges(conn, "hub_demo", puentes)
        cambios_antes = conn.total_changes
        configuracion = {
            "BIORAG_HUB_ESCALA": "1",
            "BIORAG_PUENTES_SUELO": "0.5",
            "BIORAG_PUENTES_TECHO": "1.0",
        }
        with patch.dict(os.environ, configuracion):
            with patch.dict(os.environ, {"BIORAG_HUB_MOTOR": "idf"}):
                with patch.object(neurona, "cargar", return_value=parametros):
                    with patch.object(neurona, "activa", return_value=False):
                        idf_off = hub.expandir_query_con_hub("semilla alborada", conn)
                    with patch.object(neurona, "activa", return_value=True):
                        idf_on = hub.expandir_query_con_hub("semilla alborada", conn)
                # Estado no existente: cargador real debe usar neutro.
                with patch.object(neurona, "activa", return_value=True):
                    idf_neutro = hub.expandir_query_con_hub("semilla alborada", conn)
            with patch.dict(os.environ, {"BIORAG_HUB_MOTOR": "escala"}):
                with patch.object(neurona, "cargar", return_value=parametros) as cargar:
                    with patch.object(neurona, "activa", return_value=False):
                        escala_off = hub.expandir_query_con_hub("semilla alborada", conn)
                    with patch.object(neurona, "activa", return_value=True):
                        escala_on = hub.expandir_query_con_hub("semilla alborada", conn)
                    assert cargar.call_count == 0
            with patch.dict(os.environ):
                os.environ.pop("BIORAG_HUB_MOTOR", None)
                with patch.object(neurona, "cargar", return_value=parametros) as cargar:
                    fabrica = hub.expandir_query_con_hub("semilla alborada", conn)
                    assert cargar.call_count == 0
        assert idf_off and idf_off == idf_neutro and idf_on is None
        assert escala_off and escala_on == escala_off and fabrica == escala_off
        assert conn.total_changes == cambios_antes
        print("idf=hub_off_y_neutro, sin_hub_on_simulado; escala=sin_cambio_y_sin_cargar_neurona")
        print("fixture=5_puentes_sinteticos; escrituras_durante_busqueda=0")


if __name__ == "__main__":
    main()
