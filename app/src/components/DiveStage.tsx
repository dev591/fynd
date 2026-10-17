import { createContext, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ScrollTrigger, prefersReducedMotion } from '../lib/motion'

/** One chapter as the stage sees it. */
export type DiveItem = { el: HTMLElement; length: number; onProgress: (p: number) => void }
export const DiveContext = createContext<{ register: (i: DiveItem) => () => void } | null>(null)

/** Scroll (in viewport heights) shared by two neighbouring chapters while one passes the camera. */
const OVERLAP = 0.7
const RINGS = 14

const clamp = (v: number) => Math.min(1, Math.max(0, v))
const ease = (t: number) => t * t * (3 - 2 * t)
const lerp = (a: number, b: number, t: number) => a + (b - a) * t

/**
 * "Dive" layout: every chapter lives on ONE fixed stage and scroll flies the camera forward.
 * The current chapter swells past the viewer and dissolves; the next one emerges from depth.
 * Chapters keep the same PinnedChapter API (length, onProgress, --p). Under prefers-reduced-motion
 * this renders a plain stacked page and chapters fall back to their static form.
 */
export function DiveStage({ children }: { children: ReactNode }) {
  const reduced = prefersReducedMotion()
  const root = useRef<HTMLDivElement>(null)
  const rings = useRef<HTMLDivElement>(null)
  const items = useRef<DiveItem[]>([])
  const [active, setActive] = useState(0)
  const [count, setCount] = useState(0)
  const ctx = useMemo(
    () => ({
      register: (i: DiveItem) => {
        items.current.push(i)
        return () => { items.current = items.current.filter((x) => x !== i) }
      },
    }),
    [],
  )

  useLayoutEffect(() => {
    if (reduced) return
    const list = items.current
    const n = list.length
    setCount(n)
    const starts: number[] = []
    let s = 0
    list.forEach((it, i) => { starts.push(s); s += it.length - (i < n - 1 ? OVERLAP : 0) })
    const total = s // scroll distance in viewport heights

    let lastActive = -1
    const apply = (g: number) => {
      let best = 0, bestScore = -1
      items.current.forEach((it, i) => {
        const l = g - starts[i]
        const enterK = i === 0 ? 1 : clamp(l / OVERLAP)
        const exitK = i === n - 1 ? 1 : clamp((it.length - l) / OVERLAP)
        const p = clamp(l / it.length)
        const alpha = Math.min(ease(enterK), ease(exitK))
        const scale = lerp(0.55, 1, ease(enterK)) * lerp(1.9, 1, ease(exitK))
        const blur = (1 - enterK) * 12 + (1 - exitK) * 16
        const el = it.el
        el.style.opacity = alpha.toFixed(3)
        el.style.transform = `scale(${scale.toFixed(4)})`
        el.style.filter = blur > 0.4 ? `blur(${blur.toFixed(1)}px)` : 'none'
        el.style.visibility = alpha < 0.01 ? 'hidden' : 'visible'
        el.style.pointerEvents = enterK > 0.5 && exitK > 0.5 ? 'auto' : 'none'
        el.style.zIndex = String(n - i)
        el.style.setProperty('--p', p.toFixed(4))
        el.style.setProperty('--enter', '1')
        it.onProgress(p)
        if (alpha > bestScore) { bestScore = alpha; best = i }
      })
      if (best !== lastActive) { lastActive = best; setActive(best) }
      // Rings rush outward: constant forward motion that never repeats a visible seam.
      const kids = rings.current?.children
      if (kids) {
        for (let j = 0; j < kids.length; j++) {
          const phase = ((j + g * 0.9) % RINGS + RINGS) % RINGS / RINGS
          const k = kids[j] as HTMLElement
          k.style.transform = `translate(-50%, -50%) scale(${(0.04 * 45 ** phase).toFixed(4)})`
          k.style.opacity = (Math.sin(phase * Math.PI) * 0.55).toFixed(3)
        }
      }
    }

    const st = ScrollTrigger.create({
      trigger: root.current,
      start: 'top top',
      end: `+=${total * 100}%`,
      pin: true,
      scrub: true,
      onUpdate: (self) => apply(self.progress * total),
    })
    apply(0)

    // Steer: the tunnel's vanishing point follows the cursor.
    const steer = (e: PointerEvent) => {
      const r = root.current!
      r.style.setProperty('--mx', String((e.clientX / window.innerWidth - 0.5) * 2))
      r.style.setProperty('--my', String((e.clientY / window.innerHeight - 0.5) * 2))
    }
    window.addEventListener('pointermove', steer, { passive: true })
    return () => { st.kill(); window.removeEventListener('pointermove', steer) }
  }, [reduced])

  if (reduced) return <DiveContext.Provider value={null}>{children}</DiveContext.Provider>

  return (
    <DiveContext.Provider value={ctx}>
      <div ref={root} className="relative h-screen w-full overflow-hidden" style={{ ['--mx' as string]: 0, ['--my' as string]: 0 }}>
        <div
          ref={rings}
          aria-hidden
          className="pointer-events-none absolute inset-0 transition-transform duration-500 ease-out"
          style={{ transform: 'translate(calc(var(--mx) * -22px), calc(var(--my) * -22px))' }}
        >
          {Array.from({ length: RINGS }, (_, j) => (
            <div
              key={j}
              className="absolute top-1/2 left-1/2 rounded-full border border-line"
              style={{ width: '100vmax', height: '100vmax', opacity: 0 }}
            />
          ))}
        </div>
        {children}
        <ol className="label absolute top-1/2 left-4 z-30 hidden -translate-y-1/2 flex-col gap-3 md:flex" aria-hidden>
          {Array.from({ length: count }, (_, i) => (
            <li key={i} className={`num transition-colors ${i === active ? 'text-signal' : 'text-muted'}`}>
              {i === active ? `0${i + 1}` : '·'}
            </li>
          ))}
        </ol>
      </div>
    </DiveContext.Provider>
  )
}
