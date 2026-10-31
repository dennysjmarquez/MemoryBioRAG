"""Pruebas puras del arnés N/G/R: no MCP real, fixtures, SQLite ni búsquedas."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest

import scripts.linea_base_segura as harness
from scripts.linea_base_segura import (
    ARMS,
    audit_fixture_gold,
    audit_repeatability,
    audit_names,
    classify_attempt,
    close_gold_revision,
    file_sha256,
    guarded_mcp_call,
    mcp_concept_key,
    measure_baseline,
    persist_evidence,
    require_all_active,
    validate_freeze_approval,
    validate_row_field_changes,
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


def _table(columns, rows, primary_key):
    return {"schema": [{"name": name, "type": "REAL" if name in {"peso", "creado_en", "ultimo_uso", "marcado_en", "acceso_timestamp", "top_score"} else "TEXT",
                         "notnull": 0, "default": None,
                         "pk": index + 1 if name in primary_key else 0}
                        for index, name in enumerate(columns)],
            "rows": copy.deepcopy(rows)}


def _fixture_rows():
    return {
        "largo_plazo": _table(["concepto", "estado"], [
            {"concepto": "Aster Node", "estado": "activo"},
            {"concepto": "Middle Node", "estado": "activo"},
        ], ["concepto"]),
        "log_busquedas": _table(["id", "query", "resultados_count", "top_score", "creado_en",
                                 "util", "params_json", "conceptos_top"], [], ["id"]),
        "nodo_accesos_historial": _table(["id", "concepto", "acceso_timestamp"], [], ["id"]),
        "sinapsis": _table(["origen", "destino", "peso", "tipo", "creado_en", "ultimo_uso"], [
            {"origen": "Aster Node", "destino": "Middle Node", "peso": 0.5,
             "tipo": "manual", "creado_en": 1.0, "ultimo_uso": None},
        ], ["origen", "destino"]),
        "sdm_dirty": _table(["concepto", "marcado_en"], [], ["concepto"]),
    }


def _repeatability(fixture_sha, gold_sha, report_sha="d" * 64):
    paths = ["/tmp/build-a.sqlite", "/tmp/build-b.sqlite"]
    builds = [
        {"construction_id": "build-a", "fixture_path": paths[0], "gold_sha256": gold_sha,
         "event_count": 3, "run_manifest_sha256": "1" * 64,
         "preparation_report_sha256": "2" * 64, "events_sha256": "3" * 64},
        {"construction_id": "build-b", "fixture_path": paths[1], "gold_sha256": gold_sha,
         "event_count": 3, "run_manifest_sha256": "4" * 64,
         "preparation_report_sha256": "5" * 64, "events_sha256": "6" * 64},
    ]
    return {"mode": "REPEATABLE_PAIR", "independent_builds_verified": True,
            "construction_ids": ["build-a", "build-b"], "build_evidence": builds,
            "fixture_1_sha256": fixture_sha, "fixture_2_sha256": fixture_sha,
            "identical_structural": True, "_file_sha256": report_sha}


def _run_mocked_baseline(tmp_path, monkeypatch, mutate_r=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    temp_root = tmp_path / "qa_tmp"
    temp_root.mkdir()
    monkeypatch.setattr(harness, "ROOT", repo_root)
    monkeypatch.setenv("BIORAG_QA_TEMP_ROOT", str(temp_root))
    fixture_path = temp_root / "fixture.sqlite"
    fixture_path.touch()
    gold_path = tmp_path / "gold.jsonl"
    gold_path.write_text("mock gold bytes\\n", encoding="utf-8")
    gold_sha = file_sha256(gold_path)
    monkeypatch.setattr(harness, "BASE_GOLD_SHA256", gold_sha)
    episodes = [{
        "episode_id": "mock-episode", "stratum": "mock",
        "nodos": [{"concepto": "Aster Node", "contenido": "answer"},
                  {"concepto": "Middle Node", "contenido": "context"}],
        "aristas_gold": [],
        "consultas": [{"query_id": "mock-query", "idioma": "es", "query": "where is the answer?",
                        "sustantivos_clave": ["answer"], "objetivos_principales": ["Aster Node"],
                        "relacionados_utiles": [], "ruido_tonto": [], "espera_abstencion": False}],
    }]
    state0 = _fixture_rows()
    fixture_sha = "f" * 64
    direct = copy.deepcopy(state0["sinapsis"]["rows"])
    graph = {"integridad": "ok",
        "nodos": {row["concepto"]: {**row} for row in state0["largo_plazo"]["rows"]},
        "aristas_directas": direct,
        "sinapsis_latentes": [],
        "adjacency_activos": {"Aster Node": {"Middle Node"}, "Middle Node": {"Aster Node"}},
        "divergencias_espejo": [],
        "conteos": {"nodos": 2, "nodos_activos": 2, "nodos_dormidos": 0,
                    "aristas_directas_dirigidas": 1, "sinapsis_latentes": 0},
        "tablas_sha256": {}, "sha256_fixture_logica": fixture_sha}
    states = {}

    def fake_copy(source, destination):
        destination.write_text("mock copy marker", encoding="utf-8")
        states[destination.resolve()] = copy.deepcopy(state0)

    def fake_snapshot_rows(path, root):
        return copy.deepcopy(states[path.resolve()])

    def fake_snapshot(path):
        snapshots = states[path.resolve()]
        return {table: hashlib.sha256(json.dumps(value, sort_keys=True, default=repr).encode()).hexdigest()
                for table, value in snapshots.items()}

    async def fake_mcp_call(db_path, root, arguments):
        if mutate_r and "R" in db_path.parts:
            edge = states[db_path.resolve()]["sinapsis"]["rows"][0]
            if mutate_r == "valid_reinforcement":
                edge["peso"] = 0.6
                edge["ultimo_uso"] = 1793059200.0
            elif mutate_r == "forbidden_type":
                edge["tipo"] = "co_nombre"
        return '{"status":"ok"}', {"status": "ok", "resultados": [{"concepto": "Aster Node"}],
                                      "contexto_expandido": []}, []

    monkeypatch.setattr(harness, "copy_sqlite", fake_copy)
    monkeypatch.setattr(harness, "snapshot_sha256", lambda path: fixture_sha)
    monkeypatch.setattr(harness, "readonly_snapshot", fake_snapshot)
    monkeypatch.setattr(harness, "snapshot_table_rows", fake_snapshot_rows)
    monkeypatch.setattr(harness, "inspect_fixture", lambda path, root: copy.deepcopy(graph))
    monkeypatch.setattr(harness, "guarded_mcp_call", fake_mcp_call)

    preflight = audit_fixture_gold(episodes, graph, audit_names(episodes))
    graph_review_sha = hashlib.sha256(harness._canonical(preflight).encode("utf-8")).hexdigest()
    second_fixture = temp_root / "independent-build.sqlite"
    second_fixture.touch()
    for path, build_id in ((fixture_path, "build-1"), (second_fixture, "build-2")):
        evidence = path.parent / (path.name + ".evidence")
        event = {"construction_id": build_id, "sequence": 1, "tool": "recordar"}
        build_report = {"construction_id": build_id, "fixture_path": str(path.resolve()),
                        "gold_sha256": gold_sha, "fixture_sha256": fixture_sha,
                        "fixture": {"sha256_fixture_logica": fixture_sha},
                        "baseline_searches_run": 0, "fixture_events": [event]}
        persist_evidence(evidence, "run_manifest", {"construction_id": build_id,
            "fixture_path": str(path.resolve()), "gold_sha256": gold_sha,
            "mcp_session_created_for_this_build": True})
        persist_evidence(evidence, "event_000001", event)
        persist_evidence(evidence, "preparation_report", build_report)
    repeatability = audit_repeatability(fixture_path, second_fixture, temp_root)
    repeat_path = tmp_path / "repeatability.json"
    repeat_path.write_text(json.dumps(repeatability), encoding="utf-8")
    repeat_sha = file_sha256(repeat_path)
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps({
        "estado": "APROBADO", "aprobado_por": "Dennys", "gold_sha256": gold_sha,
        "fixture_sha256": fixture_sha, "graph_review_sha256": graph_review_sha,
        "repeatability_report_sha256": repeat_sha, "arms": sorted(ARMS), "wake_W_included": False,
    }), encoding="utf-8")
    output_path = tmp_path / "reports" / "baseline.json"
    report = asyncio.run(measure_baseline(fixture_path, temp_root, episodes, gold_path,
                                          approval_path, repeat_path, output_path))
    return report, output_path, states


def test_real_measurement_harness_flow_accepts_valid_field_level_R_reforcement_with_mocks(tmp_path, monkeypatch):
    report, output_path, states = _run_mocked_baseline(tmp_path, monkeypatch, mutate_r="valid_reinforcement")
    assert report["valida"] is True
    assert report["invalidaciones"] == []
    assert output_path.is_file()
    r_transition = report["mutaciones_por_brazo"]["R"][0]
    r_delta = r_transition["row_field_audit"]["changes"]["sinapsis"]["updated"][0]
    assert r_delta["fields_changed"] == ["peso", "ultimo_uso"]
    assert len(states) == len(ARMS)


def test_real_measurement_harness_flow_invalidates_and_keeps_row_diff_with_mocks(tmp_path, monkeypatch):
    report, output_path, states = _run_mocked_baseline(tmp_path, monkeypatch, mutate_r="forbidden_type")
    assert report["valida"] is False
    assert report["estado"].startswith("INVALIDA")
    assert report["invalidaciones"][0]["arm"] == "R"
    evidence_dir = Path(report["invalidaciones"][0]["evidence_dir"])
    diff = json.loads((evidence_dir / "diff.json").read_text(encoding="utf-8"))
    assert any("UPDATE sináptico alteró identidad/tipo" in item["reason"]
               for item in diff["row_field_audit"]["violations"])
    db_path = Path(report["invalidaciones"][0]["db_path"])
    assert db_path.is_file()
    assert output_path.is_file()
    assert len(states) == len(ARMS)


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


def test_repeatability_requires_two_independent_mcp_construction_ledgers(tmp_path, monkeypatch):
    temp_root = tmp_path / "qa_tmp"
    temp_root.mkdir()
    monkeypatch.setenv("BIORAG_QA_TEMP_ROOT", str(temp_root))
    first_path = temp_root / "first.sqlite"
    second_path = temp_root / "second.sqlite"
    first_path.touch()
    second_path.touch()
    graph = _graph()
    graph["sha256_fixture_logica"] = "f" * 64
    graph["tablas_sha256"] = {"largo_plazo": "a" * 64}
    monkeypatch.setattr(harness, "inspect_fixture", lambda path, root: copy.deepcopy(graph))

    def write_build(path, construction_id):
        evidence = path.parent / (path.name + ".evidence")
        event = {"construction_id": construction_id, "sequence": 1, "tool": "recordar"}
        report = {"construction_id": construction_id, "fixture_path": str(path.resolve()),
                  "gold_sha256": "g" * 64, "fixture_sha256": "f" * 64,
                  "fixture": {"sha256_fixture_logica": "f" * 64},
                  "baseline_searches_run": 0, "fixture_events": [event]}
        persist_evidence(evidence, "run_manifest", {"construction_id": construction_id,
            "fixture_path": str(path.resolve()), "gold_sha256": "g" * 64,
            "mcp_session_created_for_this_build": True})
        persist_evidence(evidence, "event_000001", event)
        persist_evidence(evidence, "preparation_report", report)

    write_build(first_path, "build-1")
    write_build(second_path, "build-2")
    result = audit_repeatability(first_path, second_path, temp_root)
    assert result["independent_builds_verified"] is True
    assert result["identical_structural"] is True
    assert result["construction_ids"] == ["build-1", "build-2"]
    assert len(result["build_evidence"]) == 2


def test_repeatability_rejects_same_build_id_even_if_db_paths_differ(tmp_path, monkeypatch):
    temp_root = tmp_path / "qa_tmp"
    temp_root.mkdir()
    monkeypatch.setenv("BIORAG_QA_TEMP_ROOT", str(temp_root))
    first_path, second_path = temp_root / "a.sqlite", temp_root / "b.sqlite"
    first_path.touch()
    second_path.touch()
    graph = _graph()
    graph["sha256_fixture_logica"] = "f" * 64
    graph["tablas_sha256"] = {}
    monkeypatch.setattr(harness, "inspect_fixture", lambda path, root: copy.deepcopy(graph))
    for path in (first_path, second_path):
        evidence = path.parent / (path.name + ".evidence")
        event = {"construction_id": "copied-build", "sequence": 1}
        report = {"construction_id": "copied-build", "fixture_path": str(path.resolve()),
                  "gold_sha256": "g" * 64, "fixture_sha256": "f" * 64,
                  "fixture": {"sha256_fixture_logica": "f" * 64},
                  "baseline_searches_run": 0, "fixture_events": [event]}
        persist_evidence(evidence, "run_manifest", {"construction_id": "copied-build",
            "fixture_path": str(path.resolve()), "gold_sha256": "g" * 64,
            "mcp_session_created_for_this_build": True})
        persist_evidence(evidence, "event_000001", event)
        persist_evidence(evidence, "preparation_report", report)
    result = audit_repeatability(first_path, second_path, temp_root)
    assert result["independent_builds_verified"] is False
    assert result["mode"] == "UNVERIFIED"


def test_inspection_guard_accepts_fixture_copy_under_run_root_and_rejects_external_path(tmp_path, monkeypatch):
    import shutil
    import sqlite3

    temp_root = tmp_path / "qa-temp"
    temp_root.mkdir()
    monkeypatch.setenv("BIORAG_QA_TEMP_ROOT", str(temp_root))

    source = temp_root / "fixture.sqlite"
    with sqlite3.connect(source) as con:
        con.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
        con.execute("INSERT INTO sample VALUES (1, 'isolated')")
    run_root = temp_root / "execution-001"
    fixture_copy = run_root / "db" / "R" / "fixture.sqlite"
    fixture_copy.parent.mkdir(parents=True)
    shutil.copy2(source, fixture_copy)

    # Se llama al inspector real y se pasa el run_root, no un mock de la guarda.
    snapshot = harness.snapshot_table_rows(fixture_copy, run_root)
    assert snapshot["sample"]["rows"] == [{"id": 1, "value": "isolated"}]

    external = tmp_path / "outside.sqlite"
    with sqlite3.connect(external) as con:
        con.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
    with pytest.raises(ValueError, match="fuera de BIORAG_QA_TEMP_ROOT"):
        harness.snapshot_table_rows(external, run_root)


def test_R_row_policy_accepts_only_weight_and_last_use_reforcement():
    before = _fixture_rows()
    after = copy.deepcopy(before)
    after["sinapsis"]["rows"][0]["peso"] = 0.6
    after["sinapsis"]["rows"][0]["ultimo_uso"] = 1000.0
    result = validate_row_field_changes(before, after, "R", {"Aster Node", "Middle Node"})
    assert result["valid"] is True
    delta = result["changes"]["sinapsis"]["updated"][0]
    assert delta["fields_changed"] == ["peso", "ultimo_uso"]


def test_R_row_policy_rejects_allowed_table_but_forbidden_type_or_created_field():
    before = _fixture_rows()
    after = copy.deepcopy(before)
    after["sinapsis"]["rows"][0]["tipo"] = "rafaga_rememb"
    after["sinapsis"]["rows"][0]["creado_en"] = 2000.0
    result = validate_row_field_changes(before, after, "R", {"Aster Node", "Middle Node"})
    assert result["valid"] is False
    assert any("identidad/tipo/creado_en" in item["reason"] for item in result["violations"])


def test_R_new_synapse_and_sdm_dirty_require_expected_rows_and_fields():
    before = _fixture_rows()
    after = copy.deepcopy(before)
    after["sinapsis"]["rows"].append({"origen": "Aster Node", "destino": "Middle Node 2",
        "peso": 0.6, "tipo": "rafaga_rememb", "creado_en": 1000.0, "ultimo_uso": None})
    after["sdm_dirty"]["rows"].extend([
        {"concepto": "Aster Node", "marcado_en": 1000.0},
        {"concepto": "Middle Node 2", "marcado_en": 1000.0},
    ])
    known = {"Aster Node", "Middle Node", "Middle Node 2"}
    assert validate_row_field_changes(before, after, "R", known)["valid"] is True
    bad = copy.deepcopy(after)
    bad["sdm_dirty"]["rows"].append({"concepto": "Ghost Node", "marcado_en": 1000.0})
    result = validate_row_field_changes(before, bad, "R", known)
    assert not result["valid"]
    assert any("sdm_dirty contiene" in item["reason"] for item in result["violations"])


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
    repeatability = _repeatability("b" * 64, revision["revised_sha256"])

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
    repeatability = _repeatability("b" * 64, "a" * 64)

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
    with pytest.raises(ValueError, match="dos construcciones independientes"):
        validate_freeze_approval(valid, "a" * 64, "b" * 64,
                                 repeatability_report={**repeatability, "independent_builds_verified": False})


def test_mcp_error_response_invalidates_attempt():
    status = classify_attempt({"status": "error", "mensaje": "rechazado"}, [], [])
    assert status["invalida"] is True
    assert status["motivos"][0]["tipo"] == "error_mcp"


def test_transport_failure_invalidates_attempt():
    error = {"fase": "llamada_mcp", "tipo": "ConnectionError", "mensaje": "pipe cerrado"}
    status = classify_attempt({"status": "transport_error"}, [error], [])
    assert status["invalida"] is True
    assert error in status["motivos"]


def test_unexpected_mutation_invalidates_attempt_and_persists_diff(tmp_path):
    diff = {"tablas": ["sinapsis"], "arista_nueva": ["A", "B", "co_nombre", 0.2]}
    status = classify_attempt({"status": "ok"}, [], ["sinapsis/estado"])
    path = persist_evidence(tmp_path / "run" / "evidence", "diff", diff)
    assert status["invalida"] is True
    assert status["motivos"] == [{"tipo": "mutacion_inesperada", "detalles": ["sinapsis/estado"]}]
    assert json.loads(path.read_text(encoding="utf-8")) == diff


def test_evidence_file_survives_failure_without_temporary_directory_cleanup(tmp_path):
    evidence_root = tmp_path / "biorag_linea_base_run" / "evidence" / "N0" / "query-1"
    record = {"response": {"status": "error"}, "exception": "timeout", "db_diff": {"sinapsis": "changed"}}
    path = persist_evidence(evidence_root, "call", record)
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == record
    assert path.parent.exists()


@pytest.mark.parametrize("failure_phase", ["startup", "tool", "teardown", "mcp_response"])
def test_guarded_mcp_call_captures_lifecycle_failures_without_real_mcp(monkeypatch, tmp_path, failure_phase):
    class FakeMCPProcess:
        async def __aenter__(self):
            if failure_phase == "startup":
                raise OSError("stdio startup failed")
            return self

        async def call(self, name, arguments):
            assert name == "recordar"
            if failure_phase == "tool":
                raise TimeoutError("tool call timed out")
            if failure_phase == "mcp_response":
                return '{"status":"error"}', {"status": "error", "mensaje": "tool rejected"}
            return '{"status":"ok"}', {"status": "ok"}

        async def __aexit__(self, exc_type, exc, tb):
            if failure_phase == "teardown":
                raise OSError("stdio close failed")

    monkeypatch.setattr(harness, "MCPProcess", lambda db, root: FakeMCPProcess())
    raw, response, errors = asyncio.run(guarded_mcp_call(tmp_path / "unused.db", tmp_path, {}))
    outcome = classify_attempt(response, errors, [])
    assert outcome["invalida"] is True
    if failure_phase == "mcp_response":
        assert not errors
        assert response["status"] == "error"
        assert raw == '{"status":"error"}'
    elif failure_phase == "teardown":
        assert errors and raw == '{"status":"ok"}'
    else:
        assert errors and response["status"] == "transport_error"
