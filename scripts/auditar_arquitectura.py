#!/usr/bin/env python3
"""Audita las reglas de arquitectura de `AGENTS.md` sección 4b.

Qué problema resuelve: las reglas escritas en un documento se olvidan. Este
script las comprueba en el código real para que un agente o una persona sepa
en segundos si su cambio las cumple, antes de abrir un PR.

Qué comprueba:
  1. Nombres prohibidos (`utils.py`, `helpers.py`, `misc.py`, `common.py`).
  2. Anidamiento máximo de tres niveles en `core/`.
  3. Funciones sin docstring en los paquetes de `core/`.
  4. Ciclos de importación entre módulos de un mismo paquete.
  5. Antipatrones de `docs/CODIGO_LIMPIO.md` §3: `except:` desnudo e `import *`.

Cómo se usa:
    python3 scripts/auditar_arquitectura.py            # todo core/
    python3 scripts/auditar_arquitectura.py sqlite     # solo core/sqlite/
    python3 scripts/auditar_arquitectura.py --strict   # falla si hay hallazgos

Quién lo llama: a mano y desde las pruebas (`tests/test_arquitectura.py`).
Por qué existe: el proyecto va a crecer; esta es la red que evita que se
enrede. Ver `AGENTS.md` §4b.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CORE = RAIZ / "core"

NOMBRES_PROHIBIDOS = {"utils.py", "helpers.py", "misc.py", "common.py", "aux.py"}
MAX_NIVELES = 3


def paquetes(objetivo: str | None) -> list[Path]:
    """Carpetas de `core/` con `__init__.py`, filtradas por nombre si se pide."""
    encontrados = []
    for init in CORE.rglob("__init__.py"):
        carpeta = init.parent
        if objetivo and carpeta.name != objetivo:
            continue
        encontrados.append(carpeta)
    return encontrados


def hallazgo(tipo: str, donde: str, detalle: str) -> dict:
    """Un problema encontrado, con el dato justo para ir a verlo."""
    return {"tipo": tipo, "donde": donde, "detalle": detalle}


def revisar_nombres(carpeta: Path) -> list[dict]:
    """Regla 4b.2: no usar nombres de cajón de sastre."""
    return [
        hallazgo("nombre_prohibido", str(f.relative_to(RAIZ)),
                 "usa un nombre que esconde acoplamiento; ponle uno que diga qué hace")
        for f in carpeta.glob("*.py") if f.name in NOMBRES_PROHIBIDOS
    ]


def revisar_anidamiento(carpeta: Path) -> list[dict]:
    """Regla 4b.1: máximo tres niveles (`core/a/b/c.py`)."""
    relativa = carpeta.relative_to(CORE)
    if len(relativa.parts) > MAX_NIVELES:
        return [hallazgo("anidamiento", str(carpeta.relative_to(RAIZ)),
                         f"{len(relativa.parts)} niveles; el máximo es {MAX_NIVELES}")]
    return []


def revisar_docstrings(carpeta: Path) -> list[dict]:
    """Regla 4b.5: cero funciones sin docstring en un paquete."""
    faltan = []
    for archivo in carpeta.glob("*.py"):
        try:
            arbol = ast.parse(archivo.read_text())
        except SyntaxError as exc:
            faltan.append(hallazgo("sintaxis", str(archivo.relative_to(RAIZ)), str(exc)))
            continue
        for nodo in arbol.body:
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not ast.get_docstring(nodo):
                    faltan.append(hallazgo(
                        "sin_docstring", f"{archivo.relative_to(RAIZ)}:{nodo.lineno}",
                        f"`{nodo.name}` no dice qué hace ni por qué existe"))
    return faltan


def revisar_antipatrones(carpeta: Path) -> list[dict]:
    """Reglas de `docs/CODIGO_LIMPIO.md` §3: antipatrones que no cuestan nada evitar."""
    encontrados = []
    for archivo in carpeta.glob("*.py"):
        try:
            arbol = ast.parse(archivo.read_text())
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ExceptHandler) and nodo.type is None:
                encontrados.append(hallazgo(
                    "except_desnudo", f"{archivo.relative_to(RAIZ)}:{nodo.lineno}",
                    "`except:` se traga hasta Ctrl-C; usa `except Exception` "
                    "o la excepcion concreta"))
            elif isinstance(nodo, ast.ImportFrom) and any(a.name == "*" for a in nodo.names):
                encontrados.append(hallazgo(
                    "import_estrella", f"{archivo.relative_to(RAIZ)}:{nodo.lineno}",
                    "`import *` rompe el rastreo de dependencias; importa nombres"))
    return encontrados


def revisar_ciclos(carpeta: Path) -> list[dict]:
    """Regla 4b.3: sin ciclos entre los módulos de un mismo paquete."""
    grafo: dict[str, set[str]] = {}
    for archivo in carpeta.glob("*.py"):
        try:
            arbol = ast.parse(archivo.read_text())
        except SyntaxError:
            continue
        destinos = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                partes = nodo.module.split(".")
                if (len(partes) >= 3 and partes[0] == "core"
                        and partes[1] == carpeta.name):
                    destinos.add(partes[2])
        grafo[archivo.stem] = destinos

    problemas, vistos = [], set()

    def buscar(origen: str, actual: str, camino: list[str]) -> None:
        """Recorre el grafo buscando volver al origen."""
        for siguiente in grafo.get(actual, ()):
            if siguiente == origen and len(camino) > 1:
                clave = tuple(sorted(camino))
                if clave not in vistos:
                    vistos.add(clave)
                    problemas.append(hallazgo(
                        "ciclo", str(carpeta.relative_to(RAIZ)),
                        " → ".join(camino + [origen])))
            elif siguiente in grafo and siguiente not in camino:
                buscar(origen, siguiente, camino + [siguiente])

    for modulo in grafo:
        buscar(modulo, modulo, [modulo])
    return problemas


def main(argv: list[str]) -> int:
    """Recorre los paquetes y devuelve 0 si no hay hallazgos (o si no hay --strict)."""
    estricto = "--strict" in argv
    objetivo = next((a for a in argv[1:] if not a.startswith("-")), None)

    encontrados: list[dict] = []
    for carpeta in sorted(paquetes(objetivo)):
        encontrados += revisar_nombres(carpeta)
        encontrados += revisar_anidamiento(carpeta)
        encontrados += revisar_docstrings(carpeta)
        encontrados += revisar_ciclos(carpeta)
        encontrados += revisar_antipatrones(carpeta)

    if not encontrados:
        print(f"Arquitectura OK ({len(paquetes(objetivo))} paquetes revisados).")
        return 0

    print(f"{len(encontrados)} hallazgo(s):\n")
    for h in encontrados:
        print(f"  [{h['tipo']}] {h['donde']}")
        print(f"      {h['detalle']}")
    return 1 if estricto else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
