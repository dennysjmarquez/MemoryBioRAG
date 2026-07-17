import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback, useRef } from 'react'
import { getEgoGraph, eliminarSinapsis } from '../../services/api'
import { ExplorarHeader } from '../../components/ExplorarHeader/ExplorarHeader'
import { NodeIdentityPanel } from '../../components/NodeIdentityPanel/NodeIdentityPanel'
import { ConnectionsPanel } from '../../components/ConnectionsPanel/ConnectionsPanel'
import { LatentesPanel } from '../../components/LatentesPanel/LatentesPanel'
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

  const historyRef = useRef<string[]>([])
  const historyIndexRef = useRef(-1)
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

  const handleSleep = useCallback(() => {
    alert('Función dormir — próximamente')
  }, [])

  const handleDelete = useCallback(() => {
    if (!node) return
    if (!confirm(`⚠️ ELIMINAR nodo '${node.concepto}'?\nEsto borrará TODAS sus sinapsis, dimensiones y grupos.`)) return
    alert('Función eliminar — próximamente')
  }, [node])

  const handleUnlink = useCallback(async (a: string, b: string) => {
    try {
      await eliminarSinapsis({ origen: a, destino: b })
      if (node) fetchNode(node.concepto)
    } catch (e) {
      console.error('Error al cortar sinapsis:', e)
    }
  }, [node, fetchNode])

  const handleLink = useCallback(() => {
    const target = prompt('Concepto a vincular con:')
    if (!target || !node) return
    alert('Función vincular — próximamente')
  }, [node])

  const canGoBack = historyIndexRef.current > 0
  const canGoForward = historyIndexRef.current < historyRef.current.length - 1
  const breadcrumbs = historyRef.current.slice(0, historyIndexRef.current + 1)

  if (loading) {
    return (
      <div className={styles.page}>
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
      </div>
    )
  }

  if (error || (!node && concepto)) {
    return (
      <div className={styles.page}>
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
      </div>
    )
  }

  if (!concepto) {
    return (
      <div className={styles.page}>
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
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <ExplorarHeader
        canGoBack={canGoBack}
        canGoForward={canGoForward}
        breadcrumbs={breadcrumbs}
        onSearch={navigateTo}
        onBack={goBack}
        onForward={goForward}
        onJumpToCrumb={jumpToCrumb}
      />
      <div className={styles.explorar3col}>
        <NodeIdentityPanel
          node={node}
          onSleep={handleSleep}
          onDelete={handleDelete}
        />
        <ConnectionsPanel
          connections={connections}
          currentNode={concepto}
          onNavigate={navigateTo}
          onUnlink={handleUnlink}
          onLink={handleLink}
        />
        <LatentesPanel
          latentes={latentes}
          onNavigate={navigateTo}
        />
      </div>
    </div>
  )
}

export default ExplorarPage