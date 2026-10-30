"""Pruebas puras del arnés N/G/R: no MCP, fixtures, SQLite ni búsquedas."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.linea_base_segura import (
    ARMS,
    audit_fixture_gold,
    audit_names,
    close_gold_revision,
    file_sha256,
    mcp_concept_key,
    require_all_active,
    validate_freeze_approval,
    write_gold_revision,
)


def _episode(route=None):
    row = {
        "episode_id": "ep-1",
        "nodos": [
            {"concepto": "Aster Node", "contenido": "x"},
            {"concepto": "Middle Node", "contenido": "y"},
            {"concepto": "Final Node", "contenido": "z"},
        ],
        "aristas_gold": [["Aster Node", "Middle Node"], ["Middle Node", "Final Node"]],
    }
    if route:
        row["ruta_2_saltos"] = {"objetivo": "Aster Node", "intermedio": "Middle Node", "pista": "Final Node"}
    return row


def _graph(shortcut=False):
    edges = [
        {"origen": "Aster Node", "destino": "Middle Node", "peso": 1, "tipo": "coactivacion"},
        {"origen": "Middle Node", "destino": "Final Node", "peso": 1, "tipo": "coactivacion"},
    ]
    if shortcut:
        edges.append({"origen": "Aster Node", "destino": "Final Node", "peso": 0.1, "tipo": "co_nombre"})
    nodes = {name: {"concepto": name, "estado": "activo", "asociaciones": ""} for name in
             ("Aster Node", "Middle Node", "Final Node")}
    adjacency = {name: set() for name in nodes}
    for edge in edges:
        adjacency[edge["origen"]].add(edge["destino"])
        adjacency[edge["destino"]].add(edge["origen"])
    return {"nodos": nodes, "adjacency_activos": adjacency, "aristas_directas": edges,
            "sinapsis_latentes": [], "divergencias_espejo": [],
            "conteos": {"nodos": 3, "nodos_activos": 3, "nodos_dormidos": 0,
                        "aristas_directas_dirigidas": len(edges), "sinapsis_latentes": 0}}


def test_mcp_key_uses_ingest_transform_not_unicode_identity_normalizer():
    assert mcp_concept_key("Mi Concepto") == "mi_concepto"
    assert mcp_concept_key("Mi_Concepto") == "mi_concepto"
    report = audit_names([{"nodos": [{"concepto": "Mi Concepto"}, {"concepto": "Mi_Concepto"}]}])
    assert report["colisiones_clave"] == {"mi_concepto": ["Mi Concepto", "Mi_Concepto"]}


def test_co_nombre_is_reported_as_potential_risk_not_deleted_or_called_noise():
    report = audit_names([{"nodos": [{"concepto": "Aster Processing Node"},
                                       {"concepto": "Aster Processing Pipeline"}]}])
    assert report["pares_riesgo_co_nombre"]
    assert "ruido" not in report["pares_riesgo_co_nombre"][0]
    assert "aristas atribuidas" in report["nota"] or "fuente de verdad" in report["nota"]


def test_graph_audit_blocks_shortcut_without_removing_low_weight_automatic_edge():
    episode = _episode(route=True)
    graph = _graph(shortcut=True)
    result = audit_fixture_gold([episode], graph, audit_names([episode]))
    assert not result["congelacion_estructural_permitida"]
    assert "ruta_gold_2_saltos_no_es_unica" in result["bloqueos_congelacion"]
    assert any(edge["tipo"] == "co_nombre" and edge["peso"] == 0.1 for edge in graph["aristas_directas"])


def test_graph_audit_accepts_unique_two_hop_path():
    episode = _episode(route=True)
    result = audit_fixture_gold([episode], _graph(), audit_names([episode]))
    assert result["congelacion_estructural_permitida"]
    assert result["rutas_2_saltos"][0]["distancia_minima_activa"] == 2
    assert result["rutas_2_saltos"][0]["caminos_minimos_activos"] == 1


def test_graph_audit_blocks_missing_gold_edge():
    episode = _episode()
    episode["aristas_gold"].append(["Aster Node", "Final Node"])
    result = audit_fixture_gold([episode], _graph(), audit_names([episode]))
    assert not result["congelacion_estructural_permitida"]
    assert "aristas_gold_explicitas_ausentes" in result["bloqueos_congelacion"]
    assert result["gold_explicit_edges_missing"] == [["Aster Node", "Final Node"]]


def test_R_precondition_rejects_dormant_node():
    graph = _graph()
    graph["nodos"]["Middle Node"]["estado"] = "dormido"
    with pytest.raises(ValueError, match="todos los nodos activos"):
        require_all_active(graph, set(graph["nodos"]))


def test_gold_revision_preserves_base_and_requires_reason_and_closed_ledger(tmp_path):
    source = tmp_path / "gold.jsonl"
    destination = tmp_path / "gold-v2.jsonl"
    base = _episode(route=True)
    source.write_text(json.dumps(base, ensure_ascii=False) + "\n", encoding="utf-8")
    source_hash = file_sha256(source)
    revised = copy.deepcopy(base)
    revised["ruta_2_saltos"]["intermedio"] = "Middle Node (revisado)"
    with pytest.raises(ValueError, match="Ledger de ajustes"):
        write_gold_revision(source, destination, [revised], [])
    assert not destination.exists()
    revision = write_gold_revision(source, destination, [revised], [
        {"episode_id": "ep-1", "reason": "La revisión humana documentó el camino correcto antes de la búsqueda."}
    ])
    revision_path = destination.with_suffix(destination.suffix + ".revision.json")
    assert file_sha256(source) == source_hash
    assert revision["source_sha256"] == source_hash
    assert revision["closed_before_search"] is False
    closure = close_gold_revision(revision_path, "Dennys", "a" * 64)
    closure_path = revision_path.with_suffix(".closed.json")
    assert closure["closed_before_search"] is True
    closure["_file_sha256"] = file_sha256(closure_path)
    repeatability = {"mode": "MATERIALIZED_ONLY", "fixture_1_sha256": "b" * 64,
                     "not_tested_reason": "El alcance aprobado se limita a esta plantilla materializada.",
                     "_file_sha256": "d" * 64}
    approval = {"estado": "APROBADO", "aprobado_por": "Dennys",
                "gold_sha256": revision["revised_sha256"], "fixture_sha256": "b" * 64,
                "graph_review_sha256": "a" * 64, "gold_revision_closure_sha256": file_sha256(closure_path),
                "repeatability_report_sha256": "d" * 64,
                "arms": sorted(ARMS), "wake_W_included": False}
    validate_freeze_approval(approval, revision["revised_sha256"], "b" * 64, closure,
                             "a" * 64, repeatability)
    approval["gold_revision_closure_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="freeze manifest"):
        validate_freeze_approval(approval, revision["revised_sha256"], "b" * 64, closure,
                                 "a" * 64, repeatability)


def test_freeze_approval_rejects_hash_mismatch_W_and_missing_approval():
    repeatability = {"mode": "MATERIALIZED_ONLY", "fixture_1_sha256": "b" * 64,
                     "not_tested_reason": "Alcance limitado a fixture materializada.",
                     "_file_sha256": "d" * 64}
    valid = {"estado": "APROBADO", "aprobado_por": "Dennys", "gold_sha256": "a" * 64,
             "fixture_sha256": "b" * 64, "graph_review_sha256": "c" * 64,
             "repeatability_report_sha256": "d" * 64,
             "arms": sorted(ARMS), "wake_W_included": False}
    validate_freeze_approval(valid, "a" * 64, "b" * 64, repeatability_report=repeatability)
    with pytest.raises(ValueError, match="Hashes"):
        validate_freeze_approval(valid, "x" * 64, "b" * 64, repeatability_report=repeatability)
    with pytest.raises(ValueError, match="W queda pendiente"):
        validate_freeze_approval({**valid, "wake_W_included": True}, "a" * 64, "b" * 64,
                                 repeatability_report=repeatability)
    with pytest.raises(PermissionError, match="Falta aprobación"):
        validate_freeze_approval({**valid, "estado": "PENDIENTE"}, "a" * 64, "b" * 64,
                                 repeatability_report=repeatability)
