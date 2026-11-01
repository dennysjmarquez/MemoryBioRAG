"""Caracterización de búsqueda local con fixture sintética, no evaluación MCP/E1.

PYTHONPATH=. python scripts/auditar_filtro_hub_sintetico.py

Cada caso usa una DB temporal nueva; no accede a bases del usuario, no entrena,
ni cambia el motor. El parche de diagnóstico solo modifica una constante en RAM
para contrastar una hipótesis: no es una propuesta ni una aprobación de cambio.
Las aserciones describen el comportamiento actual, no aceptan pérdida de pistas.
"""
import os
import tempfile
from unittest.mock import patch

# Configuración explícita antes de importar el motor: nunca heredar una base o
# banderas de una instalación real, ni activar aprendizaje durante la prueba.
for clave in list(os.environ):
    if clave.startswith("BIORAG_"):
        del os.environ[clave]
os.environ.update({
    "BIORAG_NEURONA": "0",
    "BIORAG_WORDNET_ENABLED": "0",
    "BIORAG_PPMI_WEIGHT": "0",
    "BIORAG_DMN_SINTESIS_ACTIVA": "0",
    "BIORAG_HUB_ENABLED": "1",
    "BIORAG_HUB_ESCALA": "1",
    "BIORAG_PUENTES_SUELO": "0.5",
    "BIORAG_PUENTES_TECHO": "1.0",
})

import numpy as np

from core import concept_hub as hub
from core.memory import neurona_puentes as neurona, search
from core.memory_store import SQLiteMemoryBioRAG


PUENTES = [
    {"text": "origen nectar", "angle": "sinonimo"},
    {"text": "oscuro sendero", "angle": "problema"},
    {"text": "velero distante", "angle": "solucion"},
    {"text": "calendario urbano", "angle": "situacion"},
    {"text": "semilla alborada", "angle": "ingenuo"},
]
PARAMETROS_FABRICADOS = {
    "W": np.zeros((neurona.N_OCULTAS, neurona.N_ENTRADAS)),
    "b": np.ones(neurona.N_OCULTAS),
    "v": np.ones(neurona.N_OCULTAS),
}


def caso(carpeta, motor, consulta, activa=False, parche_diagnostico=False):
    archivo = os.path.join(carpeta, "caso.db")
    assert not os.path.exists(archivo)
    origenes = search._ORIGENES_NO_LITERALES | (
        {"concept_hub"} if parche_diagnostico else set()
    )
    with (
        patch.dict(os.environ, {"BIORAG_HUB_MOTOR": motor}),
        patch.object(neurona, "activa", return_value=activa),
        patch.object(neurona, "cargar", return_value=PARAMETROS_FABRICADOS),
        patch.object(search, "_ORIGENES_NO_LITERALES", origenes),
    ):
        cerebro = SQLiteMemoryBioRAG(archivo)
        try:
            cerebro.cursor.execute(
                "INSERT INTO largo_plazo (concepto,contenido) VALUES (?,?)",
                ("nodo_demo", "Una descripcion inventada sin vocabulario comun."),
            )
            cerebro.conn.commit()
            hub.crear_hub(cerebro.conn, "hub_demo", "nodo_demo")
            hub.agregar_bridges(cerebro.conn, "hub_demo", PUENTES)
            resultados, total = cerebro.buscar_por_frase(consulta, limite=10, preview_chars=0)
            return (
                bool(cerebro.last_hub_expansion),
                any(fila[0] == "nodo_demo" for fila in resultados),
                len(resultados),
                total,
            )
        finally:
            cerebro.cerrar_sistema()


def main():
    assert neurona._sano(PARAMETROS_FABRICADOS)
    assert not neurona.es_neutra(PARAMETROS_FABRICADOS)
    casos = [
        ("escala", "alborada", False, False, (True, False, 0, 1)),
        ("escala", "alborada", False, True, (True, True, 1, 1)),
        ("idf", "alborada", False, False, (True, False, 0, 1)),
        ("idf", "alborada", False, True, (True, True, 1, 1)),
        ("idf", "semilla alborada", False, False, (True, True, 1, 1)),
        ("idf", "semilla alborada", True, False, (False, False, 0, 0)),
    ]
    with tempfile.TemporaryDirectory(prefix="biorag-hub-sintetico-") as raiz:
        for indice, (motor, query, activa, parche, esperado) in enumerate(casos):
            carpeta = os.path.join(raiz, str(indice))
            os.mkdir(carpeta)
            observado = caso(carpeta, motor, query, activa, parche)
            assert observado == esperado, (indice, observado, esperado)
    print("casos=6; escala_e_idf_una_palabra=hub_presente_canonico_ausente")
    print("parche_diagnostico=canonico_presente; idf_dos_palabras=canonico_solo_sin_neurona_simulada")
    print("dbs=temporales_sinteticas; entrenamiento=ninguno; prueba=no_mcp_no_e1")


if __name__ == "__main__":
    main()
