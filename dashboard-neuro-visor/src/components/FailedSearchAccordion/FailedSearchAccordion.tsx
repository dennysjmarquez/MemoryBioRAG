import { useState } from 'react'
import styles from './FailedSearchAccordion.module.css'

interface FailedSearchItem {
  query: string
  freq: number
  ultima: number
  top_score: number
  ultima_hace: string
  params?: Record<string, unknown> | null
}

interface FailedSearchAccordionProps {
  items: FailedSearchItem[]
  loadingKey: string | null
  onCreateNode: (query: string) => void
  onClear?: () => void
  clearing?: boolean
}

const FailedSearchAccordion = ({ items, loadingKey, onCreateNode, onClear, clearing }: FailedSearchAccordionProps) => {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  const toggleExpand = (query: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(query)) {
        next.delete(query)
      } else {
        next.add(query)
      }
      return next
    })
  }

  const copyParams = (params: Record<string, unknown>) => {
    navigator.clipboard.writeText(JSON.stringify(params, null, 2))
  }

  if (items.length === 0) {
    return <div className={styles.empty}>No hay búsquedas fallidas recientes</div>
  }

  return (
    <>
      <div className={styles.list}>
        {items.map(item => {
          const isExpanded = expandedIds.has(item.query)
          const isLoading = loadingKey === item.query
          const hasParams = item.params && Object.keys(item.params).length > 0

          return (
            <div key={item.query} className={styles.item}>
              <div
                className={`${styles.header} ${isExpanded ? styles.headerExpanded : ''}`}
                onClick={() => toggleExpand(item.query)}
              >
                <span className={`${styles.chevron} ${isExpanded ? styles.chevronExpanded : ''}`}>
                  <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M4.18179 6.18181C4.35753 6.00608 4.64245 6.00608 4.81819 6.18181L7.49999 8.86362L10.1818 6.18181C10.3575 6.00608 10.6424 6.00608 10.8182 6.18181C10.9939 6.35755 10.9939 6.64247 10.8182 6.81821L7.81819 9.81821C7.73379 9.9026 7.61934 9.95001 7.49999 9.95001C7.38064 9.95001 7.26618 9.9026 7.18179 9.81821L4.18179 6.81821C4.00605 6.64247 4.00605 6.35755 4.18179 6.18181Z" fill="currentColor" fillRule="evenodd" clipRule="evenodd"></path>
                  </svg>
                </span>
                <div className={styles.headerInfo}>
                  <span className={styles.query}>{item.query}</span>
                  <span className={styles.meta}>
                    {item.freq}x · score {item.top_score} · {item.ultima_hace}
                  </span>
                </div>
                <button
                  className={styles.createBtn}
                  onClick={(e) => {
                    e.stopPropagation()
                    onCreateNode(item.query)
                  }}
                  disabled={isLoading}
                >
                  {isLoading ? '...' : 'Crear nodo'}
                </button>
              </div>

              {isExpanded && (
                <div className={styles.details}>
                  {hasParams ? (
                    <>
                      <div className={styles.paramsGrid}>
                        {renderParam('query', item.params?.query)}
                        {renderParam('parafrasis', item.params?.parafrasis)}
                        {renderParam('rafaga_palabras', item.params?.rafaga_palabras)}
                        {renderParam('forzar_rafaga', item.params?.forzar_rafaga)}
                        {renderParam('dimensiones', item.params?.dimensiones)}
                        {renderParam('deep', item.params?.deep)}
                        {renderParam('cat', item.params?.cat)}
                        {renderParam('dias', item.params?.dias)}
                        {renderParam('autor', item.params?.autor)}
                        {renderParam('modo_estricto', item.params?.modo_estricto)}
                        {renderParam('limite', item.params?.limite)}
                        {renderParam('asociados', item.params?.asociados)}
                        {renderParam('context_window', item.params?.context_window)}
                      </div>
                      <button
                        className={styles.copyBtn}
                        onClick={() => copyParams(item.params!)}
                      >
                        Copiar JSON
                      </button>
                    </>
                  ) : (
                    <div className={styles.noParams}>
                      Sin params guardados (log anterior a la implementación)
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
      {onClear && (
        <div className={styles.footer}>
          <button
            className={styles.clearBtn}
            onClick={onClear}
            disabled={clearing}
          >
            {clearing ? 'Limpiando...' : '🗑️ Limpiar historial (>7 días)'}
          </button>
        </div>
      )}
    </>
  )
}

function renderParam(key: string, value: unknown) {
  if (value === null || value === undefined) return null
  
  let displayValue: string
  if (typeof value === 'object') {
    displayValue = JSON.stringify(value)
  } else {
    displayValue = String(value)
  }

  return (
    <div key={key} className={styles.paramRow}>
      <span className={styles.paramKey}>{key}:</span>
      <span className={styles.paramValue}>{displayValue}</span>
    </div>
  )
}

export default FailedSearchAccordion
export type { FailedSearchItem }
