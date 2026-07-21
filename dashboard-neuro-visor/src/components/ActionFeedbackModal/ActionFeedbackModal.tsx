import { Dialog } from '@radix-ui/themes'
import styles from './ActionFeedbackModal.module.css'

interface ActionFeedbackModalProps {
  open: boolean
  state: 'loading' | 'success' | 'error'
  title: string
  target: string
  message: string
  detail?: string
  onClose: () => void
}

const ActionFeedbackModal = ({ open, state, title, target, message, detail, onClose }: ActionFeedbackModalProps) => {
  return (
    <Dialog.Root open={open}>
      <Dialog.Content
        className={styles.overlay}
        onPointerDownOutside={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <div className={styles.card}>
          <div className={styles.iconArea}>
            {state === 'loading' && <div className={styles.spinner} aria-label="Cargando" />}
            {state === 'success' && <div className={`${styles.iconBase} ${styles.iconSuccess}`}>✓</div>}
            {state === 'error' && <div className={`${styles.iconBase} ${styles.iconError}`}>!</div>}
          </div>

          <h3 className={styles.title}>
            {state === 'loading' && `${title}`}
            {state === 'success' && '¡Listo!'}
            {state === 'error' && 'Algo salió mal'}
          </h3>

          {state === 'loading' && (
            <p className={styles.message}>{message}</p>
          )}
          {state !== 'loading' && target && (
            <span className={styles.targetChip}>{target}</span>
          )}
          {state !== 'loading' && (
            <p className={styles.message}>{message}</p>
          )}
          {detail && <p className={styles.detail}>{detail}</p>}

          {state !== 'loading' && (
            <button className={styles.acceptBtn} onClick={onClose}>
              Aceptar
            </button>
          )}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

export default ActionFeedbackModal
