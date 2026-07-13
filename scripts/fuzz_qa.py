#!/usr/bin/env python3
import sys
import os
import shutil
import time
import json
import sqlite3
import traceback
from datetime import date

# Agregar el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Rutas de base de datos
PROD_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "MemoryBioRAG_Data", "memory_biorag.db")
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "MemoryBioRAG_Data", "obsolete_and_debug")
os.makedirs(TEMP_DIR, exist_ok=True)
FUZZ_DB = os.path.join(TEMP_DIR, "memory_biorag_fuzz_temp.db")

# Configurar variable de entorno para forzar a mcp_server a usar la base de datos de fuzzing
os.environ["BIORAG_PATH"] = FUZZ_DB

# Importar funciones de mcp_server después de configurar la variable de entorno
try:
    from mcp_server import _build_server
except ImportError as e:
    print(f"Error al importar mcp_server: {e}")
    sys.exit(1)

def contar_nodos(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM largo_plazo")
    cnt = c.fetchone()[0]
    conn.close()
    return cnt

def ejecutar_fuzz_tests():
    print("==================================================")
    print("INICIANDO FASE 2A: Pruebas de Fuzzing / Adversariales")
    print("==================================================")
    
    if not os.path.exists(PROD_DB):
        print(f"ERROR: No se encuentra la base de datos de producción en: {PROD_DB}")
        sys.exit(1)
        
    print(f"Copiando base de datos activa a: {FUZZ_DB}")
    shutil.copy2(PROD_DB, FUZZ_DB)
    
    # Inicializar FastMCP
    mcp = _build_server()
    biorag_recordar = mcp._tool_manager.get_tool("recordar").fn
    
    nodos_iniciales = contar_nodos(FUZZ_DB)
    print(f"Nodos iniciales en la base de datos de prueba: {nodos_iniciales}\n")
    
    # Casos de prueba
    casos = [
        # 1. Vacío y casi vacío
        {"cat": "1. Vacío y casi vacío", "name": "String vacío", "params": {"query": "", "parafrasis": "a,b"}},
        {"cat": "1. Vacío y casi vacío", "name": "Solo espacios", "params": {"query": "    ", "parafrasis": "a,b"}},
        {"cat": "1. Vacío y casi vacío", "name": "Un solo carácter", "params": {"query": "x", "parafrasis": "a,b"}},
        
        # 2. Extremadamente largo
        {"cat": "2. Extremadamente largo", "name": "Query de 60,000 caracteres", "params": {"query": "A" * 60000, "parafrasis": "a,b"}},
        {"cat": "2. Extremadamente largo", "name": "Paráfrasis de 20,000 caracteres", "params": {"query": "test", "parafrasis": "x" * 20000}},
        
        # 3. Comillas sin cerrar o desbalanceadas
        {"cat": "3. Comillas desbalanceadas", "name": "Una comilla doble abierta", "params": {"query": '"CV sin cerrar', "parafrasis": "a,b"}},
        {"cat": "3. Comillas desbalanceadas", "name": "Comillas múltiples vacías", "params": {"query": '""""', "parafrasis": "a,b"}},
        {"cat": "3. Comillas desbalanceadas", "name": "Comillas anidadas extrañas", "params": {"query": '"a "b" c"', "parafrasis": "a,b"}},
        
        # 4. Caracteres de control y bytes nulos
        {"cat": "4. Caracteres de control", "name": "Byte nulo en query", "params": {"query": "error\x00sistema", "parafrasis": "a,b"}},
        {"cat": "4. Caracteres de control", "name": "Saltos de línea múltiples", "params": {"query": "\n\n\n\nquery\r\n\t", "parafrasis": "a,b"}},
        
        # 5. Caracteres especiales de SQL
        {"cat": "5. Caracteres SQL", "name": "Inyección SQL clásica", "params": {"query": "'; DROP TABLE largo_plazo; --", "parafrasis": "a,b"}},
        {"cat": "5. Caracteres SQL", "name": "Comilla simple suelta", "params": {"query": "'", "parafrasis": "a,b"}},
        {"cat": "5. Caracteres SQL", "name": "Comodines de LIKE", "params": {"query": "%%__%%", "parafrasis": "a,b"}},
        {"cat": "5. Caracteres SQL", "name": "Or condition injection", "params": {"query": "' OR '1'='1", "parafrasis": "a,b"}},
        
        # 6. Unicode raro
        {"cat": "6. Unicode raro", "name": "Emojis y símbolos", "params": {"query": "🧠 🤖 💥 🔥", "parafrasis": "a,b"}},
        {"cat": "6. Unicode raro", "name": "Árabe y Chino", "params": {"query": "البحث 搜索内存", "parafrasis": "a,b"}},
        {"cat": "6. Unicode raro", "name": "Zero-width space", "params": {"query": "texto\u200Boculto", "parafrasis": "a,b"}},
        {"cat": "6. Unicode raro", "name": "Zalgo text", "params": {"query": "t̃êṣṭịṇng̣", "parafrasis": "a,b"}},
        
        # 7. JSON malformado en dimensiones
        {"cat": "7. JSON dimensiones malformado", "name": "JSON desbalanceado", "params": {"query": "test", "parafrasis": "a,b", "dimensiones": '{"entidad": ["identidad_artificial"'}},
        {"cat": "7. JSON dimensiones malformado", "name": "JSON tipo incorrecto (string)", "params": {"query": "test", "parafrasis": "a,b", "dimensiones": '"just a string"'}},
        {"cat": "7. JSON dimensiones malformado", "name": "JSON array vacío", "params": {"query": "test", "parafrasis": "a,b", "dimensiones": "[]"}},
        {"cat": "7. JSON dimensiones malformado", "name": "JSON valor no array", "params": {"query": "test", "parafrasis": "a,b", "dimensiones": '{"entidad": "no_array"}'}},
        {"cat": "7. JSON dimensiones malformado", "name": "JSON anidamiento excesivo", "params": {"query": "test", "parafrasis": "a,b", "dimensiones": '{"eje": [{"anidado": {"mas": "objeto"}}]}'}},
        
        # 8. Parámetros numéricos fuera de rango
        {"cat": "8. Números fuera de rango", "name": "Página negativa", "params": {"query": "test", "parafrasis": "a,b", "pagina": -1}},
        {"cat": "8. Números fuera de rango", "name": "Página gigante", "params": {"query": "test", "parafrasis": "a,b", "pagina": 999999999}},
        {"cat": "8. Números fuera de rango", "name": "Límite cero", "params": {"query": "test", "parafrasis": "a,b", "limite": 0}},
        {"cat": "8. Números fuera de rango", "name": "Límite negativo", "params": {"query": "test", "parafrasis": "a,b", "limite": -5}},
        {"cat": "8. Números fuera de rango", "name": "context_window excesiva", "params": {"query": "test", "parafrasis": "a,b", "context_window": 100}},
        {"cat": "8. Números fuera de rango", "name": "context_window negativa", "params": {"query": "test", "parafrasis": "a,b", "context_window": -1}},
        
        # 9. rafaga_palabras y parafrasis malformados
        {"cat": "9. Parámetros lista malformados", "name": "Comas consecutivas en parafrasis", "params": {"query": "test", "parafrasis": "a,,,b"}},
        {"cat": "9. Parámetros lista malformados", "name": "Solo comas en parafrasis", "params": {"query": "test", "parafrasis": ",,,"}},
        {"cat": "9. Parámetros lista malformados", "name": "rafaga_palabras vacío", "params": {"query": "test", "parafrasis": "a,b", "forzar_rafaga": True, "rafaga_palabras": ""}},
        
        # 10. Mezcla de todo
        {"cat": "10. Mezcla de fallos", "name": "SQL injection + Byte nulo + Zalgo + JSON dañado", "params": {
            "query": "'; DROP TABLE largo_plazo; --\x00t̃êṣṭịṇng̣",
            "parafrasis": ",,,",
            "dias": -1,
            "dimensiones": '{"entidad": ["no_array"'
        }},
    ]
    
    reporte = []
    exitos = 0
    fallos = 0
    
    for idx, caso in enumerate(casos, 1):
        nombre_completo = f"[{caso['cat']}] {caso['name']}"
        print(f"Ejecutando Caso {idx}/{len(casos)}: {nombre_completo}")
        
        start_time = time.time()
        excepcion = None
        duracion = 0.0
        resultado_str = ""
        
        try:
            # Llamamos a biorag_recordar con control de timeout simulado a nivel de test
            # (las tools de mcp son funciones sincronas en su llamada de ejecución final)
            resultado_str = biorag_recordar(**caso["params"])
            duracion = time.time() - start_time
        except BaseException as e:
            duracion = time.time() - start_time
            excepcion = e
            
        nodos_actuales = contar_nodos(FUZZ_DB)
        diferencia_nodos = nodos_actuales - nodos_iniciales
        
        # Validar criterios de aprobación
        aprobado = True
        motivo_fallo = []
        
        if excepcion is not None:
            aprobado = False
            motivo_fallo.append(f"Lanzó excepción no controlada: {type(excepcion).__name__}: {excepcion}")
            # Guardar el traceback para el reporte
            tb_str = "".join(traceback.format_exception(type(excepcion), excepcion, excepcion.__traceback__))
        else:
            tb_str = ""
            
        if duracion > 5.0:
            aprobado = False
            motivo_fallo.append(f"Excedió el timeout de 5s: tardó {duracion:.2f}s")
            
        if diferencia_nodos != 0:
            aprobado = False
            motivo_fallo.append(f"Se modificó la base de datos: nodos cambiaron en {diferencia_nodos}")
            
        # Si el resultado es un JSON de error controlado, sigue estando aprobado (es el comportamiento deseado)
        es_json_error = False
        if resultado_str:
            try:
                res_obj = json.loads(resultado_str)
                if isinstance(res_obj, dict) and (res_obj.get("status") == "error" or "error" in res_obj.get("mensaje", "").lower()):
                    es_json_error = True
            except:
                pass
                
        status_str = "APROBADO" if aprobado else "FALLIDO"
        if aprobado:
            exitos += 1
            print(f"  -> {status_str} (tardó {duracion:.4f}s) {'[Retornó Error Controlado]' if es_json_error else ''}")
        else:
            fallos += 1
            print(f"  -> {status_str}: {', '.join(motivo_fallo)}")
            if tb_str:
                print(f"Traceback:\n{tb_str}")
                
        reporte.append({
            "idx": idx,
            "categoria": caso["cat"],
            "nombre": caso["name"],
            "parametros": caso["params"],
            "aprobado": aprobado,
            "duracion": duracion,
            "motivo_fallo": ", ".join(motivo_fallo) if motivo_fallo else "Ninguno (Comportamiento correcto)",
            "retorno": (resultado_str[:200] + "...") if resultado_str else "N/A",
            "traceback": tb_str
        })
        print("-" * 50)
        
    # Limpieza de la base de datos de fuzzing
    if os.path.exists(FUZZ_DB):
        os.remove(FUZZ_DB)
        print("Base de datos temporal de fuzzing borrada exitosamente.")
        
    print("\n==================================================")
    print("FIN DE PRUEBAS DE FUZZING")
    print(f"Total casos: {len(casos)} | Exitos: {exitos} | Fallos: {fallos}")
    print("==================================================")
    
    # Escribir reporte Markdown
    reporte_md_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "fuzz_report.md")
    with open(reporte_md_path, "w", encoding="utf-8") as f:
        f.write("# Reporte de Fuzzing / Pruebas Adversariales (Fase 2A)\n\n")
        f.write(f"- **Fecha de ejecución:** {date.today().isoformat()}\n")
        f.write(f"- **Total de casos evaluados:** {len(casos)}\n")
        f.write(f"- **Casos Aprobados:** {exitos}\n")
        f.write(f"- **Casos Fallidos:** {fallos}\n\n")
        
        f.write("## Tabla Resumen de Resultados\n\n")
        f.write("| # | Categoría | Caso de Prueba | Estado | Duración | Motivo de Fallo |\n")
        f.write("|---|-----------|----------------|--------|----------|-----------------|\n")
        for r in reporte:
            status_emoji = "✅ APROBADO" if r["aprobado"] else "❌ FALLIDO"
            f.write(f"| {r['idx']} | {r['categoria']} | {r['nombre']} | {status_emoji} | {r['duracion']:.4f}s | {r['motivo_fallo']} |\n")
            
        f.write("\n## Detalle de Casos Fallidos e Incidentes\n\n")
        if fallos == 0:
            f.write("No se detectaron fallos. El sistema manejó correctamente todas las entradas adversariales sin tracebacks no controlados, sin mutaciones de estado y dentro de los límites de tiempo.\n")
        else:
            for r in reporte:
                if not r["aprobado"]:
                    f.write(f"### Caso {r['idx']}: {r['categoria']} - {r['nombre']}\n")
                    f.write(f"- **Parámetros:** `{json.dumps(r['parametros'])}`\n")
                    f.write(f"- **Error:** {r['motivo_fallo']}\n")
                    if r["traceback"]:
                        f.write(f"```python\n{r['traceback']}```\n")
                    f.write("\n")
                    
    print(f"Reporte escrito en: {reporte_md_path}")

if __name__ == "__main__":
    ejecutar_fuzz_tests()
