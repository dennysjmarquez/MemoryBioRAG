const API = '';
let currentView = 'corteza';
let selectedNode = null;

// Navigation state
let navHistory = [];
let navIndex = -1;

// ============================================================
// NAVIGATION (sidebar views)
// ============================================================

document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const view = btn.dataset.view;
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById(`view-${view}`).classList.add('active');
        currentView = view;
        loadView(view);
    });
});

function loadView(view) {
    switch(view) {
        case 'corteza': loadCorteza(); break;
        case 'explorar': break;
        case 'latentes': loadLatentes(); break;
        case 'comunidades': loadComunidades(); break;
        case 'suenos': loadSuenos(); break;
    }
}

// ============================================================
// TOAST
// ============================================================

function toast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

// ============================================================
// API
// ============================================================

async function api(endpoint, options = {}) {
    try {
        const res = await fetch(API + endpoint, {
            headers: { 'Content-Type': 'application/json' },
            ...options
        });
        return await res.json();
    } catch (e) {
        console.error('API Error:', e);
        return { error: e.message };
    }
}

// ============================================================
// TIME HELPERS
// ============================================================

function timeAgo(ts) {
    if (!ts) return 'nunca';
    const diff = (Date.now() / 1000) - ts;
    if (diff < 60) return `hace ${Math.floor(diff)}s`;
    if (diff < 3600) return `hace ${Math.floor(diff / 60)}min`;
    if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
    return `hace ${Math.floor(diff / 86400)}d`;
}

// ============================================================
// SEARCH
// ============================================================

const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');
let searchTimeout;

searchInput.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    const q = searchInput.value.trim();
    if (q.length < 2) { searchResults.classList.remove('open'); return; }
    searchTimeout = setTimeout(() => searchNodes(q), 300);
});

searchInput.addEventListener('focus', () => {
    if (searchInput.value.trim().length >= 2) searchResults.classList.add('open');
});

document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-container')) searchResults.classList.remove('open');
});

async function searchNodes(q) {
    const data = await api(`/api/buscar?q=${encodeURIComponent(q)}&limit=15`);
    if (!data.resultados || data.resultados.length === 0) {
        searchResults.innerHTML = '<div class="search-result"><span class="search-result-name" style="color:var(--text-muted)">Sin resultados</span></div>';
        searchResults.classList.add('open');
        return;
    }
    searchResults.innerHTML = data.resultados.map(r => `
        <div class="search-result" onclick="navigateToNode('${r.concepto.replace(/'/g, "\\'")}')">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="search-result-name">${r.concepto}</span>
                <span class="search-result-score">${r.score.toFixed(3)}</span>
            </div>
            <div class="search-result-preview">${(r.contenido || '').substring(0, 100)}</div>
        </div>
    `).join('');
    searchResults.classList.add('open');
}

// ============================================================
// NAVIGATION HISTORY
// ============================================================

function navigateToNode(concepto) {
    searchResults.classList.remove('open');
    searchInput.value = concepto;
    selectedNode = concepto;

    // Trim future history if we navigated back then chose a new path
    if (navIndex < navHistory.length - 1) {
        navHistory = navHistory.slice(0, navIndex + 1);
    }
    navHistory.push(concepto);
    navIndex = navHistory.length - 1;

    updateNavButtons();
    updateBreadcrumb();
    loadNodeExplorer(concepto);
}

function goBack() {
    if (navIndex <= 0) return;
    navIndex--;
    selectedNode = navHistory[navIndex];
    searchInput.value = selectedNode;
    updateNavButtons();
    updateBreadcrumb();
    loadNodeExplorer(selectedNode);
}

function goForward() {
    if (navIndex >= navHistory.length - 1) return;
    navIndex++;
    selectedNode = navHistory[navIndex];
    searchInput.value = selectedNode;
    updateNavButtons();
    updateBreadcrumb();
    loadNodeExplorer(selectedNode);
}

function updateNavButtons() {
    document.getElementById('btn-back').disabled = navIndex <= 0;
    document.getElementById('btn-forward').disabled = navIndex >= navHistory.length - 1;
}

