"""Pruebas del re-ranking genérico por convergencia de los cuatro campos FTS."""

from core.memory.evidence_convergence import (
    calcular_bono_convergencia,
    cobertura_campo,
    evidencia_multicampo,
    incorporar_delta_postprocesamiento,
    rerank_con_evidencia_multicampo,
)


def test_flags_publicos_006_007_controlan_esta_implementacion():
    """Los comandos A/B de las specs controlan de verdad el flag y el tope."""
    import os
    from pathlib import Path
    import subprocess
    import sys

    codigo = (
        "from core.memory.constants import CONVERGENCIA_EVIDENCIA_ACTIVA, "
        "CONVERGENCIA_EVIDENCIA_MAX_BONUS, CONVERGENCIA_ACTIVA; "
        "print(CONVERGENCIA_EVIDENCIA_ACTIVA, "
        "CONVERGENCIA_EVIDENCIA_MAX_BONUS, CONVERGENCIA_ACTIVA)"
    )
    for public_flag, legacy_flag, expected_active in (("0", "1", "False"), ("1", "0", "True")):
        env = os.environ.copy()
        env["BIORAG_CONVERGENCIA_ACTIVA"] = public_flag
        env["BIORAG_CONVERGENCIA_EVIDENCIA"] = legacy_flag
        env["BIORAG_CONVERGENCIA_006_ACTIVA"] = "0"
        env["BIORAG_CONVERGENCIA_BONUS_MAX"] = "0.045"
        env["BIORAG_CONVERGENCIA_EVIDENCIA_MAX_BONUS"] = "0.08"
        salida = subprocess.check_output(
            [sys.executable, "-c", codigo],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            text=True,
        )
        assert salida.strip() == f"{expected_active} 0.045 False"


def test_margen_reportado_se_resuelve_con_evidencia_distribuida_sin_id_rules():
    """Un nodo con evidencia estructurada supera al que solo lo menciona en body.

    Los scores-base reproducen la diferencia reportada (0.8233 vs 0.7842),
    pero los nombres son sintéticos: la regla no inspecciona IDs/categorías.
    """
    q = {"biorag", "version", "actual", "ultima"}
    query_variants = [q]
    objetivo = evidencia_multicampo(
        query_variants,
        concepto="version_actual_biorag",
        sinonimos="biorag version actual ultima release",
        sustantivos_clave="version repositorio protocolo conectoma",
        contenido="BioRAG version actual v32.3",
    )
    incidental = evidencia_multicampo(
        query_variants,
        concepto="reindex_selectivo_dirty",
        sinonimos="reindexado_sdm, dirty_set",
        sustantivos_clave="",
        contenido="Una nota menciona version_actual_biorag como referencia",
    )

    assert objetivo["concepto"] == 0.75
    assert objetivo["sinonimos"] == 1.0
    assert objetivo["sustantivos_clave"] == 0.25
    assert objetivo["contenido"] == 0.75
    assert incidental["concepto"] == 0.0
    assert incidental["sinonimos"] == 0.0
    assert incidental["sustantivos_clave"] == 0.0
    assert incidental["contenido"] == 0.75

    ranked, base, bonuses = rerank_con_evidencia_multicampo(
        [
            ("incidental", "body", 0.5, "activo", 0.8233, ""),
            ("objetivo", "structured", 0.5, "activo", 0.7842, ""),
        ],
        {"objetivo": objetivo, "incidental": incidental},
        max_bonus=0.06,
        query_size=len(q),
    )

    assert ranked[0][0] == "objetivo"
    assert ranked[0][4] > ranked[1][4]
    assert base == {"incidental": 0.8233, "objetivo": 0.7842}
    assert bonuses["objetivo"] > bonuses["incidental"]
    assert bonuses["objetivo"] - bonuses["incidental"] > 0.0391


