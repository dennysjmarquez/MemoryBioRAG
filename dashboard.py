import os
import sys
import json
import time
import sqlite3
from typing import Optional
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
import uvicorn

# Configuración de Rutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "MemoryBioRAG_Data", "memory_biorag.db")

# Importar el motor real de BioRAG para la consolidación
sys.path.insert(0, BASE_DIR)
try:
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path=DB_PATH)
except Exception as e:
    print(f"Advertencia: No se pudo importar SQLiteMemoryBioRAG: {e}. Se usará fallback directo a SQLite.")
    cerebro = None

app = FastAPI(title="BioRAG Neuro-Visor 3D")

HTML_CONTENT = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>BioRAG Neuro-Visor</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@300;400;500;700&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/force-graph"></script>
    <script src="https://unpkg.com/d3"></script>
    <style>
        :root {
            --bg-color: #080c14;
            --panel-bg: rgba(13, 20, 35, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #e2e8f0;
            --text-muted: #94a3b8;
            --neon-blue: #3b82f6;
            --neon-purple: #a855f7;
            --neon-green: #10b981;
            --neon-orange: #f97316;
            --neon-pink: #ec4899;
            --neon-cyan: #06b6d4;
            --neon-yellow: #eab308;
            --neon-red: #ef4444;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            width: 100vw;
            height: 100vh;
            overflow: hidden;
            user-select: none;
        }

        #3d-graph {
            width: 100%;
            height: 100%;
            position: absolute;
            top: 0;
            left: 0;
            z-index: 1;
        }

        /* Paneles con Glassmorphism */
        .glass-panel {
            position: absolute;
            z-index: 10;
            background: var(--panel-bg);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        /* Panel Izquierdo: Control y Búsqueda */
        #left-panel {
            top: 20px;
            left: 20px;
            bottom: 20px;
            width: 380px;
            border-radius: 16px;
            display: flex;
            flex-direction: column;
            padding: 24px;
        }

        /* Panel Derecho: Detalles del Nodo */
        #right-panel {
            top: 20px;
            right: 20px;
            bottom: 20px;
            width: 420px;
            border-radius: 16px;
            display: flex;
            flex-direction: column;
            padding: 24px;
            opacity: 0;
            pointer-events: none;
            transform: translateX(50px);
        }

        #right-panel.active {
            opacity: 1;
            pointer-events: auto;
            transform: translateX(0);
        }

        /* Panel Superior: Filtros Rápidos */
        #top-panel {
            top: 20px;
            left: 420px;
            right: 460px;
            height: 70px;
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 24px;
        }

        /* Logo y Título */
        .logo-container {
            margin-bottom: 20px;
        }

        .logo-title {
            font-family: 'Outfit', sans-serif;
            font-size: 22px;
            font-weight: 800;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .logo-subtitle {
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-top: 2px;
        }

        /* Inputs y Botones */
        .search-container {
            margin-bottom: 20px;
            position: relative;
        }

        .search-input {
            width: 100%;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border-color);
            padding: 12px 16px;
            border-radius: 8px;
            color: var(--text-main);
            font-size: 14px;
            outline: none;
            transition: all 0.2s;
        }

        .search-input:focus {
            border-color: var(--neon-cyan);
            box-shadow: 0 0 12px rgba(6, 182, 212, 0.2);
            background: rgba(255, 255, 255, 0.08);
        }

        /* Estadísticas */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            padding: 12px 8px;
            border-radius: 8px;
            text-align: center;
        }

        .stat-val {
            font-family: 'Outfit', sans-serif;
            font-size: 20px;
            font-weight: 600;
            color: var(--text-main);
        }

        .stat-label {
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 4px;
        }

        /* Categorías */
        .category-list {
            flex-grow: 1;
            overflow-y: auto;
            margin-bottom: 20px;
            padding-right: 4px;
        }

        .category-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 13px;
            margin-bottom: 6px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }

        .category-item:hover {
            background: rgba(255, 255, 255, 0.04);
        }

        .category-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
        }

        .category-count {
            background: rgba(255, 255, 255, 0.06);
            padding: 2px 6px;
            border-radius: 12px;
            font-size: 10px;
            color: var(--text-muted);
        }

        /* Detalle del Nodo */
        .detail-header {
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 16px;
        }

        .detail-title {
            font-family: 'Outfit', sans-serif;
            font-size: 22px;
            font-weight: 600;
            word-break: break-all;
            color: #ffffff;
        }

        .detail-tags {
            display: flex;
            gap: 8px;
            margin-top: 8px;
        }

        .badge {
            font-size: 11px;
            padding: 4px 8px;
            border-radius: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-active {
            background: rgba(16, 185, 129, 0.15);
            color: var(--neon-green);
        }

        .badge-sleeping {
            background: rgba(148, 163, 184, 0.15);
            color: var(--text-muted);
        }

        .detail-section {
            margin-bottom: 20px;
        }

        .detail-section-title {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 1px;
            margin-bottom: 8px;
        }

        .content-box {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            padding: 16px;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.6;
            max-height: 200px;
            overflow-y: auto;
            color: #d1d5db;
        }

        /* Botones Especiales */
        .btn {
            background: var(--neon-blue);
            color: #ffffff;
            border: none;
            padding: 12px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            width: 100%;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            outline: none;
        }

        .btn:hover {
            filter: brightness(1.2);
            transform: translateY(-1px);
        }

        .btn-sleep {
            background: linear-gradient(135deg, var(--neon-purple), var(--neon-pink));
            box-shadow: 0 4px 14px 0 rgba(168, 85, 247, 0.3);
        }

        .btn-unlink {
            background: rgba(239, 68, 68, 0.1);
            color: var(--neon-red);
            border: 1px solid rgba(239, 68, 68, 0.2);
        }

        .btn-unlink:hover {
            background: var(--neon-red);
            color: #ffffff;
        }

        .btn-link {
            background: rgba(16, 185, 129, 0.15);
            color: var(--neon-green);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .btn-link:hover {
            background: var(--neon-green);
            color: #ffffff;
        }

        /* Filtros del Panel Superior */
        .filter-group {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .toggle-container {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            cursor: pointer;
        }

        .toggle-checkbox {
            cursor: pointer;
            accent-color: var(--neon-cyan);
        }

        .slider-container {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
        }

        .slider {
            accent-color: var(--neon-cyan);
            cursor: pointer;
        }

        /* Barra de Desplazamiento Estilizada */
        ::-webkit-scrollbar {
            width: 6px;
        }

        ::-webkit-scrollbar-track {
            background: transparent;
        }

        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        /* Lista de Conexiones */
        .connection-list {
            max-height: 150px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .connection-item {
            background: rgba(255, 255, 255, 0.01);
            border: 1px solid var(--border-color);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .connection-meta {
            display: flex;
            gap: 6px;
        }

        .tag {
            font-size: 9px;
            padding: 2px 6px;
            border-radius: 10px;
            font-weight: 600;
        }

        .tag-direct {
            background: rgba(59, 130, 246, 0.1);
            color: var(--neon-blue);
        }

        .tag-latent {
            background: rgba(168, 85, 247, 0.1);
            color: var(--neon-purple);
        }

        .vinculo-box {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }

        /* Pestañas del Panel Derecho */
        .panel-tabs {
            display: flex;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 16px;
            gap: 4px;
        }

        .tab-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            padding: 8px 12px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            border-bottom: 2px solid transparent;
            font-family: 'Outfit', sans-serif;
        }

        .tab-btn:hover {
            color: var(--text-main);
        }

        .tab-btn.active {
            color: var(--neon-cyan);
            border-bottom-color: var(--neon-cyan);
        }

        .tab-content {
            display: none;
            flex-direction: column;
            flex: 1;
            min-height: 0;
            overflow-y: auto;
        }

        .tab-content.active {
            display: flex;
        }

        /* Configuración de Grafo */
        .settings-group {
            margin-bottom: 16px;
            background: rgba(255, 255, 255, 0.01);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 12px;
        }

        .settings-title {
            font-size: 10px;
            color: var(--neon-cyan);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
            font-weight: 700;
        }

        .settings-item {
            margin-bottom: 10px;
        }

        .settings-item:last-child {
            margin-bottom: 0;
        }

        .settings-label {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: var(--text-main);
            margin-bottom: 4px;
        }

        .settings-label span:last-child {
            color: var(--neon-blue);
            font-weight: 600;
        }

        /* Estado Vacío del Panel Derecho */
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            min-height: 250px;
            color: var(--text-muted);
            text-align: center;
            padding: 24px;
            font-size: 13px;
            gap: 12px;
        }

        .empty-state-icon {
            font-size: 32px;
            opacity: 0.5;
        }

        /* Resultados de Búsqueda Semántica */
        .search-results-box {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            max-height: 160px;
            overflow-y: auto;
            margin-bottom: 20px;
            display: none;
            flex-direction: column;
        }
        
        .search-result-item {
            padding: 10px 14px;
            font-size: 12px;
            border-bottom: 1px solid var(--border-color);
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s;
        }

        .search-result-item:last-child {
            border-bottom: none;
        }

        .search-result-item:hover {
            background: rgba(6, 182, 212, 0.1);
        }

        .search-result-score {
            font-family: monospace;
            color: var(--neon-cyan);
            font-weight: 600;
        }

        .search-input-wrapper {
            position: relative;
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
        }

        .btn-search {
            background: rgba(6, 182, 212, 0.15);
            color: var(--neon-cyan);
            border: 1px solid rgba(6, 182, 212, 0.3);
            border-radius: 8px;
            width: 48px;
            height: 44px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            transition: all 0.2s;
        }

        .btn-search:hover {
            background: var(--neon-cyan);
            color: #ffffff;
        }
    </style>
</head>
<body>
    <div id="3d-graph"></div>

    <!-- Panel Izquierdo -->
    <div id="left-panel" class="glass-panel">
        <div class="logo-container">
            <div class="logo-title">
                <span>🧠</span> BioRAG Neuro-Visor
            </div>
            <div class="logo-subtitle">Mapeador de Consciencia de Agentes</div>
        </div>

        <div class="search-input-wrapper">
            <input type="text" id="search-input" class="search-input" placeholder="Buscar concepto o tokens..." autocomplete="off">
            <button id="btn-buscar-semantico" class="btn-search" title="Búsqueda Semántica Real">🔍</button>
        </div>

        <!-- Resultados de Búsqueda Semántica -->
        <div id="search-results" class="search-results-box">
            <!-- Cargados dinámicamente -->
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div id="stat-active" class="stat-val">-</div>
                <div class="stat-label">Activos</div>
            </div>
            <div class="stat-card">
                <div id="stat-sleeping" class="stat-val">-</div>
                <div class="stat-label">Dormidos</div>
            </div>
            <div class="stat-card">
                <div id="stat-edges" class="stat-val">-</div>
                <div class="stat-label">Sinapsis</div>
            </div>
        </div>

        <div class="detail-section-title">Categorías del Grafo</div>
        <div id="category-list" class="category-list">
            <!-- Cargadas dinámicamente -->
        </div>

        <button id="btn-consolidar" class="btn btn-sleep">
            <span>💤</span> Consolidar Cerebro (Sueño)
        </button>
    </div>

    <!-- Panel Derecho -->
    <div id="right-panel" class="glass-panel active">
        <div class="panel-tabs">
            <button id="tab-details" class="tab-btn">Detalles</button>
            <button id="tab-aprender" class="tab-btn">Aprender</button>
            <button id="tab-settings" class="tab-btn active">Fuerzas y Estilo</button>
        </div>

        <!-- Contenido de Detalles del Nodo -->
        <div id="content-details" class="tab-content">
            <!-- Estado vacío si no hay nodo seleccionado -->
            <div id="details-empty-state" class="empty-state">
                <span class="empty-state-icon">🧠</span>
                <div>Selecciona un nodo del cerebro para inspeccionar su contenido cognitivo y sinapsis conectadas en tiempo real.</div>
            </div>

            <!-- Detalles del nodo (ocultos inicialmente) -->
            <div id="details-node-active" style="display: none; flex-direction: column; height: 100%;">
                <div class="detail-header">
                    <div id="node-title" class="detail-title">Concepto</div>
                    <div class="detail-tags">
                        <span id="node-state-badge" class="badge">activo</span>
                        <span id="node-category-badge" class="badge" style="background: rgba(6, 182, 212, 0.15); color: var(--neon-cyan);">General</span>
                    </div>
                </div>

                <div class="detail-section">
                    <div class="detail-section-title">Contenido Cognitivo</div>
                    <div id="node-content" class="content-box">
                        Texto del recuerdo...
                    </div>
                </div>

                <div class="detail-section">
                    <div class="detail-section-title">Sinapsis Conectadas (<span id="node-conn-count">0</span>)</div>
                    <div id="node-connections" class="connection-list">
                        <!-- Conexiones -->
                    </div>
                </div>

                <div class="detail-section" style="margin-top: auto; border-top: 1px solid var(--border-color); padding-top: 16px;">
                    <div class="detail-section-title">Cirugía de Grafo</div>
                    <div class="vinculo-box">
                        <input type="text" id="link-target-input" class="search-input" placeholder="Concepto a vincular..." style="padding: 8px 12px; font-size: 12px;">
                        <button id="btn-vincular-nodo" class="btn btn-link" style="width: auto; padding: 0 16px; font-size: 12px;">Vincular</button>
                    </div>
                    <button id="btn-desvincular-nodo" class="btn btn-unlink" style="margin-top: 10px;">
                        Cortar Todo Vínculo
                    </button>
                </div>
            </div>
        </div>

        <!-- Contenido de Aprender nuevo concepto -->
        <div id="content-aprender" class="tab-content">
            <div class="settings-group">
                <div class="settings-title">🧠 Aprender en BioRAG</div>
                
                <div class="settings-item">
                    <label class="settings-label">Concepto (ID):</label>
                    <input type="text" id="learn-concept" class="search-input" placeholder="Nombre único (ej: motor_biorag)...">
                </div>

                <div class="settings-item">
                    <label class="settings-label">Categoría:</label>
                    <select id="learn-category" class="search-input" style="background: rgba(255,255,255,0.04); color: var(--text-main);">
                        <!-- Categorías cargadas dinámicamente -->
                    </select>
                </div>

                <div class="settings-item">
                    <label class="settings-label">Contenido Cognitivo:</label>
                    <textarea id="learn-content" class="search-input" style="height: 120px; font-family: sans-serif; resize: vertical;" placeholder="Escribe el conocimiento completo del recuerdo..."></textarea>
                </div>

                <div class="settings-item">
                    <label class="settings-label">Sinónimos (mínimo 5, por comas):</label>
                    <input type="text" id="learn-synonyms" class="search-input" placeholder="Ej: última versión, changelog, novedad...">
                </div>

                <div class="settings-item">
                    <label class="settings-label">Dimensiones Semánticas (JSON):</label>
                    <textarea id="learn-dimensions" class="search-input" style="height: 60px; font-family: monospace; font-size: 11px;" placeholder='{"entidad": ["identidad_artificial"]}'></textarea>
                </div>

                <button id="btn-aprender-biorag" class="btn btn-sleep" style="margin-top: 12px; width: 100%;">
                    <span>🧠</span> Aprender y Consolidar
                </button>
            </div>
        </div>

        <!-- Contenido de Ajustes de Grafo (Obsidian Style) -->
        <div id="content-settings" class="tab-content active">
            <!-- Sección Filtros -->
            <div class="settings-group">
                <div class="settings-title">Filtros del Grafo</div>
                <div class="settings-item">
                    <label class="toggle-container" style="margin-bottom: 8px;">
                        <input type="checkbox" id="sett-latent-toggle" class="toggle-checkbox" checked>
                        <span style="font-size: 11px;">Mostrar Sinapsis Latentes (Inferencia)</span>
                    </label>
                </div>
                <div class="settings-item">
                    <label class="toggle-container">
                        <input type="checkbox" id="sett-sleeping-toggle" class="toggle-checkbox" checked>
                        <span style="font-size: 11px;">Mostrar Nodos Dormidos</span>
                    </label>
                </div>
                <div class="settings-item" style="margin-top: 12px;">
                    <div class="settings-label">
                        <span>Peso Umbral de Sinapsis:</span>
                        <span id="sett-weight-val">0.05</span>
                    </div>
                    <input type="range" id="sett-weight-threshold" class="slider" min="0.05" max="1.0" step="0.05" value="0.05">
                </div>
                <div class="settings-item" style="margin-top: 12px;">
                    <div class="settings-label">
                        <span>Enfoque Local (Saltos):</span>
                        <span id="sett-depth-val">Off</span>
                    </div>
                    <input type="range" id="sett-depth" class="slider" min="0" max="3" step="1" value="0">
                </div>
            </div>

            <!-- Sección Fuerzas Físicas (Obsidian style) -->
            <div class="settings-group">
                <div class="settings-title">Simulación de Fuerzas</div>
                
                <div class="settings-item">
                    <div class="settings-label">
                        <span>Repelencia (Many-Body):</span>
                        <span id="sett-charge-val">-80</span>
                    </div>
                    <input type="range" id="sett-charge" class="slider" min="-300" max="0" step="10" value="-80">
                </div>

                <div class="settings-item">
                    <div class="settings-label">
                        <span>Distancia de Sinapsis:</span>
                        <span id="sett-distance-val">45</span>
                    </div>
                    <input type="range" id="sett-distance" class="slider" min="10" max="250" step="5" value="45">
                </div>

                <div class="settings-item">
                    <div class="settings-label">
                        <span>Fuerza de Colisión:</span>
                        <span id="sett-collide-val">15</span>
                    </div>
                    <input type="range" id="sett-collide" class="slider" min="0" max="40" step="1" value="15">
                </div>

                <div class="settings-item">
                    <div class="settings-label">
                        <span>Atracción al Centro:</span>
                        <span id="sett-center-val">0.15</span>
                    </div>
                    <input type="range" id="sett-center" class="slider" min="0.0" max="1.0" step="0.05" value="0.15">
                </div>
            </div>

            <!-- Sección Apariencia -->
            <div class="settings-group">
                <div class="settings-title">Estilo Visual</div>
                
                <div class="settings-item">
                    <div class="settings-label">
                        <span>Multiplicador Tamaño de Nodos:</span>
                        <span id="sett-node-size-val">1.8</span>
                    </div>
                    <input type="range" id="sett-node-size" class="slider" min="1.0" max="5.0" step="0.2" value="1.8">
                </div>

                <div class="settings-item">
                    <div class="settings-label">
                        <span>Multiplicador Grosor de Enlaces:</span>
                        <span id="sett-link-width-val">1.5</span>
                    </div>
                    <input type="range" id="sett-link-width" class="slider" min="0.5" max="4.0" step="0.2" value="1.5">
                </div>

                <div class="settings-item">
                    <label class="toggle-container">
                        <input type="checkbox" id="sett-always-labels" class="toggle-checkbox">
                        <span style="font-size: 11px;">Mostrar Nombres Siempre</span>
                    </label>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Mapeo de Categoría ➔ Color Neón
        const colors = {
            'System': '#f97316',
            'Architecture': '#3b82f6',
            'Project': '#06b6d4',
            'Lesson': '#10b981',
            'Principle': '#ec4899',
            'Protocol': '#eab308',
            'Profile': '#00ffff',
            'Cognition': '#a855f7',
            'Relation': '#f43f5e',
            'Personal': '#14b8a6',
            'General': '#94a3b8'
        };

        // Estado y Configuración Global del Grafo (Obsidian style)
        let rawData = { nodes: [], links: [] };
        let filteredData = { nodes: [], links: [] };
        let selectedNode = null;
        let highlightedNodes = new Set();
        let highlightedLinks = new Set();
        let hoverNode = null;

        const config = {
            nodeSizeMult: 1.8,
            linkWidthMult: 1.5,
            alwaysShowLabels: false,
            collisionRadius: 15,
            chargeStrength: -80,
            linkDistance: 45,
            centerStrength: 0.15,
            showLatent: true,
            showSleeping: true,
            weightThreshold: 0.05,
            localFocusDepth: 0
        };

        const Graph = ForceGraph()(document.getElementById('3d-graph'));

        // Inicialización de la visualización física en 2D (estilo Obsidian)
        Graph
            .backgroundColor('#080c14')
            .nodeCanvasObject((node, ctx, globalScale) => {
                const label = node.id;
                const baseSize = Math.max(3.5, (node.val || 1.0) * config.nodeSizeMult);
                const size = (selectedNode && selectedNode.id === node.id) ? baseSize * 1.3 : baseSize;

                // Color del nodo basado en su categoría
                let color = colors[node.categoria] || colors['General'];
                if (highlightedNodes.size > 0 && !highlightedNodes.has(node.id)) {
                    color = 'rgba(30, 41, 59, 0.15)'; // Atenuado si no está en la búsqueda/selección
                } else if (node.estado === 'dormido') {
                    color = 'rgba(148, 163, 184, 0.35)'; // Dormido
                }

                // Dibujar sombra brillante (glow) para el nodo seleccionado o resaltado
                if (selectedNode && selectedNode.id === node.id) {
                    ctx.shadowColor = '#fbbf24';
                    ctx.shadowBlur = 15;
                } else if (highlightedNodes.has(node.id)) {
                    ctx.shadowColor = '#06b6d4'; // Resaltado de búsqueda en Cyan brillante
                    ctx.shadowBlur = 15;
                } else {
                    ctx.shadowBlur = 0;
                }

                // Dibujar círculo del nodo
                ctx.beginPath();
                ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
                ctx.fillStyle = color;
                ctx.fill();
                ctx.shadowBlur = 0; // Resetear sombra para no afectar textos

                // Borde dorado si está seleccionado
                if (selectedNode && selectedNode.id === node.id) {
                    ctx.strokeStyle = '#fbbf24';
                    ctx.lineWidth = 2 / globalScale;
                    ctx.stroke();
                }

                // Dibujar etiquetas de texto (como Obsidian)
                const shouldShowLabel = config.alwaysShowLabels || globalScale > 1.2 || highlightedNodes.has(node.id) || (selectedNode && selectedNode.id === node.id);
                if (shouldShowLabel) {
                    const fontSize = Math.max(4, 9 / globalScale);
                    ctx.font = `${highlightedNodes.has(node.id) ? 'bold' : 'normal'} ${fontSize}px 'Inter', sans-serif`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'top';

                    // Color de la etiqueta
                    let textColor = 'rgba(148, 163, 184, 0.8)'; // Color muted por defecto
                    if (selectedNode && selectedNode.id === node.id) {
                        textColor = '#fbbf24'; // Dorado si está seleccionado
                    } else if (highlightedNodes.has(node.id)) {
                        textColor = '#ffffff'; // Blanco si está resaltado
                    }

                    ctx.fillStyle = textColor;
                    ctx.fillText(label, node.x, node.y + size + 2);
                }
            })
            .nodePointerAreaPaint((node, color, ctx) => {
                const size = Math.max(6, (node.val || 1.0) * config.nodeSizeMult * 1.5);
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
                ctx.fill();
            })
            .nodeLabel(null)
            .linkWidth(link => {
                if (highlightedLinks.size > 0) {
                    return highlightedLinks.has(link) ? 2.5 * config.linkWidthMult : 0.2;
                }
                return (link.latente ? 0.8 : 1.5) * config.linkWidthMult;
            })
            .linkColor(link => {
                if (highlightedLinks.size > 0) {
                    return highlightedLinks.has(link) ? '#fbbf24' : 'rgba(255,255,255,0.01)';
                }
                return link.latente ? 'rgba(168, 85, 247, 0.35)' : 'rgba(255, 255, 255, 0.2)';
            })
            .linkDirectionalParticles(link => highlightedLinks.has(link) ? 3 : 0)
            .linkDirectionalParticleSpeed(0.008)
            .linkDirectionalParticleWidth(2.0)
            .onNodeClick(node => {
                focusNode(node);
            })
            .onNodeHover(node => {
                document.body.style.cursor = node ? 'pointer' : 'default';
            })
            .onBackgroundClick(() => {
                selectedNode = null;
                highlightedNodes.clear();
                highlightedLinks.clear();
                Graph.nodeColor(Graph.nodeColor());
                Graph.linkColor(Graph.linkColor());
                
                document.getElementById('details-node-active').style.display = 'none';
                document.getElementById('details-empty-state').style.display = 'flex';
                switchTab('settings');
                
                // Si el enfoque local estaba activo, recargar filtros para mostrar todo de nuevo
                if (config.localFocusDepth > 0) {
                    applyFilters();
                }

                Graph.zoom(0.9, 1000);
            });

        // Configurar e inicializar fuerzas dinámicas D3
        function updatePhysics() {
            Graph.d3Force('charge').strength(config.chargeStrength);
            Graph.d3Force('link').distance(link => {
                return link.latente ? config.linkDistance * 1.6 : config.linkDistance;
            });
            Graph.d3Force('center').strength(config.centerStrength);
            Graph.d3Force('collide', d3.forceCollide(node => {
                const baseSize = Math.max(3.5, (node.val || 1.0) * config.nodeSizeMult);
                return baseSize + config.collisionRadius;
            }));
            Graph.d3ReheatSimulation();
        }

        // Lógica de Pestañas
        const tabDetails = document.getElementById('tab-details');
        const tabAprender = document.getElementById('tab-aprender');
        const tabSettings = document.getElementById('tab-settings');

        const contentDetails = document.getElementById('content-details');
        const contentAprender = document.getElementById('content-aprender');
        const contentSettings = document.getElementById('content-settings');

        function switchTab(tabName) {
            const tabs = {
                'details': { btn: tabDetails, content: contentDetails },
                'aprender': { btn: tabAprender, content: contentAprender },
                'settings': { btn: tabSettings, content: contentSettings }
            };

            Object.keys(tabs).forEach(name => {
                if (name === tabName) {
                    tabs[name].btn.classList.add('active');
                    tabs[name].content.classList.add('active');
                    tabs[name].content.style.display = 'flex';
                } else {
                    tabs[name].btn.classList.remove('active');
                    tabs[name].content.classList.remove('active');
                    tabs[name].content.style.display = 'none';
                }
            });
        }

        tabDetails.addEventListener('click', () => switchTab('details'));
        tabAprender.addEventListener('click', () => switchTab('aprender'));
        tabSettings.addEventListener('click', () => switchTab('settings'));

        // Cargar Datos de la API
        async function loadData() {
            try {
                const response = await fetch('/api/grafo');
                rawData = await response.json();
                
                updateStats();
                applyFilters();
                loadCategoriesToSelect();
            } catch (err) {
                console.error("Error cargando grafo de BioRAG:", err);
            }
        }

        // Poblar el select de categorías
        async function loadCategoriesToSelect() {
            try {
                const response = await fetch('/api/categorias');
                const data = await response.json();
                const select = document.getElementById('learn-category');
                select.innerHTML = '';
                data.categorias.forEach(cat => {
                    const opt = document.createElement('option');
                    opt.value = cat;
                    opt.textContent = cat;
                    if (cat === 'General') opt.selected = true;
                    select.appendChild(opt);
                });
            } catch (err) {
                console.error("Error cargando categorías:", err);
            }
        }

        function updateStats() {
            const active = rawData.nodes.filter(n => n.estado === 'activo').length;
            const sleeping = rawData.nodes.filter(n => n.estado === 'dormido').length;
            
            document.getElementById('stat-active').textContent = active;
            document.getElementById('stat-sleeping').textContent = sleeping;
            document.getElementById('stat-edges').textContent = rawData.links.length;

            const catCounts = {};
            rawData.nodes.forEach(n => {
                catCounts[n.categoria] = (catCounts[n.categoria] || 0) + 1;
            });

            const catList = document.getElementById('category-list');
            catList.innerHTML = '';
            
            Object.keys(colors).forEach(cat => {
                const count = catCounts[cat] || 0;
                const item = document.createElement('div');
                item.className = 'category-item';
                item.innerHTML = `
                    <div>
                        <span class="category-dot" style="background: ${colors[cat]}"></span>
                        <span>${cat}</span>
                    </div>
                    <span class="category-count">${count}</span>
                `;
                catList.appendChild(item);
            });
        }

        // Aplicar Filtros (Latentes, Umbral de Peso, Dormidos y Enfoque Local)
        function applyFilters() {
            let links = rawData.links;
            let nodes = rawData.nodes;

            // Filtro por tipo latente
            if (!config.showLatent) {
                links = links.filter(l => !l.latente);
            }

            // Filtro por peso
            links = links.filter(l => l.weight >= config.weightThreshold);

            // Filtro por nodos dormidos
            if (!config.showSleeping) {
                nodes = nodes.filter(n => n.estado === 'activo');
            }

            // Filtro por Enfoque Local (Saltos) estilo Obsidian
            if (selectedNode && config.localFocusDepth > 0) {
                const visibleNodeIds = new Set();
                visibleNodeIds.add(selectedNode.id);

                // 1 salto
                const firstNeighbors = new Set();
                links.forEach(l => {
                    const sId = l.source.id || l.source;
                    const tId = l.target.id || l.target;
                    if (sId === selectedNode.id) firstNeighbors.add(tId);
                    if (tId === selectedNode.id) firstNeighbors.add(sId);
                });
                firstNeighbors.forEach(id => visibleNodeIds.add(id));

                // 2 saltos
                if (config.localFocusDepth >= 2) {
                    const secondNeighbors = new Set();
                    links.forEach(l => {
                        const sId = l.source.id || l.source;
                        const tId = l.target.id || l.target;
                        if (firstNeighbors.has(sId)) secondNeighbors.add(tId);
                        if (firstNeighbors.has(tId)) secondNeighbors.add(sId);
                    });
                    secondNeighbors.forEach(id => visibleNodeIds.add(id));
                    
                    // 3 saltos
                    if (config.localFocusDepth >= 3) {
                        links.forEach(l => {
                            const sId = l.source.id || l.source;
                            const tId = l.target.id || l.target;
                            if (secondNeighbors.has(sId)) visibleNodeIds.add(tId);
                            if (secondNeighbors.has(tId)) visibleNodeIds.add(sId);
                        });
                    }
                }

                nodes = nodes.filter(n => visibleNodeIds.has(n.id));
            }

            const nodeIds = new Set(nodes.map(n => n.id));
            links = links.filter(l => nodeIds.has(l.source.id || l.source) && nodeIds.has(l.target.id || l.target));

            filteredData = {
                nodes: nodes,
                links: links
            };

            Graph.graphData(filteredData);
            updatePhysics();
        }

        // Centrar Cámara y Mostrar Detalles
        function focusNode(node) {
            selectedNode = node;
            
            Graph.centerAt(node.x, node.y, 1000);
            Graph.zoom(3.5, 1000);

            // Resaltar conexiones
            highlightedNodes.clear();
            highlightedLinks.clear();
            
            filteredData.links.forEach(link => {
                const sId = link.source.id || link.source;
                const tId = link.target.id || link.target;
                
                if (sId === node.id || tId === node.id) {
                    highlightedNodes.add(sId);
                    highlightedNodes.add(tId);
                    highlightedLinks.add(link);
                }
            });
            highlightedNodes.add(node.id);

            Graph.nodeColor(Graph.nodeColor());
            Graph.linkColor(Graph.linkColor());

            // Rellenar panel lateral
            document.getElementById('node-title').textContent = node.id;
            
            const stateBadge = document.getElementById('node-state-badge');
            stateBadge.textContent = node.estado;
            stateBadge.className = `badge ${node.estado === 'activo' ? 'badge-active' : 'badge-sleeping'}`;
            
            const catBadge = document.getElementById('node-category-badge');
            catBadge.textContent = node.categoria;
            catBadge.style.color = colors[node.categoria] || colors['General'];
            catBadge.style.background = `${colors[node.categoria] || colors['General']}22`;

            document.getElementById('node-content').textContent = node.contenido;

            // Conexiones directas
            const connList = document.getElementById('node-connections');
            connList.innerHTML = '';
            
            let connCount = 0;
            rawData.links.forEach(link => {
                const sId = link.source.id || link.source;
                const tId = link.target.id || link.target;
                
                if (sId === node.id || tId === node.id) {
                    connCount++;
                    const neighbor = sId === node.id ? tId : sId;
                    const item = document.createElement('div');
                    item.className = 'connection-item';
                    item.innerHTML = `
                        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                            <span style="font-weight: 500; cursor: pointer; color: var(--neon-cyan);" onclick="directFocus('${neighbor}')">${neighbor}</span>
                            <div class="connection-meta" style="display: flex; align-items: center; gap: 8px;">
                                <span class="tag ${link.latente ? 'tag-latent' : 'tag-direct'}">${link.tipo}</span>
                                <span style="font-family: monospace;">${link.weight.toFixed(2)}</span>
                                ${!link.latente ? `<button class="btn-unlink" style="background: none; border: none; color: var(--neon-red); cursor: pointer; font-size: 11px; padding: 2px;" onclick="confirmDesvincular('${node.id}', '${neighbor}')" title="Cortar Vínculo Directo">❌</button>` : ''}
                            </div>
                        </div>
                    `;
                    connList.appendChild(item);
                }
            });
            document.getElementById('node-conn-count').textContent = connCount;

            document.getElementById('details-empty-state').style.display = 'none';
            document.getElementById('details-node-active').style.display = 'flex';
            switchTab('details');

            // Si el enfoque local está habilitado, aplicar filtro en caliente
            if (config.localFocusDepth > 0) {
                applyFilters();
            }
        }

        // Buscar nodo desde el texto y hacer foco
        function directFocus(nodeId) {
            const node = rawData.nodes.find(n => n.id === nodeId);
            if (node) focusNode(node);
        }

        // Eliminar vínculo específico con un clic
        async function confirmDesvincular(a, b) {
            if (!confirm(`¿Deseas cortar la sinapsis directa entre '${a}' y '${b}'?`)) return;
            try {
                const res = await fetch('/api/desvincular', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ a, b })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    await loadData();
                    // Volver a cargar el nodo seleccionado
                    const node = rawData.nodes.find(n => n.id === selectedNode.id);
                    if (node) focusNode(node);
                } else {
                    alert('Error: ' + data.mensaje);
                }
            } catch (err) {
                alert('Error al desvincular sinapsis.');
            }
        }

        // Ejecutar Búsqueda Semántica en el servidor
        async function performSemanticSearch() {
            const query = document.getElementById('search-input').value.trim();
            const resultsBox = document.getElementById('search-results');
            
            if (!query) {
                resultsBox.style.display = 'none';
                highlightedNodes.clear();
                highlightedLinks.clear();
                Graph.nodeColor(Graph.nodeColor());
                Graph.linkColor(Graph.linkColor());
                return;
            }

            try {
                const response = await fetch(`/api/buscar?q=${encodeURIComponent(query)}`);
                const data = await response.json();
                
                resultsBox.innerHTML = '';
                if (data.resultados && data.resultados.length > 0) {
                    resultsBox.style.display = 'flex';
                    
                    highlightedNodes.clear();
                    data.resultados.forEach(res => {
                        highlightedNodes.add(res.concepto);
                        
                        const item = document.createElement('div');
                        item.className = 'search-result-item';
                        item.innerHTML = `
                            <span>${res.concepto}</span>
                            <span class="search-result-score">${res.score.toFixed(2)}</span>
                        `;
                        item.addEventListener('click', () => {
                            directFocus(res.concepto);
                        });
                        resultsBox.appendChild(item);
                    });

                    // Resaltar enlaces de los resultados
                    highlightedLinks.clear();
                    filteredData.links.forEach(link => {
                        const sId = link.source.id || link.source;
                        const tId = link.target.id || link.target;
                        if (highlightedNodes.has(sId) && highlightedNodes.has(tId)) {
                            highlightedLinks.add(link);
                        }
                    });

                    Graph.nodeColor(Graph.nodeColor());
                    Graph.linkColor(Graph.linkColor());
                } else {
                    resultsBox.style.display = 'flex';
                    resultsBox.innerHTML = `<div style="padding: 10px; font-size: 11px; text-align: center; color: var(--text-muted);">Sin resultados semánticos</div>`;
                }
            } catch (err) {
                console.error("Error en búsqueda semántica:", err);
            }
        }

        document.getElementById('btn-buscar-semantico').addEventListener('click', performSemanticSearch);
        document.getElementById('search-input').addEventListener('keydown', e => {
            if (e.key === 'Enter') performSemanticSearch();
        });

        // Configuración de Binds y Eventos de UI de Ajustes (Obsidian style)
        document.getElementById('sett-latent-toggle').addEventListener('change', e => {
            config.showLatent = e.target.checked;
            applyFilters();
        });

        document.getElementById('sett-sleeping-toggle').addEventListener('change', e => {
            config.showSleeping = e.target.checked;
            applyFilters();
        });

        document.getElementById('sett-weight-threshold').addEventListener('input', e => {
            config.weightThreshold = parseFloat(e.target.value);
            document.getElementById('sett-weight-val').textContent = e.target.value;
            applyFilters();
        });

        document.getElementById('sett-depth').addEventListener('input', e => {
            const val = parseInt(e.target.value);
            config.localFocusDepth = val;
            document.getElementById('sett-depth-val').textContent = val === 0 ? 'Off' : `${val} salto${val > 1 ? 's' : ''}`;
            applyFilters();
        });

        // Sliders de simulación física
        document.getElementById('sett-charge').addEventListener('input', e => {
            config.chargeStrength = parseInt(e.target.value);
            document.getElementById('sett-charge-val').textContent = e.target.value;
            updatePhysics();
        });

        document.getElementById('sett-distance').addEventListener('input', e => {
            config.linkDistance = parseInt(e.target.value);
            document.getElementById('sett-distance-val').textContent = e.target.value;
            updatePhysics();
        });

        document.getElementById('sett-collide').addEventListener('input', e => {
            config.collisionRadius = parseInt(e.target.value);
            document.getElementById('sett-collide-val').textContent = e.target.value;
            updatePhysics();
        });

        document.getElementById('sett-center').addEventListener('input', e => {
            config.centerStrength = parseFloat(e.target.value);
            document.getElementById('sett-center-val').textContent = e.target.value;
            updatePhysics();
        });

        // Sliders de apariencia
        document.getElementById('sett-node-size').addEventListener('input', e => {
            config.nodeSizeMult = parseFloat(e.target.value);
            document.getElementById('sett-node-size-val').textContent = e.target.value;
            Graph.nodeColor(Graph.nodeColor());
            updatePhysics();
        });

        document.getElementById('sett-link-width').addEventListener('input', e => {
            config.linkWidthMult = parseFloat(e.target.value);
            document.getElementById('sett-link-width-val').textContent = e.target.value;
            Graph.linkWidth(Graph.linkWidth());
        });

        document.getElementById('sett-always-labels').addEventListener('change', e => {
            config.alwaysShowLabels = e.target.checked;
            Graph.nodeColor(Graph.nodeColor());
        });

        // Operación: Consolidar (Sueño)
        document.getElementById('btn-consolidar').addEventListener('click', async () => {
            const btn = document.getElementById('btn-consolidar');
            btn.disabled = true;
            btn.innerHTML = '<span>⏳</span> Consolidando...';
            try {
                const res = await fetch('/api/consolidar', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'ok') {
                    alert('Consolidación completada: ' + data.mensaje);
                    await loadData();
                } else {
                    alert('Error: ' + data.mensaje);
                }
            } catch (err) {
                alert('Fallo de conexión');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<span>💤</span> Consolidar Cerebro (Sueño)';
            }
        });

        // Operación: Vincular
        document.getElementById('btn-vincular-nodo').addEventListener('click', async () => {
            if (!selectedNode) return;
            const target = document.getElementById('link-target-input').value.trim();
            if (!target) return alert('Especificá un concepto a vincular');
            
            try {
                const res = await fetch('/api/vincular', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ a: selectedNode.id, b: target, tipo: 'manual' })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    alert('Vinculado con éxito');
                    document.getElementById('link-target-input').value = '';
                    await loadData();
                    const node = rawData.nodes.find(n => n.id === selectedNode.id);
                    if (node) focusNode(node);
                } else {
                    alert('Error: ' + data.mensaje);
                }
            } catch (err) {
                alert('Fallo de conexión');
            }
        });

        // Operación: Desvincular todo
        document.getElementById('btn-desvincular-nodo').addEventListener('click', async () => {
            if (!selectedNode) return;
            if (!confirm(`¿Estás seguro de cortar TODOS los vínculos de '${selectedNode.id}'?`)) return;

            try {
                const directLinks = rawData.links.filter(l => !l.latente && ((l.source.id || l.source) === selectedNode.id || (l.target.id || l.target) === selectedNode.id));
                
                for (let link of directLinks) {
                    const s = link.source.id || link.source;
                    const t = link.target.id || link.target;
                    await fetch('/api/desvincular', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ a: s, b: t })
                    });
                }
                
                alert('Vínculos cortados con éxito');
                await loadData();
                const node = rawData.nodes.find(n => n.id === selectedNode.id);
                if (node) focusNode(node);
            } catch (err) {
                alert('Fallo en la operación');
            }
        });

        // Formulario: Aprender en BioRAG
        document.getElementById('btn-aprender-biorag').addEventListener('click', async () => {
            const concepto = document.getElementById('learn-concept').value.trim();
            const cat = document.getElementById('learn-category').value;
            const contenido = document.getElementById('learn-content').value.trim();
            const syn = document.getElementById('learn-synonyms').value.trim();
            const dimRaw = document.getElementById('learn-dimensions').value.trim();

            if (!concepto || !contenido) {
                return alert('Concepto (ID) y Contenido Cognitivo son campos obligatorios.');
            }

            let dimensiones = {};
            if (dimRaw) {
                try {
                    dimensiones = JSON.parse(dimRaw);
                } catch (e) {
                    return alert('El campo de dimensiones debe ser un objeto JSON válido. Ej: {"entidad": ["identidad_artificial"]}');
                }
            }

            const btn = document.getElementById('btn-aprender-biorag');
            btn.disabled = true;
            btn.textContent = 'Aprendiendo en BioRAG...';

            try {
                const res = await fetch('/api/aprender', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ concepto, cat, contenido, syn, dimensiones })
                });
                const data = await res.json();
                
                if (data.status === 'ok') {
                    alert('¡Concepto aprendido con éxito!');
                    // Limpiar formulario
                    document.getElementById('learn-concept').value = '';
                    document.getElementById('learn-content').value = '';
                    document.getElementById('learn-synonyms').value = '';
                    document.getElementById('learn-dimensions').value = '';
                    
                    // Recargar datos y enfocar en el nuevo nodo
                    await loadData();
                    const cleanId = concepto.toLowerCase().replace(/ /g, '_');
                    const newNode = rawData.nodes.find(n => n.id === cleanId);
                    if (newNode) {
                        focusNode(newNode);
                    }
                } else {
                    alert('Error: ' + data.mensaje);
                }
            } catch (err) {
                alert('Error al conectar con la API de aprendizaje.');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<span>🧠</span> Aprender y Consolidar';
            }
        });

        // Inicializar
        loadData();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    return HTML_CONTENT


