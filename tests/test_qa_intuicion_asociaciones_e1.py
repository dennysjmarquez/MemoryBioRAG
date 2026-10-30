"""Pruebas unitarias de gold, métricas e integridad de atribución; no inician MCP ni abren SQLite."""
import copy
import json

import pytest

from scripts.evaluar_qa_intuicion_asociaciones_e1 import (
    attribute_two_hop,
    bridge_payload,
    context_concepts,
    load_gold,
    main_result_concepts,
    metrics_by_channel,
    ordered_queries,
    percentile,
    response_concepts,
    serialize_report,
    validate_duplicate_query_gold,
    validate_positive_gold,
    validate_route_structure,
    validate_query_gold,
)
from scripts.analizar_anotaciones_qa_e1 import weighted_kappa


def _case():
    ep = {"ruta_2_saltos": {"objetivo": "objetivo", "intermedio": "medio", "pista": "pista"}}
    response = {"resultados": [{"concepto": "objetivo"}],
                "contexto_expandido": [{"concepto": "pista"}]}
    adjacency = {"objetivo": {"medio"}, "medio": {"objetivo", "pista"}, "pista": {"medio"}}
    return ep, response, adjacency, {"objetivo", "medio", "pista"}


def test_gold_precongelado_cubre_88_episodios_224_consultas_y_340_nodos():
    eps = load_gold()
    assert len(eps) == 88
    assert sum(len(ep["consultas"]) for ep in eps) == 224
    assert sum(len(ep["nodos"]) for ep in eps) == 340
    assert sum(len(ep["aristas_gold"]) for ep in eps) == 56
    assert sum(bool(ep["ruta_2_saltos"]) for ep in eps) == 12
    assert sum(q["idioma"] == "en" for ep in eps for q in ep["consultas"]) == 52


def test_objetivos_y_pistas_repetidos_tienen_evidencia_semantica_en_gold():
    episodes = load_gold()
    surface = "how should pending jobs be processed in safe groups?"
    group = [q for ep in episodes for q in ep["consultas"] if q["query"].casefold() == surface]
    assert len(group) == 4
    assert len(set(group[0]["objetivos_principales"])) == 4
    assert len(set(group[0]["relacionados_utiles"])) == 4
    assert all(set(q["objetivos_principales"]) == set(group[0]["objetivos_principales"]) for q in group)
    assert all(set(q["relacionados_utiles"]) == set(group[0]["relacionados_utiles"]) for q in group)
    for q in group:
        assert set(q["evidencia_objetivos"]) == set(q["objetivos_principales"])
        assert set(q["evidencia_relacionados_utiles"]) == set(q["relacionados_utiles"])
        assert all(q["evidencia_objetivos"][c] for c in q["objetivos_principales"])
        assert all(q["justificacion_relacionados_utiles"][c] for c in q["relacionados_utiles"])
    abstentions = [q for ep in episodes for q in ep["consultas"] if q["query"].casefold() == "what color was selected for the queue interface?"]
    assert len(abstentions) == 4
    assert all(q["espera_abstencion"] and not q["objetivos_principales"] and not q["relacionados_utiles"] for q in abstentions)
    assert all(q["justificacion_abstencion"] for q in abstentions)


