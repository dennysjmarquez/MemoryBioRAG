"""Consulta no bloqueante del canal estable y aviso MCP de actualización.

Lee política pública y tags de versión; nunca envía recuerdos, configuración local
ni datos de uso. No instala ni modifica archivos automáticamente.
"""
from __future__ import annotations

import base64
import json
import os
import re
import threading
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_SOURCE_REPO_API = "https://api.github.com/repos/dennysjmarquez/MemoryBioRAG"
_STABLE_REPO_API = "https://api.github.com/repos/dennysjmarquez/MemoryBioRAG-Stable"
_POLICY_API = f"{_STABLE_REPO_API}/contents/update_policy.json?ref=main"
_TAGS_API = f"{_STABLE_REPO_API}/tags?per_page=100"
_TAGS_PAGE = "https://github.com/dennysjmarquez/MemoryBioRAG-Stable/tree/"
_DEFAULT_TIMEOUT_SECONDS = 3.0
_MAX_TAG_PAGES = 10
_DEFAULT_INTERVAL_SECONDS = 24 * 60 * 60
_VERSION_PATTERN = re.compile(r"^[vV]?(\d+(?:\.\d+){1,2})$")


def _version_key(value: str) -> tuple[int, int, int] | None:
    """Parsea etiquetas estables vN.N o vN.N.N; ignora pre-releases y texto arbitrario."""
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        return None
    parts = tuple(int(part) for part in match.group(1).split("."))
    return (parts[0], parts[1], parts[2] if len(parts) == 3 else 0)


def _canonical_version(value: str) -> str:
    key = _version_key(value)
    return ".".join(str(part) for part in key) if key is not None else value.strip()


def installed_version() -> str:
    """Obtiene la versión del checkout o, en un wheel, de sus metadatos instalados."""
    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    try:
        value = version_file.read_text(encoding="utf-8").strip()
        if _version_key(value) is not None:
            return _canonical_version(value)
    except OSError:
        pass

    try:
        return _canonical_version(distribution_version("memory-biorag"))
    except PackageNotFoundError:
        return "unknown"


def _updates_enabled_from_env() -> bool:
    value = os.environ.get("BIORAG_UPDATE_CHECK", "1").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"}


def _github_json(url: str, read_limit: int) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MemoryBioRAG-update-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=_DEFAULT_TIMEOUT_SECONDS) as response:
        return json.loads(response.read(read_limit).decode("utf-8"))


def fetch_update_policy() -> dict[str, Any] | None:
    """Lee la política estable; 404 significa que aún no se publicó el manifiesto."""
    try:
        payload = _github_json(_POLICY_API, 64 * 1024)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise

    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        raise ValueError("Respuesta de política estable inválida")
    content = payload.get("content")
    if not isinstance(content, str):
        raise ValueError("Contenido de política estable ausente")
    policy = json.loads(base64.b64decode(content, validate=False).decode("utf-8"))
    if not isinstance(policy, dict):
        raise ValueError("El manifiesto de actualización debe ser un objeto JSON")
    return policy


def fetch_stable_tags() -> list[str]:
    """Obtiene los tags numéricos estables del repo de código para validar la política."""
    tags: list[str] = []
    for page in range(1, _MAX_TAG_PAGES + 1):
        payload = _github_json(f"{_TAGS_API}&page={page}", 256 * 1024)
        if not isinstance(payload, list):
            raise ValueError("Respuesta de tags inválida")
        for item in payload:
            tag = item.get("name") if isinstance(item, dict) else None
            if isinstance(tag, str) and _version_key(tag) is not None:
                tags.append(tag)
        if len(payload) < 100:
            break
    return tags


def fetch_latest_tag() -> tuple[str, str] | None:
    """Compatibilidad: devuelve el tag estable numéricamente mayor."""
    tags = fetch_stable_tags()
    if not tags:
        return None
    tag = max(tags, key=_version_key)
    return tag, f"{_TAGS_PAGE}{tag}"


