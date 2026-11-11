"""Guardas de las reglas de arquitectura de `AGENTS.md` §4b.

Las reglas escritas en un documento se olvidan; estas pruebas las aplican.

`core/` arrastra deuda de antes de que existieran las reglas (funciones sin
docstring en archivos viejos). No se arregla de golpe: se congela la cifra y
se exige que **no crezca**. Cada cambio nuevo debe dejar el número igual o
menor.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
GUION = RAIZ / "scripts" / "auditar_arquitectura.py"

# Deuda congelada al crear la regla (2026-11-07). Solo puede bajar.
DEUDA_INICIAL = 114
# Antipatrones de docs/CODIGO_LIMPIO.md §3. Eran 7; se corrigieron todas.
EXCEPT_DESNUDOS_MAX = 0
IMPORT_ESTRELLA_MAX = 0
# SQL con f-string: 62 revisados uno a uno con el AST el 2026-11-07. Todos
# interpolan placeholders, nombres de tabla constantes o enteros del propio
# codigo. Solo puede bajar (docs/SEGURIDAD_OWASP.md §5).
SQL_FSTRING_MAX = 62


def _auditar(*args: str) -> subprocess.CompletedProcess:
    """Ejecuta el auditor de arquitectura y devuelve su salida."""
    return subprocess.run(
        [sys.executable, str(GUION), *args],
        capture_output=True, text=True, cwd=RAIZ,
    )


def test_el_paquete_sqlite_cumple_las_reglas_estrictamente():
    """Un paquete nuevo no entra con deuda: cero hallazgos."""
    resultado = _auditar("sqlite", "--strict")
    assert resultado.returncode == 0, resultado.stdout


def test_la_deuda_de_arquitectura_no_crece():
    """Cada cambio nuevo debe dejar el número igual o menor."""
    resultado = _auditar()
    total = resultado.stdout.count("[sin_docstring]")
    assert total <= DEUDA_INICIAL, (
        f"la deuda de arquitectura creció de {DEUDA_INICIAL} a {total}.\n"
        f"Documenta tus funciones (AGENTS.md §4b.4):\n{resultado.stdout[:3000]}"
    )


def test_sin_except_desnudos():
    """`except:` se traga hasta Ctrl-C y esconde fallos reales.

    Habia 7 en core/ (mcp_server/search.py y memory/schema.py). Se corrigieron
    todas el 2026-11-07: ahora el tope es cero.
    """
    resultado = _auditar()
    desnudos = resultado.stdout.count("[except_desnudo]")
    assert desnudos <= EXCEPT_DESNUDOS_MAX, (
        f"hay {desnudos} `except:` desnudos; usa la excepcion concreta "
        f"(docs/CODIGO_LIMPIO.md §3)"
    )


def test_sin_import_estrella():
    """`import *` rompe el rastreo de dependencias del que vive la arquitectura."""
    resultado = _auditar()
    estrellas = resultado.stdout.count("[import_estrella]")
    assert estrellas <= IMPORT_ESTRELLA_MAX, f"hay {estrellas} `import *`"


def test_el_sql_con_fstring_no_crece():
    """OWASP A03: cada f-string de SQL es una decision que hay que justificar.

    No se prohibe (PRAGMA no admite parametros y las listas de `?` son
    legitimas), pero el numero no puede crecer sin que alguien lo revise.
    """
    resultado = _auditar()
    total = resultado.stdout.count("[sql_fstring]")
    assert total <= SQL_FSTRING_MAX, (
        f"hay {total} SQL con f-string (tope {SQL_FSTRING_MAX}). "
        f"Revisa que cada uno interpole solo placeholders o identificadores "
        f"(docs/SEGURIDAD_OWASP.md §3 A03):\n{resultado.stdout[:2000]}"
    )


def test_sin_shell_true_en_subprocess():
    """OWASP A03: nunca shell=True con datos que no controlas."""
    resultado = _auditar()
    assert "[shell_true]" not in resultado.stdout, resultado.stdout[:2000]


def test_sin_nombres_de_cajon_de_sastre():
    """`utils.py`, `helpers.py` y compañía esconden acoplamiento (§4b.2)."""
    prohibidos = {"utils.py", "helpers.py", "misc.py", "common.py", "aux.py"}
    encontrados = [str(p.relative_to(RAIZ)) for p in (RAIZ / "core").rglob("*.py")
                   if p.name in prohibidos]
    assert not encontrados, f"nombres prohibidos: {encontrados}"


def test_anidamiento_maximo_tres_niveles():
    """`core/a/b/c.py` como máximo (§4b.1)."""
    core = RAIZ / "core"
    profundos = [str(p.relative_to(RAIZ)) for p in core.rglob("__init__.py")
                 if len(p.parent.relative_to(core).parts) > 3]
    assert not profundos, f"paquetes demasiado anidados: {profundos}"
