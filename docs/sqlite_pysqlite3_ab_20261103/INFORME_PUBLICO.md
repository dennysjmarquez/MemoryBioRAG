# Comparación sintética: SQLite estándar y pysqlite3 0.6.1

## Alcance y revisión exacta

La suite se ejecutó contra el código BioRAG en el commit **`212ca78c5fbcc4915bd7e2080a4c9eb117b5550d`** (rama `arena/9a54babb-memorybiorag`). Se compararon dos copias aisladas del código, con el mismo Python 3.11.2, pytest 9.1.1 y dependencias de proyecto; la única diferencia en las copias fue sustituir las importaciones `sqlite3` del candidato por `pysqlite3` 0.6.1. El baseline usó SQLite 3.40.1; el candidato SQLite 3.53.4.

No se leyó ni copió ninguna base original. Para ambos brazos se generó y copió byte por byte la misma base sintética, con tres nodos de prueba. Se excluyeron archivos SQLite de los árboles copiados. El probe DB-API también opera únicamente sobre bases sintéticas efímeras.

## Resultado de la suite

| Resultado | SQLite estándar | pysqlite3 0.6.1 |
|---|---:|---:|
| Pasadas | 795 | 795 |
| Fallidas | 13 | 13 |
| Omitidas | 9 | 9 |
| Errores de setup | 7 | 7 |
| Subtests pasados | 2 | 2 |
| Fallos exclusivos de un brazo | 0 | 0 |
| Errores exclusivos de un brazo | 0 | 0 |

Los 13 fallos y 7 errores fueron comunes a ambos brazos y se explican por las limitaciones de la fixture sintética: varios tests de integración requieren nodos, dimensiones, relaciones y scores del snapshot de prueba que no contiene una fixture de tres nodos. No son fallos exclusivos del driver.

La referencia histórica reportada anteriormente (baseline 802 pasadas/9 fallidas/18 omitidas/2 subtests; candidato 797/14/18/2) **no se reprodujo**. No se conservaron el prototipo ni los cinco IDs de fallos históricos exclusivos del candidato, por lo que esta corrida no los atribuye ni confirma que fueran los mismos.

## Probe de compatibilidad

El probe cubre 13 operaciones sintéticas. En tres restricciones —UNIQUE, CHECK y FOREIGN KEY— ambas versiones levantan `IntegrityError`, con el mismo mensaje y estado de transacción; el código primario coincide (`19`), pero SQLite estándar expone el código extendido (`2067`, `275`, `787`) y pysqlite3 el código primario `19`. Los otros diez casos tuvieron resultados idénticos. Ambos reportan FTS5 y `THREADSAFE=1`; el metadato DB-API `threadsafety` difiere (3 en stdlib, 1 en pysqlite3). Una prueba acotada de 8 hilos y 1600 inserciones en una conexión sintética tuvo el mismo resultado en los dos drivers; no constituye garantía general de concurrencia.

## Reproducción

Los scripts junto a este informe son públicos; los resultados completos, logs y JUnit no están incluidos en el commit. No se modificaron código productivo, instalador ni dependencias del proyecto.

1. Cree un entorno temporal con Python 3.11 y las dependencias de pruebas del proyecto; instale `pysqlite3==0.6.1` en un target separado, sin editar archivos de dependencias:

   ```sh
   python3.11 -m pip install --target /tmp/pysqlite3-target pysqlite3==0.6.1
   ```

2. Prepare un checkout del commit exacto bajo prueba y ejecute el runner público desde otro checkout/ubicación:

   ```sh
   git worktree add /tmp/biorag-sqlite-source 212ca78c5fbcc4915bd7e2080a4c9eb117b5550d
   python docs/sqlite_pysqlite3_ab_20261103/run_full_ab.py \
     --source-root /tmp/biorag-sqlite-source \
     --python /ruta/al/python-del-entorno-de-pruebas \
     --pysqlite3-path /tmp/pysqlite3-target
   ```

   El runner escribe stdout/stderr, JUnit, manifests y comparación en un directorio temporal nuevo, o en `--output DIR` si se desea elegirlo. Mantenga esos productos fuera del repositorio.

3. Ejecute el probe independiente:

   ```sh
   PYTHONPATH=/tmp/pysqlite3-target python docs/sqlite_pysqlite3_ab_20261103/sqlite_compat_probe.py
   ```

El reporte público resume los resultados observados en la corrida original; una nueva ejecución puede variar con la plataforma o dependencias instaladas. Para una auditoría que requiera logs/JUnit íntegros, no los suba a este repositorio: pueden compartirse en una carpeta restringida de Google Drive, compartida solo con las personas auditoras autorizadas. Los artefactos privados locales se conservan en `.private_evidence/`.