@app.get("/api/grafo")
def get_grafo():
    if not os.path.exists(DB_PATH):
        return {"nodes": [], "links": []}
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Obtener todos los nodos con nombres de categorías
        cursor.execute("""
            SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.creado_en, c.name
            FROM largo_plazo l
            LEFT JOIN categories c ON l.categoria = c.id
        """)
        nodes_raw = cursor.fetchall()
        
        nodes = []
        for r in nodes_raw:
            nodes.append({
                "id": r[0],
                "contenido": r[1] or "",
                "val": float(r[2]) if r[2] is not None else 1.0,
                "estado": r[3] or "activo",
                "creado_en": r[4],
                "categoria": r[5] or "General"
            })
            
        # Obtener sinapsis directas
        cursor.execute("SELECT origen, destino, peso, tipo FROM sinapsis")
        edges_raw = cursor.fetchall()
        
        links = []
        # Para evitar duplicación visual en el render de líneas bidireccionales,
        # normalizamos la clave de orden origen-destino.
        seen_edges = set()
        for r in edges_raw:
            o, d, w, t = r[0], r[1], float(r[2]) if r[2] is not None else 1.0, r[3] or "co_ocurrencia"
            edge_key = tuple(sorted([o, d]))
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                links.append({
                    "source": o,
                    "target": d,
                    "weight": w,
                    "tipo": t,
                    "latente": False
                })
                
        # Obtener sinapsis latentes (inferencias)
        cursor.execute("SELECT origen, destino, peso_atenuado, saltos FROM sinapsis_latentes")
        latentes_raw = cursor.fetchall()
        for r in latentes_raw:
            o, d, w, s = r[0], r[1], float(r[2]) if r[2] is not None else 0.5, r[3]
            tc = f"latente_{s}_saltos"
            edge_key = (o, d, "latent")  # Las latentes son direccionales
            links.append({
                "source": o,
                "target": d,
                "weight": w,
                "saltos": s,
                "tipo": tc,
                "latente": True
            })
            
        conn.close()
        return {"nodes": nodes, "links": links}
    except Exception as exc:
        return {"nodes": [], "links": [], "error": str(exc)}


