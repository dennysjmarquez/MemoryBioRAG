"""Tests unitarios puros del diseño E1; no levantan MCP ni abren SQLite."""
from scripts.evaluar_qa_intuicion_asociaciones_e1 import (
    attribute_two_hop, bridge_payload, load_gold, ordered_queries,
)
from scripts.analizar_anotaciones_qa_e1 import weighted_kappa


def _case():
    ep = {"ruta_2_saltos": {"objetivo": "objetivo", "intermedio": "medio", "pista": "pista"}}
    response = {"resultados": [{"concepto": "objetivo"}],
                "contexto_expandido": [{"concepto": "pista"}]}
    adjacency = {"objetivo": {"medio"}, "medio": {"objetivo", "pista"}, "pista": {"medio"}}
    return ep, response, adjacency, {"objetivo", "medio", "pista"}


def test_gold_precongelado_cubre_88_episodios_y_224_consultas():
    eps = load_gold()
    assert len(eps) == 88
    assert sum(len(ep["consultas"]) for ep in eps) == 224
    assert sum(bool(ep["ruta_2_saltos"]) for ep in eps) == 12
    assert sum(q["idioma"] == "en" for ep in eps for q in ep["consultas"]) == 52


def test_bridges_sinteticos_cumplen_el_contrato_mcp_sin_validacion_humana():
    from core.concept_hub import validar_bridges
    for ep in load_gold():
        for node in ep["nodos"]:
            validos, rechazados = validar_bridges(bridge_payload(node["concepto"]), node["concepto"])
            assert len(validos) == 5, (node["concepto"], rechazados)


def test_dos_saltos_solo_se_atribuyen_con_camino_efectivo_y_semilla_objetivo():
    ep, response, adjacency, known = _case()
    q = {"query_id": "q", "relacionados_utiles": ["pista"], "objetivos_principales": []}
    out = attribute_two_hop(ep, q, response, adjacency, known, max_depth=2)
    assert out["estado"] == "atribuible_2_saltos"
    assert out["ruta_efectiva"] == ["objetivo", "medio", "pista"]
    response["resultados"] = [{"concepto": "otra_semilla"}]
    out = attribute_two_hop(ep, q, response, adjacency, known | {"otra_semilla"}, max_depth=2)
    assert out["estado"] == "no atribuible"


def test_atajo_efectivo_o_ruta_no_coincidente_se_reporta_no_atribuible():
    ep, response, adjacency, known = _case()
    adjacency["objetivo"].add("pista")
    adjacency["pista"].add("objetivo")
    out = attribute_two_hop(ep, {}, response, adjacency, known, max_depth=2)
    assert out["estado"] == "no atribuible"
    assert "exactamente dos saltos" in out["motivo"]


def test_control_inverso_preserva_orden_interno_de_cada_episodio():
    eps = load_gold()[:3]
    original = ordered_queries(eps, "D")
    inverse = ordered_queries(eps, "D-inv")
    assert [q["query_id"] for _, q in inverse] == [q["query_id"] for ep in reversed(eps) for q in ep["consultas"]]
    assert len(original) == len(inverse)


def test_acuerdo_ponderado_no_aplica_umbral_de_aceptacion():
    assert weighted_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == 1.0
    assert weighted_kappa([0, 0, 3, 3], [3, 3, 0, 0]) <= 0.0
