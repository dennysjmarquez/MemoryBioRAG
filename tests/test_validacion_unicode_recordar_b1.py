"""B1: solo cambia el formato de sustantivos en recordar, no el guardado."""
import json
import unicodedata

import pytest

from core.mcp_server import search, write
from core.mcp_server._shared import _sustantivo_valido
from core.memory_store import normalizar_sustantivos_clave


@pytest.mark.parametrize("termino", [
    "海岸", "灯台", "바닷가", "हिंदी", "ガラス", "чай", "hola",
    "ñandú", "aa", "a1", "dos_palabras", "_a", "__",
    "a" * 15, "가" * 15, "１２", "a\u093e", "a\u0301b",
])
def test_terminos_unicode_validos(termino):
    assert _sustantivo_valido(termino)


@pytest.mark.parametrize("termino", [
    "水", "本", "문", "문", "１", "a", "я", "", "foo-bar",
    "a b", "a@b", "a/b", "😀😀", "a" * 16, "가" * 16, "水" * 16, "a\u200bb",
])
def test_terminos_invalidos(termino):
    assert not _sustantivo_valido(termino)


def test_un_caracter_no_pasa_aunque_sea_ancho():
    assert not _sustantivo_valido("水")
    assert not _sustantivo_valido("문")
    assert not _sustantivo_valido("１")
    assert not _sustantivo_valido("－")
    assert not _sustantivo_valido("a")
    assert not _sustantivo_valido("я")


def test_nfc_solo_cuenta_no_modifica_normalizador_compartido():
    # La regla compone jamos para contar una sílaba, pero el valor guardado por
    # el normalizador existente no se corrige en B1 (identidad es B3).
    assert unicodedata.normalize("NFC", normalizar_sustantivos_clave("문")) == "문"
    assert not _sustantivo_valido(normalizar_sustantivos_clave("문"))
    assert normalizar_sustantivos_clave("ガラス") == "カラス"
    assert normalizar_sustantivos_clave("ガラス,カラス") == "カラス"
    # En este ejemplo concreto las marcas sobreviven; otras, como nukta, no.
    assert normalizar_sustantivos_clave("हिंदी") == "हिंदी"
    assert normalizar_sustantivos_clave("क़िला") == "किला"


class _ValidacionSuperada(Exception):
    pass


def _impedir_base():
    raise _ValidacionSuperada("la búsqueda llegó al acceso al motor")


@pytest.mark.parametrize("sk", [
    "海岸", "灯台", "바닷가", "हिंदी", "ガラス", "чай", "hola",
    "海岸,灯塔", "a1", ",".join(f"t{i}" for i in range(10)),
])
def test_recordar_supera_validacion_y_llega_al_motor(monkeypatch, sk):
    monkeypatch.setattr(search, "_get_cerebro", _impedir_base)
    with pytest.raises(_ValidacionSuperada):
        search._recordar_impl(query="prueba", sustantivos_clave=sk)


@pytest.mark.parametrize("sk", ["水", "本", "문", "a", "я", "foo-bar", "a@b", "a" * 16, "가" * 16])
def test_recordar_rechaza_formatos_antes_de_abrir_base(monkeypatch, sk):
    monkeypatch.setattr(search, "_get_cerebro", _impedir_base)
    obj = json.loads(search._recordar_impl(query="prueba", sustantivos_clave=sk))
    assert obj["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"


def test_recordar_conserva_deduplicacion_y_maximo_de_diez(monkeypatch):
    monkeypatch.setattr(search, "_get_cerebro", _impedir_base)
    with pytest.raises(_ValidacionSuperada):
        search._recordar_impl(query="prueba", sustantivos_clave="海岸,海岸")
    obj = json.loads(search._recordar_impl(
        query="prueba", sustantivos_clave=",".join(f"t{i}" for i in range(11))))
    assert obj["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"
    assert obj["cantidad_recibida"] == 11


def test_aprender_aun_rechaza_sustantivos_no_latinos(monkeypatch):
    # B2 queda pendiente: el guardado conserva su validador original.
    monkeypatch.setattr(write, "_get_cerebro", _impedir_base)
    bridges = [
        {"text": "corte intempestivo de comunicacion backend", "angle": "sinonimo"},
        {"text": "pagina en blanco sin respuesta del servidor", "angle": "problema"},
        {"text": "reintentos exponenciales y keepalive configurado", "angle": "solucion"},
        {"text": "usuario reportando caida intermitente de la web", "angle": "situacion"},
        {"text": "la web se cae sola y no carga", "angle": "ingenuo"},
    ]
    obj = json.loads(write._aprender_impl(
        concepto="nodo_prueba", contenido="Contenido de prueba suficiente.",
        bridges=bridges, cat="General", busqueda_previa=True,
        sustantivos_clave="水,海"))
    assert obj["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"
