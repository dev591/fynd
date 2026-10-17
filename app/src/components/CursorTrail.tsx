import { useEffect, useRef } from 'react'
import { prefersReducedMotion } from '../lib/motion'

type Dot = { x: number; y: number; size: number; age: number }

const LIFE = 1100 // ms
const MAX = 320

/**
 * Site-wide cursor trail: ink-drop blobs that swell then shrink behind the pointer, merged
 * by an SVG "goo" filter. Own implementation (canvas, no per-frame DOM nodes). Sits behind
 * all content, never over text. Off for touch devices and prefers-reduced-motion.
 */
export function CursorTrail() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current!
    if (prefersReducedMotion() || window.matchMedia('(pointer: coarse)').matches) {
      canvas.style.display = 'none'
      return
    }
    const ctx = canvas.getContext('2d')!
    const dots: Dot[] = []
    const m = { x: -100, y: -100, sx: -100, sy: -100, seen: false }
    let raf = 0, last = 0, color = '#c8381a'

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
    }
    const frame = (t: number) => {
      const dt = Math.min(48, t - (last || t))
      last = t
      m.sx += (m.x - m.sx) * 0.12
      m.sy += (m.y - m.sy) * 0.12
      const diff = Math.hypot(m.x - m.sx, m.y - m.sy)
      if (diff > 0.6 && dots.length < MAX) {
        const n = Math.min(3, Math.ceil(diff / 14))
        for (let i = 0; i < n; i++) {
          dots.push({
            x: m.sx + (Math.random() - 0.5) * 6,
            y: m.sy + (Math.random() - 0.5) * 6,
            size: Math.min(26, 4 + diff * 0.28),
            age: 0,
          })
        }
      }
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.fillStyle = color
      for (let i = dots.length - 1; i >= 0; i--) {
        const d = dots[i]
        d.age += dt
        const k = d.age / LIFE
        if (k >= 1) { dots.splice(i, 1); continue }
        // swell fast, then shrink slowly
        const r = d.size * (k < 0.25 ? k / 0.25 : (1 - (k - 0.25) / 0.75) ** 2)
        ctx.beginPath()
        ctx.arc(d.x, d.y, r, 0, Math.PI * 2)
        ctx.fill()
      }
      // Idle: stop the loop until the pointer moves again.
      raf = dots.length || diff > 0.6 ? requestAnimationFrame(frame) : 0
    }
    const wake = () => { if (!raf && !document.hidden) { last = 0; raf = requestAnimationFrame(frame) } }
    const move = (e: PointerEvent) => {
      if (!m.seen) { m.sx = e.clientX; m.sy = e.clientY; m.seen = true; color = getComputedStyle(document.documentElement).getPropertyValue('--signal').trim() || color }
      m.x = e.clientX
      m.y = e.clientY
      wake()
    }
    const vis = () => { if (document.hidden) { cancelAnimationFrame(raf); raf = 0 } }

    resize()
    window.addEventListener('pointermove', move, { passive: true })
    window.addEventListener('resize', resize)
    document.addEventListener('visibilitychange', vis)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', vis)
    }
  }, [])

  return (
    <>
      <svg width="0" height="0" className="absolute" aria-hidden>
        <filter id="goo">
          <feGaussianBlur in="SourceGraphic" stdDeviation="9" />
          <feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 24 -10" />
        </filter>
      </svg>
      <canvas
        ref={ref}
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0 h-screen w-screen opacity-20"
        style={{ filter: 'url(#goo)' }}
      />
    </>
  )
}
