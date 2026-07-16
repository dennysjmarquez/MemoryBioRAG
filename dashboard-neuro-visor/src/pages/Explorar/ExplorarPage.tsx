import { useParams } from 'react-router-dom'
import styles from './ExplorarPage.module.css'

const ExplorarPage = () => {
  const { concepto } = useParams()

  return (
    <div className={styles.page}>
      <h2>Explorar</h2>
      {concepto ? (
        <p className={styles.placeholder}>Inspector de nodo: <strong>{concepto}</strong></p>
      ) : (
        <p className={styles.placeholder}>Buscador de nodos y explorer de conexiones.</p>
      )}
    </div>
  )
}

export default ExplorarPage
