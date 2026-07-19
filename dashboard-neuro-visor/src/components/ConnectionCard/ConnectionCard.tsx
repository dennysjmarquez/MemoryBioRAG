import { useState } from 'react'
import { AlertDialog } from '@radix-ui/themes'
import styles from './ConnectionCard.module.css'

const TIPO_COLORS: Record<string, string> = {
  manual: 'tipo-manual',
  sinonimo_explicito: 'tipo-sinonimo_explicito',
  co_ocurrencia: 'tipo-co_ocurrencia',
  rafaga_rememb: 'tipo-rafaga_rememb',
  co_nombre: 'tipo-co_nombre',
  co_semantica: 'tipo-co_semantica',
}

const DIR_SYMBOLS: Record<string, string> = {
  saliente: '→',
  entrante: '←',
  bidireccional: '↔',
}

const DIR_CLASSES: Record<string, string> = {
  saliente: 'dir-saliente',
  entrante: 'dir-entrante',
  bidireccional: 'dir-bidireccional',
}

interface ConnectionCardProps {
  connection: {
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
  }
  currentNode: string
  onNavigate: (concepto: string) => void
  onUnlink: (a: string, b: string) => void
}

export function ConnectionCard({
  connection,
  currentNode,
  onNavigate,
  onUnlink,
}: ConnectionCardProps) {
  const [unlinkConfirmOpen, setUnlinkConfirmOpen] = useState(false)
  const tipoClass = TIPO_COLORS[connection.tipo] || 'tipo-default'
  const dirSymbol = DIR_SYMBOLS[connection.direccion] || '?'
  const dirClass = DIR_CLASSES[connection.direccion] || ''
  const barWidth = Math.round(connection.peso * 100)

  const timeAgo = (ts: number): string => {
    if (!ts) return 'nunca'
    const diff = (Date.now() / 1000) - ts
    if (diff < 60) return `hace ${Math.floor(diff)}s`
    if (diff < 3600) return `hace ${Math.floor(diff / 60)}min`
    if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`
    return `hace ${Math.floor(diff / 86400)}d`
  }

  const handleClick = (e: React.MouseEvent) => {
    if (
      !(e.target as HTMLElement).closest('.conn-card-actions') &&
      !(e.target as HTMLElement).closest('.conn-card-name')
    ) {
      onNavigate(connection.destino_concepto)
    }
  }

  return (
    <div className={styles.connCard} onClick={handleClick}>
      <div className={styles.connCardHeader}>
        <span className={`${styles.connCardDir} ${dirClass}`}>{dirSymbol}</span>
        <span
          className={styles.connCardName}
          onClick={(e) => {
            e.stopPropagation()
            onNavigate(connection.destino_concepto)
          }}
        >
          {connection.destino_concepto}
        </span>
      </div>
      <div className={styles.connCardBar}>
        <div
          className={styles.connCardBarFill}
          style={{ width: `${barWidth}%` }}
        />
      </div>
      <div className={styles.connCardMeta}>
        <span className={`${styles.connCardTipo} ${tipoClass}`}>
          {connection.tipo}
        </span>
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '11px', color: 'var(--text)' }}>
          {connection.peso.toFixed(2)}
        </span>
        <span className={styles.connCardFecha}>{timeAgo(connection.ultimo_uso)}</span>
      </div>
      {connection.destino_preview && (
        <div className={styles.connCardPreview}>{connection.destino_preview}</div>
      )}
      <div className={styles.connCardActions}>
        <button
          className={`${styles.btnGo} ${styles.btnActionSm}`}
          onClick={(e) => {
            e.stopPropagation()
            onNavigate(connection.destino_concepto)
          }}
        >
          Ir →
        </button>
        <button
          className={`${styles.btnUnlink} ${styles.btnActionSm}`}
          onClick={(e) => {
            e.stopPropagation()
            setUnlinkConfirmOpen(true)
          }}
        >
          ✕ Cortar
        </button>
      </div>

      <AlertDialog.Root open={unlinkConfirmOpen} onOpenChange={setUnlinkConfirmOpen}>
        <AlertDialog.Content style={{ maxWidth: 400 }}>
          <AlertDialog.Title>Cortar sinapsis</AlertDialog.Title>
          <AlertDialog.Description size="2">
            ¿Cortar la sinapsis entre <strong>{currentNode}</strong> y <strong>{connection.destino_concepto}</strong>?
            <br /><br />
            La conexión se eliminará permanentemente.
          </AlertDialog.Description>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
            <AlertDialog.Cancel>
              <button style={{
                padding: '6px 12px', fontSize: 12, background: 'var(--bg-input)',
                border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)', cursor: 'pointer', fontFamily: 'inherit'
              }}>
                Cancelar
              </button>
            </AlertDialog.Cancel>
            <AlertDialog.Action>
              <button
                onClick={() => onUnlink(currentNode, connection.destino_concepto)}
                style={{
                  padding: '6px 12px', fontSize: 12, background: '#ef4444',
                  color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer', fontFamily: 'inherit', fontWeight: 500
                }}
              >
                ✕ Cortar
              </button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Root>
    </div>
  )
}