import { AlertDialog } from '@radix-ui/themes'
import type { EgoNode } from '../../types/explorar'

interface SleepConfirmProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  node: EgoNode
  onConfirm: () => void
}

export function SleepConfirm({ open, onOpenChange, node, onConfirm }: SleepConfirmProps) {
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Content style={{ maxWidth: 420 }}>
        <AlertDialog.Title>Dormir nodo</AlertDialog.Title>
        <AlertDialog.Description size="2">
          ¿Seguro que querés dormir <strong>{node.concepto}</strong>?
          <br /><br />
          El nodo pasará a estado inactivo. Su peso se reducirá y no aparecerá en búsquedas normales hasta que lo despierten.
        </AlertDialog.Description>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
          <AlertDialog.Cancel>
            <button style={{
              padding: '8px 16px', fontSize: 13, background: 'var(--bg-input)',
              border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)', cursor: 'pointer', fontFamily: 'inherit'
            }}>
              Cancelar
            </button>
          </AlertDialog.Cancel>
          <AlertDialog.Action>
            <button
              onClick={onConfirm}
              style={{
                padding: '8px 16px', fontSize: 13, background: '#6366f1',
                color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)',
                cursor: 'pointer', fontFamily: 'inherit', fontWeight: 500
              }}
            >
              😴 Dormir
            </button>
          </AlertDialog.Action>
        </div>
      </AlertDialog.Content>
    </AlertDialog.Root>
  )
}