def test_validador_rechaza_objetivos_o_pistas_repetidos_sin_evidencia():
    queries = [
        {"query": "Same question?", "query_id": "q1", "objetivos_principales": ["a"], "relacionados_utiles": [], "espera_abstencion": False,
         "evidencia_objetivos": {"a": "answer A"}, "justificacion_objetivos": {"a": "A answers the question."},
         "evidencia_relacionados_utiles": {}, "justificacion_relacionados_utiles": {}},
        {"query": " same   question? ", "query_id": "q2", "objetivos_principales": ["b"], "relacionados_utiles": [], "espera_abstencion": False,
         "evidencia_objetivos": {"b": "answer B"}, "justificacion_objetivos": {"b": "B answers the question."},
         "evidencia_relacionados_utiles": {}, "justificacion_relacionados_utiles": {}},
    ]
    contents = {"a": "answer A", "b": "answer B", "c": "clue C"}
    with pytest.raises(ValueError, match="Objetivos incompletos"):
        validate_duplicate_query_gold(queries, contents)
    queries[0]["objetivos_principales"] = ["a", "b"]
    queries[1]["objetivos_principales"] = ["a", "b"]
    queries[0]["evidencia_objetivos"] = queries[1]["evidencia_objetivos"] = {"a": "answer A", "b": "answer B"}
    queries[0]["justificacion_objetivos"] = queries[1]["justificacion_objetivos"] = {"a": "A answers it.", "b": "B answers it."}
    validate_duplicate_query_gold(queries, contents)
    queries[0]["evidencia_objetivos"]["b"] = "not a literal excerpt"
    with pytest.raises(ValueError, match="Evidencia/justificación inválida"):
        validate_duplicate_query_gold(queries, contents)
    queries[0]["evidencia_objetivos"]["b"] = "answer B"
    for q in queries:
        q["relacionados_utiles"] = ["c"]
    with pytest.raises(ValueError, match="Cada pista repetida requiere evidencia"):
        validate_duplicate_query_gold(queries, contents)
    for q in queries:
        q["evidencia_relacionados_utiles"] = {"c": "clue C"}
        q["justificacion_relacionados_utiles"] = {"c": "The clue gives relevant context."}
    validate_duplicate_query_gold(queries, contents)
    queries[0]["espera_abstencion"] = True
    with pytest.raises(ValueError, match="mezcla gold answerable y abstención"):
        validate_duplicate_query_gold(queries, contents)


def test_gold_sin_objetivo_se_distingue_de_etiqueta_omitida():
    missing = {"query_id": "q-missing", "objetivos_principales": [], "relacionados_utiles": []}
    with pytest.raises(ValueError, match="sin answerability/tipo explícitos"):
        validate_query_gold(missing)
    abstention = {**missing, "espera_abstencion": True, "respuesta_gold": "abstenerse", "tipo_consulta": "asunto_ausente"}
    validate_query_gold(abstention)
    contradictory = {**abstention, "objetivos_principales": ["nodo"]}
    with pytest.raises(ValueError, match="contradictorio"):
        validate_query_gold(contradictory)


def test_cada_positivo_cumple_diseno_de_apoyos_pistas_y_dos_distractores():
    positives = [ep for ep in load_gold() if ep["positivo"]]
    assert positives
    for ep in positives:
        validate_positive_gold(ep)
        nodes = {n["concepto"] for n in ep["nodos"]}
        distractors = set(ep["consultas"][0]["ruido_tonto"])
        assert len(ep["recuerdos_apoyo"]) >= 2
        assert ep["pistas_serendipia_utiles"]
        assert len(distractors) >= 2
        assert set(ep["recuerdos_apoyo"]).isdisjoint(distractors)
        assert set(ep["evidencia_pistas"]) <= nodes


def test_falla_gold_positivo_si_se_quitan_apoyos_o_evidencia_de_pista():
    ep = copy.deepcopy(next(ep for ep in load_gold() if ep["positivo"]))
    ep["recuerdos_apoyo"] = ep["recuerdos_apoyo"][:1]
    with pytest.raises(ValueError, match=">=2 recuerdos de apoyo"):
        validate_positive_gold(ep)
    ep = copy.deepcopy(next(ep for ep in load_gold() if ep["positivo"]))
    ep["evidencia_pistas"] = {}
    with pytest.raises(ValueError, match="justificación y evidencia"):
        validate_positive_gold(ep)


def test_bridges_sinteticos_cumplen_el_contrato_mcp_sin_validacion_humana():
    from core.concept_hub import validar_bridges
    for ep in load_gold():
        for node in ep["nodos"]:
            validos, rechazados = validar_bridges(bridge_payload(node["concepto"]), node["concepto"])
            assert len(validos) == 5, (node["concepto"], rechazados)


