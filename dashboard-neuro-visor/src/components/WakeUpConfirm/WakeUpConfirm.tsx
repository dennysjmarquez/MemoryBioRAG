import { AlertDialog } from '@radix-ui/themes'
import type { EgoNode } from '../../types/explorar'

interface WakeUpConfirmProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  node: EgoNode
  onConfirm: () => void
}

export function WakeUpConfirm({ open, onOpenChange, node, onConfirm }: WakeUpConfirmProps) {
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Content style={{ maxWidth: 420 }}>
        <AlertDialog.Title>Despertar nodo</AlertDialog.Title>
        <AlertDialog.Description size="2">
          ¿Seguro que querés despertar <strong>{node.concepto}</strong>?
          <br /><br />
          El nodo volverá a estado activo y recuperará su peso completo en las búsquedas.
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
                padding: '8px 16px', fontSize: 13, background: '#10b981',
                color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)',
                cursor: 'pointer', fontFamily: 'inherit', fontWeight: 500
              }}
            >
              🔔 Despertar
            </button>
          </AlertDialog.Action>
        </div>
      </AlertDialog.Content>
    </AlertDialog.Root>
  )
}