#!/usr/bin/env python3
"""Smoke de instalación del wheel y del flujo MCP, siempre sobre una DB temporal.

Se ejecuta después de `pip install .` desde fuera del checkout para detectar
paquetes omitidos del wheel y verificar persistencia tras reiniciar el servidor.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import asynccontextmanager
from importlib.metadata import version as installed_distribution_version
from pathlib import Path
from sysconfig import get_path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SOURCE_ROOT = Path(__file__).resolve().parents[1]
ANCHOR = "biorag_smoke_install_anchor"
LINKED = "biorag_smoke_install_link"
BRIDGES = [
    {"text": "corte intempestivo de comunicacion backend", "angle": "sinonimo"},
    {"text": "pagina en blanco sin respuesta del servidor", "angle": "problema"},
    {"text": "reintentos exponenciales y keepalive configurado", "angle": "solucion"},
    {"text": "usuario reportando caida intermitente de la web", "angle": "situacion"},
    {"text": "la web se cae sola y no carga", "angle": "ingenuo"},
]


def _console_script(name: str) -> str | None:
    """Localiza entry points aunque el entorno virtual no esté activado en PATH."""
    found = shutil.which(name)
    if found:
        return found
    scripts_dir = Path(get_path("scripts"))
    suffixes = (".exe", "-script.py", "") if os.name == "nt" else ("",)
    for suffix in suffixes:
        candidate = scripts_dir / f"{name}{suffix}"
        if candidate.is_file():
            return str(candidate)
    return None


def _assert_installed_wheel() -> str:
    """Asegura que los imports y los entry points vienen del wheel, no del checkout."""
    modules = [
        importlib.import_module(name)
        for name in ("biorag", "mcp_server", "core", "config", "middleware")
    ]
    for module in modules:
        origin = Path(module.__file__).resolve()
        if origin == SOURCE_ROOT or SOURCE_ROOT in origin.parents:
            raise RuntimeError(f"{module.__name__} se importó desde el checkout: {origin}")

    executable = _console_script("biorag-mcp")
    if not executable:
        raise RuntimeError("No se encontró el entry point instalado 'biorag-mcp'.")
    if not _console_script("biorag"):
        raise RuntimeError("No se encontró el entry point instalado 'biorag'.")
    return executable


def _json_text(text: str, operation: str) -> dict[str, Any]:
    start = text.find("{")
    if start < 0:
        raise RuntimeError(f"Respuesta MCP {operation!r} sin JSON: {text[:500]!r}")
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON MCP inválido en {operation!r}: {text[:500]!r}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Respuesta MCP {operation!r} no es un objeto JSON.")
    return value


def _json_result(result: Any, operation: str) -> dict[str, Any]:
    if getattr(result, "isError", False):
        raise RuntimeError(f"La herramienta MCP {operation!r} devolvió isError.")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        # FastMCP envuelve los resultados string como {"result": "..."}.
        nested = structured.get("result")
        if isinstance(nested, str):
            return _json_text(nested, operation)
        return structured

    text = "\n".join(
        part.text for part in getattr(result, "content", [])
        if isinstance(getattr(part, "text", None), str)
    )
    return _json_text(text, operation)


@asynccontextmanager
async def _session(executable: str, db_path: Path):
    env = os.environ.copy()
    env["BIORAG_PATH"] = str(db_path)
    env["BIORAG_DAEMON_ENABLED"] = "0"
    params = StdioServerParameters(command=executable, args=[], env=env)
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await session.initialize()
            expected_version = installed_distribution_version("memory-biorag")
            if initialized.serverInfo.version != expected_version:
                raise RuntimeError(
                    "MCP serverInfo.version no coincide con el paquete instalado: "
                    f"{initialized.serverInfo.version!r} != {expected_version!r}"
                )
            yield session


def _aprender_args(concepto: str, contenido: str, sustantivos: str) -> dict[str, Any]:
    return {
        "concepto": concepto,
        "contenido": contenido,
        "dimensiones": '{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
        "syn": "instalacion,persistencia,memoria,prueba,recuerdo,configuracion,agente,proceso",
        "cat": "Lesson",
        "bridges": BRIDGES,
        "sustantivos_clave": sustantivos,
        "busqueda_previa": True,
    }


async def _smoke(executable: str, db_path: Path) -> None:
    async with _session(executable, db_path) as session:
        names = {tool.name for tool in (await session.list_tools()).tools}
        required = {"aprender", "consolidar", "recordar"}
        if not required.issubset(names):
            raise RuntimeError(f"Faltan herramientas MCP {sorted(required - names)}.")

        version_resource = "biorag://version"
        resources = await session.list_resources()
        if version_resource not in {str(item.uri) for item in resources.resources}:
            raise RuntimeError("No se publicó el recurso MCP biorag://version.")
        version_result = await session.read_resource(version_resource)
        version_text = next(
            (item.text for item in version_result.contents if isinstance(getattr(item, "text", None), str)),
            None,
        )
        if version_text is None:
            raise RuntimeError("El recurso biorag://version no devolvió JSON de texto.")
        version_status = json.loads(version_text)
        if (
            version_status.get("estado") != "deshabilitado"
            or version_status.get("version_instalada") != installed_distribution_version("memory-biorag")
        ):
            raise RuntimeError(f"Estado de versión inesperado en el smoke aislado: {version_status}")

        # La comprobación previa forma parte del contrato actual de escritura.
        preflight = _json_result(
            await session.call_tool(
                "recordar",
                arguments={"query": ANCHOR, "sustantivos_clave": "biorag,instalacion"},
            ),
            "recordar(preflight)",
        )
        if not isinstance(preflight.get("resultados"), list):
            raise RuntimeError(f"La búsqueda MCP previa no devolvió resultados: {preflight}")

        first = _json_result(
            await session.call_tool(
                "aprender",
                arguments=_aprender_args(
                    ANCHOR,
                    "BioRAG conserva este recuerdo de instalación y persistencia entre procesos.",
                    "biorag,instalacion,persistencia",
                ),
            ),
            "aprender(anchor)",
        )
        if first.get("status") != "ok":
            raise RuntimeError(f"No se pudo guardar el recuerdo principal: {first}")

        second_args = _aprender_args(
            LINKED,
            "Recuerdo relacionado para comprobar enlaces persistentes de BioRAG.",
            "biorag,asociacion,persistencia",
        )
        second_args["vincular_con"] = [ANCHOR]
        second = _json_result(
            await session.call_tool("aprender", arguments=second_args),
            "aprender(linked)",
        )
        if second.get("status") != "ok":
            raise RuntimeError(f"No se pudo guardar el recuerdo asociado: {second}")

        consolidated = _json_result(
            await session.call_tool("consolidar", arguments={}), "consolidar"
        )
        if consolidated.get("status") != "ok":
            raise RuntimeError(f"No se pudo consolidar la memoria: {consolidated}")

    # La sesión/processo MCP anterior ya cerró. La siguiente conexión es un reinicio real.
    async with _session(executable, db_path) as session:
        found = _json_result(
            await session.call_tool(
                "recordar",
                arguments={
                    "query": LINKED,
                    "sustantivos_clave": "biorag,asociacion,persistencia",
                    "completo": True,
                    "limite": 10,
                },
            ),
            "recordar(after restart)",
        )
        results = found.get("resultados")
        if not isinstance(results, list):
            raise RuntimeError(f"La búsqueda MCP no devolvió resultados: {found}")
        item = next(
            (row for row in results if row.get("concepto") == LINKED), None
        )
        if item is None:
            raise RuntimeError(f"No se recuperó {LINKED!r} después del reinicio: {found}")
        if "Recuerdo relacionado" not in (item.get("contenido") or ""):
            raise RuntimeError("El contenido no sobrevivió al reinicio del servidor MCP.")

    # Verificar en la DB temporal la categoría y la sinapsis, no solo la respuesta del proceso.
    with sqlite3.connect(str(db_path)) as conn:
        from core.contextual.schema import COLUMNS
        for table, expected in COLUMNS.items():
            actual = tuple(row[1] for row in conn.execute('PRAGMA table_info('+table+')'))
            if actual != expected:
                raise RuntimeError(f"Esquema contextual ausente/incompatible en wheel instalado: {table}")
        row = conn.execute(
            "SELECT l.contenido, c.name FROM largo_plazo AS l "
            "LEFT JOIN categories AS c ON c.id = l.categoria WHERE l.concepto = ?",
            (LINKED,),
        ).fetchone()
        if row != (
            "Recuerdo relacionado para comprobar enlaces persistentes de BioRAG.",
            "Lesson",
        ):
            raise RuntimeError(f"Contenido/categoría inesperados después del reinicio: {row!r}")
        edge = conn.execute(
            "SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ? LIMIT 1",
            (LINKED, ANCHOR),
        ).fetchone()
        if edge is None:
            raise RuntimeError("La asociación esperada no persistió en la DB temporal.")


def main() -> int:
    # No importar desde el checkout ni crear datos junto al repositorio.
    os.chdir(tempfile.gettempdir())
    with tempfile.TemporaryDirectory(prefix="biorag-install-smoke-") as directory:
        db_path = Path(directory) / "memory_biorag.db"
        os.environ["BIORAG_PATH"] = str(db_path)
        os.environ["BIORAG_NLTK_DATA"] = str(Path(directory) / "nltk_data")
        os.environ["BIORAG_NLTK_AUTO_DOWNLOAD"] = "0"
        os.environ["BIORAG_DAEMON_ENABLED"] = "0"
        os.environ["BIORAG_UPDATE_CHECK"] = "0"
        executable = _assert_installed_wheel()
        asyncio.run(_smoke(executable, db_path))
    print("OK: wheel, herramientas MCP, escritura, consolidación, reinicio y persistencia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
