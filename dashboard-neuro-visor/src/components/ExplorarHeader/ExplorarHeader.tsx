import { useState, useEffect, useRef, ChangeEvent, KeyboardEvent } from 'react'
import { buscar } from '../../services/api'
import type { Nodo } from '../../types'
import styles from './ExplorarHeader.module.css'

interface SearchResult {
  concepto: string
  contenido: string
  score: number
}

interface ExplorarHeaderProps {
  canGoBack: boolean
  canGoForward: boolean
  breadcrumbs: string[]
  onSearch: (concepto: string) => void
  onBack: () => void
  onForward: () => void
  onJumpToCrumb: (index: number) => void
}

export function ExplorarHeader({
  canGoBack,
  canGoForward,
  breadcrumbs,
  onSearch,
  onBack,
  onForward,
  onJumpToCrumb,
}: ExplorarHeaderProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [showResults, setShowResults] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const searchContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setShowResults(false)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  const handleKeyDown = (e: KeyboardEvent) => {
    if (!showResults) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(prev => Math.min(prev + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(prev => Math.max(prev - 1, -1))
    } else if (e.key === 'Enter' && selectedIndex >= 0) {
      e.preventDefault()
      if (results[selectedIndex]) {
        onSearch(results[selectedIndex].concepto)
        setQuery(results[selectedIndex].concepto)
        setShowResults(false)
        setSelectedIndex(-1)
      }
    } else if (e.key === 'Escape') {
      setShowResults(false)
    }
  }

  useEffect(() => {
    if (!showResults) return
    const handler = (e: Event) => handleKeyDown(e as unknown as KeyboardEvent)
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [showResults, results, selectedIndex, onSearch])

  const handleSearchChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setQuery(value)
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current)
    if (value.trim().length < 2) {
      setShowResults(false)
      return
    }
    searchTimeoutRef.current = setTimeout(async () => {
      try {
        const data = await buscar(value)
        const mapped = (data.resultados || []).map((n: Nodo) => ({
          concepto: n.concepto,
          contenido: n.contenido || '',
          score: n.score_hibrido || 1.0
        }))
        setResults(mapped)
        setShowResults(true)
        setSelectedIndex(-1)
      } catch {
        setResults([])
        setShowResults(true)
      }
    }, 300)
  }

  const handleResultClick = (concepto: string) => {
    onSearch(concepto)
    setQuery(concepto)
    setShowResults(false)
  }

  const maxCrumbs = 5
  const displayCrumbs = breadcrumbs.length > maxCrumbs
    ? [breadcrumbs[0], '...', ...breadcrumbs.slice(breadcrumbs.length - 2)]
    : breadcrumbs

  return (
    <div className={styles.header} ref={searchContainerRef}>
      <div className={styles.searchContainer}>
        <input
          type="text"
          id="search-input"
          className={styles.searchInput}
          placeholder="Buscar concepto..."
          value={query}
          onChange={handleSearchChange}
          onFocus={() => query.trim().length >= 2 && setShowResults(true)}
          autoComplete="off"
        />
        {showResults && (
          <div className={styles.searchDropdown}>
            {results.length > 0 ? (
              results.map((r, i) => (
                <div
                  key={r.concepto}
                  className={`${styles.searchResult} ${i === selectedIndex ? styles.selected : ''}`}
                  onClick={() => handleResultClick(r.concepto)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className={styles.searchResultName}>{r.concepto}</span>
                    <span className={styles.searchResultScore}>{r.score.toFixed(3)}</span>
                  </div>
                  <div className={styles.searchResultPreview}>
                    {(r.contenido || '').substring(0, 100)}
                  </div>
                </div>
              ))
            ) : (
              <div className={styles.searchResult} style={{ color: 'var(--text-muted)' }}>
                Sin resultados
              </div>
            )}
          </div>
        )}
      </div>

      <div className={styles.navButtons}>
        <button
          className={`${styles.navBtnSm} ${!canGoBack ? styles.disabled : ''}`}
          onClick={onBack}
          disabled={!canGoBack}
          title="Atrás"
        >
          ◀
        </button>
        <button
          className={`${styles.navBtnSm} ${!canGoForward ? styles.disabled : ''}`}
          onClick={onForward}
          disabled={!canGoForward}
          title="Adelante"
        >
          ▶
        </button>
      </div>

      <div className={styles.breadcrumb}>
        {displayCrumbs.map((crumb, i) => {
          if (!crumb) return null
          const originalIndex = breadcrumbs.indexOf(crumb)
          if (crumb === '...') {
            return <span key={`sep-${i}`} className={styles.crumbSep}>…</span>
          }
          const isLast = i === displayCrumbs.length - 1
          const label = crumb.length > 25 ? crumb.substring(0, 22) + '...' : crumb
          return (
            <span key={`crumb-${i}-${crumb}`} className={`${styles.crumb} ${isLast ? styles.current : ''}`}>
              {i > 0 && displayCrumbs[i - 1] !== '...' && <span className={styles.crumbSep}>›</span>}
              {!isLast ? (
                <span onClick={() => onJumpToCrumb(originalIndex)} style={{ cursor: 'pointer' }}>
                  {i === 0 ? '🏠 ' : ''}{label}
                </span>
              ) : (
                <span style={{ color: 'var(--text)', cursor: 'default' }}>
                  {i === 0 ? '🏠 ' : ''}{label}
                </span>
              )}
            </span>
          )
        })}
      </div>
    </div>
  )
}