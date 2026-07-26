#!/usr/bin/env python3
"""
Backfill de predicados SRL para todos los nodos de BioRAG.
Extrae predicados {sujeto, accion, objeto, contexto} del contenido de cada nodo
y los almacena en la tabla predicados.

Usa el extractor SRL existente + extracción ampliada de keywords como fallback.
"""
import sqlite3
import re
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.srl_extractor import extraer_predicados_determinista, extraerte_normalizado

def extraer_keywords_tecnicos(texto: str) -> list[str]:
    """Extrae keywords técnicos relevantes del contenido.
    Más amplio que el SRL extractor — captura sustantivos técnicos,
    no solo verbos canónicos."""
    if not texto:
        return []
    
    texto_norm = extraerte_normalizado(texto)
    # Stopwords básicas
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
        'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'as', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
        'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
        'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
        'don', 'now', 'and', 'but', 'or', 'if', 'while', 'that', 'this',
        'these', 'those', 'what', 'which', 'who', 'whom', 'whose',
        # Español
        'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'pero',
        'si', 'no', 'de', 'del', 'al', 'en', 'por', 'para', 'con', 'sin',
        'sobre', 'entre', 'hasta', 'desde', 'como', 'mas', 'que', 'es', 'son',
        'fue', 'ser', 'estar', 'hay', 'tiene', 'tienen', 'hacer', 'hecho',
        'puede', 'pueden', 'dicho', 'todo', 'toda', 'todos', 'todas', 'otro',
        'otra', 'otros', 'otras', 'este', 'esta', 'estos', 'estas', 'ese',
        'esa', 'esos', 'esas', 'aquel', 'aquella', 'aquellos', 'aquellas',
        'muy', 'mucho', 'poco', 'más', 'menos', 'tan', 'también', 'donde',
        'cuando', 'como', 'porque', 'aunque', 'sino', 'ni', 'e', 'u',
    }
    
    # Extraer palabras de4+ caracteres
    words = re.findall(r'\w{4,}', texto_norm)
    keywords = []
    seen = set()
    for w in words:
        w_lower = w.lower()
        if w_lower not in stopwords and w_lower not in seen and len(w_lower) >= 4:
            seen.add(w_lower)
            keywords.append(w_lower)
    
    return keywords[:50]  # Top50 keywords — más cobertura para queries específicas

def backfill_predicados(db_path: str, dry_run: bool = False):
    """Extrae predicados de todos los nodos y los inserta en la tabla."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Contar nodos actuales
    total = c.execute('SELECT COUNT(*) FROM largo_plazo').fetchone()[0]
    with_preds = c.execute('SELECT COUNT(DISTINCT concepto) FROM predicados').fetchone()[0]
    print(f'Total nodos: {total}')
    print(f'Nodos con predicados: {with_preds} ({with_preds/total*100:.1f}%)')
    print(f'Nodos sin predicados: {total - with_preds}')
    print()
    
    # Obtener TODOS los nodos (el script agrega keyword predicates a todos)
    c.execute('''
        SELECT l.concepto, l.contenido, l.sinonimos
        FROM largo_plazo l
    ''')
    nodos = c.fetchall()
    print(f'Procesando {len(nodos)} nodos...')
    
    if dry_run:
        print('[DRY RUN] No se insertarán predicados')
        # Mostrar ejemplo
        for concepto, contenido, sinonimos in nodos[:3]:
            preds_srl = extraer_predicados_determinista(contenido or '')
            keywords = extraer_keywords_tecnicos(contenido or '')
            print(f'  {concepto}:')
            print(f'    SRL: {len(preds_srl)} predicados')
            print(f'    Keywords: {keywords[:5]}')
        return
    
    # Eliminar keyword predicates existentes para re-insertarlos
    c.execute('DELETE FROM predicados WHERE sujeto = \"\" AND accion = \"\" AND objeto = \"\"')
    deleted = c.rowcount
    print(f'Eliminados {deleted} keyword predicates anteriores')
    
    # Insertar predicados
    inserted = 0
    start = time.time()
    
    for concepto, contenido, sinonimos in nodos:
        texto = f"{concepto} {contenido or ''} {sinonimos or ''}"
        
        #1. SRL extractor (narrative verbs)
        preds_srl = extraer_predicados_determinista(contenido or '')
        
        #2. Keywords como predicados adicionales
        keywords = extraer_keywords_tecnicos(texto)
        
        # Insertar SRL predicates
        for pred in preds_srl:
            c.execute(
                "INSERT OR IGNORE INTO predicados (concepto, sujeto, accion, objeto, contexto, creado_en) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (concepto, pred.get('sujeto', ''), pred.get('accion', ''),
                 pred.get('objeto', ''), pred.get('contexto', ''), time.time())
            )
        
        # Insertar keyword predicates (como "contexto" del nodo)
        if keywords:
            # Crear un predicado que capture los keywords principales
            keywords_str = ','.join(keywords[:50])
            c.execute(
                "INSERT OR IGNORE INTO predicados (concepto, sujeto, accion, objeto, contexto, creado_en) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (concepto, '', '', '', keywords_str, time.time())
            )
        
        inserted += 1
        if inserted % 100 == 0:
            print(f'  Procesados: {inserted}/{len(nodos)}')
    
    conn.commit()
    elapsed = time.time() - start
    
    # Verificar
    new_with_preds = c.execute('SELECT COUNT(DISTINCT concepto) FROM predicados').fetchone()[0]
    total_preds = c.execute('SELECT COUNT(*) FROM predicados').fetchone()[0]
    
    print(f'\\nCompletado en {elapsed:.1f}s')
    print(f'Nodos con predicados: {new_with_preds}/{total} ({new_with_preds/total*100:.1f}%)')
    print(f'Total predicados: {total_preds}')
    print(f'Nuevos nodos con predicados: {new_with_preds - with_preds}')
    
    conn.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Backfill predicados SRL')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar, no insertar')
    parser.add_argument('--db', default='MemoryBioRAG_Data/memory_biorag.db', help='Path a la DB')
    args = parser.parse_args()
    
    backfill_predicados(args.db, dry_run=args.dry_run)
