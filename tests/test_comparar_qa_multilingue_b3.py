import copy

from scripts.comparar_qa_multilingue_b3 import comparar_guardados


def _datos(cantidades):
    filas = []
    for idioma in ("zh", "ja", "ko", "ru"):
        for i in range(20):
            guardado = i < cantidades[idioma]
            filas.append({
                "id": f"{idioma}-{i + 1:02}", "idioma": idioma, "concepto": f"nombre-{idioma}-{i}",
                "sustantivos_guardado_entrada": "nombre", "sustantivo_busqueda_previa": "nombre",
                "busqueda_previa_ejecutada": True, "busqueda_previa_confirmada": True,
                "excepcion": None, "error_consolidacion": None, "guardado_en_db": guardado,
                "confirmado_por_mcp": guardado, "consolidado": guardado, "puentes_guardados": 5 if guardado else 0,
                "primer_rechazo": None if guardado else "FORMATO", "respuesta_aprender": {} if guardado else {"codigo": "FORMATO"},
                "sustantivos_en_db": "nombre" if guardado else None, "sustantivos_normalizados": "nombre",
            })
    return {"metadatos": {"gold_guardado_sha256": "fijo", "write_sha256": "fijo", "pythonhashseed": "0",
                          "biorag_neurona": "0", "reloj_fijo_unix": 1}, "integridad": "ok", "casos": filas}


def test_sin_regresion_no_implica_que_coreano_haya_subido():
    antes = _datos({"zh": 0, "ja": 0, "ko": 16, "ru": 20})
    despues = _datos({"zh": 18, "ja": 15, "ko": 16, "ru": 20})
    informe, problemas, expectativas = comparar_guardados(antes, despues)
    assert not problemas
    assert expectativas == ["ko: no aumentaron los guardados (16→16)"]
    assert informe["ko"]["ids_perdidos"] == []


def test_caso_perdido_se_detecta_aunque_el_total_del_idioma_no_baje():
    antes = _datos({"zh": 0, "ja": 0, "ko": 16, "ru": 20})
    despues = _datos({"zh": 18, "ja": 15, "ko": 17, "ru": 20})
    filas = despues["casos"]
    anterior = next(f for f in filas if f["id"] == "ko-01")
    rechazo = copy.deepcopy(next(f for f in filas if f["id"] == "ko-18"))
    for clave in ("guardado_en_db", "confirmado_por_mcp", "consolidado", "puentes_guardados",
                  "primer_rechazo", "respuesta_aprender", "sustantivos_en_db"):
        anterior[clave] = rechazo[clave]
    informe, problemas, _ = comparar_guardados(antes, despues)
    assert informe["ko"]["guardados_b2"] == informe["ko"]["guardados_b3"] == 16
    assert informe["ko"]["ids_perdidos"] == ["ko-01"]
    assert any("ko-01: se guardó en B2" in p for p in problemas)
