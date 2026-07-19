import { useState } from 'react'
import styles from './ConnectionsPanel.module.css'
import { ConnectionCard } from '../ConnectionCard/ConnectionCard'

const TIPO_OPTIONS = [
  { value: '', label: 'Todos los tipos' },
  { value: 'manual', label: 'manual' },
  { value: 'sinonimo_explicito', label: 'sinónimo explícito' },
  { value: 'co_ocurrencia', label: 'co-ocurrencia' },
  { value: 'rafaga_rememb', label: 'ráfaga' },
  { value: 'co_nombre', label: 'co-nombre' },
  { value: 'co_semantica', label: 'co-semántica' },
]

const ORDEN_OPTIONS = [
  { value: 'peso', label: 'Mayor peso' },
  { value: 'ultimo_uso', label: 'Más reciente' },
  { value: 'alfabeto', label: 'Alfabético' },
]

interface ConnectionsPanelProps {
  connections: {
    direccion: string
    destino_concepto: string
    peso: number
    tipo: string
    creado_en: number
    ultimo_uso: number
    destino_categoria: string
    destino_peso: number
    destino_estado: string
    destino_preview: string
  }[]
  currentNode: string
  onNavigate: (concepto: string) => void
  onUnlink: (a: string, b: string) => void
}

export function ConnectionsPanel({
  connections,
  currentNode,
  onNavigate,
  onUnlink,
}: ConnectionsPanelProps) {
  const [filterTipo, setFilterTipo] = useState('')
  const [filterOrden, setFilterOrden] = useState<'peso' | 'ultimo_uso' | 'alfabeto'>('peso')

  const filtered = connections
    .filter(c => !filterTipo || c.tipo === filterTipo)
    .sort((a, b) => {
      if (filterOrden === 'peso') return b.peso - a.peso
      if (filterOrden === 'ultimo_uso') return (b.ultimo_uso || 0) - (a.ultimo_uso || 0)
      return a.destino_concepto.localeCompare(b.destino_concepto)
    })

  return (
    <div className={styles.colCentro}>
      <div className={styles.colHeader}>
        <h3>🔗 Sinapsis Directas (<span id="conn-total">{connections.length}</span>)</h3>
      </div>
      <div className={styles.connFilters}>
        <select
          className={styles.filterSelect}
          value={filterTipo}
          onChange={e => setFilterTipo(e.target.value)}
        >
          {TIPO_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select
          className={styles.filterSelect}
          value={filterOrden}
          onChange={e => setFilterOrden(e.target.value as any)}
        >
          {ORDEN_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
      <div id="connections-list" className={styles.connectionsList}>
        {filtered.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '20px', fontSize: '13px' }}>
            Sin conexiones con este filtro
          </div>
        ) : (
          filtered.map((conn, i) => (
            <ConnectionCard
              key={`${conn.direccion}-${conn.destino_concepto}-${i}`}
              connection={conn}
              currentNode={currentNode}
              onNavigate={onNavigate}
              onUnlink={onUnlink}
            />
          ))
        )}
      </div>
    </div>
  )
}