function updateBreadcrumb() {
    const bc = document.getElementById('breadcrumb');
    const maxCrumbs = 5;
    let crumbs = navHistory.slice(0, navIndex + 1);

    if (crumbs.length > maxCrumbs) {
        crumbs = [crumbs[0], '...', ...crumbs.slice(crumbs.length - 2)];
    }

    bc.innerHTML = crumbs.map((c, i) => {
        if (c === '...') return '<span class="crumb-sep">…</span>';
        const isLast = i === crumbs.length - 1;
        const label = c.length > 25 ? c.substring(0, 22) + '...' : c;
        return `${i > 0 ? '<span class="crumb-sep">›</span>' : ''}
            <span class="crumb" ${!isLast ? `onclick="jumpToCrumb(${navHistory.indexOf(c)})"` : ''} style="${isLast ? 'color:var(--text);cursor:default' : ''}">${i === 0 ? '🏠 ' : ''}${label}</span>`;
    }).join('');
}

function jumpToCrumb(idx) {
    if (idx < 0 || idx >= navHistory.length) return;
    navIndex = idx;
    selectedNode = navHistory[navIndex];
    searchInput.value = selectedNode;
    updateNavButtons();
    updateBreadcrumb();
    loadNodeExplorer(selectedNode);
}

// Back/Forward buttons
document.getElementById('btn-back').addEventListener('click', goBack);
document.getElementById('btn-forward').addEventListener('click', goForward);

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.altKey && e.key === 'ArrowLeft') { e.preventDefault(); goBack(); }
    if (e.altKey && e.key === 'ArrowRight') { e.preventDefault(); goForward(); }
});

// ============================================================
// NODE EXPLORER — Panel de Inspección y Curación
// ============================================================

async function loadNodeExplorer(concepto) {
    const data = await api(`/api/nodo/${encodeURIComponent(concepto)}/ego?limit=50`);
    if (data.error || data.detail) {
        toast(`Error: ${data.detail || data.error}`, 'error');
        return;
    }

    document.getElementById('explorar-empty').style.display = 'none';
    document.getElementById('explorar-content').style.display = 'grid';

    renderNodeIdentity(data.center, data.stats);
    renderConnections(data.connections);
    renderLatentes(data.latentes);
}

// --- COLUMNA IZQ: Identidad del nodo ---

function renderNodeIdentity(center, stats) {
    document.getElementById('node-title').textContent = center.concepto;

    const dot = document.getElementById('node-state-dot');
    dot.className = `state-dot ${center.estado}`;

    const estadoBadge = document.getElementById('node-badge-estado');
    estadoBadge.textContent = center.estado;
    estadoBadge.className = `badge ${center.estado === 'activo' ? 'badge-activo' : 'badge-dormido'}`;

    const catBadge = document.getElementById('node-badge-cat');
    catBadge.textContent = center.categoria;

    document.getElementById('node-peso').textContent = center.peso.toFixed(3);
    document.getElementById('node-conn-count').textContent = stats.total_conexiones;
    document.getElementById('node-creado').textContent = timeAgo(center.creado_en);
    document.getElementById('node-acceso').textContent = timeAgo(center.ultimo_acceso);

    // Dimensiones
    const dimEl = document.getElementById('node-dimensiones');
    if (center.dimensiones && Object.keys(center.dimensiones).length > 0) {
        document.getElementById('section-dimensiones').style.display = 'block';
        dimEl.innerHTML = Object.entries(center.dimensiones).map(([eje, vals]) =>
            vals.map(v => `<span class="chip chip-dim" title="${eje}">${eje}.${v}</span>`).join('')
        ).join('');
    } else {
        document.getElementById('section-dimensiones').style.display = 'none';
    }

    // WordNet
    const wnEl = document.getElementById('node-wordnet');
    if (center.grupos && center.grupos.length > 0) {
        document.getElementById('section-wordnet').style.display = 'block';
        wnEl.innerHTML = center.grupos.map(g => `<span class="chip chip-wn" title="${g.fuente}">${g.nombre}</span>`).join('');
    } else {
        document.getElementById('section-wordnet').style.display = 'none';
    }

    // Sinónimos
    const sinEl = document.getElementById('node-sinonimos');
    if (center.sinonimos && center.sinonimos.trim()) {
        document.getElementById('section-sinonimos').style.display = 'block';
        sinEl.innerHTML = center.sinonimos.split(',').map(s =>
            `<span class="chip">${s.trim()}</span>`
        ).join('');
    } else {
        document.getElementById('section-sinonimos').style.display = 'none';
    }

    // Contenido
    document.getElementById('node-contenido').textContent = center.contenido || '(vacío)';
}

