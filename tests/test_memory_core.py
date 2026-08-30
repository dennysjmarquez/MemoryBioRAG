#!/usr/bin/env python3
"""
Wrapper: integra el test de memoria completo (test_memory.py) en la suite QA.
No toca la DB en vivo — crea su propio test_memory.db al lado del snapshot.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_memory import test_sistema as _test_sistema_monolito


def test_memoria_core():
    """Ejecuta el suite completo de tests de memoria como función pytest."""
    _test_sistema_monolito()
