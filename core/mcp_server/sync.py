"""MCP Tools for synchronization and exporting to NotebookLM.

Exposes tools:
- sync_status
- export_sync
- export_full
"""

import json
import os
import subprocess
from typing import Any

from core.mcp_server._shared import _get_cerebro
from core.paths import project_root


def register(mcp: Any) -> None:
    @mcp.tool(
        name="sync_status",
        description=(
            "Mostrá qué categorías tienen cambios pendientes de subir a NotebookLM. Llamá a esto antes de export_sync para saber qué se va a subir. Sin parámetros."
        ),
    )
    def biorag_sync_status() -> str:
        cerebro = _get_cerebro()
        try:
            pending = cerebro.sync_status()
            if not pending:
                return json.dumps({
                    "status": "ok",
                    "mensaje": "No hay categorías pendientes. Todo sincronizado.",
                    "pendientes": [],
                }, ensure_ascii=False)
            items = [{"id": p[0], "nombre": p[1], "cambios": p[2]} for p in pending]
            msg = f"{len(items)} categoría(s) pendiente(s): " + ", ".join(f"{p[1]}({p[2]})" for p in pending)
            return json.dumps({
                "status": "ok",
                "mensaje": msg,
                "pendientes": items,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="export_sync",
        description=(
            "Exportá solo lo nuevo — las categorías con cambios pendientes se guardan como archivos .jsonl.txt en db/, listos para subir a NotebookLM. Para exportar todo, usá export_full. Sin parámetros."
        ),
    )
    def biorag_export_sync() -> str:
        script_path = os.path.join(
            project_root(),
            "..", "MemoryBioRAG_NOTEBOOK_MCP", "scripts", "export_pending.py"
        )
        try:
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                return json.dumps({
                    "status": "error",
                    "mensaje": f"Error en export:\n{result.stderr}",
                }, ensure_ascii=False)
            return json.dumps({
                "status": "ok",
                "mensaje": output,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "mensaje": str(e),
            }, ensure_ascii=False)

    @mcp.tool(
        name="export_full",
        description=(
            "Exportá todo — todas las categorías a archivos .jsonl.txt en db/. Para la primera sincronización completa o como fallback. Si querés solo lo nuevo, usá export_sync. Sin parámetros."
        ),
    )
    def biorag_export_full() -> str:
        script_path = os.path.join(
            project_root(),
            "..", "MemoryBioRAG_NOTEBOOK_MCP", "scripts", "export_full.py"
        )
        try:
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True, text=True, timeout=60
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                return json.dumps({
                    "status": "error",
                    "mensaje": f"Error en export:\n{result.stderr}",
                }, ensure_ascii=False)
            return json.dumps({
                "status": "ok",
                "mensaje": output,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "mensaje": str(e),
            }, ensure_ascii=False)
