import { useRef, useEffect, useState } from 'react'
import styles from './LineChart.module.css'

interface DataPoint {
  timestamp: number
  energia: number
  total_nodos: number
  dormidos: number
  activos: number
  latencia_ms: number
  conceptos: Array<{ concepto: string; contenido: string }>
}

interface LineChartProps {
  title: string
  data: DataPoint[]
  height?: number
}

const LineChart = ({ title, data, height = 200 }: LineChartProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || data.length === 0) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)

    const width = rect.width
    const height = rect.height
    const pad = { top: 20, right: 40, bottom: 30, left: 50 }
    const plotWidth = width - pad.left - pad.right
    const plotHeight = height - pad.top - pad.bottom

    const draw = () => {
      ctx.clearRect(0, 0, width, height)

      const values = data.map(d => d.energia)
      const minVal = Math.min(...values)
      const maxVal = Math.max(...values)
      const range = maxVal - minVal || 1

      ctx.strokeStyle = 'rgba(255,255,255,0.05)'
      ctx.lineWidth = 1
      for (let i = 0; i <= 4; i++) {
        const y = pad.top + (plotHeight / 4) * i
        ctx.beginPath()
        ctx.moveTo(pad.left, y)
        ctx.lineTo(width - pad.right, y)
        ctx.stroke()

        const val = maxVal - (range / 4) * i
        ctx.fillStyle = 'var(--text-muted)'
        ctx.font = '10px system-ui'
        ctx.textAlign = 'right'
        ctx.fillText(val.toFixed(1), pad.left - 8, y + 3)
      }

      const xLabels = [0, Math.floor(data.length / 2), data.length - 1]
      ctx.fillStyle = 'var(--text-muted)'
      ctx.font = '10px system-ui'
      ctx.textAlign = 'center'
      xLabels.forEach(idx => {
        if (data[idx]) {
          const x = pad.left + (plotWidth / (data.length - 1)) * idx
          const date = new Date(data[idx].timestamp * 1000)
          const label = date.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' })
          ctx.fillText(label, x, height - pad.bottom + 18)
        }
      })

      const gradient = ctx.createLinearGradient(0, pad.top, 0, height - pad.bottom)
      gradient.addColorStop(0, 'rgba(88, 166, 255, 0.25)')
      gradient.addColorStop(1, 'rgba(88, 166, 255, 0)')

      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.moveTo(pad.left, height - pad.bottom)
      data.forEach((point, i) => {
        const x = pad.left + (plotWidth / (data.length - 1)) * i
        const y = pad.top + plotHeight - ((point.energia - minVal) / range) * plotHeight
        if (i === 0) ctx.lineTo(x, y)
        else ctx.lineTo(x, y)
      })
      ctx.lineTo(pad.left + plotWidth, height - pad.bottom)
      ctx.closePath()
      ctx.fill()

      ctx.strokeStyle = 'var(--accent-color)'
      ctx.lineWidth = 2
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      ctx.beginPath()
      data.forEach((point, i) => {
        const x = pad.left + (plotWidth / (data.length - 1)) * i
        const y = pad.top + plotHeight - ((point.energia - minVal) / range) * plotHeight
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      })
      ctx.stroke()

      if (hoverIndex !== null && data[hoverIndex]) {
        const point = data[hoverIndex]
        const x = pad.left + (plotWidth / (data.length - 1)) * hoverIndex
        const y = pad.top + plotHeight - ((point.energia - minVal) / range) * plotHeight

        ctx.fillStyle = 'var(--accent-color)'
        ctx.beginPath()
        ctx.arc(x, y, 6, 0, Math.PI * 2)
        ctx.fill()

        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 2
        ctx.stroke()

        const conceptos = point.conceptos?.map(c => c.concepto).join(', ') || 'Sin conceptos'
        const tooltip = [
          `Energ\u00eda: ${point.energia.toFixed(2)}`,
          `Activos: ${point.activos} | Dormidos: ${point.dormidos}`,
          `Conceptos: ${conceptos}`
        ]

        ctx.fillStyle = 'rgba(13, 17, 23, 0.95)'
        ctx.font = '11px system-ui'
        const lines = tooltip
        const tooltipWidth = Math.max(...lines.map(l => ctx.measureText(l).width)) + 16
        const tooltipHeight = lines.length * 16 + 8
        const tooltipX = Math.min(x + 10, width - 40 - tooltipWidth - 10)
        const tooltipY = Math.max(y - tooltipHeight - 10, pad.top + 10)

        ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight)

        ctx.fillStyle = 'var(--text-primary)'
        lines.forEach((line, i) => {
          ctx.fillText(line, tooltipX + 8, tooltipY + 16 + i * 16)
        })
      }
    }

    draw()
  }, [data, hoverIndex])

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = e.currentTarget
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left

    if (x < 50 || x > rect.width - 40) {
      setHoverIndex(null)
      return
    }

    const relativeX = x - 50
    const pWidth = rect.width - 50 - 40
    const index = Math.round((relativeX / pWidth) * (data.length - 1))
    const clamped = Math.max(0, Math.min(data.length - 1, index))
    setHoverIndex(clamped)
  }

  const handleMouseLeave = () => setHoverIndex(null)

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>{title}</h3>
      <div className={styles.canvasWrapper}>
        <canvas
          ref={canvasRef}
          width={800}
          height={height}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        />
      </div>
    </div>
  )
}

export default LineChart