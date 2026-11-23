"""Tests del canal estable MCP: respuestas simuladas, sin llamadas a GitHub."""
from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

from core.mcp_server import update_checker
from core.mcp_server.update_checker import UpdateChecker


TAG_URL = f"{update_checker._TAGS_PAGE}v36.2.0"
DEFAULT_TAGS = ["v4.0", "v36.0", "v36.1", "v36.2.0", "v36.10.0"]
_UNSET = object()


def _policy(recommended="v36.2.0", blocked=()):
    return {
        "schema_version": 1,
        "channel": "stable",
        "recommended_tag": recommended,
        "blocked_tags": list(blocked),
    }


def _checker(
    *,
    current="v36.1",
    policy=_UNSET,
    tags=None,
    fetch_policy=None,
    fetch_tags=None,
):
    if fetch_policy is None:
        value = _policy() if policy is _UNSET else policy
        fetch_policy = lambda: value
    if fetch_tags is None:
        fetch_tags = lambda: list(DEFAULT_TAGS if tags is None else tags)
    return UpdateChecker(
        current_version=current,
        enabled=True,
        fetch_policy=fetch_policy,
        fetch_tags=fetch_tags,
    )


def test_manifiesto_ejemplo_no_recomienda_tag_sin_aprobacion():
    example_path = Path(__file__).resolve().parents[1] / "update_policy.example.json"
    policy = json.loads(example_path.read_text(encoding="utf-8"))

    assert policy["schema_version"] == 1
    assert policy["channel"] == "stable"
    assert policy["recommended_tag"] is None
    assert policy["blocked_tags"] == []


def test_versiones_estables_se_comparan_numericamente():
    assert update_checker._version_key("v36.10.0") > update_checker._version_key("v36.2.0")
    assert update_checker._version_key("v36.1") == (36, 1, 0)
    assert update_checker._version_key("v37.0.0-rc1") is None
    assert update_checker._version_key("release") is None


def test_solo_anuncia_la_version_aprobada_no_el_tag_mas_nuevo():
    checker = _checker(current="v36.1", policy=_policy("v36.2.0"))

    status = checker.check_once()
    notice = checker.take_notice()

    assert status["estado"] == "actualizacion_disponible"
    assert status["version_instalada"] == "36.1.0"
    assert status["version_remota"] == "v36.2.0"
    assert status["url_tag"] == TAG_URL
    assert notice and "v36.2.0" in notice
    assert "v36.10.0" not in notice
    assert "not automatic" in notice


def test_una_notificacion_por_tag_y_se_conserva_hasta_consumirla():
    checker = _checker(current="v36.1")

    checker.check_once()
    checker.check_once()

    notice = checker.take_notice()
    assert notice and "v36.2.0" in notice
    assert checker.take_notice() is None


def test_tag_mas_nuevo_sin_aprobacion_no_se_anuncia():
    checker = _checker(current="v36.0", policy=_policy("v36.1"))

    status = checker.check_once()
    notice = checker.take_notice()

    assert status["version_remota"] == "v36.1"
    assert status["actualizacion_disponible"] is True
    assert notice and "v36.1" in notice
    assert "v36.10.0" not in notice


def test_tag_bloqueado_no_se_anuncia_aunque_sea_recomendado():
    calls = []
    checker = _checker(
        current="v36.0",
        policy=_policy("v36.2.0", blocked=("v36.2",)),
        fetch_tags=lambda: calls.append("tags") or list(DEFAULT_TAGS),
    )

    status = checker.check_once()

    assert status["estado"] == "sin_actualizacion"
    assert status["version_remota"] is None
    assert status["url_tag"] is None
    assert checker.take_notice() is None
    assert calls == []


def test_politica_puede_no_recomendar_version_todavia():
    calls = []
    checker = _checker(
        current="v36.0",
        policy=_policy(recommended=None),
        fetch_tags=lambda: calls.append("tags") or list(DEFAULT_TAGS),
    )

    status = checker.check_once()

    assert status["estado"] == "sin_actualizacion"
    assert "no recomienda" in status["detalle"]
    assert checker.take_notice() is None
    assert calls == []