@app.post("/api/vincular")
def api_vincular(data: dict):
    a = data.get("a")
    b = data.get("b")
    tipo = data.get("tipo", "manual")
    peso = data.get("peso", 1.0)
    
    if not a or not b:
        return {"status": "error", "mensaje": "Faltan parámetros 'a' y 'b'"}
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        t = time.time()
        
        # Verificar que ambos conceptos existan
        cursor.execute("SELECT count(*) FROM largo_plazo WHERE concepto = ?", (a,))
        if cursor.fetchone()[0] == 0:
            # Crear nodo a si no existe para prevenir FK issues
            cursor.execute("INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en) VALUES (?, 'nodo_creado_via_dashboard', 1.0, 'activo', ?)", (a, t))
            
        cursor.execute("SELECT count(*) FROM largo_plazo WHERE concepto = ?", (b,))
        if cursor.fetchone()[0] == 0:
            # Crear nodo b si no existe para prevenir FK issues
            cursor.execute("INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en) VALUES (?, 'nodo_creado_via_dashboard', 1.0, 'activo', ?)", (b, t))
            
        # Crear aristas bidireccionales
        cursor.execute("INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, ?, ?, ?)", (a, b, peso, tipo, t))
        cursor.execute("INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, ?, ?, ?)", (b, a, peso, tipo, t))
        conn.commit()
        conn.close()
        return {"status": "ok", "mensaje": f"Vínculo bidireccional creado: {a} <-> {b}"}
    except Exception as exc:
        return {"status": "error", "mensaje": str(exc)}


