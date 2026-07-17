import { useState, useCallback, useEffect } from 'react'

export function useNavigationHistory() {
  const [history, setHistory] = useState<string[]>([])
  const [index, setIndex] = useState(-1)

  const navigateTo = useCallback((concepto: string) => {
    setHistory(prev => {
      const newHistory = prev.slice(0, index + 1)
      newHistory.push(concepto)
      return newHistory
    })
    setIndex(prev => prev + 1)
  }, [index])

  const goBack = useCallback(() => {
    if (index <= 0) return
    setIndex(prev => prev - 1)
  }, [index])

  const goForward = useCallback(() => {
    if (index >= history.length - 1) return
    setIndex(prev => prev + 1)
  }, [index, history.length])

  const jumpTo = useCallback((targetIndex: number) => {
    if (targetIndex < 0 || targetIndex >= history.length) return
    setIndex(targetIndex)
  }, [history.length])

  const currentNode = history[index] || null
  const canGoBack = index > 0
  const canGoForward = index < history.length - 1

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && e.key === 'ArrowLeft') {
        e.preventDefault()
        goBack()
      }
      if (e.altKey && e.key === 'ArrowRight') {
        e.preventDefault()
        goForward()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [goBack, goForward])

  const breadcrumbs = history.slice(0, index + 1)

  return {
    history,
    index,
    currentNode,
    canGoBack,
    canGoForward,
    navigateTo,
    goBack,
    goForward,
    jumpTo,
    breadcrumbs,
  }
}