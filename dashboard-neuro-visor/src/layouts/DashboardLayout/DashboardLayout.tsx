import { NavLink, Outlet } from 'react-router-dom'
import styles from './DashboardLayout.module.css'

const NAV_ITEMS = [
  { to: '/corteza', label: 'Corteza' },
  { to: '/explorar', label: 'Explorar' },
  { to: '/sinapsis', label: 'Sinapsis' },
  { to: '/actividad', label: 'Actividad' },
  { to: '/dimensiones', label: 'Dimensiones' },
]

export default function DashboardLayout() {
  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <h1 className={styles.title}>BioRAG Neuro-Visor</h1>
        <nav className={styles.nav}>
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
