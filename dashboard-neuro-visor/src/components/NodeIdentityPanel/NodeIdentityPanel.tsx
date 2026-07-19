import { useState, useRef, useEffect } from "react";
import { Tooltip } from "@radix-ui/themes";
import styles from "./NodeIdentityPanel.module.css";
import type { EgoNode } from "@/types/explorar";

interface NodeIdentityPanelProps {
  node: EgoNode | null;
  onSave?: (contenido: string) => void;
}

const timeAgo = (ts: number): string => {
  if (!ts) return "nunca";
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return `hace ${Math.floor(diff)}s`;
  if (diff < 3600) return `hace ${Math.floor(diff / 60)}min`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
  return `hace ${Math.floor(diff / 86400)}d`;
};

export function NodeIdentityPanel({
  node,
  onSave,
}: NodeIdentityPanelProps) {
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.setSelectionRange(
        textareaRef.current.value.length,
        textareaRef.current.value.length,
      );
    }
  }, [editing]);

  if (!node) return null;

  const handleEdit = () => {
    setEditContent(node.contenido || "");
    setEditing(true);
  };

  const handleCancel = () => {
    setEditing(false);
    setEditContent("");
  };

  const handleSave = async () => {
    if (!onSave) return;
    setSaving(true);
    try {
      await onSave(editContent);
      setEditing(false);
      setEditContent("");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.colIzq}>
      <div className={styles.nodeBadges}>
        <span className={styles.badgeLabel}>
          ESTADO:
          <Tooltip content={node.estado === "activo"
            ? "Activo: participa en búsquedas normales y aparece en resultados"
            : "Dormido: no aparece en búsquedas normales, pero sigue existiendo en la DB"}>
            <span
              className={`${styles.badge} ${node.estado === "activo" ? styles.badgeActivo : styles.badgeDormido}`}
            >
              {node.estado}
            </span>
          </Tooltip>
        </span>
        <span className={styles.badgeLabel}>
          CATEGORÍA:
          <Tooltip content="Categoría del nodo: Architecture, Cognition, General, Lesson, Personal, Principle, Profile, Project, Protocol, Relation, System">
            <span
              className={`${styles.badge} ${styles.badgeCat}`}
            >
              {node.categoria}
            </span>
          </Tooltip>
        </span>
      </div>
      <div className={styles.nodeMetaGrid}>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>⚖️ Peso</span>
          <span className={styles.metaValue}>{node.peso.toFixed(3)}</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>🔗 Conexiones</span>
          <span className={styles.metaValue}>{node.num_conexiones || 0}</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>⏱ Creado</span>
          <span className={styles.metaValue}>{timeAgo(node.creado_en)}</span>
        </div>
        <div className={styles.metaItem}>
          <span className={styles.metaLabel}>👁 Último acceso</span>
          <span className={styles.metaValue}>
            {timeAgo(node.ultimo_acceso)}
          </span>
        </div>
      </div>

      <div className={styles.nodeSection}>
        <div className={styles.sectionHeader}>
          <h4>📝 Contenido</h4>
          {onSave && !editing && (
            <button
              className={styles.editBtn}
              onClick={handleEdit}
              title="Editar contenido"
            >
              ✏️
            </button>
          )}
        </div>
        {editing ? (
          <>
            <textarea
              ref={textareaRef}
              className={styles.contentEditor}
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              placeholder="Escribí el contenido del nodo..."
              rows={6}
            />
            <div className={styles.editActions}>
              <button
                className={styles.btnSave}
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? "Guardando..." : "💾 Guardar"}
              </button>
              <button
                className={styles.btnCancel}
                onClick={handleCancel}
                disabled={saving}
              >
                Cancelar
              </button>
            </div>
          </>
        ) : (
          <div className={styles.contentBox}>{node.contenido || "(vacío)"}</div>
        )}
      </div>

      {Object.keys(node.dimensiones).length > 0 && (
        <div className={styles.nodeSection} id="section-dimensiones">
          <h4>🎭 Dimensiones</h4>
          <div className={styles.chipList}>
            {Object.entries(
              node.dimensiones as Record<string, string[]>,
            ).flatMap(([eje, vals]) =>
              vals.map((v, i) => (
                <span
                  key={`${eje}-${v}-${i}`}
                  className={`${styles.chip} ${styles.chipDim}`}
                  title={eje}
                >
                  {eje}.{v}
                </span>
              )),
            )}
          </div>
        </div>
      )}
      {node.grupos && node.grupos.length > 0 && (
        <div className={styles.nodeSection} id="section-wordnet">
          <h4>📚 WordNet</h4>
          <div className={styles.chipList}>
            {node.grupos.map(
              (g: { nombre: string; fuente: string }, i: number) => (
                <span
                  key={`${g.nombre}-${i}`}
                  className={`${styles.chip} ${styles.chipWn}`}
                  data-type={g.nombre}
                  title={g.fuente}
                >
                  {g.nombre}
                </span>
              ),
            )}
          </div>
        </div>
      )}
      {node.sinonimos && node.sinonimos.trim() && (
        <div className={styles.nodeSection} id="section-sinonimos">
          <h4>🏷️ Sinónimos</h4>
          <div className={styles.chipList}>
            {node.sinonimos.split(",").map((s: string, i: number) => (
              <span key={`${s.trim()}-${i}`} className={styles.chip}>
                {s.trim()}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