class UpdateChecker:
    """Comprueba una vez al inicio y luego cada 24 horas, sin bloquear acciones MCP."""

    def __init__(
        self,
        *,
        current_version: str | None = None,
        enabled: bool | None = None,
        fetch_policy: Callable[[], dict[str, Any] | None] = fetch_update_policy,
        fetch_tags: Callable[[], list[str]] = fetch_stable_tags,
        interval_seconds: float = _DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self.current_version = _canonical_version(current_version or installed_version())
        self.enabled = _updates_enabled_from_env() if enabled is None else enabled
        self._fetch_policy = fetch_policy
        self._fetch_tags = fetch_tags
        self._interval_seconds = max(60.0, float(interval_seconds))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._pending_notice: str | None = None
        self._notified_tag: str | None = None
        self._status: dict[str, Any] = {
            "estado": "deshabilitado" if not self.enabled else "pendiente",
            "detalle": None,
            "version_instalada": self.current_version,
            "version_remota": None,
            "actualizacion_disponible": False,
            "url_tag": None,
            "ultima_comprobacion": None,
        }

    def start(self) -> None:
        """Inicia la comprobación en background; no espera la red ni retrasa initialize."""
        if not self.enabled:
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="biorag-update-check",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """Pide detener el refresco periódico; no espera a una petición de red en curso."""
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.check_once()
            if self._stop.wait(self._interval_seconds):
                break

    def _set_status(
        self,
        state: str,
        detail: str,
        *,
        remote_tag: str | None = None,
        tag_url: str | None = None,
        available: bool = False,
        clear_notice: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            self._status = {
                "estado": state,
                "detalle": detail,
                "version_instalada": self.current_version,
                "version_remota": remote_tag,
                "actualizacion_disponible": available,
                "url_tag": tag_url,
                "ultima_comprobacion": datetime.now(timezone.utc).isoformat(),
            }
            if clear_notice:
                self._pending_notice = None
                if not available:
                    self._notified_tag = None
            return dict(self._status)

    def check_once(self) -> dict[str, Any]:
        """Consulta la política estable; tags nuevos no se anuncian sin aprobación."""
        if not self.enabled:
            return self.status()

        try:
            policy = self._fetch_policy()
        except HTTPError as exc:
            if exc.code == 404:
                policy = None
            else:
                with self._lock:
                    self._status["estado"] = "sin_respuesta"
                    self._status["detalle"] = "No se pudo leer la política del canal estable."
                    self._status["ultima_comprobacion"] = datetime.now(timezone.utc).isoformat()
                    return dict(self._status)
        except Exception:
            with self._lock:
                self._status["estado"] = "sin_respuesta"
                self._status["detalle"] = "No se pudo leer la política del canal estable."
                self._status["ultima_comprobacion"] = datetime.now(timezone.utc).isoformat()
                return dict(self._status)

        if policy is None:
            return self._set_status(
                "sin_politica",
                "MemoryBioRAG-Stable aún no publica update_policy.json.",
            )

        try:
            if (
                not isinstance(policy, dict)
                or type(policy.get("schema_version")) is not int
                or policy.get("schema_version") != 1
                or policy.get("channel") != "stable"
                or "recommended_tag" not in policy
                or "blocked_tags" not in policy
            ):
                raise ValueError("Esquema de política desconocido")

            blocked = policy["blocked_tags"]
            if not isinstance(blocked, list) or any(
                not isinstance(tag, str) or _version_key(tag) is None for tag in blocked
            ):
                raise ValueError("Lista de tags bloqueados inválida")
            blocked_keys = {_version_key(tag) for tag in blocked}

            recommended = policy["recommended_tag"]
            if recommended is None:
                return self._set_status(
                    "sin_actualizacion",
                    "El canal estable aún no recomienda una versión.",
                )
            if not isinstance(recommended, str):
                raise ValueError("Tag recomendado inválido")
            recommended_key = _version_key(recommended)
            if recommended_key is None:
                raise ValueError("Tag recomendado no es una versión estable")
            if recommended_key in blocked_keys:
                return self._set_status(
                    "sin_actualizacion",
                    "La política no permite anunciar la versión recomendada.",
                )

            tags = self._fetch_tags()
            if not isinstance(tags, list):
                raise ValueError("Respuesta de tags inválida")
            matching_tags = [
                tag for tag in tags
                if isinstance(tag, str) and _version_key(tag) == recommended_key
            ]
            if not matching_tags:
                return self._set_status(
                    "tag_no_publicado",
                    "La versión recomendada aún no existe como tag en MemoryBioRAG.",
                )
            tag = recommended if recommended in matching_tags else matching_tags[0]
            tag_url = f"{_TAGS_PAGE}{tag}"
            local_key = _version_key(self.current_version)
            if local_key is None:
                raise ValueError("Versión instalada no reconocida")
        except (OSError, URLError, TimeoutError):
            return self._set_status(
                "sin_respuesta",
                "No se pudieron validar los tags del repositorio de código.",
                clear_notice=False,
            )
        except Exception:
            return self._set_status(
                "politica_invalida",
                "La política de versiones no cumple el esquema estable esperado.",
            )

        available = recommended_key > local_key
        state = (
            "actualizacion_disponible"
            if available
            else "version_local_mas_reciente"
            if recommended_key < local_key
            else "actualizado"
        )
        with self._lock:
            self._status = {
                "estado": state,
                "detalle": None,
                "version_instalada": self.current_version,
                "version_remota": tag,
                "actualizacion_disponible": available,
                "url_tag": tag_url,
                "ultima_comprobacion": datetime.now(timezone.utc).isoformat(),
            }
            if available and tag != self._notified_tag:
                self._pending_notice = (
                    f"A new approved stable BioRAG version is available: {tag} "
                    f"(installed: {self.current_version}). Release tag: {tag_url}. "
                    "This update is not automatic. After explicit authorization, run "
                    "python -m core.updater --channel stable from the installed Git "
                    "checkout. The CLI stops only BioRAG's own verified daemon, backs "
                    "up the database, updates code and dependencies, then verifies it. "
                    "A failure triggers automatic rollback when it can be verified; "
                    "otherwise keep the backup and do not restart BioRAG. Ask the external "
                    "MCP host to reconnect after success. Other installation "
                    "methods must use their original package manager, then run "
                    "python -m core.lifecycle. Never replace the user's database file."
                )
                self._notified_tag = tag
            elif not available:
                self._pending_notice = None
                self._notified_tag = None
            return dict(self._status)

    def status(self) -> dict[str, Any]:
        """Copia serializable del estado más reciente, sin iniciar una petición."""
        with self._lock:
            return dict(self._status)

    def take_notice(self) -> str | None:
        """Consume como máximo un aviso por versión; lo llama el middleware MCP."""
        with self._lock:
            notice = self._pending_notice
            self._pending_notice = None
            return notice


async def notify_pending_update(
    checker: UpdateChecker,
    context: Any,
    logger: Any | None = None,
) -> bool:
    """Envía una logging notification MCP sin permitir que falle la herramienta."""
    notice = checker.take_notice()
    if not notice:
        return False
    try:
        await context.warning(notice)
    except Exception as exc:
        if logger is not None:
            logger.debug("El cliente MCP no aceptó el aviso de versión: %s", exc)
        return False
    return True


def version_aware_server_class(
    base_class: type[Any],
    checker: UpdateChecker,
    logger: Any | None = None,
) -> type[Any]:
    """Crea un FastMCP compatible que avisa antes de ejecutar la siguiente herramienta."""
    class VersionAwareServer(base_class):
        def __init__(self, *args, **kwargs):
            self.update_checker = checker
            super().__init__(*args, **kwargs)
            low_level_server = getattr(self, "_mcp_server", None)
            if low_level_server is not None:
                # MCP serverInfo.version debe identificar BioRAG, no el SDK MCP.
                low_level_server.version = checker.current_version

        async def call_tool(self, name, arguments):
            notice = self.update_checker.take_notice()
            if notice:
                try:
                    await self.get_context().warning(notice)
                except Exception as exc:
                    if logger is not None:
                        logger.debug("El cliente MCP no aceptó el aviso de versión: %s", exc)
            result = await super().call_tool(name, arguments)
            if notice and result:
                # Inyectar banner visible en el payload de retorno (TextContent) para que el agente lo lea directamente
                banner = f"ℹ️ [BioRAG Update Notice]: {notice}\n---\n"
                try:
                    from mcp.types import TextContent
                    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], TextContent):
                        result[0] = TextContent(type='text', text=banner + result[0].text)
                except Exception:
                    pass
            return result

    return VersionAwareServer


def register(mcp: Any, checker: UpdateChecker) -> None:
    """Expone el estado de versión en el recurso estándar biorag://version."""
    @mcp.resource(
        uri="biorag://version",
        name="Versión de BioRAG",
        description=(
            "Estado de la versión instalada y del tag aprobado por MemoryBioRAG-Stable. "
            "Una política ausente se informa explícitamente; el chequeo es no bloqueante, "
            "periódico y desactivable con BIORAG_UPDATE_CHECK=0."
        ),
        mime_type="application/json",
    )
    def recurso_version() -> str:
        return json.dumps(checker.status(), ensure_ascii=False, sort_keys=True)
