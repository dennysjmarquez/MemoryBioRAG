import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback, useRef } from 'react'
import { getEgoGraph, eliminarSinapsis, actualizarNodo, eliminarNodo, dormirNodo, fusionarNodos, crearSinapsis } from '../../services/api'
import { ExplorarHeader } from '../../components/ExplorarHeader/ExplorarHeader'
import { NodeIdentityPanel } from '../../components/NodeIdentityPanel/NodeIdentityPanel'
import { ConnectionsPanel } from '../../components/ConnectionsPanel/ConnectionsPanel'
import { LatentesPanel } from '../../components/LatentesPanel/LatentesPanel'
import { MergeModal } from '../../components/MergeModal/MergeModal'
import { SleepConfirm } from '../../components/SleepConfirm/SleepConfirm'
import { DeleteConfirm } from '../../components/DeleteConfirm/DeleteConfirm'
import { LinkModal } from '../../components/LinkModal/LinkModal'
import styles from './ExplorarPage.module.css'

interface EgoGraphResponse {
  center: {
    id: number
    concepto: string
    contenido: string
    peso: number
    estado: 'activo' | 'dormido'
    sinonimos: string
    ultimo_acceso: number
    creado_en: number
    categoria: string
    num_conexiones: number
    dimensiones: Record<string, string[]>
    grupos: { nombre: string; fuente: string }[]
  }
  connections: {
    direccion: string
    destino_concepto: string
    peso: number
    tipo: string
    creado_en: number
    ultimo_uso: number
    destino_categoria: string
    destino_peso: number
    destino_estado: string
    destino_preview: string
  }[]
  latentes: {
    destino_concepto: string
    peso: number
    saltos: number
    destino_categoria: string
    destino_preview: string
  }[]
  stats: {
    total_conexiones: number
    salientes: number
    entrantes: number
    latentes: number
  }
}