def test_manifiesto_ausente_404_se_informa_sin_romper_ni_consultar_tags():
    calls = []
    checker = _checker(
        current="v36.0",
        policy=None,
        fetch_tags=lambda: calls.append("tags") or list(DEFAULT_TAGS),
    )

    status = checker.check_once()

    assert status["estado"] == "sin_politica"
    assert "update_policy.json" in status["detalle"]
    assert status["actualizacion_disponible"] is False
    assert checker.take_notice() is None
    assert calls == []


def test_http_404_del_manifiesto_no_escapa_como_error():
    error = HTTPError(update_checker._POLICY_API, 404, "Not Found", {}, None)
    checker = _checker(fetch_policy=lambda: (_ for _ in ()).throw(error))

    assert checker.check_once()["estado"] == "sin_politica"


def test_politica_invalida_falla_cerrado():
    invalid_policies = (
        {"recommended_tag": "v36.2.0", "blocked_tags": []},
        {**_policy(), "channel": "preview"},
        _policy(blocked=("not-a-version",)),
        _policy(recommended="v36.2.0-rc1"),
    )
    for policy in invalid_policies:
        checker = _checker(
            current="v36.0",
            policy=policy,
        )
        status = checker.check_once()
        assert status["estado"] == "politica_invalida"
        assert status["version_remota"] is None
        assert checker.take_notice() is None


def test_tag_aprobado_que_no_existe_no_se_anuncia():
    checker = _checker(
        current="v36.0",
        policy=_policy("v36.99.0"),
        tags=DEFAULT_TAGS,
    )

    status = checker.check_once()

    assert status["estado"] == "tag_no_publicado"
    assert status["actualizacion_disponible"] is False
    assert status["version_remota"] is None
    assert checker.take_notice() is None


def test_version_local_mas_reciente_no_ve_actualizacion():
    checker = _checker(current="36.10.0", policy=_policy("v36.2.0"))

    status = checker.check_once()

    assert status["estado"] == "version_local_mas_reciente"
    assert status["actualizacion_disponible"] is False
    assert checker.take_notice() is None


def test_version_igual_no_ve_actualizacion():
    checker = _checker(current="36.2.0", policy=_policy("v36.2"))

    status = checker.check_once()

    assert status["estado"] == "actualizado"
    assert status["actualizacion_disponible"] is False
    assert checker.take_notice() is None


def test_fallo_de_red_no_interrumpe_y_un_reintento_puede_notificar():
    attempts = 0

    def fetch_tags():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise URLError("offline")
        return list(DEFAULT_TAGS)

    checker = _checker(current="v36.1", fetch_tags=fetch_tags)

    assert checker.check_once()["estado"] == "sin_respuesta"
    assert "validar los tags" in checker.status()["detalle"]
    assert checker.take_notice() is None
    assert checker.check_once()["actualizacion_disponible"] is True
    assert checker.take_notice() is not None


def test_chequeo_deshabilitado_no_consulta_red(monkeypatch):
    monkeypatch.setenv("BIORAG_UPDATE_CHECK", "0")
    fail = lambda: (_ for _ in ()).throw(AssertionError("No debe consultar GitHub"))
    checker = UpdateChecker(
        current_version="36.1.0",
        fetch_policy=fail,
        fetch_tags=fail,
    )

    assert checker.check_once()["estado"] == "deshabilitado"
    checker.start()
    assert checker.take_notice() is None


def test_fetch_stable_tags_filtra_etiquetas_y_maneja_paginacion(monkeypatch):
    calls = []
    pages = [
        [
            {"name": "v4.0"},
            {"name": "v36.2.0"},
            *({"name": f"v37.0.0-rc{index}"} for index in range(98)),
        ],
        [{"name": "v36.10.0"}, {"name": "not-a-version"}],
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, limit):
            assert limit == 256 * 1024
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        page = int(request.full_url.rsplit("=", 1)[1])
        return FakeResponse(pages[page - 1])

    monkeypatch.setattr(update_checker, "urlopen", fake_urlopen)

    assert update_checker.fetch_stable_tags() == ["v4.0", "v36.2.0", "v36.10.0"]
    assert [call[0].full_url for call in calls] == [
        update_checker._TAGS_API + "&page=1",
        update_checker._TAGS_API + "&page=2",
    ]
    assert all(call[1] == update_checker._DEFAULT_TIMEOUT_SECONDS for call in calls)


