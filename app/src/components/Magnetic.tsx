import { useRef, type ReactNode } from 'react'
import { prefersReducedMotion } from '../lib/motion'

/** Reactive wrapper: the child leans toward the cursor and springs back on leave. Plain CSS transform. */
export function Magnetic({ children, pull = 0.3, className = '' }: { children: ReactNode; pull?: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const set = (x: number, y: number, ms: number) => {
    const el = ref.current!
    el.style.transitionDuration = `${ms}ms`
    el.style.transform = `translate(${x}px, ${y}px)`
  }
  return (
    <span
      ref={ref}
      className={`inline-block transition-transform ease-out ${className}`}
      onPointerMove={(e) => {
        if (prefersReducedMotion()) return
        const r = ref.current!.getBoundingClientRect()
        set((e.clientX - (r.left + r.width / 2)) * pull, (e.clientY - (r.top + r.height / 2)) * pull, 80)
      }}
      onPointerLeave={() => set(0, 0, 450)}
    >
      {children}
    </span>
  )
}