def test_validacion_estructural_rechaza_atajo_y_ruta_minima_ambigua():
    route = {"objetivo": "objetivo", "intermedio": "medio", "pista": "pista"}
    adjacency = {"objetivo": {"medio"}, "medio": {"objetivo", "pista"}, "pista": {"medio"}}
    assert validate_route_structure(route, adjacency)["estructura_gold_exactamente_2"] is True
    shortcut = {**adjacency, "objetivo": {"medio", "pista"}, "pista": {"medio", "objetivo"}}
    with pytest.raises(ValueError, match="único camino mínimo"):
        validate_route_structure(route, shortcut)
    ambiguous = {**adjacency, "objetivo": {"medio", "alterno"},
                 "medio": {"objetivo", "pista"}, "alterno": {"objetivo", "pista"},
                 "pista": {"medio", "alterno"}}
    with pytest.raises(ValueError, match="único camino mínimo"):
        validate_route_structure(route, ambiguous)


def test_resultados_y_contexto_solo_cuentan_sus_conceptos_propios():
    known = {"principal", "contexto", "lateral_plano", "lateral_enriquecido"}
    result_payload = [{
        "concepto": "principal",
        "asociaciones": {"items": [{"concepto": "lateral_plano"}]},
        "asociaciones_enriquecidas": [{"concepto": "lateral_enriquecido"}],
    }]
    context_payload = [{
        "concepto": "contexto",
        "asociaciones": [{"concepto": "lateral_plano"}],
    }]
    main = set(main_result_concepts(result_payload, known))
    context = context_concepts(context_payload, known)
    flat = response_concepts(result_payload[0]["asociaciones"], known)
    enriched = response_concepts(result_payload[0]["asociaciones_enriquecidas"], known)
    assert main == {"principal"}
    assert context == {"contexto"}
    assert flat == {"lateral_plano"}
    assert enriched == {"lateral_enriquecido"}
    assert main.isdisjoint(flat | enriched)
    assert context.isdisjoint(flat)


def test_asociacion_anidada_no_cuenta_como_semilla_para_atribucion():
    ep, response, adjacency, known = _case()
    response["resultados"] = [{"concepto": "otro", "asociaciones": [{"concepto": "objetivo"}]}]
    response["trazabilidad"] = {"rutas_expansion": [{
        "desde": "objetivo", "hasta": "pista", "ruta": ["objetivo", "medio", "pista"], "saltos": 2,
    }]}
    q = {"query_id": "q", "relacionados_utiles": ["pista"], "objetivos_principales": []}
    out = attribute_two_hop(ep, q, response, adjacency, known | {"otro"}, max_depth=2)
    assert out["estado"] == "no atribuible"
    assert "semillas devueltas" in out["motivo"]


def test_asociacion_anidada_en_contexto_no_cuenta_como_exposicion():
    ep, response, adjacency, known = _case()
    response["contexto_expandido"] = [{"concepto": "medio", "asociaciones": [{"concepto": "pista"}]}]
    response["trazabilidad"] = {"rutas_expansion": [{
        "desde": "objetivo", "hasta": "pista", "ruta": ["objetivo", "medio", "pista"], "saltos": 2,
    }]}
    q = {"query_id": "q", "relacionados_utiles": ["pista"], "objetivos_principales": []}
    out = attribute_two_hop(ep, q, response, adjacency, known, max_depth=2)
    assert out["estado"] == "no atribuible"
    assert out["motivo"] == "pista no aparece en contexto_expandido"


def test_ruta_en_grafo_y_contexto_sin_traza_efectiva_es_no_atribuible():
    ep, response, adjacency, known = _case()
    q = {"query_id": "q", "relacionados_utiles": ["pista"], "objetivos_principales": []}
    out = attribute_two_hop(ep, q, response, adjacency, known, max_depth=2)
    assert out["estado"] == "no atribuible"
    assert "no expone" in out["motivo"]
    # La mera existencia de la ruta gold en el grafo sigue sin ser evidencia de recorrido.
    assert adjacency["objetivo"] == {"medio"}


