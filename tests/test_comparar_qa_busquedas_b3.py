from copy import deepcopy

from scripts.comparar_qa_busquedas_b3 import (
    CORPUS,
    HUB_B2,
    HUB_B3,
    comparar_crecimiento,
    comparar_misma_base,
    resumen_expansiones_cjk,
)


def _datos(hub):
    resultado = {"acierto_r5": True, "acierto_r1": True, "last_hub_expansion": None, "top5": ["海岸灯塔"]}
    return {
        "metadatos": {
            "semilla": {"sha256": "misma"}, "hub_sha256": hub, "corpus_sha256": CORPUS,
            "reloj_fijo_unix": 1, "pythonhashseed": "0", "biorag_neurona": "0", "profundidad": "activos",
            "limite_publico": 5, "limite_interno_mcp": 15, "ignore_peso_sinaptico": "default", "control_hub": "1/0",
        },
        "casos": [{"id": "zh-01", "idioma": "zh", "tipo": "nombre", "concepto": "海岸灯塔",
                   "query": "海岸灯塔", "sustantivos_clave": "海岸灯塔", "contiene_nombre": True,
                   "on": deepcopy(resultado), "off": deepcopy(resultado)}],
    }


def test_misma_base_exige_misma_huella_y_la_respuesta_completa():
    a, b = _datos(HUB_B2), _datos(HUB_B3)
    resumen, problemas = comparar_misma_base(a, b)
    assert not problemas and not resumen["respuestas_o_trazas_diferentes"]
    b["casos"][0]["on"]["top5"] = []
    resumen, problemas = comparar_misma_base(a, b)
    assert resumen["respuestas_o_trazas_diferentes"] and problemas
    b["metadatos"]["semilla"]["sha256"] = "distinta"
    _, problemas = comparar_misma_base(a, b)
    assert any("misma semilla" in p for p in problemas)


def test_reconoce_perdidas_en_las_dos_bases():
    a, b = _datos(HUB_B2), _datos(HUB_B3)
    b["casos"][0]["on"]["acierto_r5"] = False
    resumen = comparar_crecimiento(a, b)
    assert resumen["metricas"]["on_acierto_r5"]["perdidas"] == [{"id": "zh-01", "tipo": "nombre"}]
    assert not resumen["metricas"]["off_acierto_r5"]["perdidas"]


def test_una_expansion_al_hub_no_significa_resultado_entregado():
    dato = _datos(HUB_B3)
    fila = dato["casos"][0]
    fila["tipo"] = "puente_completo"
    fila["on"].update({"acierto_r5": False, "last_hub_expansion": {"canonical_nodes": ["海岸灯塔"]},
                       "origen_esperado": ["concept_hub", 1.0]})
    resumen = resumen_expansiones_cjk(dato)
    assert resumen["expansion_al_nodo_correcto"] == 1
    assert resumen["origen_esperado_concept_hub"] == 1
    assert resumen["sin_nodo_en_top5"] == 1