@app.post("/api/desvincular")
def api_desvincular(data: dict):
    a = data.get("a")
    b = data.get("b")
    
    if not a or not b:
        return {"status": "error", "mensaje": "Faltan parámetros 'a' y 'b'"}
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sinapsis WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)", (a, b, b, a))
        conn.commit()
        conn.close()
        return {"status": "ok", "mensaje": f"Vínculo eliminado: {a} <-/-> {b}"}
    except Exception as exc:
        return {"status": "error", "mensaje": str(exc)}


@app.post("/api/consolidar")
def api_consolidar():
    if cerebro is None:
        return {"status": "error", "mensaje": "Motor de BioRAG no disponible para consolidación directa."}
    try:
        # Invocar la consolidación (ciclo de sueño) real
        cerebro.consolidar()
        return {"status": "ok", "mensaje": "Proceso de consolidación y equilibrio sináptico completado con éxito en el motor principal."}
    except Exception as exc:
        return {"status": "error", "mensaje": str(exc)}


@app.get("/api/categorias")
def get_categorias():
    if not os.path.exists(DB_PATH):
        return {"categorias": ["General"]}
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM categories ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        # Si está vacío, rellenamos con las predefinidas
        cats = [r[0] for r in rows] if rows else ["System", "Architecture", "Project", "Lesson", "Principle", "Protocol", "Profile", "Cognition", "Relation", "Personal", "General"]
        return {"categorias": cats}
    except Exception as exc:
        return {"categorias": ["General"], "error": str(exc)}


