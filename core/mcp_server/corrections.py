"""Correcciones para cliente MCP local confiable, sin permisos temáticos.

SSE sigue denegado: no trasladar la confianza del proceso local a Internet.
"""
import os
from typing import Optional
from core.paths import resolve_db_path
from core.contextual.service import Corrections


def configured_service(*, stdio):
    if not stdio or os.environ.get('BIORAG_CORRECTIONS','1') != '1':
        raise PermissionError('Correcciones deshabilitadas; solo disponibles en MCP stdio local habilitado')
    return Corrections(resolve_db_path())


def register(mcp, *, stdio=False):
    @mcp.tool()
    def registrar_correccion(id: str, mensaje: str, nodo_anterior: str, nodo_sucesor: str,
                             observado_en: float, efectivo_desde: float,
                             anterior_desde: Optional[float] = None) -> dict:
        """Proponer actualización natural sin confirmar. Fechas/nodos explícitos.
        Si no hay ledger, anterior_desde permite proponer el antecedente; la revisión
        mostrará que se aprobarán ambos hechos. No verifica el contenido por sí solo.
        """
        service=configured_service(stdio=stdio)
        try:
            return service.register(id,mensaje,nodo_anterior,nodo_sucesor,
                                    observado_en,efectivo_desde,anterior_desde)
        finally:
            service.close()

    @mcp.tool()
    def revisar_correccion(id: str) -> dict:
        """Revisar evidencia, bootstrap y digest; el digest NO autentica al aprobador."""
        service=configured_service(stdio=stdio)
        try:
            return service.review(id)
        finally:
            service.close()

    @mcp.tool()
    def confirmar_correccion(id: str, digest: str, request_id: str) -> dict:
        """Confirmación explícita por el cliente MCP stdio local confiable.
        Revalidación y commit atómico de ledger+arista tipada+recibo en la misma DB.
        No modifica el contenido histórico, sinapsis asociativas ni pesos.
        """
        service=configured_service(stdio=stdio)
        try:
            return service.confirm(id,digest,request_id)
        finally:
            service.close()
