#!/usr/bin/env python3
"""Side-by-side DB-API/SQLite exception probe on synthetic databases only."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sqlite3 as std_sqlite
import tempfile
import pysqlite3 as py_sqlite


def one(driver, root: Path) -> dict:
    cases = {}
    def capture(name, fn):
        try:
            cases[name] = {'result': fn()}
        except BaseException as exc:
            cases[name] = {
                'exception_type': type(exc).__name__,
                'is_database_error': isinstance(exc, driver.DatabaseError),
                'is_operational_error': isinstance(exc, driver.OperationalError),
                'message': str(exc),
                'sqlite_errorcode': getattr(exc, 'sqlite_errorcode', None),
                'sqlite_errorname': getattr(exc, 'sqlite_errorname', None),
            }

    capture('malformed_sql', lambda: driver.connect(':memory:').execute('SELEC 1').fetchall())
    capture('missing_table', lambda: driver.connect(':memory:').execute('SELECT * FROM no_such_synthetic_table').fetchall())
    capture('wrong_bind_count', lambda: driver.connect(':memory:').execute('SELECT ?', ()).fetchall())
    capture('unknown_function', lambda: driver.connect(':memory:').execute('SELECT synthetic_unknown_function(1)').fetchall())
    capture('bad_builtin_arity', lambda: driver.connect(':memory:').execute("SELECT substr('abc')").fetchall())

    def unique_violation():
        con = driver.connect(':memory:')
        con.execute('CREATE TABLE t(x INTEGER UNIQUE)')
        con.execute('INSERT INTO t VALUES (1)')
        try:
            con.execute('INSERT INTO t VALUES (1)')
        except BaseException as exc:
            return {'type': type(exc).__name__, 'message': str(exc),
                    'errorcode': getattr(exc, 'sqlite_errorcode', None),
                    'errorname': getattr(exc, 'sqlite_errorname', None),
                    'in_transaction_after': con.in_transaction}
        finally:
            con.close()
    capture('unique_violation', unique_violation)

    def check_violation():
        con = driver.connect(':memory:')
        con.execute('CREATE TABLE t(x INTEGER CHECK(x > 0))')
        try:
            con.execute('INSERT INTO t VALUES (0)')
        except BaseException as exc:
            return {'type': type(exc).__name__, 'message': str(exc),
                    'errorcode': getattr(exc, 'sqlite_errorcode', None),
                    'errorname': getattr(exc, 'sqlite_errorname', None),
                    'in_transaction_after': con.in_transaction}
        finally:
            con.close()
    capture('check_violation', check_violation)

    def foreign_key_violation():
        con = driver.connect(':memory:')
        con.execute('PRAGMA foreign_keys=ON')
        con.executescript('CREATE TABLE p(id INTEGER PRIMARY KEY); CREATE TABLE c(pid INTEGER REFERENCES p(id));')
        try:
            con.execute('INSERT INTO c VALUES (7)')
        except BaseException as exc:
            return {'type': type(exc).__name__, 'message': str(exc),
                    'errorcode': getattr(exc, 'sqlite_errorcode', None),
                    'errorname': getattr(exc, 'sqlite_errorname', None),
                    'in_transaction_after': con.in_transaction}
        finally:
            con.close()
    capture('foreign_key_violation', foreign_key_violation)

    def fts_invalid_query():
        con = driver.connect(':memory:')
        con.execute('CREATE VIRTUAL TABLE f USING fts5(content)')
        con.execute('INSERT INTO f VALUES (?)', ('synthetic text',))
        try:
            con.execute('SELECT rowid FROM f WHERE f MATCH ?', ('"unterminated',)).fetchall()
        except BaseException as exc:
            return {'type': type(exc).__name__, 'message': str(exc),
                    'errorcode': getattr(exc, 'sqlite_errorcode', None),
                    'errorname': getattr(exc, 'sqlite_errorname', None)}
        finally:
            con.close()
    capture('fts_invalid_query', fts_invalid_query)

    def authorizer_denial():
        con = driver.connect(':memory:')
        con.execute('CREATE TABLE t(x)')
        con.set_authorizer(lambda action, *args: driver.SQLITE_DENY if action == driver.SQLITE_INSERT else driver.SQLITE_OK)
        try:
            con.execute('INSERT INTO t VALUES (1)')
        except BaseException as exc:
            return {'type': type(exc).__name__, 'message': str(exc),
                    'errorcode': getattr(exc, 'sqlite_errorcode', None),
                    'errorname': getattr(exc, 'sqlite_errorname', None)}
        finally:
            con.close()
    capture('authorizer_denial', authorizer_denial)

    def readonly_write():
        path = root / f'{driver.__name__}_readonly.db'
        con = driver.connect(str(path)); con.execute('CREATE TABLE t(x)'); con.close()
        ro = driver.connect(f'file:{path}?mode=ro', uri=True)
        try:
            ro.execute('INSERT INTO t VALUES (1)')
        except BaseException as exc:
            return {'type': type(exc).__name__, 'message': str(exc),
                    'errorcode': getattr(exc, 'sqlite_errorcode', None),
                    'errorname': getattr(exc, 'sqlite_errorname', None)}
        finally:
            ro.close()
    capture('readonly_write', readonly_write)

    def fts_and_scalar_results():
        con = driver.connect(':memory:')
        con.execute('CREATE VIRTUAL TABLE f USING fts5(content)')
        con.executemany('INSERT INTO f(content) VALUES (?)', [('alpha café',), ('beta synthetic',)])
        rows = con.execute('SELECT rowid, content FROM f WHERE f MATCH ? ORDER BY rowid', ('alpha',)).fetchall()
        scalar = con.execute("SELECT typeof(NULL), NULL IS NULL, 'café', 2.0/1.0").fetchone()
        description = [tuple(item) for item in con.execute('SELECT 1 AS one').description]
        return {'fts_rows': rows, 'scalar': scalar, 'description': description,
                'total_changes': con.total_changes, 'in_transaction': con.in_transaction}
    capture('fts_and_scalar_results', fts_and_scalar_results)

    def shared_connection_concurrency():
        from concurrent.futures import ThreadPoolExecutor
        con = driver.connect(':memory:', check_same_thread=False, isolation_level=None, timeout=10)
        con.execute('CREATE TABLE writes(worker INTEGER, item INTEGER)')
        def worker(worker_id):
            cur = con.cursor()
            try:
                for item in range(200):
                    cur.execute('INSERT INTO writes VALUES (?, ?)', (worker_id, item))
            finally:
                cur.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(worker, range(8)))
        result = {'row_count': con.execute('SELECT COUNT(*) FROM writes').fetchone()[0],
                  'distinct_keys': con.execute('SELECT COUNT(DISTINCT worker || \'/\' || item) FROM writes').fetchone()[0],
                  'in_transaction': con.in_transaction}
        con.close()
        return result
    capture('shared_connection_concurrency', shared_connection_concurrency)

    probe = driver.connect(':memory:')
    compile_options = sorted(row[0] for row in probe.execute('PRAGMA compile_options'))
    probe.close()
    return {'module': driver.__name__, 'module_file': driver.__file__,
            'python_dbapi_version': getattr(driver, 'version', None),
            'sqlite_version': driver.sqlite_version, 'sqlite_version_info': driver.sqlite_version_info,
            'threadsafety': driver.threadsafety, 'paramstyle': driver.paramstyle,
            'threadsafe_compile_options': [x for x in compile_options if x.startswith('THREADSAFE=')],
            'compile_options_fts5': any(x == 'ENABLE_FTS5' for x in compile_options), 'cases': cases}

with tempfile.TemporaryDirectory(prefix='sqlite_compat_synthetic_') as temp:
    root = Path(temp)
    out = {'synthetic_only': True, 'standard': one(std_sqlite, root), 'candidate': one(py_sqlite, root)}
    diffs = {}
    for name in out['standard']['cases']:
        a, b = out['standard']['cases'][name], out['candidate']['cases'][name]
        if a != b:
            diffs[name] = {'standard': a, 'candidate': b}
    out['case_result_differences'] = diffs
    exception_contracts = {}
    for name in ('unique_violation', 'check_violation', 'foreign_key_violation'):
        left = out['standard']['cases'][name]['result']
        right = out['candidate']['cases'][name]['result']
        exception_contracts[name] = {
            'same_exception_class': left['type'] == right['type'],
            'same_message': left['message'] == right['message'],
            'same_transaction_state': left['in_transaction_after'] == right['in_transaction_after'],
            'same_primary_code': (left['errorcode'] & 0xff) == (right['errorcode'] & 0xff),
            'primary_code': left['errorcode'] & 0xff,
            'extended_error_metadata_differs': (
                left['errorcode'] != right['errorcode'] or left['errorname'] != right['errorname']
            ),
        }
    exact_other_results = all(
        out['standard']['cases'][name] == out['candidate']['cases'][name]
        for name in out['standard']['cases']
        if name not in ('unique_violation', 'check_violation', 'foreign_key_violation')
    )
    out['normalized_compatibility'] = {
        'constraint_exception_contracts': exception_contracts,
        'all_non_constraint_cases_exactly_equal': exact_other_results,
        'shared_connection_stress_exactly_equal': (
            out['standard']['cases']['shared_connection_concurrency']
            == out['candidate']['cases']['shared_connection_concurrency']
        ),
    }
    out['module_differences'] = {
        'sqlite_version': [out['standard']['sqlite_version'], out['candidate']['sqlite_version']],
        'python_dbapi_version': [out['standard']['python_dbapi_version'], out['candidate']['python_dbapi_version']],
        'threadsafety': [out['standard']['threadsafety'], out['candidate']['threadsafety']],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
