#!/usr/bin/env python3
"""E2d: observar la media temática SIN cambiar el motor ni la QA oficial.

Ejemplo (ajustar las rutas de salida y la base):

    BIORAG_PATH=/ruta/copia.db BIORAG_NEURONA=0 BIORAG_QA_RUIDO='' \
    BIORAG_QA_TEMATICO_CENSO=1 BIORAG_QA_METRICS=/tmp/qa.json \
    BIORAG_QA_FAILED_CASES=/tmp/fallos.jsonl \
    python scripts/censo_tematico_e2d.py --salida /tmp/censo.json \
        --baseline docs/e1c_qa_honesta_viva_20261026.json

El arnés sigue siendo scripts/evaluar_qa.py. Su propio censo envuelve el método
observado aquí. Este envoltorio solo lee las variables locales de la búsqueda,
llama a la fórmula original con los mismos argumentos y devuelve su resultado.
Cada media se comprueba contra la señal entregada a la fórmula. La comparación
con E1c sirve para detectar cambios en las métricas y clasificaciones guardadas;
no demuestra por sí sola que todos los rankings individuales sean idénticos.
"""

import argparse
from array import array
import json
import math
import os
from pathlib import Path
import runpy
import sys


RAIZ = Path(__file__).resolve().parents[1]
RUTA_QA = str(RAIZ / "scripts" / "evaluar_qa.py")
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Límites izquierdos incluidos y derechos excluidos, salvo el último sin techo.
INTERVALOS = (
    ("< 0.10", 0.10),
    ("[0.10, 0.20)", 0.20),
    ("[0.20, 0.30)", 0.30),
    ("[0.30, 1/3)", 1 / 3),
    ("[1/3, 0.40)", 0.40),
    ("[0.40, 0.50)", 0.50),
    ("[0.50, 0.60)", 0.60),
    ("[0.60, 0.70)", 0.70),
    ("[0.70, 0.80)", 0.80),
    ("[0.80, 0.90)", 0.90),
    ("[0.90, 1.00)", 1.00),
    (">= 1.00", math.inf),
)


def leer_media(locales, tematico):
    """Clasifica la llamada y, si existe, lee la media previa a ×3.

    `sims` puede conservar la lista de OTRO candidato cuando la compuerta no
    se ejecuta: en ese caso jamás se lee. Los nombres y condiciones reproducen
    el guardia de core/memory/search.py, sin sustituir su cálculo.
    """
    guardia = bool(
        locales["_perfiles_tematicos"]
        and locales["_todas_dims"]
        and (locales["bm25_val"] > 0.001 or locales["concepto_ratio"] > 0.001)
        and locales["sinonimos_ratio"] < 0.5
    )
    if not guardia:
        if tematico != 0.0:
            raise ValueError("compuerta cerrada, pero tematico_score no es cero")
        return "compuerta_cerrada", None, 0

    sims = locales["sims"]
    if not isinstance(sims, list):
        raise TypeError("la lista sims no es una lista")
    if not sims:
        if tematico != 0.0:
            raise ValueError("lista vacía, pero tematico_score no es cero")
        return "lista_vacia", None, 0
    if any(not math.isfinite(s) or s <= 0.02 for s in sims):
        raise ValueError("sims contiene un valor no finito o que no pasa >0.02")

    media = sum(sims) / len(sims)  # exactamente la operación del motor
    if not math.isfinite(media):
        raise ValueError("la media no es finita")
    recalculado = min(1.0, media * 3.0)
    if recalculado != tematico:
        raise ValueError(f"media × 3 -> {recalculado!r}, tematico_score -> {tematico!r}")
    if (media >= 1 / 3) != (tematico == 1.0):
        raise ValueError("el umbral 1/3 no coincide con la saturación real")
    return "media_valida", media, len(sims)


def percentil_ordenado(valores, porcentaje):
    """Percentil por rango más próximo: posición ceil(p/100 * n), desde 1."""
    if not valores:
        return None
    posicion = max(0, math.ceil(porcentaje / 100 * len(valores)) - 1)
    return valores[posicion]


