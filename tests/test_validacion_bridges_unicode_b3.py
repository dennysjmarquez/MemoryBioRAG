"""E3 B3: unidades Unicode, controles existentes y puentes reales de QA."""

import unicodedata

import pytest

from core.concept_hub import ANGULOS_OFICIALES, validar_bridges


_COMPLEMENTOS = (
    "corte red general",
    "apagar encender motor",
    "periodo trabajo rural",
    "sin luces visibles",
)


def _bridges(primero):
    textos = (primero, *_COMPLEMENTOS)
    return [{"text": texto, "angle": angulo}
            for texto, angulo in zip(textos, ANGULOS_OFICIALES)]


@pytest.mark.parametrize("texto,esperado", [
    ("바다 등대", True),
    ("우산 가게", True),
    ("海岸的灯塔", True),
    ("灯塔", False),
    ("海辺の灯台", True),
    ("que con", False),
    ("go to", False),
    ("??? @@@", False),
    ("x q", False),
    ("水", False),
    ("문", False),
    ("memoria artificial", True),
    ("once lunas", True),  # No mezclar stopwords inglesas en el filtro español.
    ("the and", True),  # La lista inglesa no se agrega en B3.
    ("１２３４", True),  # La regla cuenta números anchos; no infiere significado.
    ("哈哈哈哈", True),
    ("1234 5678", True),
    ("jaja jaja", True),
])
def test_unidades_de_contenido(texto, esperado):
    validos, _ = validar_bridges(_bridges(texto), "farol_costero")
    assert any(b["text"] == texto for b in validos) is esperado
    assert len(validos) == (5 if esperado else 4)


# Puentes del snapshot QA, hub_arquitectura_memoria; nodo esperado del caso 0593.
_BRIDGES_QA = [
    {"text": "blueprint of recollection and cognitive persistence tiers", "angle": "sinonimo"},
    {"text": "duda sobre como se estructura la persistencia frente a la sesion activa", "angle": "problema"},
    {"text": "dos niveles de memoria con conversacion activa y base persistente", "angle": "solucion"},
    {"text": "diseno de corteza operativa para retener informacion entre conversaciones", "angle": "situacion"},
    {"text": "how the recollection and long term brain blueprint works in english", "angle": "ingenuo"},
]


def test_cinco_puentes_reales_de_qa():
    validos, rechazados = validar_bridges(_BRIDGES_QA, "arquitectura_memoria")
    assert len(validos) == 5
    assert not rechazados
    assert {b["text"] for b in validos} == {b["text"] for b in _BRIDGES_QA}


@pytest.mark.parametrize("texto,clave", [
    ("faro costero", "faro_costero"),
    ("海辺の灯台", "海辺の灯台"),
])
def test_se_conserva_antidestinatario(texto, clave):
    validos, rechazados = validar_bridges(_bridges(texto), clave)
    assert all(b["text"] != texto for b in validos)
    assert any("variación morfológica del nombre del nodo" in r for r in rechazados)


def test_se_rechaza_texto_duplicado():
    bridges = _bridges("corte red general")
    validos, rechazados = validar_bridges(bridges, "farol_costero")
    assert len(validos) == 4
    assert any("texto repetido" in r for r in rechazados)


def test_se_rechaza_angulo_duplicado():
    bridges = _bridges("tejido suave brilloso")
    bridges[1]["angle"] = "sinonimo"
    validos, rechazados = validar_bridges(bridges, "farol_costero")
    assert len(validos) == 4
    assert any("repite el ángulo" in r for r in rechazados)


def test_nfc_iguala_formas_canonicas_para_validar():
    compuesto = "ガラス"
    descompuesto = unicodedata.normalize("NFD", compuesto)
    assert compuesto != descompuesto
    for texto in (compuesto, descompuesto):
        validos, _ = validar_bridges(_bridges(texto), "farol_costero")
        assert all(b["text"] != texto for b in validos)


def test_nfc_no_modifica_el_texto_devuelto():
    texto = unicodedata.normalize("NFD", "ガラス製灯台")
    validos, _ = validar_bridges(_bridges(texto), "farol_costero")
    assert any(b["text"] == texto for b in validos)
