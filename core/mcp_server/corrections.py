"""MCP de correcciones: permisos del host, nunca de argumentos o del texto.

Solo stdio explícitamente delegado. SSE no dispone de identidad autenticada para
esta operación y permanece denegado, aunque existan variables de entorno.
"""
import json
import os
from typing import Optional
from core.paths import resolve_db_path
from core.contextual.service import Corrections


def configured_service(*, stdio):
    if not stdio or os.environ.get('BIORAG_CORRECTIONS','0') != '1':
        raise PermissionError('Correcciones deshabilitadas; requieren delegación explícita del host stdio')
    principal=os.environ.get('BIORAG_CORRECTIONS_PRINCIPAL','').strip()
    grants=json.loads(os.environ.get('BIORAG_CORRECTIONS_GRANTS','[]'))
    if not principal or not isinstance(grants,list) or not grants:
        raise PermissionError('Configurar principal y contextos delegados en el anfitrión')
    if any(not isinstance(g,list) or len(g)!=3 or any(not isinstance(v,str) or not v.strip() for v in g) for g in grants):
        raise ValueError('Delegaciones requieren listas [entity,attribute,scope] exactas')
    return Corrections(resolve_db_path(),principal,grants)


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
        """Confirmación explícita por propietario/agente delegado por host stdio.
        Revalidación y commit atómico de ledger+arista tipada+recibo en la misma DB.
        No modifica el contenido histórico, sinapsis asociativas ni pesos.
        """
        service=configured_service(stdio=stdio)
        try:
            return service.confirm(id,digest,request_id)
        finally:
            service.close()