// --- COLUMNA CENTRO: Conexiones directas ---

const TIPO_COLORS = {
    manual: 'tipo-manual',
    sinonimo_explicito: 'tipo-sinonimo_explicito',
    co_ocurrencia: 'tipo-co_ocurrencia',
    rafaga_rememb: 'tipo-rafaga_rememb',
    co_nombre: 'tipo-co_nombre',
    co_semantica: 'tipo-co_semantica'
};

const DIR_SYMBOLS = {
    saliente: '→',
    entrante: '←',
    bidireccional: '↔'
};

const DIR_CLASSES = {
    saliente: 'dir-saliente',
    entrante: 'dir-entrante',
    bidireccional: 'dir-bidireccional'
};

let allConnections = [];

function renderConnections(connections) {
    allConnections = connections;
    document.getElementById('conn-total').textContent = connections.length;
    applyFilters();
}

function applyFilters() {
    const tipoFilter = document.getElementById('filter-tipo').value;
    const orden = document.getElementById('filter-orden').value;

    let filtered = [...allConnections];
    if (tipoFilter) {
        filtered = filtered.filter(c => c.tipo === tipoFilter);
    }

    if (orden === 'peso') {
        filtered.sort((a, b) => b.peso - a.peso);
    } else if (orden === 'ultimo_uso') {
        filtered.sort((a, b) => (b.ultimo_uso || 0) - (a.ultimo_uso || 0));
    } else if (orden === 'alfabeto') {
        filtered.sort((a, b) => a.destino_concepto.localeCompare(b.destino_concepto));
    }

    const list = document.getElementById('connections-list');
    list.innerHTML = filtered.map(c => {
        const tipoClass = TIPO_COLORS[c.tipo] || 'tipo-default';
        const dirSymbol = DIR_SYMBOLS[c.direccion] || '?';
        const dirClass = DIR_CLASSES[c.direccion] || '';
        const barWidth = Math.round(c.peso * 100);
        const escapedName = c.destino_concepto.replace(/'/g, "\\'");

        return `
        <div class="conn-card">
            <div class="conn-card-header">
                <span class="conn-card-dir ${dirClass}">${dirSymbol}</span>
                <span class="conn-card-name" onclick="navigateToNode('${escapedName}')">${c.destino_concepto}</span>
            </div>
            <div class="conn-card-bar">
                <div class="conn-card-bar-fill" style="width:${barWidth}%"></div>
            </div>
            <div class="conn-card-meta">
                <span class="conn-card-tipo ${tipoClass}">${c.tipo}</span>
                <span style="font-family:'JetBrains Mono';font-size:11px;color:var(--text)">${c.peso.toFixed(2)}</span>
                <span class="conn-card-fecha">${timeAgo(c.ultimo_uso)}</span>
            </div>
            ${c.destino_preview ? `<div class="conn-card-preview">${c.destino_preview}</div>` : ''}
            <div class="conn-card-actions">
                <button class="btn-go" onclick="navigateToNode('${escapedName}')">Ir →</button>
                <button class="btn-unlink" onclick="event.stopPropagation();desvincular('${selectedNode}','${escapedName}')">✕ Cortar</button>
            </div>
        </div>`;
    }).join('');

    if (filtered.length === 0) {
        list.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:20px;font-size:13px">Sin conexiones con este filtro</div>';
    }
}

document.getElementById('filter-tipo').addEventListener('change', applyFilters);
document.getElementById('filter-orden').addEventListener('change', applyFilters);

// --- COLUMNA DER: Latentes ---

function renderLatentes(latentes) {
    document.getElementById('lat-total').textContent = latentes.length;
    const list = document.getElementById('latentes-list');

    if (latentes.length === 0) {
        list.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:20px;font-size:12px">Sin sinapsis latentes</div>';
        return;
    }

    list.innerHTML = latentes.map(l => {
        const escapedName = l.destino_concepto.replace(/'/g, "\\'");
        return `
        <div class="lat-card">
            <div class="lat-card-name" onclick="navigateToNode('${escapedName}')">${l.destino_concepto}</div>
            <div class="lat-card-meta">
                <span>p=${l.peso.toFixed(2)}</span>
                <span>${l.saltos} saltos</span>
                <span>${l.destino_categoria}</span>
            </div>
        </div>`;
    }).join('');
}

// ============================================================
// CRUD OPERATIONS
// ============================================================

async function desvincular(a, b) {
    if (!confirm(`¿Cortar sinapsis entre '${a}' y '${b}'?`)) return;
    const data = await api('/api/sinapsis', {
        method: 'DELETE',
        body: JSON.stringify({ origen: a, destino: b })
    });
    if (data.status === 'ok') {
        toast(`Sinapsis cortada: ${a} ↔ ${b}`, 'success');
        loadNodeExplorer(selectedNode);
    } else {
        toast('Error al cortar sinapsis', 'error');
    }
}

function showVincularModal() {
    const target = prompt('Concepto a vincular con:');
    if (!target || !selectedNode) return;
    vincularCon(target);
}

async function vincularCon(target) {
    const data = await api('/api/sinapsis', {
        method: 'POST',
        body: JSON.stringify({ origen: selectedNode, destino: target, tipo: 'manual' })
    });
    toast(data.mensaje || data.detail || 'Hecho', data.status === 'ok' ? 'success' : 'info');
    if (data.status === 'ok') loadNodeExplorer(selectedNode);
}

async function dormirNodo() {
    if (!selectedNode) return;
    if (!confirm(`¿Dormir nodo '${selectedNode}'?`)) return;
    toast('Función de dormir — próximamente', 'info');
}

async function eliminarNodo() {
    if (!selectedNode) return;
    if (!confirm(`⚠️ ELIMINAR nodo '${selectedNode}'?\nEsto borrará TODAS sus sinapsis, dimensiones y grupos.`)) return;
    toast('Función de eliminar — próximamente', 'info');
}

// ============================================================
// VISTA 1: CORTEZA
// ============================================================

async function loadCorteza() {
    const [estado, actividad] = await Promise.all([
        api('/api/corteza/estado'),
        api('/api/corteza/actividad?dias=7')
    ]);

    if (estado.error) return;

    document.getElementById('corteza-activos').textContent = estado.activos;
    document.getElementById('corteza-dormidos').textContent = estado.dormidos;
    document.getElementById('corteza-directas').textContent = estado.directas;
    document.getElementById('corteza-latentes').textContent = estado.latentes;
    document.getElementById('corteza-energia').textContent = `${estado.energia} / ${estado.energia_max}`;
    document.getElementById('corteza-energy-fill').style.width = `${estado.energia_pct}%`;
    document.getElementById('corteza-sueno').textContent = estado.ultimo_sueno;
    document.getElementById('corteza-latencia').textContent = `${estado.latencia_ms}ms`;

    document.getElementById('stat-activos').textContent = estado.activos;
    document.getElementById('stat-dormidos').textContent = estado.dormidos;

    // Categorías
    const catEl = document.getElementById('corteza-categorias');
    if (estado.categorias && estado.categorias.length > 0) {
        const max = Math.max(...estado.categorias.map(c => c.count));
        catEl.innerHTML = estado.categorias.map(c => `
            <div class="cat-row">
                <span class="cat-name">${c.nombre}</span>
                <div class="cat-bar"><div class="cat-fill" style="width:${(c.count/max)*100}%"></div></div>
                <span class="cat-count">${c.count}</span>
            </div>
        `).join('');
    }

    // Dimensiones
    const dimEl = document.getElementById('corteza-dimensiones');
    if (estado.dimensiones_top && estado.dimensiones_top.length > 0) {
        dimEl.innerHTML = estado.dimensiones_top.map(d => `
            <div class="dim-row">
                <span class="dim-eje">${d.eje}</span>
                <span class="dim-valor">${d.valor}</span>
                <span class="dim-count">${d.count}</span>
            </div>
        `).join('');
    }

    // Chart energía
    const energiaHistorial = actividad.energia_historial || actividad.historial || [];
    if (energiaHistorial.length > 0) {
        drawEnergyChart(energiaHistorial);
    }
}

function drawEnergyChart(historial) {
    const canvas = document.getElementById('chart-energia');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.parentElement.clientWidth;
    const h = canvas.height = 200;

    ctx.clearRect(0, 0, w, h);
    if (!historial || historial.length === 0) return;

    const maxE = Math.max(...historial.map(h => h.energia || 0), 1);
    const step = w / Math.max(historial.length - 1, 1);

    // Gradient
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, 'rgba(124,58,237,0.3)');
    grad.addColorStop(1, 'rgba(124,58,237,0.02)');

    ctx.beginPath();
    ctx.moveTo(0, h);
    historial.forEach((p, i) => {
        const x = i * step;
        const y = h - (p.energia / maxE) * (h - 20);
        ctx.lineTo(x, y);
    });
    ctx.lineTo(w, h);
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.beginPath();
    historial.forEach((p, i) => {
        const x = i * step;
        const y = h - (p.energia / maxE) * (h - 20);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = '#7c3aed';
    ctx.lineWidth = 2;
    ctx.stroke();
}

// ============================================================
// VISTA 3: LATENTES
// ============================================================

let latentesData = [];

async function loadLatentes() {
    const data = await api('/api/latentes?min_peso=0.3&max_saltos=3&limit=100');
    latentesData = data.resultados || [];
    document.getElementById('lat-total-view').textContent = latentesData.length;
    renderLatentesList(latentesData);
}

function renderLatentesList(items) {
    const el = document.getElementById('latentes-list-view');
    el.innerHTML = items.map(l => `
        <div class="latente-card">
            <div class="latente-route">
                <span style="cursor:pointer;color:var(--cyan)" onclick="navigateToNode('${l.origen.replace(/'/g, "\\'")}')">${l.origen}</span>
                <span class="latente-arrow">→</span>
                <span style="cursor:pointer;color:var(--cyan)" onclick="navigateToNode('${l.destino.replace(/'/g, "\\'")}')">${l.destino}</span>
            </div>
            <div class="latente-meta">
                <span>p=${l.peso.toFixed(3)}</span>
                <span>${l.saltos} saltos</span>
                <span>${l.tipo || 'latente'}</span>
            </div>
            <div class="latente-actions">
                <button class="btn-action" onclick="confirmarLatente('${l.origen}','${l.destino}')">✓ Confirmar</button>
                <button class="btn-action btn-danger" onclick="rechazarLatente('${l.origen}','${l.destino}')">✗ Rechazar</button>
            </div>
        </div>
    `).join('');
}

async function confirmarLatente(origen, destino) {
    await api('/api/latentes/confirmar', {
        method: 'POST', body: JSON.stringify({ origen, destino })
    });
    toast('Latente confirmada como directa', 'success');
    loadLatentes();
}

async function rechazarLatente(origen, destino) {
    await api('/api/latentes/rechazar', {
        method: 'POST', body: JSON.stringify({ origen, destino })
    });
    toast('Latente rechazada', 'success');
    loadLatentes();
}

async function batchLatentes(accion) {
    const items = latentesData.slice(0, 50);
    if (items.length === 0) return;
    if (!confirm(`${accion === 'confirmar' ? 'Confirmar' : 'Rechazar'} ${items.length} latentes?`)) return;
    await api('/api/latentes/batch', {
        method: 'POST',
        body: JSON.stringify({ accion, items: items.map(l => ({ origen: l.origen, destino: l.destino })) })
    });
    toast(`${items.length} latentes ${accion}das`, 'success');
    loadLatentes();
}

// ============================================================
// VISTA 4: COMUNIDADES
// ============================================================

async function loadComunidades() {
    const data = await api('/api/comunidades');
    const container = document.getElementById('comunidades-container');
    if (!data.comunidades || data.comunidades.length === 0) {
        container.innerHTML = '<div class="comunidades-empty"><p>Las comunidades se calculan durante "Consolidar Cerebro".</p></div>';
        return;
    }
    container.innerHTML = data.comunidades.map(c => `
        <div class="comunidad-card" onclick="loadComunidadNodos(${c.id})">
            <div class="comunidad-header">
                <span class="comunidad-id">Cluster ${c.id}</span>
                <span class="comunidad-count">${c.count} nodos</span>
            </div>
            <div class="comunidad-nodos">
                ${(c.nodos || []).slice(0, 8).map(n => `<span class="comunidad-nodo">${n}</span>`).join('')}
                ${c.count > 8 ? `<span class="comunidad-nodo">+${c.count - 8}</span>` : ''}
            </div>
        </div>
    `).join('');
}

// ============================================================
// VISTA 5: SUEÑOS
// ============================================================

async function loadSuenos() {
    const data = await api('/api/suenos/historial?limit=10');
    const container = document.getElementById('suenos-list');
    if (!data.historial || data.historial.length === 0) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:60px">No hay registros de sueño aún</div>';
        return;
    }
    container.innerHTML = data.historial.map(s => `
        <div class="sueno-card">
            <div class="sueno-header">
                <span class="sueno-fecha">${new Date(s.fecha * 1000).toLocaleDateString('es-AR')}</span>
            </div>
            <div class="sueno-stats">
                <div class="sueno-stat"><span class="sueno-stat-icon">🔄</span><span class="sueno-stat-label">Ciclos:</span><span class="sueno-stat-value">${s.ciclos}</span></div>
                <div class="sueno-stat"><span class="sueno-stat-icon">😴</span><span class="sueno-stat-label">Podidos:</span><span class="sueno-stat-value">${s.podidos || 0}</span></div>
                <div class="sueno-stat"><span class="sueno-stat-icon">🔗</span><span class="sueno-stat-label">Sinapsis creadas:</span><span class="sueno-stat-value">${s.sinapsis_creadas || 0}</span></div>
                <div class="sueno-stat"><span class="sueno-stat-icon">⚡</span><span class="sueno-stat-label">Energía:</span><span class="sueno-stat-value">${s.energia_final || '-'}</span></div>
            </div>
        </div>
    `).join('');
}

// ============================================================
// COMMAND PALETTE (Ctrl+K)
// ============================================================

const cmdPalette = document.getElementById('command-palette');
const cmdInput = document.getElementById('command-input');
const cmdResults = document.getElementById('command-results');

document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        cmdPalette.style.display = cmdPalette.style.display === 'none' ? 'flex' : 'none';
        if (cmdPalette.style.display === 'flex') {
            cmdInput.value = '';
            cmdInput.focus();
            cmdResults.innerHTML = '';
        }
    }
    if (e.key === 'Escape') cmdPalette.style.display = 'none';
});

document.querySelector('.command-backdrop')?.addEventListener('click', () => {
    cmdPalette.style.display = 'none';
});

cmdInput.addEventListener('input', async () => {
    const q = cmdInput.value.trim();
    if (q.length < 2) { cmdResults.innerHTML = ''; return; }
    const data = await api(`/api/buscar?q=${encodeURIComponent(q)}&limit=8`);
    cmdResults.innerHTML = (data.resultados || []).map(r => `
        <div class="search-result" onclick="cmdPalette.style.display='none';navigateToNode('${r.concepto.replace(/'/g, "\\'")}')">
            <span class="search-result-name">${r.concepto}</span>
        </div>
    `).join('');
});

// ============================================================
// CONSOLIDAR
// ============================================================

document.getElementById('btn-consolidar').addEventListener('click', async () => {
    if (!confirm('¿Ejecutar ciclo de consolidación (sueño)?')) return;
    toast('Consolidando...', 'info');
    const data = await api('/api/consolidar', { method: 'POST' });
    toast(data.mensaje || 'Consolidación completada', 'success');
    loadCorteza();
});

// ============================================================
// INIT
// ============================================================

loadCorteza();