def test_atribucion_acepta_solo_traza_mcp_explicita_y_gold_de_dos_saltos():
    ep, response, adjacency, known = _case()
    q = {"query_id": "q", "relacionados_utiles": ["pista"], "objetivos_principales": []}
    response["trazabilidad"] = {"rutas_expansion": [{
        "desde": "objetivo", "hasta": "pista", "ruta": ["objetivo", "medio", "pista"], "saltos": 2,
    }]}
    out = attribute_two_hop(ep, q, response, adjacency, known, max_depth=2)
    assert out["estado"] == "atribuible_2_saltos"
    assert out["ruta_efectiva"] == ["objetivo", "medio", "pista"]
    response["trazabilidad"]["rutas_expansion"][0]["ruta"] = ["objetivo", "pista"]
    assert attribute_two_hop(ep, q, response, adjacency, known, max_depth=2)["estado"] == "no atribuible"


def test_dos_saltos_sin_semilla_objetivo_o_sin_ventana_se_reportan_no_atribuible():
    ep, response, adjacency, known = _case()
    q = {"query_id": "q", "relacionados_utiles": ["pista"], "objetivos_principales": []}
    assert attribute_two_hop(ep, q, response, adjacency, known, max_depth=1)["estado"] == "no atribuible"
    response["resultados"] = [{"concepto": "otra_semilla"}]
    assert attribute_two_hop(ep, q, response, adjacency, known | {"otra_semilla"}, max_depth=2)["estado"] == "no atribuible"


def _metric_row(*, objective, useful, noise, channel_values, abstain, ranking, rank):
    return {
        "objetivos_principales": objective,
        "relacionados_utiles": useful,
        "ruido_tonto": noise,
        "canales": channel_values,
        "espera_abstencion": abstain,
        "ranking_resultados": ranking,
        "rango_objetivo_resultados": rank,
        "episode_id": "ep",
    }


def test_metricas_union_no_indexa_clave_inexistente_y_cuenta_abstenciones_explicitas():
    channels = {"resultados": ["objetivo"], "asociaciones_enriquecidas": ["pista"],
                "asociaciones": [], "contexto_expandido": ["pista"]}
    positive = _metric_row(objective=["objetivo"], useful=["pista"], noise=["ruido"],
                           channel_values=channels, abstain=False, ranking=["objetivo"], rank=1)
    negative = _metric_row(objective=[], useful=[], noise=["ruido"],
                           channel_values={k: ["ruido"] if k == "resultados" else [] for k in channels},
                           abstain=True, ranking=["ruido"], rank=None)
    report = metrics_by_channel([positive, negative])
    assert report["union_canales"]["objetivo_visible_consultas"] == 1
    assert report["union_canales"]["relacionados_utiles_visibles"] == 1
    assert report["resultados"]["consultas_sin_objetivo"] == 1
    assert report["resultados"]["falsos_positivos_consultas_sin_objetivo"] == 1
    assert report["resultados"]["R_at_1"] == 1.0


def test_percentiles_y_reporte_son_sincronos_y_json_serializables():
    assert percentile([3, 1, 2], 0.50) == 2
    assert percentile([], 0.95) is None
    payload = serialize_report({"metricas": metrics_by_channel([]), "latencia": {"p50": percentile([4], 0.5)}})
    assert json.loads(payload)["latencia"]["p50"] == 4
    with pytest.raises(TypeError):
        serialize_report({"coroutine_o_objeto_no_json": object()})


def test_control_inverso_preserva_orden_interno_de_cada_episodio():
    eps = load_gold()[:3]
    original = ordered_queries(eps, "D")
    inverse = ordered_queries(eps, "D-inv")
    assert [q["query_id"] for _, q in inverse] == [q["query_id"] for ep in reversed(eps) for q in ep["consultas"]]
    assert len(original) == len(inverse)


def test_acuerdo_ponderado_no_aplica_umbral_de_aceptacion():
    assert weighted_kappa([0, 1, 2, 3], [0, 1, 2, 3]) == 1.0
    assert weighted_kappa([0, 0, 3, 3], [3, 3, 0, 0]) <= 0.0
