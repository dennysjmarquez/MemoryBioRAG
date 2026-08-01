import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback, useRef } from 'react'
import { getEgoGraph, eliminarSinapsis, actualizarNodo, eliminarNodo, dormirNodo, despertarNodo, fusionarNodos, crearSinapsis, procesarNodo } from '../../services/api'
import { ExplorarHeader } from '../../components/ExplorarHeader/ExplorarHeader'
import { NodeIdentityPanel } from '../../components/NodeIdentityPanel/NodeIdentityPanel'
import { ConnectionsPanel } from '../../components/ConnectionsPanel/ConnectionsPanel'
import { LatentesPanel } from '../../components/LatentesPanel/LatentesPanel'
import { MergeModal } from '../../components/MergeModal/MergeModal'
import { SleepConfirm } from '../../components/SleepConfirm/SleepConfirm'
import { DeleteConfirm } from '../../components/DeleteConfirm/DeleteConfirm'
import { LinkModal } from '../../components/LinkModal/LinkModal'
import { ProcessConfirm } from '../../components/ProcessConfirm/ProcessConfirm'
import { WakeUpConfirm } from '../../components/WakeUpConfirm/WakeUpConfirm'
import ActionFeedbackModal from '../../components/ActionFeedbackModal/ActionFeedbackModal'
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
    total_latentes: number
    salientes: number
    entrantes: number
    mostrando_conexiones: number
    mostrando_latentes: number
    offset_conexiones: number
    offset_latentes: number
  }
}