def test_margen_observado_en_db_local_se_resuelve_con_cap_calibrado():
    """El margen real del smoke (0.8233 vs 0.7562) exige más que el cap 0.06.

    La evidencia se midió en la DB local del usuario: objetivo (1, 1, 0.5, 1),
    mención incidental solo en contenido (0, 0, 0, 1). Se valida la fórmula sin
    introducir reglas para los IDs concretos.
    """
    objetivo = {"concepto": 1.0, "sinonimos": 1.0, "sustantivos_clave": 0.5, "contenido": 1.0}
    incidental = {"concepto": 0.0, "sinonimos": 0.0, "sustantivos_clave": 0.0, "contenido": 1.0}
    ranked, _, bonuses = rerank_con_evidencia_multicampo(
        [
            ("incidental", "body", 0.5, "activo", 0.8233, ""),
            ("objetivo", "structured", 0.5, "activo", 0.7562, ""),
        ],
        {"objetivo": objetivo, "incidental": incidental},
        query_size=4,
    )

    assert ranked[0][0] == "objetivo"
    assert round(ranked[0][4], 4) == 0.8341
    assert round(ranked[1][4], 4) == 0.8304
    assert bonuses["objetivo"] - bonuses["incidental"] > 0.0671


def test_un_campo_curado_aporta_mas_que_el_body_incidental():
    # Los pesos son los ya usados por BM25: concepto=5, synonyms=2,
    # sustantivos=4, contenido=1. Ningún canal aislado se descarta.
    content_only = calcular_bono_convergencia({"contenido": 1.0})
    synonyms_only = calcular_bono_convergencia({"sinonimos": 1.0})
    nouns_only = calcular_bono_convergencia({"sustantivos_clave": 1.0})
    concept_only = calcular_bono_convergencia({"concepto": 1.0})

    assert 0.0 < content_only < synonyms_only < nouns_only < concept_only
    assert calcular_bono_convergencia({}) == 0.0
    assert calcular_bono_convergencia({"contenido": 0.0}) == 0.0


def test_coincidencia_morfologica_y_difusa_no_se_convierte_en_cero():
    assert cobertura_campo({"version"}, "versiones") == 1.0
    assert cobertura_campo({"actualizar"}, "actualizando") == 1.0
    assert cobertura_campo({"biorag"}, "bioag") >= 0.75


def test_escala_por_ambiguedad_de_consulta_corta():
    evidence = {"concepto": 1, "sinonimos": 1, "sustantivos_clave": 1, "contenido": 1}
    bonus_one = calcular_bono_convergencia(evidence, query_size=1)
    bonus_two = calcular_bono_convergencia(evidence, query_size=2)
    bonus_three = calcular_bono_convergencia(evidence, query_size=3)
    assert 0 < bonus_one < bonus_two < bonus_three
    assert bonus_one == 0.0085
    assert bonus_two == 0.0425
    assert bonus_three == 0.085


def test_repetir_un_token_en_contenido_no_multiplica_la_evidencia():
    query = {"biorag", "version", "actual", "ultima"}
    una_mencion = cobertura_campo(query, "BioRAG version actual")
    repetido = cobertura_campo(query, " ".join(["BioRAG version actual"] * 100))
    assert una_mencion == repetido == 0.75


def test_parafrasis_se_evalua_como_alternativa_sin_diluir_consulta():
    scores = evidencia_multicampo(
        [{"version", "biorag", "actual", "ultima"}, {"version", "biorag"}],
        concepto="version_actual_biorag",
        sinonimos="version actual biorag ultima",
        sustantivos_clave="version",
        contenido="BioRAG version actual",
    )
    assert scores["concepto"] == 1.0
    assert scores["sinonimos"] == 1.0
    assert scores["sustantivos_clave"] == 0.5
    assert scores["contenido"] == 1.0


def test_el_reranker_es_aditivo_monotonico_y_respeta_el_formato_de_resultado():
    resultados = [
        ("solo_body", "x", 0.1, "activo", 0.50, "asoc"),
        ("sin_evidencia", "y", 0.1, "activo", 0.49, ""),
    ]
    ranked, base, bonuses = rerank_con_evidencia_multicampo(
        resultados,
        {"solo_body": {"contenido": 1.0}, "sin_evidencia": {}},
    )

    assert all(len(row) == 6 for row in ranked)
    assert ranked[0][0] == "solo_body"
    assert ranked[0][4] > 0.50
    assert ranked[1][4] == 0.49
    assert base["solo_body"] == 0.50
    assert bonuses["solo_body"] > 0.0
    assert bonuses["sin_evidencia"] == 0.0
    assert all(ranked[i][4] >= ranked[i + 1][4] for i in range(len(ranked) - 1))


