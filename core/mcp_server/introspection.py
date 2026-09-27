"""MCP Tools for system introspection, graph mapping and cognitive metrics history.

Exposes tools:
- introspeccion
- estado
- mapear
- corteza
- metricas_historial
"""

from datetime import datetime
import json
from typing import Annotated, Any
from pydantic import Field

from core.mcp_server._shared import _get_cerebro, _interceptar


def register(mcp: Any) -> None:
    @mcp.tool(
        name="introspeccion",
        description=(
            "Mirá el estado de la memoria. No modifica nada — solo muestra cuántos nodos activos, dormidos, en corto plazo, y cuánta energía sináptica queda. Sin parámetros."
        ),
    )
    def biorag_introspeccion() -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'"
            )
            activos = cerebro.cursor.fetchone()[0]
            cerebro.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'"
            )
            dormidos = cerebro.cursor.fetchone()[0]
            cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo")
            corto = cerebro.cursor.fetchone()[0]
            cerebro.cursor.execute(
                "SELECT ROUND(SUM(peso_sinaptico), 2) FROM largo_plazo WHERE estado = 'activo'"
            )
            energia = cerebro.cursor.fetchone()[0] or 0.0
            resultado = json.dumps({
                "activos": activos,
                "dormidos": dormidos,
                "corto_plazo": corto,
                "energia_sinaptica": energia,
            }, ensure_ascii=False)
            _interceptar("introspeccion", f"activos:{activos} dormidos:{dormidos}", cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="estado",
        description=(
            "(legado) Alias de 'introspeccion' — preferir 'introspeccion' para identificar la operación cognitiva real. "
            "Sin parámetros. "
            "Retorna: {activos (int), dormidos (int), corto_plazo (int), energia_sinaptica (float)}"
        ),
    )
    def biorag_estado() -> str:
        return biorag_introspeccion()

    @mcp.tool(
        name="mapear",
        description=(
            "Listá todos los nodos de la memoria — activos y dormidos — ordenados de más fuerte a más débil. Para explorar qué hay, detectar nodos huérfanos, revisar categorías, o verificar que algo se guardó bien. Ojo: si hay muchos nodos, la respuesta es larga. Sin parámetros."
        ),
    )
    def biorag_mapear() -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.cursor.execute(
                "SELECT concepto, categoria, peso_sinaptico, estado, asociaciones "
                "FROM largo_plazo ORDER BY peso_sinaptico DESC, estado ASC"
            )
            filas = cerebro.cursor.fetchall()
            items = [
                {
                    "concepto": c,
                    "categoria": cat,
                    "peso_sinaptico": p,
                    "estado": est,
                    "asociaciones": [v.strip() for v in (a or "").split(",") if v.strip()],
                }
                for c, cat, p, est, a in filas
            ]
            resultado = json.dumps({"total": len(items), "nodos": items}, ensure_ascii=False)
            _interceptar("mapear", "", cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="corteza",
        description=(
            "Alias viejo de mapear. Usá mapear en vez de esta."
        ),
    )
    def biorag_corteza() -> str:
        return biorag_mapear()

    @mcp.tool(
        name="metricas_historial",
        description=(
            "Mostrá el historial de ciclos de sueño — cuánto se consolidó, cuánto se olvidó, qué categoría se usa más, y si el cerebro está mejorando o empeorando. Requiere haber ejecutado consolidar al menos una vez."
        ),
    )
    def biorag_metricas_historial(
        n: Annotated[int, Field(
            description=(
                "Número de ciclos de sueño a incluir en el análisis (más recientes primero). "
                "Default: 10. Aumentar para tendencias históricas más largas."
            ),
            ge=1,
        )] = 10,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            cur = cerebro.cursor
            cur.execute("SELECT COUNT(*) FROM metricas_cognitivas")
            total = cur.fetchone()[0]

            if total == 0:
                return json.dumps({
                    "status": "ok",
                    "mensaje": "No hay métricas registradas aún. Ejecuta un ciclo de sueño primero.",
                    "total_registros": 0,
                }, ensure_ascii=False)

            cur.execute(
                "SELECT timestamp, nodos_consolidados, nodos_dormidos_ciclo, "
                "sinapsis_creadas, sinapsis_podadas, categoria_dominante, ratio_consolidacion "
                "FROM metricas_cognitivas ORDER BY timestamp DESC LIMIT ?", (n,)
            )
            filas = cur.fetchall()

            # Calcular promedios
            n_filas = len(filas)
            avg_consolidados = sum(f[1] for f in filas) / n_filas
            avg_dormidos = sum(f[2] for f in filas) / n_filas
            avg_creadas = sum(f[3] for f in filas) / n_filas
            avg_podadas = sum(f[4] for f in filas) / n_filas
            avg_ratio = sum(f[6] for f in filas) / n_filas if filas[0][6] else 0

            # Categoría dominante histórica
            cats = [f[5] for f in filas if f[5]]
            cat_dominante = max(set(cats), key=cats.count) if cats else "N/A"

            # Tendencia: comparar primera mitad vs segunda mitad
            if n_filas >= 4:
                mitad = n_filas // 2
                recientes = filas[:mitad]
                antiguos = filas[mitad:]
                avg_rec_consolidados = sum(f[1] for f in recientes) / len(recientes)
                avg_ant_consolidados = sum(f[1] for f in antiguos) / len(antiguos)
                if avg_rec_consolidados > avg_ant_consolidados * 1.1:
                    tendencia = "MEJORANDO (consolida más)"
                elif avg_rec_consolidados < avg_ant_consolidados * 0.9:
                    tendencia = "EMPEORANDO (consolida menos)"
                else:
                    tendencia = "ESTABLE"
            else:
                tendencia = "DATOS_INSUFICIENTES (menos de 4 ciclos)"

            # Formatear tabla
            tabla = "Fecha              Consol  Dormidos  Sin/Pod  Cat Dom     Ratio\n"
            tabla += "─" * 70 + "\n"
            for f in reversed(filas):
                fecha = datetime.fromtimestamp(f[0]).strftime("%Y-%m-%d %H:%M")
                tabla += f"{fecha}     {f[1]:<7}{f[2]:<9}{f[3]}/{f[4]}     {(f[5] or 'N/A'):<10}{f[6] or 0:.2f}\n"

            resultado = {
                "status": "ok",
                "total_registros": total,
                "ultimos_ciclos": n_filas,
                "tabla": tabla,
                "tendencias": {
                    "consolidacion_promedio": round(avg_consolidados, 2),
                    "olvido_promedio": round(avg_dormidos, 2),
                    "sinapsis_creadas_promedio": round(avg_creadas, 1),
                    "sinapsis_podadas_promedio": round(avg_podadas, 1),
                    "ratio_promedio": round(avg_ratio, 3),
                    "categoria_dominante": cat_dominante,
                    "tendencia": tendencia,
                },
                "salud_sinaptica": {
                    "creadas_total": sum(f[3] for f in filas),
                    "podadas_total": sum(f[4] for f in filas),
                    "ratio": round(sum(f[3] for f in filas) / max(1, sum(f[4] for f in filas)), 2),
                },
            }
            return json.dumps(resultado, ensure_ascii=False, indent=2)
        finally:
            cerebro.cerrar_sistema()
