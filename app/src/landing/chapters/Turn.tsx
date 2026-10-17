import { useMemo, useState } from 'react'
import { PinnedChapter } from '../../components/PinnedChapter'
import { CostChart, chartPoint } from '../CostChart'
import { QuoteCard } from '../QuoteCard'
import { QtyControl } from '../QtyControl'
import { NEED, QUOTES } from '../fixture'
import { evaluate, inr, landed, naivePick, negotiation, type Row } from '../engine'
import { ease, lerp, seg } from '../scrub'

/** Where each messy card starts (in % of the chart box) before it collapses into its curve. */
const START: Record<string, { l: number; t: number; r: number }> = {
  A: { l: 2, t: 4, r: -7 },
  B: { l: 30, t: 30, r: 5 },
  C: { l: 54, t: 2, r: -3 },
  D: { l: 60, t: 44, r: 7 },
}
/** D has no curve. It ends parked in the empty lower-right of the chart, blocked. */
const D_END = { left: 64, top: 60 }

/** Chapter 3: cards become curves, the curves cross, and the judge drives the quantity. */
export function Turn() {
  const [p, setP] = useState(0)
  const [qty, setQty] = useState(NEED.qty)
  const [sheet, setSheet] = useState(false)
  const res = useMemo(() => evaluate(QUOTES, { ...NEED, qty }), [qty])

  const fly = ease(seg(p, 0.05, 0.35))
  const showQty = p >= 0.62
  const panel = seg(p, 0.62, 0.74)
  const live = p >= 0.7

  return (
    <PinnedChapter id="ch3" length={4} onProgress={setP}>
      <div className="mx-auto flex h-full max-w-6xl flex-col justify-center gap-5 px-6 pt-14 pb-6">
        <header className="rise">
          <p className="label text-muted">03 · The turn</p>
          <h2 className="display mt-1 text-[clamp(2rem,4.5vw,3.75rem)] leading-[1.05]">
            A quote isn't a price. It's a curve.
          </h2>
          <p className="mt-2 text-muted" style={{ opacity: seg(p, 0.15, 0.3) }}>
            Freight is where the line starts. Unit price is how steep it climbs. Pack size makes it climb in steps.
          </p>
        </header>

        <div className="grid items-center gap-6 md:grid-cols-[1.5fr_1fr]">
          <div className="relative">
            <CostChart
              draw={ease(seg(p, 0.2, 0.6))}
              cross={seg(p, 0.55, 0.66)}
              qty={showQty ? qty : null}
              winnerId={showQty ? (res.winner?.quote.id ?? null) : null}
            />
            <div className="pointer-events-none absolute inset-0" aria-hidden>
              {QUOTES.map((q) => {
                const s = START[q.id]
                const isD = !q.packSize
                const end = isD ? D_END : chartPoint(0, q.freight)
                return (
                  <QuoteCard
                    key={q.id}
                    quote={q}
                    tag={isD && fly > 0.5 ? 'blocked' : null}
                    className="absolute"
                    style={{
                      left: `${lerp(s.l, end.left, fly)}%`,
                      top: `${lerp(s.t, end.top, fly)}%`,
                      transformOrigin: '0 0',
                      transform: `rotate(${lerp(s.r, 0, fly)}deg) scale(${lerp(1, isD ? 0.85 : 0.2, fly)})`,
                      opacity: isD ? 1 : 1 - seg(fly, 0.6, 1),
                    }}
                  />
                )
              })}
            </div>
          </div>

          <div
            style={{ opacity: panel }}
            className={live ? '' : 'pointer-events-none'}
            inert={!live}
          >
            <Verdict qty={qty} rows={res.rows} winner={res.winner} pool={res.pool} tie={res.tie}
              excluded={res.cheaperExcluded} sheet={sheet} />
            <div className="mt-4">
              <QtyControl
                qty={qty}
                onQty={setQty}
                sheet={sheet}
                onSheet={setSheet}
                onReset={() => { setQty(NEED.qty); setSheet(false) }}
              />
            </div>
          </div>
        </div>
      </div>
    </PinnedChapter>
  )
}

type VerdictProps = {
  qty: number; rows: Row[]; winner: Row | null; pool: Row[]; tie: boolean; excluded: Row[]; sheet: boolean
}

function Verdict({ qty, rows, winner, pool, tie, excluded, sheet }: VerdictProps) {
  const rival = pool.find((r) => r !== winner)
  const deal = rival && winner && !tie ? negotiation(rival, winner) : null
  const naive = naivePick(QUOTES, { ...NEED, qty })
  const naiveCost = naive ? landed(naive, qty)! : 0
  const late = excluded[0]

  return (
    <div className="text-[14px] leading-snug">
      <p className="label text-muted">{qty} bolts · needed in {NEED.needInDays} days</p>
      <ul className="mt-2 divide-y divide-line border-y border-line">
        {rows.map((r) => {
          const win = r === winner || (tie && pool.slice(0, 2).includes(r))
          return (
            <li key={r.quote.id} className="flex items-center gap-3 py-1.5">
              <span className={`h-4 w-0.5 ${win ? 'bg-signal' : 'bg-transparent'}`} />
              <span className="w-4 font-medium">{r.quote.id}</span>
              <span
                className={`label flex-1 ${r.status === 'blocked' ? 'text-error' : r.status === 'exception' ? 'text-warn' : win ? 'text-bone' : 'text-muted'}`}
              >
                {r.status === 'blocked' ? `blocked · ${r.reason}` : r.status === 'exception' ? 'late · needs exception' : win ? (tie ? 'tie' : 'pick') : 'eligible'}
              </span>
              <span className="num">{r.landed === null ? '—' : inr(r.landed)}</span>
            </li>
          )
        })}
      </ul>

      <p className="mt-3 text-[17px]">
        {tie && winner
          ? <>A and B tie at <span className="num">{inr(winner.landed!)}</span>. One more bolt and A pulls ahead.</>
          : winner && <>Crossover picks <span className="font-semibold text-signal">{winner.quote.id}</span> at <span className="num">{inr(winner.landed!)}</span>.</>}
      </p>

      {sheet && naive && winner && (
        <p className="mt-2 rounded-md border border-line bg-surface px-3 py-2 text-muted">
          A sheet sorted by price per bolt picks <span className="text-bone">{naive.id}</span>.{' '}
          {naive.id !== winner.quote.id && naiveCost > winner.landed!
            ? <>That costs <span className="num text-error">{inr(naiveCost - winner.landed!)}</span> more at this quantity.</>
            : <>Right this time, by luck. It can't tell you the answer flips at 150.</>}
        </p>
      )}

      {deal && rival && (
        <p className="mt-2 text-muted">
          <span className="text-bone">{rival.quote.id}</span> wins this order if they cut
          {deal.freight !== null && <> freight by <span className="num text-bone">{inr(deal.freight)}</span> or</>}
          {' '}price by <span className="num text-bone">{inr(deal.perUnit)}</span> per bolt.
        </p>
      )}

      {late && winner && (
        <p className="mt-2 text-muted">
          <span className="text-warn">{late.quote.id}</span> would land at <span className="num">{inr(late.landed!)}</span> but
          arrives in {late.quote.leadDays} days. Saving given up: <span className="num">{inr(winner.landed! - late.landed!)}</span>.
          Only a written exception unlocks it.
        </p>
      )}
    </div>
  )
}