def test_bonus_tiene_tope_y_no_supera_score_uno():
    ranked, _, bonuses = rerank_con_evidencia_multicampo(
        [("hub", "x", 1.0, "activo", 0.99, "")],
        {"hub": {"concepto": 1, "sinonimos": 1, "sustantivos_clave": 1, "contenido": 1}},
        max_bonus=0.06,
    )
    assert ranked[0][4] == 1.0
    assert bonuses["hub"] == 0.01
    assert calcular_bono_convergencia({"concepto": 1}, max_bonus=100) <= 0.12


def test_convergencia_no_cambia_membresia_topk_ni_semillas(tmp_path, monkeypatch):
    """El re-ranker MCP conserva top-k visible y el pool de semillas.

    MCP sobreconsulta 3x para recall. El bono debe limitarse al top-k público;
    ni un candidato del overfetch puede entrar en la respuesta ni cambiar las
    semillas candidatas del grafo.
    """
    import shutil
    from pathlib import Path

    from core.memory_store import SQLiteMemoryBioRAG
    import core.memory.constants as constants

    monkeypatch.setenv("BIORAG_NO_LOG", "1")
    source_db = Path(__file__).resolve().parents[1] / "snapshots" / "qa_escape_qcr_20260811.db"
    nombres_por_modo = []
    scores_por_modo = []
    bonuses_por_modo = []
    for active in (False, True):
        db_path = tmp_path / f"convergence_{int(active)}.db"
        shutil.copyfile(source_db, db_path)
        cerebro = SQLiteMemoryBioRAG(db_path=str(db_path))
        monkeypatch.setattr(constants, "CONVERGENCIA_EVIDENCIA_ACTIVA", active)
        if active and len(nombres_por_modo[0]) > 5:
            # El sexto candidato del overfetch recibe deliberadamente evidencia
            # máxima: no debe reemplazar a nadie del top-5 visible.
            import core.memory.evidence_convergence as convergence
            concepto_fuera_top_k = nombres_por_modo[0][5]

            def evidencia_sintetica(_queries, concepto, *_campos, **_kwargs):
                fuerza = 1.0 if concepto == concepto_fuera_top_k else 0.0
                return {
                    "concepto": fuerza,
                    "sinonimos": fuerza,
                    "sustantivos_clave": fuerza,
                    "contenido": fuerza,
                }

            monkeypatch.setattr(convergence, "evidencia_multicampo", evidencia_sintetica)
        rows, _ = cerebro.buscar_por_frase(
            "denys-identidad-profunda",
            profundidad="activos",
            limite=15,
            convergencia_limite=5,
            preview_chars=0,
            ignore_peso_sinaptico=True,
        )
        nombres_por_modo.append([row[0] for row in rows])
        scores_por_modo.append([row[4] for row in rows])
        bonuses_por_modo.append(set(cerebro.last_score_bonus_map))
        cerebro.conn.close()

    assert set(nombres_por_modo[0][:5]) == set(nombres_por_modo[1][:5])
    assert set(nombres_por_modo[0]) == set(nombres_por_modo[1])
    if len(nombres_por_modo[0]) > 5:
        assert nombres_por_modo[0][5] not in bonuses_por_modo[1]
    assert all(scores_por_modo[1][i] >= scores_por_modo[1][i + 1] for i in range(4))


def test_delta_del_grafo_separa_score_base_y_bono_multicampo():
    base = {"seed": 0.50}
    bonuses = {"seed": 0.03}
    salida_grafo = [("seed", "x", 0.1, "activo", 0.55, "")]
    incorporar_delta_postprocesamiento(salida_grafo, base, bonuses)
    assert base["seed"] == 0.52
    assert bonuses["seed"] == 0.03

    # Un descenso sináptico que deja el total debajo del bono no debe crear un
    # score-base negativo ni exponer un bonus mayor que el score final.
    base["seed"] = 0.02
    bonuses["seed"] = 0.03
    incorporar_delta_postprocesamiento(
        [("seed", "x", 0.1, "activo", 0.02, "")], base, bonuses
    )
    assert base["seed"] == 0.0
    assert bonuses["seed"] == 0.02


