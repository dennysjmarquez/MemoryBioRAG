"""scripts/despertar_neurona.py: práctica acelerada de la neurona sobre recuerdos existentes."""
import importlib.util
import os
import sqlite3

import pytest

from core import memory_service
from core.memory_store import SQLiteMemoryBioRAG

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("despertar_neurona", os.path.join(RAIZ, "scripts", "despertar_neurona.py"))
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)

NODOS = [
    ("leccion_backup_base_datos", "Hacer copia de la base de datos cada noche; restaurar probando en otra maquina."),
    ("configuracion_servidor_nginx", "El servidor nginx escucha en el puerto 80 y redirige a la aplicacion en el 8000."),
    ("error_timeout_api_pagos", "La API de pagos corta a los 30 segundos; reintentar con espera exponencial."),
    ("plan_entrenamiento_correr", "Correr tres veces por semana: series cortas el martes y fondo largo el domingo."),
    ("fix_cache_redis_expira", "La cache en redis expiraba antes de tiempo por un TTL en segundos y no en minutos."),
]


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    p = str(tmp_path / "mia.db")
    c = SQLiteMemoryBioRAG(p)
    for k, v in NODOS:
        memory_service.aprender(c, k, v)
    c.cerrar_sistema()
    monkeypatch.setenv("BIORAG_NEURONA", "1")
    return p


def _filas_neurona(p):
    c = sqlite3.connect(p)
    try:
        return c.execute("SELECT COUNT(*) FROM neurona_estado").fetchone()[0]
    except sqlite3.OperationalError:
        return None
    finally:
        c.close()


def _respaldos(p):
    d, base = os.path.dirname(p), os.path.basename(p)
    return [f for f in os.listdir(d) if f.startswith(base + ".antes_despertar_")]


def test_estado_solo_mira(db, capsys):
    assert D.main([db, "--estado"]) == 0
    out = capsys.readouterr().out
    assert "ESTADO DE TU NEURONA" in out and "¿Ya mejora tus búsquedas?" in out
    assert _filas_neurona(db) is None          # no creó ni escribió nada
    assert _respaldos(db) == []                 # ni respaldo


def test_practica_guarda_estado_y_respalda(db, capsys):
    assert D.main([db, "--ciclos", "3", "--cada", "1"]) == 0
    out = capsys.readouterr().out
    assert "DESPUÉS" in out and "3 ciclos" in out
    assert _filas_neurona(db) == 2              # pesos + memoria de examen
    assert len(_respaldos(db)) == 1
    resp = os.path.join(os.path.dirname(db), _respaldos(db)[0])
    assert _filas_neurona(resp) is None         # el respaldo es de ANTES de practicar


def test_sin_respaldo(db):
    assert D.main([db, "--ciclos", "1", "--sin-respaldo"]) == 0
    assert _respaldos(db) == []


def test_olvidar_pide_confirmacion_y_borra(db, capsys):
    assert D.main([db, "--ciclos", "2", "--sin-respaldo"]) == 0
    assert D.main([db, "--olvidar"]) == 1       # sin --si no borra
    assert _filas_neurona(db) == 2
    assert D.main([db, "--olvidar", "--si", "--sin-respaldo"]) == 0
    assert _filas_neurona(db) == 0
    assert "fórmula a mano" in capsys.readouterr().out


def test_rechaza_snapshot_congelado_y_db_inexistente(tmp_path, capsys):
    snap = os.path.join(RAIZ, "snapshots", "qa_escape_qcr_20260811.db")
    if os.path.isfile(snap):
        assert D.main([snap, "--estado"]) == 1
        assert "snapshot congelado" in capsys.readouterr().out
    assert D.main([str(tmp_path / "no_existe.db")]) == 1


def test_neurona_apagada_no_corre(db, monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    assert D.main([db, "--ciclos", "1", "--sin-respaldo"]) == 1
    assert _filas_neurona(db) is None
