#!/usr/bin/env python3
"""Auto-save script for biorag-remember plugin.

Called by the plugin via child_process to save context to BioRAG
without requiring the AI to explicitly call the MCP tool.

Usage:
  python3 auto_save_plugin.py <agente> [resumen]
"""

import json
import os
import sys
import time

# Add the project root to the path
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "message": "Usage: auto_save_plugin.py <agente> [resumen]"}))
        sys.exit(1)

    agente = sys.argv[1]
    resumen = sys.argv[2] if len(sys.argv) > 2 else ""

    try:
        # Import BioRAG modules
        from core.memory_store import SQLiteMemoryBioRAG
        from middleware.auto_guardado import registrar_accion
        
        # Initialize the brain
        cerebro = SQLiteMemoryBioRAG()
        
        try:
            # Register the action
            registrar_accion("fin", f"[{agente}] {resumen}")
            
            # Generate unique concept with timestamp
            timestamp = int(time.time())
            concepto = f"auto_save_{agente}_{timestamp}"
            
            # Save directly to short-term memory (bypass duplicate check)
            contenido = resumen if resumen else f"Auto-save from {agente} at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            cerebro.percibir_corto_plazo(
                concepto=concepto,
                contenido=contenido[:1200].strip(),
                sinonimos=f"auto-save,{agente}",
                categoria="General",
            )
            
            msg = f"Auto-guardado: '{concepto}'"
            
            print(json.dumps({
                "status": "ok",
                "message": msg,
                "auto_saved": {"concepto": concepto, "categoria": "General"},
            }))
            
        finally:
            cerebro.cerrar_sistema()
            
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "message": str(e),
        }))
        sys.exit(1)

if __name__ == "__main__":
    main()
