#!/usr/bin/env python3
"""Mapa de dependencias internas de `core/` (solo lectura).

POR QUÉ EXISTE (2026-10-28, Constitución Pilares 9 y 10): los README de
`core/`, `core/memory/` y `core/mcp_server/` dicen "con qué se conecta" cada
archivo. Este script lo saca del código (imports reales, incluidos los que
están dentro de funciones), para que esas tablas se puedan verificar y
actualizar sin depender de la memoria de nadie.

No importa ni ejecuta el motor: solo lee el texto de los .py con `ast`.

Uso:
    python3 scripts/mapa_dependencias_core.py            # todos los módulos
    python3 scripts/mapa_dependencias_core.py memory     # filtra por texto
    python3 scripts/mapa_dependencias_core.py --huerfanos

"Huérfano" = ningún otro archivo de core/ ni de la raíz, scripts/ o tests/ lo
importa. No significa "borrar": significa "revisar por qué existe".
"""
from __future__ import annotations

import ast
import collections
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _modulos() -> dict[str, str]:
    mods: dict[str, str] = {}
    for root, _, files in os.walk(os.path.join(RAIZ, "core")):
        for f in sorted(files):
            if f.endswith(".py"):
                ruta = os.path.join(root, f)
                nombre = os.path.relpath(ruta, RAIZ)[:-3].replace(os.sep, ".")
                if nombre.endswith(".__init__"):
                    nombre = nombre[: -len(".__init__")]
                mods[nombre] = ruta
    return mods


def _dependencias(mods: dict[str, str]) -> dict[str, set[str]]:
    dep: dict[str, set[str]] = collections.defaultdict(set)
    for mod, ruta in mods.items():
        es_paquete = ruta.endswith("__init__.py")
        arbol = ast.parse(open(ruta, encoding="utf-8").read())
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom):
                if nodo.level:
                    partes = mod.split(".") + (["_"] if es_paquete else [])
                    base = ".".join(partes[: len(partes) - nodo.level] + ([nodo.module] if nodo.module else []))
                else:
                    base = nodo.module or ""
                if base in mods:
                    dep[mod].add(base)
                for alias in nodo.names:
                    if f"{base}.{alias.name}" in mods:
                        dep[mod].add(f"{base}.{alias.name}")
            elif isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    if alias.name in mods:
                        dep[mod].add(alias.name)
    return dep


def _usos_externos(mods: dict[str, str]) -> collections.Counter:
    usos: collections.Counter = collections.Counter()
    carpetas = [("scripts", True), ("tests", True), (".", False)]
    for carpeta, recursivo in carpetas:
        base = os.path.join(RAIZ, carpeta)
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for f in files:
                if f.endswith(".py"):
                    texto = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
                    for mod in mods:
                        if re.search(r"\b" + re.escape(mod) + r"\b", texto):
                            usos[mod] += 1
            if not recursivo:
                break
    return usos


def main() -> None:
    args = sys.argv[1:]
    mods = _modulos()
    dep = _dependencias(mods)
    inv: dict[str, set[str]] = collections.defaultdict(set)
    for a, destinos in dep.items():
        for b in destinos:
            inv[b].add(a)
    externos = _usos_externos(mods)

    if "--huerfanos" in args:
        for mod in mods:
            if not inv[mod] and not externos[mod] and mod not in ("core", "core.mcp_server.server"):
                print(mod)
        return

    filtro = next((a for a in args if not a.startswith("--")), "")
    for mod, ruta in mods.items():
        if filtro and filtro not in mod:
            continue
        lineas = open(ruta, encoding="utf-8").read().count("\n")
        corto = lambda xs: ", ".join(sorted(x.replace("core.", "", 1) for x in xs)) or "—"  # noqa: E731
        print(f"{mod}  ({lineas} líneas)")
        print(f"   usa:      {corto(dep[mod])}")
        print(f"   lo usan:  {corto(inv[mod])}  | fuera de core/: {externos[mod]} archivo(s)")
    print(f"\n{len(mods)} módulos, {sum(len(s) for s in dep.values())} conexiones internas")


if __name__ == "__main__":
    main()
