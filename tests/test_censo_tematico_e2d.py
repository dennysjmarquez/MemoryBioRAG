"""El censo E2d no inventa medias ni modifica la fórmula observada."""

import pytest

from scripts.censo_tematico_e2d import (
    CensoCrudo,
    comparar_resultados,
    crear_observador,
    leer_media,
    percentil_ordenado,
)


def _locales(**cambios):
    datos = {
        "_perfiles_tematicos": {"x": {1}},
        "_todas_dims": {1},
        "bm25_val": 0.5,
        "concepto_ratio": 0.0,
        "sinonimos_ratio": 0.1,
        "sims": [0.2, 0.4],
    }
    datos.update(cambios)
    return datos


def test_no_se_lee_lista_del_candidato_anterior_con_compuerta_cerrada():
    # Una lista vieja incluso inválida debe ser ignorada si no se ejecutó el guardia.
    datos = _locales(sinonimos_ratio=0.7, sims=["lista anterior"])
    assert leer_media(datos, 0.0) == ("compuerta_cerrada", None, 0)
    censo = CensoCrudo()
    censo.observar(datos, 0.0)
    resumen = censo.resumen()
    assert resumen["compuerta_no_ejecutada"] == 1
    assert resumen["compuerta_ejecutada_con_media"] == 0
    assert resumen["errores_observacion"] == 0


def test_lista_vacia_no_inventa_un_cero_en_la_distribucion():
    censo = CensoCrudo()
    censo.observar(_locales(sims=[]), 0.0)
    resultado = censo.resumen()
    assert resultado["compuerta_ejecutada_lista_vacia"] == 1
    assert resultado["media_sims"]["n"] == 0
    assert resultado["media_sims"]["media"] is None


def test_media_previa_a_tres_y_saturacion_exacta():
    assert leer_media(_locales(sims=[0.1, 0.3]), 0.2 * 3) == ("media_valida", 0.2, 2)
    umbral = 1 / 3
    assert leer_media(_locales(sims=[umbral]), 1.0) == ("media_valida", umbral, 1)
    with pytest.raises(ValueError, match="media × 3"):
        leer_media(_locales(sims=[0.1, 0.3]), 1.0)
    with pytest.raises(ValueError, match="no pasa"):
        leer_media(_locales(sims=[0.02]), 0.06)


def test_recuentos_histograma_percentiles_y_detectar_error():
    censo = CensoCrudo()
    for valor in (0.1, 0.2, 0.3, 1 / 3, 0.9, 1.1):
        censo.observar(_locales(sims=[valor]), min(1.0, valor * 3.0))
    resumen = censo.resumen()
    media = resumen["media_sims"]
    assert media["n"] == 6
    assert media["saturadas_media_mayor_o_igual_1_tercio"] == 3
    assert media["porcentaje_saturadas_sobre_medias"] == 50
    assert sum(x["llamadas"] for x in media["histograma"]) == 6
    assert media["percentiles_rango_mas_proximo"]["p50"] == 0.3
    assert percentil_ordenado([], 50) is None
    censo.observar(_locales(sims=[0.2]), 1.0)
    assert censo.resumen()["errores_observacion"] == 1


def test_envoltorio_conserva_argumentos_y_valor_original():
    censo = CensoCrudo()
    recibido = []
    marcador = object()
    valor_original = object()

    def original(self, **kw):
        recibido.append((self, kw))
        return valor_original

    def buscar():
        _perfiles_tematicos = {"x": {1}}
        _todas_dims = {1}
        bm25_val, concepto_ratio, sinonimos_ratio = 0.2, 0.0, 0.1
        sims = [0.1, 0.3]
        return envoltura(marcador, tematico_score=0.2 * 3, otra_senal=0.123)

    envoltura = crear_observador(original, buscar.__code__, censo)
    assert buscar() is valor_original
    assert recibido == [(marcador, {"tematico_score": 0.2 * 3, "otra_senal": 0.123})]
    assert censo.resumen()["media_sims"]["n"] == 1
    assert censo.resumen()["errores_observacion"] == 0


def test_huella_fuera_de_la_qa_no_cuenta_como_candidato():
    censo = CensoCrudo()
    censo.observar(None, 0.7, huella=True)
    resumen = censo.resumen()
    assert resumen["llamadas_observadas_total_incluida_huella"] == 1
    assert resumen["llamadas_fuera_de_busqueda"] == 1
    assert resumen["llamadas_formula"] == 0
    assert resumen["errores_observacion"] == 0
    censo.observar(None, 0.7)  # origen inesperado: no se ignora silenciosamente
    censo.observar(None, 0.7, huella=True, en_censo_nativo=True)
    assert censo.resumen()["errores_observacion"] == 2
    assert censo.resumen()["llamadas_fuera_en_censo_nativo"] == 1


def test_envoltorio_reconoce_el_codigo_de_huella_permitido():
    censo = CensoCrudo()
    sentinel = object()

    def original(self, **kw):
        return sentinel

    def una_huella():
        return envoltura(None, tematico_score=0.7)

    def buscar_no_llamado():
        pass

    envoltura = crear_observador(original, buscar_no_llamado.__code__, censo, (una_huella.__code__,))
    assert una_huella() is sentinel
    assert censo.resumen()["llamadas_fuera_de_busqueda"] == 1
    assert censo.resumen()["errores_observacion"] == 0


def test_compara_qa_y_censo_nativo_y_detecta_diferencias():
    censo = CensoCrudo()
    censo.observar(_locales(sims=[0.4]), 1.0)
    resumen = censo.resumen()
    baseline = {"casos_total": 1, "global": {}, "categorias": {}, "qa_honesta": {}}
    actual = {
        **baseline,
        "e2b": {"censo_tematico": {"candidatos": 1, "con_tematico": 1, "saturados": 1}},
    }
    qa, conteos = comparar_resultados(actual, baseline, resumen)
    assert all(qa.values()) and all(conteos.values())
    actual["global"] = {"fallos": 1}
    actual["e2b"]["censo_tematico"]["saturados"] = 0
    qa, conteos = comparar_resultados(actual, baseline, resumen)
    assert not qa["global"]
    assert not conteos["saturadas"]