const ExplorarPage = () => {
  const { concepto } = useParams<{ concepto?: string }>()
  const navigate = useNavigate()
  const [node, setNode] = useState<EgoGraphResponse['center'] | null>(null)
  const [connections, setConnections] = useState<EgoGraphResponse['connections']>([])
  const [latentes, setLatentes] = useState<EgoGraphResponse['latentes']>([])
  const [stats, setStats] = useState<EgoGraphResponse['stats'] | null>(null)
  const [offsetConexiones, setOffsetConexiones] = useState(0)
  const [offsetLatentes, setOffsetLatentes] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [mergeModalOpen, setMergeModalOpen] = useState(false)
  const [sleepConfirmOpen, setSleepConfirmOpen] = useState(false)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [linkModalOpen, setLinkModalOpen] = useState(false)
  const [processConfirmOpen, setProcessConfirmOpen] = useState(false)
  const [wakeUpConfirmOpen, setWakeUpConfirmOpen] = useState(false)
  const [feedbackState, setFeedbackState] = useState<'closed' | 'loading' | 'success' | 'error'>('closed')
  const [feedbackTitle, setFeedbackTitle] = useState('')
  const [feedbackMessage, setFeedbackMessage] = useState('')
  const [feedbackDetail, setFeedbackDetail] = useState('')

  const historyRef = useRef<string[]>([])
  const historyIndexRef = useRef(-1)
  const skipHistoryRef = useRef(false)
  const [_historyVersion, setHistoryVersion] = useState(0)
  const forceHistoryUpdate = useCallback(() => setHistoryVersion(v => v + 1), [])

  const fetchNode = useCallback(async (c: string) => {
    setOffsetConexiones(0)
    setOffsetLatentes(0)
    setLoading(true)
    setError(null)
    try {
      const data = await getEgoGraph(c, 0, 0)
      setNode(data.center)
      setConnections(data.connections)
      setLatentes(data.latentes)
      setStats(data.stats)
    } catch (err: any) {
      setError(err.message || 'Error cargando nodo')
      setNode(null)
      setConnections([])
      setLatentes([])
      setStats(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadMoreConnections = useCallback(async () => {
    if (!node) return
    const nuevo = offsetConexiones + 50
    const data = await getEgoGraph(node.concepto, nuevo, offsetLatentes)
    setConnections(prev => [...prev, ...data.connections])
    setOffsetConexiones(nuevo)
    setStats(data.stats)
  }, [node, offsetConexiones, offsetLatentes])

  const loadMoreLatentes = useCallback(async () => {
    if (!node) return
    const nuevo = offsetLatentes + 50
    const data = await getEgoGraph(node.concepto, offsetConexiones, nuevo)
    setLatentes(prev => [...prev, ...data.latentes])
    setOffsetLatentes(nuevo)
    setStats(data.stats)
  }, [node, offsetConexiones, offsetLatentes])

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

  const handleProcess = useCallback(async () => {
    if (!node) return
    if (feedbackState === 'loading') return
    setProcessConfirmOpen(false)
    setFeedbackState('loading')
    setFeedbackTitle('Optimizando nodo')
    setFeedbackMessage('Evaluando conexiones con el motor de reflexión...')
    setFeedbackDetail('')
    try {
      const result = await procesarNodo(node.concepto)

      if (result.status === 'ya_procesado') {
        setFeedbackState('success')
        setFeedbackTitle('Ya optimizado')
        setFeedbackMessage(result.mensaje)
        setFeedbackDetail('No se gastaron tokens adicionales.')
        return
      }

      setFeedbackState('success')
      setFeedbackTitle('¡Listo!')

      const eliminados = result.eliminados || 0
      const ajustes = Math.max(0, (result.aplicados || 0) - eliminados)
      const lotes = result.lotes || 0
      const prefiltrados = result.prefiltrados || 0

      const lineas: string[] = []
      if (!result.completo) {
        lineas.push('Terminó con fallos de API en algún lote.')
      } else {
        lineas.push('Optimización terminada.')
      }
      if (eliminados > 0) lineas.push(`${eliminados} conexiones eliminadas`)
      if (ajustes > 0) lineas.push(`${ajustes} ajustes de metadata`)
      if (prefiltrados > 0) lineas.push(`${prefiltrados} cortes automáticos (sin IA)`)
      if (lotes > 0) lineas.push(`${lotes} lotes al motor`)
      if (lineas.length === 1) lineas.push('Sin cambios — el motor no encontró nada que corregir')

      setFeedbackMessage(lineas[0] ?? 'Optimización terminada.')
      setFeedbackDetail(lineas.slice(1).join('\n') || '')
      fetchNode(node.concepto)
    } catch (e: any) {
      setFeedbackState('error')
      setFeedbackTitle('Algo salió mal')
      const msg = e?.detail || e?.message || 'Error al optimizar nodo'
      setFeedbackMessage(msg)
    }
  }, [node, fetchNode, feedbackState])

  const handleWakeUp = useCallback(async () => {
    if (!node) return
    setWakeUpConfirmOpen(false)
    setFeedbackState('loading')
    setFeedbackTitle('Despertando nodo')
    setFeedbackMessage('Reactivando conexiones...')
    setFeedbackDetail('')
    try {
      await despertarNodo(node.concepto)
      setFeedbackState('success')
      setFeedbackTitle('¡Despertado!')
      setFeedbackMessage(`Nodo '${node.concepto}' reactivado`)
      setFeedbackDetail('')
      fetchNode(node.concepto)
    } catch (e: any) {
      setFeedbackState('error')
      setFeedbackTitle('Algo salió mal')
      const msg = e?.detail || e?.message || 'Error al despertar nodo'
      setFeedbackMessage(msg)
    }
  }, [node, fetchNode])

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
            {node.estado === 'dormido' ? (
              <button
                className={styles.toolBtn}
                disabled
                title="Despertá el nodo primero"
                style={{ opacity: 0.5, cursor: 'not-allowed' }}
              >
                ⚡ Optimizar
              </button>
            ) : (
              <button className={styles.toolBtn} onClick={() => setProcessConfirmOpen(true)}>
                ⚡ Optimizar
              </button>
            )}
            <button className={styles.toolBtn} onClick={() => setLinkModalOpen(true)}>
              ✏️ Vincular
            </button>
            <button className={styles.toolBtn} onClick={() => setMergeModalOpen(true)}>
              🔗 Fusionar
            </button>
            {node.estado === 'dormido' ? (
              <button className={`${styles.toolBtn} ${styles.toolBtnSuccess}`} onClick={() => setWakeUpConfirmOpen(true)}>
                🔔 Despertar
              </button>
            ) : (
              <button className={styles.toolBtn} onClick={() => setSleepConfirmOpen(true)}>
                😴 Dormir
              </button>
            )}
            <button className={`${styles.toolBtn} ${styles.toolBtnDanger}`} onClick={() => setDeleteConfirmOpen(true)}>
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
          totalReal={stats?.total_conexiones ?? connections.length}
          onLoadMore={loadMoreConnections}
          hasMore={stats ? stats.mostrando_conexiones >= 50 && connections.length < stats.total_conexiones : false}
        />
        <LatentesPanel
          latentes={latentes}
          onNavigate={navigateTo}
          totalReal={stats?.total_latentes ?? latentes.length}
          onLoadMore={loadMoreLatentes}
          hasMore={stats ? stats.mostrando_latentes >= 50 && latentes.length < stats.total_latentes : false}
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
      {node && (
        <ProcessConfirm
          open={processConfirmOpen}
          onOpenChange={setProcessConfirmOpen}
          node={node}
          onConfirm={handleProcess}
        />
      )}
      {node && (
        <WakeUpConfirm
          open={wakeUpConfirmOpen}
          onOpenChange={setWakeUpConfirmOpen}
          node={node}
          onConfirm={handleWakeUp}
        />
      )}
      <ActionFeedbackModal
        open={feedbackState !== 'closed'}
        state={feedbackState === 'closed' ? 'loading' : feedbackState}
        title={feedbackTitle}
        target={node?.concepto || ''}
        message={feedbackMessage}
        detail={feedbackDetail || undefined}
        onClose={() => setFeedbackState('closed')}
      />
    </>
  )
}

export default ExplorarPage