#!/usr/bin/env python3
"""Reintenta cuatro rechazos MCP con frases de la pregunta, sin alterar motor.

Las etiquetas se eligieron tras observar la validación de la primera ejecución;
no es una comparación ciega ni una evaluación independiente.
"""
import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import explorar_mcp_cjk_sintetico as exploration

exploration.IDS = ('zh-18', 'ja-15', 'ja-17', 'ja-18')
exploration.LABELS = ROOT / 'scripts/casos_sustantivos_cjk_reintento_20261101.jsonl'
asyncio.run(exploration.main())
