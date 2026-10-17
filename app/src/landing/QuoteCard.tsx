import { useRef, type CSSProperties } from 'react'
import type { Quote } from './engine'

type Props = { quote: Quote; tag?: 'blocked' | 'late' | null; className?: string; style?: CSSProperties }

/** One quote as it arrived: messy, in its own format. The protagonist's "broken" state. */
export function QuoteCard({ quote, tag = null, className = '', style }: Props) {
  const inner = useRef<HTMLDivElement>(null)
  const tilt = (x: number, y: number, ms: number) => {
    const el = inner.current!
    el.style.transitionDuration = `${ms}ms`
    el.style.transform = `perspective(600px) rotateX(${y}deg) rotateY(${x}deg)`
  }
  return (
    <div className={`${className}`} style={style}>
      <div
        ref={inner}
        className="pointer-events-auto w-44 rounded-lg border border-line bg-surface p-3 shadow-[0_12px_40px_-12px_rgb(40_30_10/var(--shadow))] transition-transform ease-out sm:w-52"
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect()
          tilt(((e.clientX - r.left) / r.width - 0.5) * 14, -((e.clientY - r.top) / r.height - 0.5) * 14, 60)
        }}
        onPointerLeave={() => tilt(0, 0, 400)}
      >
        <div className="label flex justify-between text-muted">
          <span>{quote.supplier}</span>
          <span>{quote.channel}</span>
        </div>
        <p className="mt-1.5 text-[15px] leading-snug text-bone">{quote.raw}</p>
        {tag === 'blocked' && <p className="label mt-2 text-error">Blocked · pack size unknown</p>}
        {tag === 'late' && <p className="label mt-2 text-warn">Late · needs exception</p>}
      </div>
    </div>
  )
}
