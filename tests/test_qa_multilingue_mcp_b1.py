"""Los rechazos de un carácter siguen visibles en las métricas de B1."""

from scripts.evaluar_qa_multilingue_mcp_b1 import marcar_pendiente_hueco_1


def test_marcar_hueco_sin_contar_como_busqueda_o_abstencion():
    brazo = {"casos": [
        {"id": "zh-18", "idioma": "zh", "termino_invalido": "伞",
         "error": "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO", "busqueda_ejecutada": False,
         "falso_positivo": None},
        {"id": "ko-05", "idioma": "ko", "termino_invalido": "연",
         "error": "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO", "busqueda_ejecutada": False,
         "falso_positivo": None},
        {"id": "ja-x", "idioma": "ja", "termino_invalido": "!",
         "error": "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO", "busqueda_ejecutada": False,
         "falso_positivo": None},
        {"id": "en-01", "idioma": "en", "termino_invalido": None,
         "error": None, "busqueda_ejecutada": True, "falso_positivo": None},
    ]}
    marcar_pendiente_hueco_1(brazo)
    assert brazo["pendiente_hueco_1"]["total"] == 2
    assert brazo["pendiente_hueco_1"]["por_idioma"]["zh"] == 1
    assert brazo["pendiente_hueco_1"]["por_idioma"]["ko"] == 1
    assert brazo["pendiente_hueco_1"]["ids"] == ["zh-18", "ko-05"]
    assert [c["marca_auditoria"] for c in brazo["casos"]] == [
        "pendiente hueco 1", "pendiente hueco 1", None, None]
    assert all(not c["busqueda_ejecutada"] and c["falso_positivo"] is None
               for c in brazo["casos"][:2])
