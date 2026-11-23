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
                             contexto: dict, valor_anterior: str, valor_nuevo: str,
                             anterior_desde: Optional[float] = None) -> dict:
        """Proponer sustitución estructurada: TÚ interpretas el mensaje, no el motor.

        contexto exige {entity,attribute,scope} con identificadores estables exactos;
        valor_anterior/valor_nuevo son valores explícitos, no palabras detectadas.
        mensaje conserva evidencia original en cualquier idioma; no exige frases.
        Nodos deben existir y ser distintos. Fechas en segundos UNIX explícitos.
        Si falta ledger, anterior_desde propone bootstrap revisable, NO lo aprueba.
        Luego revisar_correccion y solo confirmar si la evidencia es correcta.
        No inferir correcciones por leer texto recordado. Registro no es aprobación.
        """
        service=configured_service(stdio=stdio)
        try:
            return service.register_structured(id,mensaje,nodo_anterior,nodo_sucesor,
                                    observado_en,efectivo_desde,contexto,
                                    valor_anterior,valor_nuevo,anterior_desde)
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