class CensoCrudo:
    def __init__(self):
        self.llamadas = 0
        self.en_busqueda = 0
        self.fuera_de_busqueda = 0
        self.fuera_en_censo_nativo = 0
        self.compuerta_cerrada = 0
        self.lista_vacia = 0
        self.medias = array("d")
        self.pares_aceptados = 0
        self.errores = []
        self.cantidad_errores = 0

    def observar(self, locales, tematico, *, huella=False, en_censo_nativo=False):
        """No conservar frames, listas ni referencias a la base: solo números.

        La QA calcula una huella de la fórmula antes de instalar su censo. Esa
        huella llama a la fórmula 12 veces, pero no son búsquedas ni pares reales.
        Se cuentan aparte SOLO si provienen de huella_motor y no pasan por el
        censo nativo; cualquier otro origen fuera de búsqueda invalida la corrida.
        """
        if locales is None:
            self.fuera_de_busqueda += 1
            if en_censo_nativo:
                self.fuera_en_censo_nativo += 1
            if not huella or en_censo_nativo:
                self._error("llamada fuera de búsqueda de origen inesperado o en el censo QA")
            return
        self.llamadas += 1
        self.en_busqueda += 1
        try:
            tipo, media, pares = leer_media(locales, tematico)
            if tipo == "compuerta_cerrada":
                self.compuerta_cerrada += 1
            elif tipo == "lista_vacia":
                self.lista_vacia += 1
            else:
                self.medias.append(media)
                self.pares_aceptados += pares
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            self._error(f"{type(exc).__name__}: {exc}")

    def _error(self, descripcion):
        self.cantidad_errores += 1
        if len(self.errores) < 10:
            self.errores.append(descripcion)

    def resumen(self):
        valores = sorted(self.medias)
        n = len(valores)
        histogramas = [{"intervalo": nombre, "llamadas": 0} for nombre, _ in INTERVALOS]
        saturadas = 0
        for media in valores:
            saturadas += media >= 1 / 3
            for fila, (_, techo) in zip(histogramas, INTERVALOS):
                if media < techo:
                    fila["llamadas"] += 1
                    break
        for fila in histogramas:
            fila["porcentaje_de_medias"] = fila["llamadas"] / n * 100 if n else None
        return {
            "unidad": "llamadas a la fórmula por candidato y consulta; no candidatos únicos",
            "llamadas_observadas_total_incluida_huella": self.llamadas + self.fuera_de_busqueda,
            "llamadas_formula": self.llamadas,
            "llamadas_en_busqueda": self.en_busqueda,
            "llamadas_fuera_de_busqueda": self.fuera_de_busqueda,
            "llamadas_fuera_en_censo_nativo": self.fuera_en_censo_nativo,
            "compuerta_no_ejecutada": self.compuerta_cerrada,
            "compuerta_ejecutada_lista_vacia": self.lista_vacia,
            "compuerta_ejecutada_con_media": n,
            "suma_de_pares_sobre_umbral": self.pares_aceptados,
            "media_sims": {
                "n": n,
                "minimo": valores[0] if n else None,
                "media": sum(valores) / n if n else None,
                "percentiles_rango_mas_proximo": {
                    f"p{p}": percentil_ordenado(valores, p)
                    for p in (1, 5, 10, 25, 50, 75, 90, 95, 99)
                },
                "maximo": valores[-1] if n else None,
                "saturadas_media_mayor_o_igual_1_tercio": saturadas,
                "porcentaje_saturadas_sobre_medias": saturadas / n * 100 if n else None,
                "histograma": histogramas,
            },
            "errores_observacion": self.cantidad_errores,
            "primeros_errores": self.errores,
        }


def crear_observador(original, codigo_busqueda, censo, codigos_huella=()):
    """Lee el frame de búsqueda y delega sin modificar argumentos ni retorno."""
    def observado(self, **kw):
        frame = sys._getframe(1)
        es_huella = False
        en_censo_nativo = False
        while frame is not None and frame.f_code is not codigo_busqueda:
            es_huella = es_huella or frame.f_code in codigos_huella
            en_censo_nativo = en_censo_nativo or (
                frame.f_code.co_name == "_hibrido_censado"
                and frame.f_code.co_filename == RUTA_QA
            )
            frame = frame.f_back
        try:
            censo.observar(
                frame.f_locals if frame is not None else None,
                float(kw.get("tematico_score", 0.0) or 0.0),
                huella=es_huella,
                en_censo_nativo=en_censo_nativo,
            )
        finally:
            # No guardar el frame. La fórmula y su retorno son los originales.
            del frame
        return original(self, **kw)
    return observado


