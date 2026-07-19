import { useState, useEffect, useRef, useCallback } from 'react'
import { Dialog } from '@radix-ui/themes'
import { buscarNodos, getNodo, type BuscarNodoResult } from '../../services/api'
import styles from './LinkModal.module.css'

interface LinkModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentNode: string
  onLink: (target: string) => void
}

export function LinkModal({ open, onOpenChange, currentNode, onLink }: LinkModalProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<BuscarNodoResult[]>([])
  const [selectedNode, setSelectedNode] = useState<BuscarNodoResult | null>(null)
  const [exactMatch, setExactMatch] = useState(false)
  const [searching, setSearching] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) {
      setQuery('')
      setResults([])
      setSelectedNode(null)
      setExactMatch(false)
      setShowDropdown(false)
      setError('')
    }
  }, [open])

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus()
    }
  }, [open])

  const search = useCallback(async (q: string) => {
    if (q.trim().length < 2) {
      setResults([])
      setShowDropdown(false)
      return
    }
    setSearching(true)
    try {
      const data = await buscarNodos(q, 10)
      const filtered = data.resultados.filter(r => r.concepto !== currentNode)
      setResults(filtered)
      setShowDropdown(filtered.length > 0)
    } catch {
      setResults([])
    } finally {
      setSearching(false)
    }
  }, [currentNode])

  // Validate exact match on text change (debounced)
  const validateExactMatch = useCallback(async (q: string) => {
    if (q.trim().length < 2 || q === currentNode) {
      setExactMatch(false)
      return
    }
    try {
      await getNodo(q.trim())
      setExactMatch(true)
    } catch {
      setExactMatch(false)
    }
  }, [currentNode])

  useEffect(() => {
    const timer = setTimeout(() => {
      search(query)
      validateExactMatch(query)
    }, 300)
    return () => clearTimeout(timer)
  }, [query, search, validateExactMatch])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const selectNode = (node: BuscarNodoResult) => {
    setQuery(node.concepto)
    setSelectedNode(node)
    setExactMatch(false)
    setShowDropdown(false)
    setError('')
  }

  const handleInputChange = (value: string) => {
    setQuery(value)
    setSelectedNode(null)
    setExactMatch(false)
    setError('')
  }

  const handleConfirm = async () => {
    const target = selectedNode?.concepto || query.trim()
    if (!target) return

    setSubmitting(true)
    setError('')
    try {
      await getNodo(target)
      onLink(target)
    } catch {
      setError(`El nodo "${target}" ya no existe. Buscá otro.`)
      setSelectedNode(null)
      setExactMatch(false)
    } finally {
      setSubmitting(false)
    }
  }

  const isButtonDisabled = (!selectedNode && !exactMatch) || submitting

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content style={{ maxWidth: 460 }}>
        <Dialog.Title>Vincular nodos</Dialog.Title>
        <Dialog.Description size="2" mb="4">
          Buscá y seleccioná el nodo que querés vincular con <strong>{currentNode}</strong>.
        </Dialog.Description>

        <div className={styles.searchWrap}>
          <input
            ref={inputRef}
            type="text"
            className={styles.searchInput}
            placeholder="Buscar nodo..."
            value={query}
            onChange={e => handleInputChange(e.target.value)}
            onFocus={() => results.length > 0 && setShowDropdown(true)}
          />
          {searching && <span className={styles.searchSpinner}>...</span>}

          {showDropdown && results.length > 0 && (
            <div ref={dropdownRef} className={styles.dropdown}>
              {results.map(r => (
                <button
                  key={r.concepto}
                  className={styles.dropdownItem}
                  onClick={() => selectNode(r)}
                >
                  <span className={styles.dropdownConcepto}>{r.concepto}</span>
                  <span className={styles.dropdownCat}>{r.categoria || r.estado}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {error && <div className={styles.errorMsg}>{error}</div>}

        {!selectedNode && !exactMatch && query.trim().length >= 2 && !searching && results.length === 0 && (
          <div className={styles.hintMsg}>No se encontró ningún nodo con ese nombre.</div>
        )}

        {selectedNode && (
          <div className={styles.selectedIndicator}>
            ✓ Seleccionado: <strong>{selectedNode.concepto}</strong>
          </div>
        )}

        {!selectedNode && exactMatch && (
          <div className={styles.selectedIndicator}>
            ✓ Nodo encontrado: <strong>{query.trim()}</strong>
          </div>
        )}

        <div className={styles.footer}>
          <Dialog.Close>
            <button className={styles.btnCancel}>Cancelar</button>
          </Dialog.Close>
          <button
            className={styles.btnLink}
            disabled={isButtonDisabled}
            onClick={handleConfirm}
          >
            {submitting ? 'Validando...' : '✏️ Vincular'}
          </button>
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