@app.get("/api/buscar")
def api_buscar(q: str = ""):
    if not q:
        return {"resultados": []}
    try:
        if cerebro is not None:
            # Buscar por frase
            resultados, total = cerebro.buscar_por_frase(q, profundidad="profundo", limite=15)
            mapped = []
            for r in resultados:
                mapped.append({
                    "concepto": r[0],
                    "contenido": r[1],
                    "score": float(r[4]) if r[4] is not None else 1.0,
                    "estado": r[3]
                })
            return {"resultados": mapped}
        else:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT concepto, contenido, peso_sinaptico, estado 
                FROM largo_plazo 
                WHERE concepto LIKE ? OR contenido LIKE ?
            """, (f"%{q}%", f"%{q}%"))
            rows = cursor.fetchall()
            mapped = []
            for r in rows:
                mapped.append({
                    "concepto": r[0],
                    "contenido": r[1],
                    "score": 1.0,
                    "estado": r[3]
                })
            conn.close()
            return {"resultados": mapped}
    except Exception as exc:
        return {"resultados": [], "error": str(exc)}


@app.post("/api/aprender")
def api_aprender(data: dict):
    concepto = data.get("concepto")
    contenido = data.get("contenido")
    cat = data.get("cat", "General")
    syn = data.get("syn", "")
    dimensiones = data.get("dimensiones", {})
    
    if not concepto or not contenido:
        return {"status": "error", "mensaje": "Concepto y contenido son obligatorios."}
        
    try:
        clave = concepto.lower().strip().replace(" ", "_")
        
        if cerebro is not None:
            # Registrar en BioRAG
            dimensiones_dict = {}
            if dimensiones:
                if isinstance(dimensiones, str):
                    try:
                        dim_raw = json.loads(dimensiones)
                    except Exception:
                        dim_raw = {}
                else:
                    dim_raw = dimensiones
                
                for eje, valores in dim_raw.items():
                    if isinstance(valores, list):
                        ids, _ = cerebro._resolver_dimension_ids(eje, ",".join(valores))
                        if ids:
                            dimensiones_dict[eje] = ids
            
            cerebro.percibir_corto_plazo(clave, contenido, syn, cat, dimensiones_dict)
            
            # Auto-vincular
            from core.sinapsis import auto_vincular, vincular_por_sinonimos
            enlaces = auto_vincular(cerebro, clave, contenido)
            if syn:
                vincular_por_sinonimos(cerebro, clave, syn)
                
            # Consolidar
            cerebro.consolidar_concepto(clave)
            return {"status": "ok", "mensaje": f"Concepto '{clave}' consolidado con éxito."}
        else:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            t = time.time()
            cursor.execute("SELECT id FROM categories WHERE name = ?", (cat,))
            cat_row = cursor.fetchone()
            cat_id = cat_row[0] if cat_row else 1
            
            cursor.execute("""
                INSERT OR REPLACE INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en, categoria)
                VALUES (?, ?, 1.0, 'activo', ?, ?)
            """, (clave, contenido, t, cat_id))
            conn.commit()
            conn.close()
            return {"status": "ok", "mensaje": f"Concepto '{clave}' guardado (fallback SQLite)."}
    except Exception as exc:
        return {"status": "error", "mensaje": str(exc)}


if __name__ == "__main__":
    print("--------------------------------------------------")
    print("🧠 Iniciando BioRAG Neuro-Visor 3D...")
    print(f"📁 Cargando base de datos desde: {DB_PATH}")
    print("🔗 Abre en tu navegador: http://localhost:8002")
    print("--------------------------------------------------")
    uvicorn.run(app, host="0.0.0.0", port=8002)
