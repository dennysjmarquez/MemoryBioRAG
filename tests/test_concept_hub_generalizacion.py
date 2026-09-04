"""
Suite de evaluación de generalización semántica para Concept Hub.

Verifica que Concept Hub resuelva paráfrasis naturales reales que no coinciden
literalmente con el texto de ningún bridge (anti-memorización / anti-overfitting).
"""

import os
import pytest
from core.memory_store import SQLiteMemoryBioRAG
from core.concept_hub import expandir_query_con_hub, cargar_hubs_iniciales, crear_tablas


CASOS_PARAFRASIS = [
    {
        "id": "paraf_2a_cambio_rompio",
        "query": "metí un cambio y todo se rompió",
        "esperado": "leccion_control_flujo_codigo_preexistente",
        "hub_esperado": "control_flujo",
        "descripcion": "Paráfrasis caso 2: regresión por modificación"
    },
    {
        "id": "paraf_2b_tocar_estable",
        "query": "toqué algo que andaba bien y dejó de andar",
        "esperado": "leccion_control_flujo_codigo_preexistente",
        "hub_esperado": "control_flujo",
        "descripcion": "Paráfrasis caso 2: ruptura de código previo"
    },
    {
        "id": "paraf_5_desacuerdo_ias",
        "query": "dos modelos de IA que no están de acuerdo, ¿cómo resuelvo?",
        "esperado": "resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad",
        "hub_esperado": "consenso_multi_modelo",
        "descripcion": "Paráfrasis caso 5: contradicción entre LLMs"
    },
    {
        "id": "paraf_1_antes_programador",
        "query": "qué hacía antes de ser programador",
        "esperado": "historia_tasajera_fumigador_rufino",
        "hub_esperado": "trabajo_previo",
        "descripcion": "Paráfrasis caso 1: vida laboral previa a IT"
    },
    {
        "id": "paraf_4_sobrevivir_sin_tecnologia",
        "query": "cómo sobrevivía económicamente antes de la tecnología",
        "esperado": "historia_tasajera_fumigador_rufino",
        "hub_esperado": "trabajo_previo",
        "descripcion": "Paráfrasis caso 4: supervivencia económica pre-tecnología"
    },
]


@pytest.fixture(scope="module")
def cerebro_eval():
    """Instancia de SQLiteMemoryBioRAG configurada con HUBS_INICIALES cargados."""
    db_path = os.environ.get("BIORAG_PATH") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "MemoryBioRAG_Data", "memory_biorag.db"
    )
    cerebro = SQLiteMemoryBioRAG(db_path)
    crear_tablas(cerebro.conn)
    cargar_hubs_iniciales(cerebro.conn)
    yield cerebro
    cerebro.cerrar_sistema()


@pytest.mark.parametrize("caso", CASOS_PARAFRASIS, ids=[c["id"] for c in CASOS_PARAFRASIS])
def test_generalizacion_hub_expansion(cerebro_eval, caso):
    """Verifica que expandir_query_con_hub active el hub correcto para la paráfrasis."""
    hub_res = expandir_query_con_hub(caso["query"], cerebro_eval.conn)
    assert hub_res is not None, f"El hub no activó ninguna expansión para '{caso['query']}'"
    assert hub_res["hub_id"] == caso["hub_esperado"], (
        f"Hub incorrecto: esperado '{caso['hub_esperado']}', obtenido '{hub_res['hub_id']}'"
    )
    assert caso["esperado"] in hub_res["canonical_nodes"], (
        f"El nodo '{caso['esperado']}' debe estar en canonical_nodes del hub expandido"
    )


@pytest.mark.parametrize("caso", CASOS_PARAFRASIS, ids=[c["id"] for c in CASOS_PARAFRASIS])
def test_generalizacion_recuperacion_top5(cerebro_eval, caso):
    """Verifica que buscar_por_frase recupere el nodo esperado en el Top 5 con la paráfrasis."""
    res, total = cerebro_eval.buscar_por_frase(caso["query"], limite=5)
    recuperados = [r[0] for r in res]
    assert caso["esperado"] in recuperados, (
        f"Para la query '{caso['query']}' ({caso['descripcion']}), el nodo '{caso['esperado']}' "
        f"no fue encontrado en el Top 5. Recuperados: {recuperados}"
    )
