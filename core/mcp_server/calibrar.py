"""MCP Tools for conformal certainty calibration and Platt scaling.

Exposes tools:
- calibrar
"""

import json
from typing import Annotated, Any

from pydantic import Field

from core.mcp_server._shared import _get_cerebro


def register(mcp: Any) -> None:
    @mcp.tool(
        name="calibrar",
        description=(
            "Calibra (o recalibra) la garantía de falso positivo del motor contra el corpus ACTUAL y la persiste. "
            "El umbral conforme fija FP <= alpha (distribution-free, Vovk 2005) usando los 40 negativos del QA baseline. "
            "Se recalibra automáticamente cuando el corpus cambia de tamaño >20%; esta tool fuerza la recalibración "
            "con los parámetros pedidos. Retorna el umbral y el estado de calibración."
        ),
    )
    def biorag_calibrar(
        alpha: Annotated[float, Field(
            description="Garantía FP objetivo (0 < alpha < 1). Default: BIORAG_ALPHA_CONFORME o 0.10. Si es menor que 1/(n_negativos+1), se usa el mínimo alcanzable y se avisa (DECISION_ALPHA.md)."
        )] = None,
        n_negativos: Annotated[int, Field(
            description="Máximo de negativos a usar (hasta 40 disponibles en QA baseline)."
        )] = 40,
        forzar: Annotated[bool, Field(
            description="True = recalibrar aunque el corpus no haya cambiado. False (default) = reutilizar calibración vigente si no hay drift."
        )] = False,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            if forzar:
                res = cerebro.calibrar_y_persistir(
                    alpha=alpha, n_negativos=n_negativos, force=True
                )
                res["forzado"] = True
            else:
                res = cerebro.calibrar_y_persistir(alpha=alpha, n_negativos=n_negativos)
            return json.dumps(res, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()
