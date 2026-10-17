import { useState } from 'react'
import { PinnedChapter } from '../../components/PinnedChapter'
import { NEED, QUOTES } from '../fixture'
import { inr, landed, naivePick } from '../engine'
import { lerp, seg } from '../scrub'

/** Ramesh's sheet: price per bolt as he typed it ("per pack" read as per bolt), sorted ascending. */
const SHEET = QUOTES
  .map((q) => ({ q, perUnit: q.packPrice / (q.packSize ?? 1), total: landed(q, NEED.qty) }))
  .sort((a, b) => a.perUnit - b.perUnit)
const PICK = naivePick(QUOTES, NEED)!.id

const BEATS: [number, React.ReactNode][] = [
  [0, <>Four quotes for the same bolt. WhatsApp, email, a phone call. <span className="text-bone">None in the same format.</span></>],
  [0.2, <>Sorted by price per bolt, A looks cheapest. But the sheet never added freight. <span className="text-bone">A lands at ₹1,200. B lands at ₹1,150.</span></>],
  [0.45, <>C looks cheapest of all. <span className="text-bone">It arrives in 7 days.</span> The bolts are needed by Friday.</>],
  [0.6, <>D quoted ₹95 "per pack". <span className="text-bone">Nobody said how many bolts are in a pack.</span> It can't be compared at all.</>],
  [0.8, <>His boss signed it anyway, <span className="text-bone">because the spreadsheet looked clean.</span></>],
]

/** Chapter 2: scroll through Ramesh's sheet and watch every hidden difference surface. */
export function Cost() {
  const [p, setP] = useState(0)
  const beat = BEATS.reduce((acc, [at], i) => (p >= at ? i : acc), 0)
  const total = seg(p, 0.2, 0.35)
  const late = seg(p, 0.45, 0.55)
  const pack = seg(p, 0.6, 0.7)
  const sign = seg(p, 0.8, 0.9)

  return (
    <PinnedChapter id="ch2" length={3.4} onProgress={setP}>
      <div className="mx-auto grid h-full max-w-6xl items-center gap-10 px-6 py-16 md:grid-cols-[1fr_1.2fr]">
        <div className="rise">
          <p className="label text-muted">02 · The cost</p>
          <h2 className="display mt-1 text-[clamp(2rem,4.5vw,3.75rem)] leading-[1.05]">The sheet that looked right.</h2>
          <div className="relative mt-6 min-h-[7.5rem]">
            {BEATS.map(([, text], i) => (
              <p
                key={i}
                className="absolute inset-0 text-[clamp(1rem,1.6vw,1.2rem)] text-muted transition-opacity duration-300"
                style={{ opacity: beat === i ? 1 : 0 }}
                aria-hidden={beat !== i}
              >
                {text}
              </p>
            ))}
          </div>
          <p className="mt-4 text-[13px] text-muted" style={{ opacity: sign }}>
            Procol, an Indian procurement startup, says most of its target manufacturers still buy through phone, email and Excel.
          </p>
        </div>

        <div className="relative">
          <table className="num w-full border-collapse rounded-lg border border-line bg-surface text-left text-[14px]">
            <thead className="label text-muted">
              <tr className="border-b border-line">
                <th className="px-3 py-2 font-medium">Supplier</th>
                <th className="px-3 py-2 font-medium">₹ / bolt ↑</th>
                <th className="px-3 py-2 font-medium">Delivery</th>
                <th className="px-3 py-2 font-medium" style={{ opacity: total }}>Landed, 100</th>
              </tr>
            </thead>
            <tbody>
              {SHEET.map(({ q, perUnit, total: t }) => {
                const isC = q.leadDays > NEED.needInDays
                const isD = !q.packSize
                const struck = isC && late > 0.5
                return (
                  <tr key={q.id} className={`border-b border-line last:border-0 ${q.id === PICK ? 'bg-raised' : ''}`}>
                    <td className="px-3 py-2.5 font-sans">
                      {q.supplier}
                      {q.id === PICK && <span className="label ml-2 text-muted">← cheapest</span>}
                    </td>
                    <td className={`px-3 py-2.5 ${struck ? 'text-muted line-through' : ''}`}>
                      {perUnit.toFixed(2)}
                      {isD && <span className="ml-1 text-error" style={{ opacity: pack }}>per pack?</span>}
                    </td>
                    <td className={`px-3 py-2.5 ${isC ? '' : 'text-muted'}`}>
                      <span className={isC && late > 0 ? 'text-warn' : ''}>{q.leadDays} days</span>
                      {isC && <span className="label ml-2 text-warn" style={{ opacity: late }}>misses Fri</span>}
                    </td>
                    <td className="px-3 py-2.5" style={{ opacity: total }}>
                      {t === null
                        ? <span className="text-error" style={{ opacity: pack }}>can't compare</span>
                        : <span className={q.id === 'A' ? 'text-error' : q.id === 'B' ? 'text-success' : 'text-muted'}>{inr(t)}</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <div
            className="pointer-events-none absolute -right-2 -bottom-8 rounded-md border-2 border-error px-4 py-2 text-error"
            style={{ opacity: sign, transform: `rotate(-8deg) scale(${lerp(1.4, 1, sign)})` }}
            aria-hidden={sign < 0.5}
          >
            <p className="label">Approved · Supplier A</p>
            <p className="num text-[15px]">₹50 overpaid</p>
          </div>
        </div>
      </div>
    </PinnedChapter>
  )
}
