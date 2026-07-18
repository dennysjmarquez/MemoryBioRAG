import { NavLink, Outlet } from "react-router-dom";
import styles from "./DashboardLayout.module.css";

const NAV_ITEMS = [
  { to: "/corteza", label: "Corteza", icon: "⚡" },
  { to: "/explorar", label: "Explorar", icon: "🔍" },
  { to: "/sinapsis", label: "Sinapsis", icon: "🔗" },
  { to: "/actividad", label: "Actividad", icon: "📈" },
  { to: "/dimensiones", label: "Dimensiones", icon: "🌐" },
];

export default function DashboardLayout() {
  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>🧠</span>
          <div className={styles.logoText}>
            <span className={styles.logoTitle}>BioRAG</span>
            <span className={styles.logoVersion}>v18.3 · Neuro-Visor</span>
          </div>
        </div>

        <nav className={styles.nav}>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.active : ""}`
              }
            >
              <span className={styles.navIcon}>{item.icon}</span>
              <span className={styles.navLabel}>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className={styles.sidebarFooter}>
          <div className={styles.statusIndicator}>
            <span className={styles.statusDot}></span>
            <span className={styles.statusText}>Sistema activo</span>
          </div>
        </div>
      </aside>

      <main className={styles.main}>
        <section className={styles.page}>
          <Outlet />
        </section>
      </main>
    </div>
  );
}
