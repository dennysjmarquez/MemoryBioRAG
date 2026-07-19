import { useState, useEffect, useRef, useCallback } from 'react'
import { Dialog } from '@radix-ui/themes'
import { buscarNodos, getNodo, type BuscarNodoResult } from '../../services/api'
import styles from './MergeModal.module.css'

interface MergeModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  origen: string
  onMerge: (origen: string, destinos: string[]) => Promise<void>
}

export function MergeModal({ open, onOpenChange, origen, onMerge }: MergeModalProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<BuscarNodoResult[]>([])
  const [selected, setSelected] = useState<BuscarNodoResult[]>([])
  const [exactMatch, setExactMatch] = useState(false)
  const [searching, setSearching] = useState(false)
  const [merging, setMerging] = useState(false)
  const [confirmStep, setConfirmStep] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) {
      setQuery('')
      setResults([])
      setSelected([])
      setExactMatch(false)
      setConfirmStep(false)
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
      const filtered = data.resultados.filter(
        r => r.concepto !== origen && !selected.some(s => s.concepto === r.concepto)
      )
      setResults(filtered)
      setShowDropdown(filtered.length > 0)
    } catch {
      setResults([])
    } finally {
      setSearching(false)
    }
  }, [origen, selected])

  const validateExactMatch = useCallback(async (q: string) => {
    if (q.trim().length < 2 || q === origen || selected.some(s => s.concepto === q.trim())) {
      setExactMatch(false)
      return
    }
    try {
      await getNodo(q.trim())
      setExactMatch(true)
    } catch {
      setExactMatch(false)
    }
  }, [origen, selected])

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

  const addNode = (node: BuscarNodoResult) => {
    setSelected(prev => [...prev, node])
    setQuery('')
    setResults([])
    setExactMatch(false)
    setShowDropdown(false)
    setError('')
    inputRef.current?.focus()
  }

  const addExactMatch = () => {
    if (!query.trim() || !exactMatch) return
    const alreadySelected = selected.some(s => s.concepto === query.trim())
    if (alreadySelected || query.trim() === origen) return
    setSelected(prev => [...prev, { concepto: query.trim(), contenido: '', score: 1, estado: 'activo' }])
    setQuery('')
    setExactMatch(false)
    inputRef.current?.focus()
  }

  const removeNode = (concepto: string) => {
    setSelected(prev => prev.filter(s => s.concepto !== concepto))
  }

  const handleInputChange = (value: string) => {
    setQuery(value)
    setExactMatch(false)
    setError('')
  }

  const handleConfirmMerge = async () => {
    setMerging(true)
    setError('')

    // Validate all selected nodes still exist
    const valid: BuscarNodoResult[] = []
    const gone: string[] = []
    for (const node of selected) {
      try {
        await getNodo(node.concepto)
        valid.push(node)
      } catch {
        gone.push(node.concepto)
      }
    }

    if (gone.length > 0) {
      setSelected(valid)
      setError(`Estos nodos ya no existen: ${gone.join(', ')}. Se eliminaron de la selección.`)
      setMerging(false)
      return
    }

    try {
      await onMerge(origen, selected.map(s => s.concepto))
      onOpenChange(false)
    } finally {
      setMerging(false)
    }
  }

  const isDisabled = selected.length === 0 || merging
  const canAddExact = exactMatch && query.trim() !== origen && !selected.some(s => s.concepto === query.trim())

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content style={{ maxWidth: 480 }}>
        <Dialog.Title>Fusionar nodos en &ldquo;{origen}&rdquo;</Dialog.Title>
        <Dialog.Description size="2" mb="4">
          Seleccioná los nodos que querés fusionar. Sus sinapsis, dimensiones y WordNet se moverán al nodo origen.
        </Dialog.Description>

        {!confirmStep ? (
          <>
            <div className={styles.searchWrap}>
              <input
                ref={inputRef}
                type="text"
                className={styles.searchInput}
                placeholder="Buscar nodo para fusionar..."
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
                      onClick={() => addNode(r)}
                    >
                      <span className={styles.dropdownConcepto}>{r.concepto}</span>
                      <span className={styles.dropdownCat}>{r.categoria || r.estado}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {!showDropdown && canAddExact && (
              <button className={styles.addExactBtn} onClick={addExactMatch}>
                + Agregar &ldquo;{query.trim()}&rdquo;
              </button>
            )}

            {!showDropdown && !canAddExact && query.trim().length >= 2 && !searching && results.length === 0 && (
              <div className={styles.hintMsg}>No se encontró ningún nodo con ese nombre.</div>
            )}

            {error && <div className={styles.errorMsg}>{error}</div>}

            {selected.length > 0 && (
              <div className={styles.selectedList}>
                {selected.map(s => (
                  <span key={s.concepto} className={styles.tag}>
                    {s.concepto}
                    <button className={styles.tagRemove} onClick={() => removeNode(s.concepto)}>
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}

            <div className={styles.footer}>
              <Dialog.Close>
                <button className={styles.btnCancel}>Cancelar</button>
              </Dialog.Close>
              <button
                className={styles.btnMerge}
                disabled={isDisabled}
                onClick={() => setConfirmStep(true)}
              >
                Fusionar {selected.length > 0 ? `${selected.length} nodo(s)` : ''}
              </button>
            </div>
          </>
        ) : (
          <div className={styles.confirmStep}>
            <div className={styles.confirmIcon}>⚠️</div>
            <p className={styles.confirmText}>
              ¿Estás seguro? Los siguientes nodos se <strong>eliminarán</strong> y sus datos se moverán a &ldquo;{origen}&rdquo;:
            </p>
            <ul className={styles.confirmList}>
              {selected.map(s => (
                <li key={s.concepto}>
                  <strong>{s.concepto}</strong>
                  <span className={styles.confirmDetail}>
                    {s.categoria || 'sin categoría'} — {s.estado}
                  </span>
                </li>
              ))}
            </ul>
            <p className={styles.confirmWarning}>Esta acción no se puede deshacer.</p>

            {error && <div className={styles.errorMsg}>{error}</div>}

            <div className={styles.footer}>
              <button
                className={styles.btnCancel}
                onClick={() => setConfirmStep(false)}
                disabled={merging}
              >
                ← Volver
              </button>
              <button
                className={styles.btnConfirmDanger}
                disabled={merging}
                onClick={handleConfirmMerge}
              >
                {merging ? 'Validando...' : `Sí, fusionar ${selected.length} nodo(s)`}
              </button>
            </div>
          </div>
        )}
      </Dialog.Content>
    </Dialog.Root>
  )
}
