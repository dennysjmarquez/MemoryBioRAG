import { AlertDialog } from '@radix-ui/themes'
import type { EgoNode } from '../../types/explorar'

interface ProcessConfirmProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  node: EgoNode
  onConfirm: () => void
}

export function ProcessConfirm({ open, onOpenChange, node, onConfirm }: ProcessConfirmProps) {
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Content style={{ maxWidth: 420 }}>
        <AlertDialog.Title>Optimizar nodo</AlertDialog.Title>
        <AlertDialog.Description size="2">
          ¿Querés optimizar las conexiones de <strong>{node.concepto}</strong>?
          <br /><br />
          El motor de reflexión revisará:
          <br />• Conexiones débiles → candidatas a poda
          <br />• Dimensiones faltantes → candidatas a agregar
          <br />• Sinónimos obsoletos → candidatos a limpiar
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
              ⚡ Optimizar
            </button>
          </AlertDialog.Action>
        </div>
      </AlertDialog.Content>
    </AlertDialog.Root>
  )
}