def test_busqueda_directa_preserva_bonus_y_suma_delta_sinaptico(tmp_path, monkeypatch):
    import shutil
    from pathlib import Path

    from core.memory_store import SQLiteMemoryBioRAG
    import core.memory.constants as constants

    monkeypatch.setenv("BIORAG_NO_LOG", "1")
    monkeypatch.setattr(constants, "CONVERGENCIA_EVIDENCIA_ACTIVA", True)
    source_db = Path(__file__).resolve().parents[1] / "snapshots" / "qa_escape_qcr_20260811.db"
    db_path = tmp_path / "direct_convergence.db"
    shutil.copyfile(source_db, db_path)
    cerebro = SQLiteMemoryBioRAG(db_path=str(db_path))
    monkeypatch.setattr(
        cerebro,
        "expandir_contexto_vecinos",
        lambda resultados, **_kwargs: (
            [tuple(fila[:4]) + (round(fila[4] + 0.02, 4),) + tuple(fila[5:]) for fila in resultados],
            [],
        ),
    )

    rows, _ = cerebro.buscar_por_frase(
        "biorag version actual ultima",
        profundidad="activos",
        limite=5,
        preview_chars=0,
        context_window=1,
    )
    row_by_concept = {row[0]: row for row in rows}

    assert cerebro.last_score_bonus_map
    assert any(bonus > 0.0 for bonus in cerebro.last_score_bonus_map.values())
    for concept, base in cerebro.last_score_base_map.items():
        assert round(base + cerebro.last_score_bonus_map[concept], 4) == row_by_concept[concept][4]
    cerebro.conn.close()


def test_mcp_publica_score_base_y_bono_tras_delta_del_grafo(tmp_path, monkeypatch):
    """La API mantiene trazables score-base, bono y delta de contexto sináptico."""
    import json
    import shutil
    from pathlib import Path

    from core.memory_store import SQLiteMemoryBioRAG
    from core.mcp_server import search as mcp_search
    import core.memory.constants as constants

    source_db = Path(__file__).resolve().parents[1] / "snapshots" / "qa_escape_qcr_20260811.db"
    db_path = tmp_path / "mcp_convergence.db"
    shutil.copyfile(source_db, db_path)
    cerebro = SQLiteMemoryBioRAG(db_path=str(db_path))
    confianza_recibida = []
    monkeypatch.setattr(constants, "CONVERGENCIA_EVIDENCIA_ACTIVA", True)
    monkeypatch.setattr(
        cerebro,
        "confianza_calibrada",
        lambda score: confianza_recibida.append(float(score)) or float(score),
    )
    monkeypatch.setattr(
        cerebro,
        "expandir_contexto_vecinos",
        lambda resultados, **_kwargs: (
            [tuple(fila[:4]) + (round(fila[4] + 0.02, 4),) + tuple(fila[5:]) for fila in resultados],
            [],
        ),
    )
    monkeypatch.setattr(mcp_search, "_get_cerebro", lambda: cerebro)

    raw = mcp_search._recordar_impl(
        query="biorag version actual ultima",
        parafrasis="version biorag,version actual biorag,ultima version biorag,biorag v version",
        limite=5,
        asociados=False,
        completo=True,
        context_window=1,
    )
    payload_start = raw.find('{"total"')
    assert payload_start >= 0, raw
    payload = json.loads(raw[payload_start:])
    first = payload["resultados"][0]

    assert first["concepto"] == "version_actual_biorag"
    assert first["score_hibrido"] > first["score_hibrido_base"]
    assert first["bonus_convergencia_multicampo"] > 0.0
    assert round(
        first["score_hibrido_base"] + first["bonus_convergencia_multicampo"], 4
    ) == first["score_hibrido"]
    assert first["confianza_calibrada"] == first["score_hibrido_base"]
    assert confianza_recibida[0] == first["score_hibrido_base"]