def test_fetch_update_policy_decodifica_contenido_del_repo_stable(monkeypatch):
    policy = _policy("v36.1", blocked=("v36.2.0",))
    api_response = {
        "encoding": "base64",
        "content": base64.b64encode(json.dumps(policy).encode()).decode(),
    }
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps(api_response).encode("utf-8")

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(update_checker, "urlopen", fake_urlopen)

    assert update_checker.fetch_update_policy() == policy
    assert calls[0][0].full_url == update_checker._POLICY_API
    assert calls[0][1] == update_checker._DEFAULT_TIMEOUT_SECONDS


def test_fetch_update_policy_404_es_un_manifiesto_ausente(monkeypatch):
    def not_found(_request, timeout):
        assert timeout == update_checker._DEFAULT_TIMEOUT_SECONDS
        raise HTTPError(update_checker._POLICY_API, 404, "Not Found", {}, None)

    monkeypatch.setattr(update_checker, "urlopen", not_found)

    assert update_checker.fetch_update_policy() is None


def test_notificacion_mcp_se_envia_una_vez_y_no_rompe_la_herramienta():
    checker = _checker(current="v36.1")
    checker.check_once()
    messages = []

    class FakeContext:
        async def warning(self, message):
            messages.append(message)

    sent = asyncio.run(update_checker.notify_pending_update(checker, FakeContext()))

    assert sent is True
    assert len(messages) == 1 and "v36.2.0" in messages[0]
    assert asyncio.run(update_checker.notify_pending_update(checker, FakeContext())) is False


def test_fallo_de_notificacion_no_rompe_la_operacion():
    checker = _checker(current="v36.1")
    checker.check_once()

    class BrokenContext:
        async def warning(self, _message):
            raise RuntimeError("cliente no soporta logging")

    assert asyncio.run(update_checker.notify_pending_update(checker, BrokenContext())) is False


def test_fastmcp_compatible_usa_version_biorag_y_notifica_antes_de_la_herramienta():
    checker = _checker(current="v36.1")
    checker.check_once()

    class FakeContext:
        def __init__(self, order):
            self.order = order

        async def warning(self, _message):
            self.order.append("aviso")

    class FakeFastMCP:
        def __init__(self, *_args, **_kwargs):
            self._mcp_server = type("LowLevel", (), {"version": None})()
            self.order = []
            self.context = FakeContext(self.order)

        def get_context(self):
            return self.context

        async def call_tool(self, _name, _arguments):
            self.order.append("herramienta")
            return {"status": "ok"}

    aware_class = update_checker.version_aware_server_class(FakeFastMCP, checker)
    server = aware_class("biorag")

    assert server._mcp_server.version == "36.1.0"
    assert asyncio.run(server.call_tool("recordar", {})) == {"status": "ok"}
    assert server.order == ["aviso", "herramienta"]


def test_banner_inyectado_en_text_content_para_visibilidad_del_agente():
    from mcp.types import TextContent

    checker = _checker(current="v36.1")
    checker.check_once()

    class FakeContext:
        async def warning(self, _message):
            pass

    class FakeFastMCP:
        def __init__(self, *_args, **_kwargs):
            self._mcp_server = type("LowLevel", (), {"version": None})()
            self.context = FakeContext()

        def get_context(self):
            return self.context

        async def call_tool(self, _name, _arguments):
            return [TextContent(type="text", text='{"recuerdos": ["usuario_dennys"]}')]

    aware_class = update_checker.version_aware_server_class(FakeFastMCP, checker)
    server = aware_class("biorag")

    result = asyncio.run(server.call_tool("recordar", {}))
    assert isinstance(result, list) and len(result) > 0
    assert "ℹ️ [BioRAG Update Notice]" in result[0].text
    assert "v36.2.0" in result[0].text
    assert '{"recuerdos": ["usuario_dennys"]}' in result[0].text


def test_recurso_version_expone_estado_404_sin_otra_peticion():
    class FakeMCP:
        resource_options = None
        resource_handler = None

        def resource(self, **options):
            self.resource_options = options

            def register(handler):
                self.resource_handler = handler
                return handler

            return register

    mcp = FakeMCP()
    checker = _checker(current="36.1.0", policy=None)
    assert checker.check_once()["estado"] == "sin_politica"
    update_checker.register(mcp, checker)

    result = json.loads(mcp.resource_handler())
    assert mcp.resource_options["uri"] == "biorag://version"
    assert result["estado"] == "sin_politica"
    assert "update_policy.json" in result["detalle"]
    assert result["version_remota"] is None