const ExplorarPage = () => {
  const { concepto } = useParams<{ concepto?: string }>()
  const navigate = useNavigate()
  const [node, setNode] = useState<EgoGraphResponse['center'] | null>(null)
  const [connections, setConnections] = useState<EgoGraphResponse['connections']>([])
  const [latentes, setLatentes] = useState<EgoGraphResponse['latentes']>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [mergeModalOpen, setMergeModalOpen] = useState(false)
  const [sleepConfirmOpen, setSleepConfirmOpen] = useState(false)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [linkModalOpen, setLinkModalOpen] = useState(false)

  const historyRef = useRef<string[]>([])
  const historyIndexRef = useRef(-1)
  const skipHistoryRef = useRef(false)
  const [_historyVersion, setHistoryVersion] = useState(0)
  const forceHistoryUpdate = useCallback(() => setHistoryVersion(v => v + 1), [])

  const fetchNode = useCallback(async (c: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getEgoGraph(c)
      setNode(data.center)
      setConnections(data.connections)
      setLatentes(data.latentes)
    } catch (err: any) {
      setError(err.message || 'Error cargando nodo')
      setNode(null)
      setConnections([])
      setLatentes([])
    } finally {
      setLoading(false)
    }
  }, [])

  const lastFetchedRef = useRef<string | undefined>(undefined)

  useEffect(() => {
    if (concepto && concepto !== lastFetchedRef.current) {
      lastFetchedRef.current = concepto
      fetchNode(concepto)

      if (skipHistoryRef.current) {
        skipHistoryRef.current = false
        forceHistoryUpdate()
        return
      }

      const hist = historyRef.current
      const idx = historyIndexRef.current
      const newHist = hist.slice(0, idx + 1)
      if (newHist[newHist.length - 1] !== concepto) {
        newHist.push(concepto)
      }
      historyRef.current = newHist
      historyIndexRef.current = newHist.length - 1
      forceHistoryUpdate()
    }
  }, [concepto, fetchNode, forceHistoryUpdate])

  const navigateTo = useCallback((nextConcepto: string) => {
    if (!nextConcepto.trim()) return
    navigate(`/explorar/${encodeURIComponent(nextConcepto)}`)
  }, [navigate])

  const goBack = useCallback(() => {
    const idx = historyIndexRef.current
    const hist = historyRef.current
    if (idx <= 0) return
    const prevConcepto = hist[idx - 1]
    if (!prevConcepto) return
    historyIndexRef.current = idx - 1
    skipHistoryRef.current = true
    forceHistoryUpdate()
    navigate(`/explorar/${encodeURIComponent(prevConcepto)}`)
  }, [navigate, forceHistoryUpdate])

  const goForward = useCallback(() => {
    const idx = historyIndexRef.current
    const hist = historyRef.current
    if (idx >= hist.length - 1) return
    const nextConcepto = hist[idx + 1]
    if (!nextConcepto) return
    historyIndexRef.current = idx + 1
    skipHistoryRef.current = true
    forceHistoryUpdate()
    navigate(`/explorar/${encodeURIComponent(nextConcepto)}`)
  }, [navigate, forceHistoryUpdate])

  const jumpToCrumb = useCallback((targetIndex: number) => {
    const hist = historyRef.current
    if (targetIndex < 0 || targetIndex >= hist.length) return
    const targetConcepto = hist[targetIndex]
    if (!targetConcepto) return
    historyIndexRef.current = targetIndex
    forceHistoryUpdate()
    navigate(`/explorar/${encodeURIComponent(targetConcepto)}`)
  }, [navigate, forceHistoryUpdate])

  const handleSleep = useCallback(async () => {
    if (!node) return
    try {
      await dormirNodo(node.concepto)
      setToast('😴 Nodo dormido')
      setTimeout(() => setToast(null), 4000)
      setSleepConfirmOpen(false)
      fetchNode(node.concepto)
    } catch (e: any) {
      setError(e.message || 'Error al dormir nodo')
    }
  }, [node, fetchNode])

  const handleDelete = useCallback(async () => {
    if (!node) return
    try {
      await eliminarNodo(node.concepto)
      setToast('🗑️ Nodo eliminado')
      setTimeout(() => setToast(null), 4000)
      setDeleteConfirmOpen(false)
      navigate('/explorar')
    } catch (e: any) {
      setError(e.message || 'Error al eliminar nodo')
    }
  }, [node, navigate])

  const handleUnlink = useCallback(async (a: string, b: string) => {
    try {
      await eliminarSinapsis({ origen: a, destino: b })
      if (node) fetchNode(node.concepto)
    } catch (e) {
      console.error('Error al cortar sinapsis:', e)
    }
  }, [node, fetchNode])

  const handleSaveContent = useCallback(async (contenido: string) => {
    if (!node) return
    try {
      await actualizarNodo(node.concepto, contenido)
      setToast('✓ Contenido actualizado')
      setTimeout(() => setToast(null), 4000)
      fetchNode(node.concepto)
    } catch (e: any) {
      setError(e.message || 'Error guardando contenido')
    }
  }, [node, fetchNode])

  const handleLink = useCallback(async (target: string) => {
    if (!node || !target.trim()) return
    try {
      await crearSinapsis({ origen: node.concepto, destino: target.trim(), peso: 0.5, tipo: 'manual' })
      setToast(`✏️ Vinculado con '${target.trim()}'`)
      setTimeout(() => setToast(null), 4000)
      setLinkModalOpen(false)
      fetchNode(node.concepto)
    } catch (e: any) {
      setError(e.message || 'Error al vincular')
    }
  }, [node, fetchNode])

  const handleMerge = useCallback(async (origen: string, destinos: string[]) => {
    try {
      const result = await fusionarNodos(origen, destinos)
      setToast(`🔗 ${result.mensaje}`)
      setTimeout(() => setToast(null), 4000)
      fetchNode(origen)
    } catch (e: any) {
      setError(e.message || 'Error al fusionar nodos')
    }
  }, [fetchNode])

  const canGoBack = historyIndexRef.current > 0
  const canGoForward = historyIndexRef.current < historyRef.current.length - 1
  const breadcrumbs = historyRef.current.slice(0, historyIndexRef.current + 1)

  if (loading) {
    return (
      <>
        <ExplorarHeader
          canGoBack={canGoBack}
          canGoForward={canGoForward}
          breadcrumbs={breadcrumbs}
          onSearch={navigateTo}
          onBack={goBack}
          onForward={goForward}
          onJumpToCrumb={jumpToCrumb}
        />
        <div className={styles.loading}>Cargando explorador...</div>
      </>
    )
  }

  if (error || (!node && concepto)) {
    return (
      <>
        <ExplorarHeader
          canGoBack={canGoBack}
          canGoForward={canGoForward}
          breadcrumbs={breadcrumbs}
          onSearch={navigateTo}
          onBack={goBack}
          onForward={goForward}
          onJumpToCrumb={jumpToCrumb}
        />
        <div className={styles.error}>
          Error cargando nodo: {error || 'Nodo no encontrado'}
        </div>
      </>
    )
  }

  if (!concepto) {
    return (
      <>
        <ExplorarHeader
          canGoBack={canGoBack}
          canGoForward={canGoForward}
          breadcrumbs={breadcrumbs}
          onSearch={navigateTo}
          onBack={goBack}
          onForward={goForward}
          onJumpToCrumb={jumpToCrumb}
        />
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>🧠</div>
          <p>Buscá un concepto para inspeccionarlo</p>
          <p className={styles.emptySub}>Escribí en el buscador o seleccioná de las categorías</p>
        </div>
      </>
    )
  }

  return (
    <>
      <ExplorarHeader
        canGoBack={canGoBack}
        canGoForward={canGoForward}
        breadcrumbs={breadcrumbs}
        onSearch={navigateTo}
        onBack={goBack}
        onForward={goForward}
        onJumpToCrumb={jumpToCrumb}
      />
      {node && (
        <div className={styles.toolbar}>
          <span className={styles.toolbarNodeName}>{node.concepto}</span>
          <div className={styles.toolbarRight}>
            <button className={styles.toolBtn} onClick={() => setLinkModalOpen(true)} title="Vincular con otro nodo">
              ✏️ Vincular
            </button>
            <button className={styles.toolBtn} onClick={() => setMergeModalOpen(true)} title="Fusionar con otros nodos">
              🔗 Fusionar
            </button>
            <button className={styles.toolBtn} onClick={() => setSleepConfirmOpen(true)} title="Dormir nodo">
              😴 Dormir
            </button>
            <button className={`${styles.toolBtn} ${styles.toolBtnDanger}`} onClick={() => setDeleteConfirmOpen(true)} title="Eliminar nodo">
              🗑️ Eliminar
            </button>
          </div>
        </div>
      )}
      <div className={styles.explorar3col}>
        <NodeIdentityPanel
          node={node}
          onSave={handleSaveContent}
        />
        <ConnectionsPanel
          connections={connections}
          currentNode={concepto}
          onNavigate={navigateTo}
          onUnlink={handleUnlink}
        />
        <LatentesPanel
          latentes={latentes}
          onNavigate={navigateTo}
        />
      </div>
      {toast && <div className={styles.toast}>{toast}</div>}
      {node && (
        <MergeModal
          open={mergeModalOpen}
          onOpenChange={setMergeModalOpen}
          origen={node.concepto}
          onMerge={handleMerge}
        />
      )}
      {node && (
        <SleepConfirm
          open={sleepConfirmOpen}
          onOpenChange={setSleepConfirmOpen}
          node={node}
          onConfirm={handleSleep}
        />
      )}
      {node && (
        <DeleteConfirm
          open={deleteConfirmOpen}
          onOpenChange={setDeleteConfirmOpen}
          node={node}
          onConfirm={handleDelete}
        />
      )}
      {node && (
        <LinkModal
          open={linkModalOpen}
          onOpenChange={setLinkModalOpen}
          currentNode={node.concepto}
          onLink={handleLink}
        />
      )}
    </>
  )
}

export default ExplorarPage