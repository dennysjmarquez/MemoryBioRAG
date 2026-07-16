import { useNavigate } from 'react-router-dom'
import styles from './Breadcrumb.module.css'

interface Segment {
  label: string
  path?: string
}

interface Props {
  segments: Segment[]
}

const Breadcrumb = ({ segments }: Props) => {
  const navigate = useNavigate()

  return (
    <nav className={styles.breadcrumb}>
      {segments.map((seg, i) => (
        <span key={i}>
          {seg.path ? (
            <button className={styles.link} onClick={() => navigate(seg.path!)}>
              {seg.label}
            </button>
          ) : (
            <span className={styles.current}>{seg.label}</span>
          )}
          {i < segments.length - 1 && <span className={styles.sep}>/</span>}
        </span>
      ))}
    </nav>
  )
}

export default Breadcrumb
