import { useId, useMemo } from 'react'
import { landed, type Quote } from './engine'
import { QUOTES } from './fixture'

const W = 640, H = 380, L = 52, R = 20, T = 16, B = 36
const QMAX = 300, YMAX = 3600
const x = (q: number) => L + (q / QMAX) * (W - L - R)
const y = (v: number) => T + (1 - v / YMAX) * (H - T - B)

/** Where a (qty, ₹) point sits, in % of the chart box. Lets HTML overlays land on the curves. */
export const chartPoint = (q: number, v: number) => ({ left: (x(q) / W) * 100, top: (y(v) / H) * 100 })

function curve(q: Quote) {
  let prev = landed(q, 0)!
  let d = `M${x(0)},${y(prev)}`
  for (let i = 1; i <= QMAX; i++) {
    const v = landed(q, i)!
    if (q.packSize === 1 && !q.moq) continue // straight line
    if (v !== prev) d += `L${x(i)},${y(prev)}L${x(i)},${y(v)}`
    prev = v
  }
  return d + `L${x(QMAX)},${y(landed(q, QMAX)!)}`
}

type Props = {
  /** 0..1, how much of each curve is drawn (left to right). */
  draw?: number
  /** 0..1, visibility of the A/B crossover marker at 150 units. */
  cross?: number
  qty?: number | null
  winnerId?: string | null
  /** Quote ids that are late (drawn dashed in warn). */
  late?: string[]
  /** Quotes to plot. Defaults to fixture data (for the landing story). */
  quotes?: Quote[]
  className?: string
}

export function CostChart({ draw = 1, cross = 0, qty = null, winnerId = null, late = ['C'], quotes, className = '' }: Props) {
  const clip = useId()
  const plotW = W - L - R

  // Use provided quotes or default to fixture (landing page)
  const sourceQuotes = quotes ?? QUOTES
  const plotted = useMemo(() => sourceQuotes.filter(q => q.packSize), [sourceQuotes])
  const paths = useMemo(() => Object.fromEntries(plotted.map(q => [q.id, curve(q)])), [plotted])

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={`block h-auto w-full ${className}`}
      role="img"
      aria-label="Landed cost of each quote by order quantity."
    >
      <defs>
        <clipPath id={clip}>
          <rect x={L - 4} y={0} width={plotW * draw + 8} height={H} />
        </clipPath>
      </defs>

      {[0, 1000, 2000, 3000].map((v) => (
        <g key={v}>
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--line)" />
          <text x={L - 8} y={y(v) + 4} textAnchor="end" className="num" fontSize="11" fill="var(--muted)">
            {v === 0 ? '₹0' : `₹${v / 1000}k`}
          </text>
        </g>
      ))}
      {[0, 50, 100, 150, 200, 250, 300].map((q) => (
        <text key={q} x={x(q)} y={H - 14} textAnchor="middle" className="num" fontSize="11" fill="var(--muted)">
          {q}
        </text>
      ))}
      <text x={W - R} y={H - 1} textAnchor="end" fontSize="11" fill="var(--muted)">units ordered →</text>

      <g clipPath={`url(#${clip})`}>
        {plotted.map((q) => {
          const win = q.id === winnerId
          const isLate = late.includes(q.id)
          return (
            <path
              key={q.id}
              d={paths[q.id]}
              fill="none"
              stroke={win ? 'var(--signal)' : isLate ? 'var(--warn)' : 'var(--bone)'}
              strokeOpacity={win || isLate ? 1 : 0.55}
              strokeWidth={win ? 3 : 2}
              strokeDasharray={isLate ? '6 5' : undefined}
              strokeLinejoin="round"
            />
          )
        })}
      </g>
      {plotted.map((q) => {
        const v = landed(q, QMAX)!
        return (
          <text
            key={q.id}
            x={x(QMAX) - 4}
            y={y(v) - 8}
            textAnchor="end"
            fontSize="13"
            fontWeight="600"
            opacity={draw > 0.95 ? 1 : 0}
            fill={q.id === winnerId ? 'var(--signal)' : late.includes(q.id) ? 'var(--warn)' : 'var(--bone)'}
          >
            {q.id}{late.includes(q.id) ? ' · late' : ''}
          </text>
        )
      })}

      {cross > 0 && (
        <g opacity={cross} transform={`translate(${x(150)},${y(1700)})`}>
          <circle r="7" fill="none" stroke="var(--bone)" strokeWidth="1.5" />
          <text x="-12" y="-14" textAnchor="end" fontSize="12" fill="var(--bone)">
            A and B cross at 150
          </text>
        </g>
      )}

      {qty !== null && (
        <g>
          <line x1={x(qty)} x2={x(qty)} y1={T} y2={H - B} stroke="var(--muted)" strokeDasharray="2 4" />
          {plotted.map((q) => (
            <circle
              key={q.id}
              cx={x(qty)}
              cy={y(landed(q, qty)!) }
              r={q.id === winnerId ? 5 : 3.5}
              fill={q.id === winnerId ? 'var(--signal)' : late.includes(q.id) ? 'var(--warn)' : 'var(--bone)'}
            />
          ))}
          <text x={x(qty)} y={T + 12} dx="6" className="num" fontSize="12" fill="var(--bone)">
            {qty} units
          </text>
        </g>
      )}
    </svg>
  )
}
