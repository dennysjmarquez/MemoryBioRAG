import styles from './ConnectionCard.module.css'

type ConexionTipo = 'manual' | 'sinonimo_explicito' | 'co_ocurrencia' | 'rafaga_rememb' | 'co_nombre' | 'co_semantica'
type Direccion = 'saliente' | 'entrante' | 'bidireccional'

interface Props {
  concepto: string
  peso: number
  tipo: ConexionTipo
  direction?: Direccion
  onClick?: () => void
}

const TIPO_LABELS: Record<ConexionTipo, string> = {
  manual: 'Manual',
  sinonimo_explicito: 'Sinónimo',
  co_ocurrencia: 'Co-ocurrencia',
  rafaga_rememb: 'Ráfaga',
  co_nombre: 'Co-nombre',
  co_semantica: 'Co-semántica',
}

const DIRECTION_ICON: Record<Direccion, string> = {
  saliente: '→',
  entrante: '←',
  bidireccional: '↔',
}

const ConnectionCard = ({ concepto, peso, tipo, direction, onClick }: Props) => (
  <button className={styles.card} onClick={onClick}>
    <div className={styles.header}>
      <span className={`${styles.tipo} ${styles[tipo]}`}>
        {TIPO_LABELS[tipo]}
      </span>
      {direction && (
        <span className={`${styles.dir} ${styles[direction]}`}>
          {DIRECTION_ICON[direction]}
        </span>
      )}
    </div>
    <span className={styles.concepto}>{concepto}</span>
    <span className={styles.peso}>peso: {peso.toFixed(2)}</span>
  </button>
)

export default ConnectionCard