def comparar_resultados(actual, baseline, resumen):
    """Contrasta datos oficiales guardados y el censo nativo de la QA."""
    comparacion_qa = {
        nombre: actual.get(nombre) == baseline.get(nombre)
        for nombre in ("casos_total", "global", "categorias", "qa_honesta")
    }
    nativo = actual.get("e2b", {}).get("censo_tematico") or {}
    comparacion_censo = {
        "llamadas": resumen["llamadas_formula"] == nativo.get("candidatos"),
        "medias": resumen["compuerta_ejecutada_con_media"] == nativo.get("con_tematico"),
        "saturadas": resumen["media_sims"]["saturadas_media_mayor_o_igual_1_tercio"]
        == nativo.get("saturados"),
        "desglose_completo": resumen["llamadas_formula"] == (
            resumen["compuerta_no_ejecutada"]
            + resumen["compuerta_ejecutada_lista_vacia"]
            + resumen["compuerta_ejecutada_con_media"]
        ),
    }
    return comparacion_qa, comparacion_censo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", required=True, type=Path, help="JSON de la distribución")
    parser.add_argument("--baseline", required=True, type=Path, help="JSON E1c de la misma base")
    args = parser.parse_args()

    exigidas = {
        "BIORAG_PATH": None,
        "BIORAG_NEURONA": "0",
        "BIORAG_QA_TEMATICO_CENSO": "1",
        "BIORAG_QA_METRICS": None,
        "BIORAG_QA_FAILED_CASES": None,
    }
    for nombre, valor in exigidas.items():
        recibido = os.environ.get(nombre)
        if not recibido or (valor is not None and recibido != valor):
            parser.error(f"debe establecerse {nombre}={valor or '<ruta>'}")
    if os.environ.get("BIORAG_QA_RUIDO", "").strip():
        parser.error("E2d mide sin BIORAG_QA_RUIDO")
    if not args.baseline.is_file():
        parser.error("la baseline indicada no existe")
    metrics_path = Path(os.environ["BIORAG_QA_METRICS"])
    if len({args.salida.resolve(), metrics_path.resolve(), args.baseline.resolve()}) != 3:
        parser.error("salida, métricas y baseline deben ser archivos distintos")
    # No usar métricas viejas si la QA aborta antes de escribir las nuevas.
    if metrics_path.exists():
        parser.error("la ruta de métricas ya existe; elegir una ruta nueva")

    from core.memory_store import SQLiteMemoryBioRAG
    from core.memory.search import buscar_por_frase
    from core.memory import neurona

    original = SQLiteMemoryBioRAG._calcular_score_hibrido
    censo = CensoCrudo()
    SQLiteMemoryBioRAG._calcular_score_hibrido = crear_observador(
        original, buscar_por_frase.__code__, censo, (neurona.huella_motor.__code__,)
    )
    argv_original = sys.argv
    error_qa = None
    try:
        sys.argv = [str(RAIZ / "scripts" / "evaluar_qa.py")]
        runpy.run_path(sys.argv[0], run_name="__main__")
    except SystemExit as exc:
        error_qa = exc.code if exc.code is not None else 0
    finally:
        sys.argv = argv_original
        SQLiteMemoryBioRAG._calcular_score_hibrido = original

    resumen = censo.resumen()
    resumen["baseline"] = str(args.baseline)
    resumen["metricas"] = str(metrics_path)
    resumen["salida_qa"] = error_qa or 0
    if metrics_path.is_file():
        actual = json.loads(metrics_path.read_text(encoding="utf-8"))
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        qa, nativo = comparar_resultados(actual, baseline, resumen)
    else:
        qa, nativo = {}, {}
    resumen["igualdad_con_baseline_e1c"] = qa
    resumen["coincide_con_censo_qa"] = nativo
    resumen["valido"] = bool(
        metrics_path.is_file() and not error_qa and not resumen["errores_observacion"]
        and qa and all(qa.values()) and nativo and all(nativo.values())
    )
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n[E2d] Censo guardado en {args.salida}; válido: {resumen['valido']}")
    if not resumen["valido"]:
        print("[E2d] ATENCIÓN: no interpretar la distribución; revisar el JSON de validación.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
