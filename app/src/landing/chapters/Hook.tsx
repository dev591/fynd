import { useEffect, useRef, useState } from 'react'
import { PinnedChapter } from '../../components/PinnedChapter'
import { QuoteCard } from '../QuoteCard'
import { QUOTES } from '../fixture'
import { prefersReducedMotion } from '../../lib/motion'

/** Scattered, tilted, each in its own format. They drift further apart as you scroll. */
const SPOTS = [
  { cls: 'left-[6%] top-[16%]', r: -8, dx: -60, dy: -30 },
  { cls: 'right-[7%] top-[20%]', r: 6, dx: 70, dy: -20 },
  { cls: 'left-[9%] bottom-[14%]', r: 5, dx: -50, dy: 40 },
  { cls: 'right-[10%] bottom-[12%]', r: -5, dx: 60, dy: 50 },
]

/** Chapter 1: one number, alone. Its weight follows the cursor. */
export function Hook() {
  const [p, setP] = useState(0)
  const num = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const el = num.current
    if (!el || prefersReducedMotion()) return
    let w = 400, target = 400, raf = 0
    const tick = () => {
      w += (target - w) * 0.15
      el.style.fontWeight = String(Math.round(w))
      raf = Math.abs(target - w) > 0.5 ? requestAnimationFrame(tick) : 0
    }
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect()
      const d = Math.hypot(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2))
      target = 300 + 500 * Math.max(0, 1 - d / Math.max(r.width, 300))
      if (!raf) raf = requestAnimationFrame(tick)
    }
    window.addEventListener('pointermove', move)
    return () => {
      window.removeEventListener('pointermove', move)
      cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <PinnedChapter id="ch1" length={1.6} onProgress={setP}>
      {QUOTES.map((q, i) => {
        const s = SPOTS[i]
        return (
          <QuoteCard
            key={q.id}
            quote={q}
            className={`absolute hidden md:block ${s.cls}`}
            style={{
              transform: `translate(${s.dx * p}px, ${s.dy * p}px) rotate(${s.r * (1 + p)}deg)`,
              opacity: 0.9 - p * 0.4,
            }}
          />
        )
      })}
      <div className="relative grid h-full place-items-center px-6 text-center">
        <div>
          <p className="label text-muted">Ramesh · purchase manager · 40-person fan factory</p>
          <span
            ref={num}
            className="display mt-2 block leading-none text-(length:--text-hook)"
            style={{ fontWeight: 400, letterSpacing: '-0.04em' }}
          >
            ₹50
          </span>
          <p className="mx-auto mt-6 max-w-[34ch] text-[clamp(1.1rem,2vw,1.4rem)] text-bone">
            That's what his spreadsheet overpaid on one order of 100 bolts.
          </p>
          <p className="mx-auto mt-2 max-w-[44ch] text-muted">
            It sorted four quotes by price per bolt. It looked clean, so his boss signed it.
          </p>
        </div>
        <p className="label absolute bottom-8 left-1/2 -translate-x-1/2 text-muted" style={{ opacity: 1 - p * 2 }}>
          Scroll ↓
        </p>
      </div>
    </PinnedChapter>
  )
}
