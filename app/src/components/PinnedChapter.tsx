import { useContext, useEffect, useLayoutEffect, useRef, type ReactNode } from 'react'
import { DiveContext } from './DiveStage'
import { gsap, ScrollTrigger, reducedMotionQuery } from '../lib/motion'

type Props = {
  id: string
  /** Scroll distance the chapter stays pinned, in viewport heights. */
  length?: number
  /** Called every frame with scrub progress 0..1. Drive the protagonist/timeline from this. */
  onProgress?: (p: number) => void
  /** Render prop gets a ref to a static (reduced-motion) flag via data attr; children read --p CSS var too. */
  children: ReactNode | ((p: { reduced: boolean }) => ReactNode)
  className?: string
  grid?: boolean
}

/**
 * Generic pinned, scrubbed chapter. Exposes progress as `--p` CSS variable on the section
 * and via onProgress. Under prefers-reduced-motion it renders unpinned at progress 1 (static).
 */
export function PinnedChapter({ id, length = 3, onProgress, children, className = '', grid = true }: Props) {
  const ref = useRef<HTMLElement>(null)
  const cb = useRef(onProgress)
  const dive = useContext(DiveContext)

  // Keep the callback ref current without accessing it during render
  useEffect(() => {
    cb.current = onProgress
  }, [onProgress])

  // Inside a DiveStage the stage drives position, depth and progress.
  useLayoutEffect(() => {
    if (!dive) return
    return dive.register({ el: ref.current!, length, onProgress: (p) => cb.current?.(p) })
  }, [dive, length])

  useEffect(() => {
    if (dive) return
    const el = ref.current!
    const mm = gsap.matchMedia()
    mm.add(
      { reduce: reducedMotionQuery, ok: `not all and ${reducedMotionQuery}` },
      (ctx) => {
        if (ctx.conditions?.reduce) {
          el.style.setProperty('--p', '1')
          el.style.setProperty('--enter', '1')
          cb.current?.(1)
          return
        }
        const st = ScrollTrigger.create({
          trigger: el,
          start: 'top top',
          end: `+=${length * 100}%`,
          pin: true,
          scrub: true,
          onUpdate: (self) => {
            el.style.setProperty('--p', self.progress.toFixed(4))
            cb.current?.(self.progress)
          },
        })
        // Scrubbed entrance: content rises as the chapter slides up, before it pins.
        const enter = ScrollTrigger.create({
          trigger: el,
          start: 'top bottom',
          end: 'top 25%',
          scrub: true,
          onUpdate: (self) => el.style.setProperty('--enter', self.progress.toFixed(4)),
        })
        return () => { st.kill(); enter.kill() }
      },
    )
    return () => mm.revert()
  }, [length, dive])

  const reduced = typeof window !== 'undefined' && window.matchMedia(reducedMotionQuery).matches
  return (
    <section
      ref={ref}
      id={id}
      data-chapter
      className={`${dive ? 'absolute inset-0 will-change-[transform,opacity]' : `relative h-screen w-full ${grid ? 'dotgrid' : ''}`} overflow-hidden ${className}`}
    >
      {typeof children === 'function' ? children({ reduced }) : children}
    </section>
  )
}
