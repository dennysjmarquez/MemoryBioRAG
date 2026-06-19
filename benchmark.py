#!/usr/bin/env python3
"""
BioRAG Benchmark Script — Compara BioRAG con LangChain y LlamaIndex.

Métricas:
- Latencia de búsqueda (ms)
- Uso de memoria (MB)
-throughput (queries/segundo)

Uso:
    python3 benchmark.py
"""

import os
import sys
import time
import psutil
import json
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import init_sinapsis_table


def get_memory_mb():
    """Obtiene uso de memoria actual en MB."""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


def benchmark_biorag(n_queries=50, n_nodes=100):
    """Benchmark de BioRAG."""
    print("\n" + "="*60)
    print("BENCHMARK: BioRAG")
    print("="*60)
    
    # Crear DB temporal
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        # Inicializar
        mem_before = get_memory_mb()
        cerebro = SQLiteMemoryBioRAG(db_path=db_path)
        
        # Poblar con nodos de prueba
        print(f"\nPoblando {n_nodes} nodos...")
        for i in range(n_nodes):
            cerebro.percibir_corto_plazo(
                f"concepto_{i}",
                f"Contenido del concepto {i} con palabras de prueba sobre tecnología y desarrollo.",
                f"sinonimo_{i},test_{i}"
            )
        cerebro.ciclo_sueno_consolidacion()
        mem_after_setup = get_memory_mb()
        print(f"Memoria después de setup: {mem_after_setup:.1f} MB")
        
        # Queries de prueba
        queries = [
            "concepto",
            "tecnología",
            "desarrollo",
            "prueba",
            "python",
        ] * (n_queries // 5)
        
        # Benchmark de búsqueda
        print(f"\nEjecutando {n_queries} queries...")
        latencias = []
        memoria_queries = []
        
        for q in queries:
            mem_before_query = get_memory_mb()
            start = time.perf_counter()
            resultados, total = cerebro.buscar_por_frase(q, limite=10)
            end = time.perf_counter()
            latencia_ms = (end - start) * 1000
            latencias.append(latencia_ms)
            memoria_queries.append(get_memory_mb() - mem_before_query)
        
        # Resultados
        avg_latencia = sum(latencias) / len(latencias)
        min_latencia = min(latencias)
        max_latencia = max(latencias)
        mem_final = get_memory_mb()
        
        print(f"\nResultados BioRAG:")
        print(f"  Latencia promedio: {avg_latencia:.2f} ms")
        print(f"  Latencia min: {min_latencia:.2f} ms")
        print(f"  Latencia max: {max_latencia:.2f} ms")
        print(f"  Memoria final: {mem_final:.1f} MB")
        print(f"  Throughput: {1000/avg_latencia:.1f} queries/segundo")
        
        return {
            "sistema": "BioRAG",
            "nodos": n_nodes,
            "queries": n_queries,
            "latencia_avg_ms": round(avg_latencia, 2),
            "latencia_min_ms": round(min_latencia, 2),
            "latencia_max_ms": round(max_latencia, 2),
            "memoria_mb": round(mem_final, 1),
            "throughput_qps": round(1000/avg_latencia, 1),
        }
    finally:
        os.unlink(db_path)


def benchmark_langchain(n_queries=50, n_docs=100):
    """Benchmark de LangChain con SQLite vector store."""
    print("\n" + "="*60)
    print("BENCHMARK: LangChain + SQLite")
    print("="*60)
    
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_community.embeddings import FakeEmbeddings
    except ImportError as e:
        print(f"  Error: No se pudo importar LangChain: {e}")
        return None
    
    try:
        # Usar embeddings fake para no depender de API key
        from langchain.embeddings import FakeEmbeddings
        
        print(f"\nPoblando {n_docs} documentos...")
        mem_before = get_memory_mb()
        
        # Crear documentos de prueba
        docs = []
        for i in range(n_docs):
            from langchain_core.documents import Document
            docs.append(Document(
                page_content=f"Contenido del documento {i} con palabras de prueba sobre tecnología y desarrollo.",
                metadata={"id": i}
            ))
        
        # Crear vector store (usando embeddings fake para no depender de API key)
        embeddings = FakeEmbeddings(size=768)
        vectorstore = FAISS.from_documents(docs, embeddings)
        
        mem_after_setup = get_memory_mb()
        print(f"Memoria después de setup: {mem_after_setup:.1f} MB")
        
        # Queries de prueba
        queries = [
            "concepto",
            "tecnología",
            "desarrollo",
            "prueba",
            "python",
        ] * (n_queries // 5)
        
        # Benchmark de búsqueda
        print(f"\nEjecutando {n_queries} queries...")
        latencias = []
        
        for q in queries:
            start = time.perf_counter()
            resultados = vectorstore.similarity_search(q, k=10)
            end = time.perf_counter()
            latencia_ms = (end - start) * 1000
            latencias.append(latencia_ms)
        
        # Resultados
        avg_latencia = sum(latencias) / len(latencias)
        min_latencia = min(latencias)
        max_latencia = max(latencias)
        mem_final = get_memory_mb()
        
        print(f"\nResultados LangChain:")
        print(f"  Latencia promedio: {avg_latencia:.2f} ms")
        print(f"  Latencia min: {min_latencia:.2f} ms")
        print(f"  Latencia max: {max_latencia:.2f} ms")
        print(f"  Memoria final: {mem_final:.1f} MB")
        print(f"  Throughput: {1000/avg_latencia:.1f} queries/segundo")
        
        return {
            "sistema": "LangChain+FAISS",
            "nodos": n_docs,
            "queries": n_queries,
            "latencia_avg_ms": round(avg_latencia, 2),
            "latencia_min_ms": round(min_latencia, 2),
            "latencia_max_ms": round(max_latencia, 2),
            "memoria_mb": round(mem_final, 1),
            "throughput_qps": round(1000/avg_latencia, 1),
        }
    except Exception as e:
        print(f"  Error en benchmark LangChain: {e}")
        return None


def benchmark_langchain_sequential(n_queries=50, n_docs=100):
    """Benchmark de LangChain con Chroma vector store (más realista)."""
    print("\n" + "="*60)
    print("BENCHMARK: LangChain + Chroma (In-Memory)")
    print("="*60)
    
    try:
        import chromadb
        from langchain_community.vectorstores import Chroma
        from langchain_community.embeddings import FakeEmbeddings
        
        print(f"\nPoblando {n_docs} documentos...")
        mem_before = get_memory_mb()
        
        # Crear documentos de prueba
        docs = []
        for i in range(n_docs):
            from langchain_core.documents import Document
            docs.append(Document(
                page_content=f"Contenido del documento {i} con palabras de prueba sobre tecnología y desarrollo.",
                metadata={"id": i}
            ))
        
        # Crear vector store en memoria
        embeddings = FakeEmbeddings(size=768)
        vectorstore = Chroma.from_documents(docs, embeddings, persist_directory=None)
        
        mem_after_setup = get_memory_mb()
        print(f"Memoria después de setup: {mem_after_setup:.1f} MB")
        
        # Queries de prueba
        queries = [
            "concepto",
            "tecnología",
            "desarrollo",
            "prueba",
            "python",
        ] * (n_queries // 5)
        
        # Benchmark de búsqueda
        print(f"\nEjecutando {n_queries} queries...")
        latencias = []
        
        for q in queries:
            start = time.perf_counter()
            resultados = vectorstore.similarity_search(q, k=10)
            end = time.perf_counter()
            latencia_ms = (end - start) * 1000
            latencias.append(latencia_ms)
        
        # Resultados
        avg_latencia = sum(latencias) / len(latencias)
        min_latencia = min(latencias)
        max_latencia = max(latencias)
        mem_final = get_memory_mb()
        
        print(f"\nResultados LangChain+Chroma:")
        print(f"  Latencia promedio: {avg_latencia:.2f} ms")
        print(f"  Latencia min: {min_latencia:.2f} ms")
        print(f"  Latencia max: {max_latencia:.2f} ms")
        print(f"  Memoria final: {mem_final:.1f} MB")
        print(f"  Throughput: {1000/avg_latencia:.1f} queries/segundo")
        
        return {
            "sistema": "LangChain+Chroma",
            "nodos": n_docs,
            "queries": n_queries,
            "latencia_avg_ms": round(avg_latencia, 2),
            "latencia_min_ms": round(min_latencia, 2),
            "latencia_max_ms": round(max_latencia, 2),
            "memoria_mb": round(mem_final, 1),
            "throughput_qps": round(1000/avg_latencia, 1),
        }
    except ImportError as e:
        print(f"  Error: Chroma no instalado: {e}")
        return None
    except Exception as e:
        print(f"  Error en benchmark: {e}")
        return None


def main():
    print("="*60)
    print("BioRAG BENCHMARK SUITE v1.0")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Configuración
    N_NODES = 100
    N_QUERIES = 50
    
    resultados = []
    
    # 1. BioRAG
    resultado_biorag = benchmark_biorag(n_queries=N_QUERIES, n_nodes=N_NODES)
    if resultado_biorag:
        resultados.append(resultado_biorag)
    
    # 2. LangChain + FAISS
    resultado_langchain = benchmark_langchain(n_queries=N_QUERIES, n_docs=N_NODES)
    if resultado_langchain:
        resultados.append(resultado_langchain)
    
    # 3. LangChain + Chroma
    resultado_chroma = benchmark_langchain_sequential(n_queries=N_QUERIES, n_docs=N_NODES)
    if resultado_chroma:
        resultados.append(resultado_chroma)
    
    # Resumen comparativo
    if len(resultados) > 1:
        print("\n" + "="*60)
        print("RESUMEN COMPARATIVO")
        print("="*60)
        print(f"\n{'Sistema':<20} {'Latencia avg':<15} {'Memoria':<12} {'Throughput':<15}")
        print("-" * 60)
        for r in resultados:
            print(f"{r['sistema']:<20} {r['latencia_avg_ms']:<15} {r['memoria_mb']:<12} {r['throughput_qps']:<15}")
        
        # Guardar resultados
        output_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "benchmark_results.json"
        )
        with open(output_file, 'w') as f:
            json.dump({
                "fecha": datetime.now().isoformat(),
                "config": {"n_nodes": N_NODES, "n_queries": N_QUERIES},
                "resultados": resultados,
            }, f, indent=2)
        print(f"\nResultados guardados en: {output_file}")
    else:
        print("\nNo hay suficientes resultados para comparar.")
    
    print("\n" + "="*60)
    print("BENCHMARK COMPLETADO")
    print("="*60)


if __name__ == "__main__":
    main()
