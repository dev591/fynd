import { useState, type ReactNode } from 'react'
import { Check } from 'lucide-react'
import { PinnedChapter } from '../../components/PinnedChapter'
import { QUOTES } from '../fixture'
import { inr, order } from '../engine'

/** Brief's pack-rounding example: need 100, pack of 12 at ₹120. */
const PACK = order({ ...QUOTES[0], packPrice: 120, packSize: 12, freight: 0 }, 100)!

const STEPS: { title: string; rule: string; example: ReactNode }[] = [
  {
    title: 'Same item?',
    rule: 'A quote for M8 bolts is not an offer for M10 bolts.',
    example: <>Order: M10 bolt. Quote: M8 bolt → <span className="text-error">blocked · different item</span></>,
  },
  {
    title: 'Pack size known?',
    rule: 'Without it, cost per unit is undefined. Never guessed.',
    example: <>Supplier D: ₹95 "per pack", size ? → <span className="text-error">blocked · pack size unknown</span></>,
  },
  {
    title: 'Work out the real order',
    rule: 'Buy at least the MOQ, then round up to whole packs.',
    example: (
      <>
        Need 100, packs of 12 at ₹120 → <span className="num text-bone">{PACK.packs}</span> packs,{' '}
        <span className="num text-bone">{PACK.units}</span> bolts,{' '}
        <span className="num text-warn">{PACK.overbuy}</span> extra. Landed{' '}
        <span className="num text-bone">{inr(PACK.landed)}</span>,{' '}
        <span className="num text-warn">{inr(PACK.overbuy * 10)}</span> of cash on a shelf.
      </>
    ),
  },
  {
    title: 'Landed cost, one tax basis',
    rule: 'Goods + freight, all ex-GST when GST is claimable.',
    example: <>₹10 + 18% GST vs ₹11.80 incl. GST → both <span className="num text-bone">₹1,000</span> ex-GST for 100. <span className="num">₹1,180</span> each if GST can't be claimed.</>,
  },
  {
    title: 'Delivery and capacity gates',
    rule: 'Late needs a written exception. Short supply only fits a split order.',
    example: <>Need in 5 days, C arrives in 7 → <span className="text-warn">needs exception</span>, with a reason and an approver.</>,
  },
]

/** Chapter 4: the five rules light up one per fifth of scroll. */
export function How() {
  const [p, setP] = useState(0)
  const active = Math.min(STEPS.length - 1, Math.floor(p * STEPS.length))

  return (
    <PinnedChapter id="ch4" length={3.4} onProgress={setP}>
      <div className="mx-auto grid h-full max-w-6xl items-center gap-10 px-6 py-16 md:grid-cols-[1fr_1fr]">
        <div className="rise">
          <p className="label text-muted">04 · How it works</p>
          <h2 className="display mt-1 text-[clamp(2rem,4.5vw,3.75rem)] leading-[1.05]">Five rules. Same order. Every quote.</h2>
          <ol className="mt-6 space-y-1">
            {STEPS.map((s, i) => (
              <li
                key={s.title}
                className={`flex items-center gap-3 border-l-2 py-1.5 pl-3 transition-colors duration-200 ${i === active ? 'border-signal text-bone' : 'border-line text-muted'}`}
              >
                <span className="num w-5 text-[13px]">{i < active ? <Check size={14} strokeWidth={1.5} /> : i + 1}</span>
                <span className="text-[17px]">{s.title}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="rounded-xl border border-line bg-surface p-6">
          <p className="label text-muted">Step {active + 1} of 5</p>
          <p className="mt-2 text-[clamp(1.1rem,1.8vw,1.35rem)] text-bone">{STEPS[active].rule}</p>
          <p className="mt-4 border-t border-line pt-4 text-[15px] text-muted">{STEPS[active].example}</p>
          <p className="num mt-6 text-[12px] leading-relaxed text-muted">
            packs = ⌈max(q, MOQ) ÷ pack size⌉<br />
            landed = packs × pack price + freight<br />
            winner = cheapest landed that passes every gate
          </p>
        </div>
      </div>
    </PinnedChapter>
  )
}
