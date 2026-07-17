# Explorar — Panel de Inspección y Curación de Nodos

## Resumen
Migración exacta del panel "Explorar" del dashboard viejo (puerto 8011, `/mnt/recursos_compartidos_y_otros/MemoryBioRAG/dashboard/`) al nuevo dashboard React (`/mnt/recursos_compartidos_y_otros/MemoryBioRAG/dashboard-neuro-visor/`).

**URL**: `/explorar` (vacío) → `/explorar/:concepto` (inspector)

---

## Arquitectura

```
src/
├── pages/Explorar/
│   ├── ExplorarPage.tsx          # Página principal (router: /explorar, /explorar/:concepto)
│   └── ExplorarPage.module.css   # Layout 3 columnas + responsive
├── components/
│   ├── ExplorarHeader/           # Search autocomplete + nav buttons + breadcrumb
│   ├── NodeIdentityPanel/        # Columna IZQ: identidad, dimensiones, wordnet, sinónimos, contenido, actions
│   ├── ConnectionsPanel/         # Columna CENTRO: sinapsis directas con filtros (tipo, orden)
│   ├── LatentesPanel/            # Columna DER: sinapsis latentes
│   └── ConnectionCard/           # Tarjeta reutilizable para conexión directa
├── hooks/
│   ├── useNavigationHistory.ts   # Historial back/forward + breadcrumb + Alt+←/→
│   └── useApi.ts                 # Data fetching genérico (ya existía)
├── services/api.ts               # Endpoints: getEgoGraph, crearSinapsis, eliminarSinapsis, etc.
└── types/explorar.ts             # Tipos TypeScript: EgoNode, EgoConnection, EgoLatent, EgoGraphResponse, etc.
```

---

## Funcionalidades Implementadas

### 1. Header Explorar (`ExplorarHeader`)
- **Search autocomplete**: debounce 300ms, llama `GET /api/buscar?q=`, muestra score + preview 100 chars
- **Navegación teclado**: ↑/↓ selecciona, Enter navega, Escape cierra
- **Botones ◀ ▶**: back/forward con historial, disabled según posición
- **Breadcrumb clickeable**: máx 5 items, colapsa con `...`, click salta a posición
- **Shortcuts globales**: `Alt+←` / `Alt+→` para back/forward

### 2. Columna Izquierda — Identidad del Nodo (`NodeIdentityPanel`)
- State dot: verde (activo) / gris (dormido) con glow
- Título + badges: estado + categoría
- Grid metadata: Peso (3 decimales), Conexiones, Creado, Último acceso (relative time)
- Secciones colapsables:
  - **Dimensiones**: chips cyan `eje.valor`
  - **WordNet**: chips yellow `grupo` (tooltip fuente)
  - **Sinónimos**: chips purple
- **Contenido**: pre-wrap, max-height 180px, scroll
- **Actions**: 😴 Dormir, 🗑️ Eliminar (confirm modal)

### 3. Columna Centro — Sinapsis Directas (`ConnectionsPanel` + `ConnectionCard`)
- Header: contador + botón **+ Vincular** (prompt → POST `/api/sinapsis`)
- Filtros:
  - Tipo: manual, sinonimo_explicito, co_ocurrencia, rafaga_rememb, co_nombre, co_semantica
  - Orden: Mayor peso / Más reciente / Alfabético
- Tarjetas (`ConnectionCard`):
  - Dirección: → (naranja), ← (verde), ↔ (purple)
  - Nombre clickeable → navega
  - Barra de peso (gradient purple→cyan)
  - Badge tipo (colores por tipo)
  - Preview 2 líneas truncado
  - Actions: **Ir →** / **✕ Cortar** (confirm + DELETE `/api/sinapsis` + toast + refetch)

### 4. Columna Derecha — Latentes (`LatentesPanel`)
- Header: contador
- Lista: nombre (clickeable, purple) + meta `p=0.xx` `N saltos` `categoría` (JetBrains Mono)

### 5. Historial de Navegación (`useNavigationHistory`)
- Array `history[]` + `index`
- `navigateTo(concepto)`: trunca future history, push, incrementa index
- `goBack()` / `goForward()`: mueve index, navega por router
- `jumpToCrumb(i)`: salta a posición en breadcrumb
- Persiste en sesión (no en localStorage)

---

## Endpoints Backend Utilizados

| Función | Endpoint | Método |
|---------|----------|--------|
| Ego-graph (1 salto) | `/api/nodo/{concepto}/ego?limit=50` | GET |
| Buscar autocomplete | `/api/buscar?q=&limit=15` | GET |
| Crear sinapsis | `/api/sinapsis` | POST `{origen, destino, peso, tipo}` |
| Eliminar sinapsis | `/api/sinapsis` | DELETE `{origen, destino}` |
| Dormir nodo | `/api/nodo/{concepto}/dormir` | POST |
| Eliminar nodo | `/api/nodo/{concepto}` | DELETE |
| Consolidar cerebro | `/api/consolidar` | POST |

---

## Responsive Breakpoints

```css
@media (max-width: 1100px) {
  .explorar3col { grid-template-columns: 240px 1fr; }
  .col-der { display: none; }
}
@media (max-width: 900px) {
  .explorar3col { grid-template-columns: 1fr; }
  .col-izq, .col-der { display: none; }
}
```

---

## Estilos — Coherencia con Corteza

- Variables CSS globales (`globals.css`): `--bg`, `--bg-card`, `--purple`, `--cyan`, `--green`, `--orange`, `--red`, `--yellow`, `--border`, `--radius`, etc.
- CSS Modules co-localizados (sin `biorag.css` monolítico)
- Tipografía: Inter + JetBrains Mono
- Hover states: border `--purple-glow`, color `--purple`/`--cyan`
- Chips, badges, barras, scrollbars idénticos a Corteza

---

## Archivos Creados/Modificados

### Nuevos
- `src/types/explorar.ts`
- `src/hooks/useNavigationHistory.ts`
- `src/components/ExplorarHeader/ExplorarHeader.tsx` + `.module.css`
- `src/components/NodeIdentityPanel/NodeIdentityPanel.tsx` + `.module.css`
- `src/components/ConnectionsPanel/ConnectionsPanel.tsx` + `.module.css`
- `src/components/LatentesPanel/LatentesPanel.tsx` + `.module.css`
- `src/components/ConnectionCard/ConnectionCard.tsx` + `.module.css`
- `src/pages/Explorar/ExplorarPage.tsx` + `.module.css`

### Modificados
- `src/services/api.ts` — añadidos: `getEgoGraph`, `crearSinapsis`, `eliminarSinapsis`, `dormirNodo`, `eliminarNodo`, `actualizarSinapsis`, `despertarNodo`, `consolidarCerebro`
- `src/hooks/useApi.ts` — acepta `deps` array opcional

---

## Próximos Pasos (Fase 2)

1. **Modal "Vincular" accesible** (reemplazar `prompt()`)
2. **Toast notifications** (reemplazar `alert()`)
3. **Implementar Dormir/Eliminar nodo** (backend ya tiene endpoints)
4. **Command Palette (Ctrl+K)** — igual que dashboard viejo
5. **Tests** de integración con backend real