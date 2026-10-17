import { useMemo, useState } from 'react'
import { Check, X } from 'lucide-react'
import { PinnedChapter } from '../../components/PinnedChapter'
import { CostChart } from '../CostChart'
import { caseChecks, NEED, QUOTES } from '../fixture'
import { fingerprint } from '../engine'
import { seg } from '../scrub'

/** Chapter 5: the three scored case checks, actually run on page load. Nothing hardcoded. */
export function Proof() {
  const [p, setP] = useState(0)
  const run = useMemo(() => {
    const checks = caseChecks()
    // Same inputs, keys in a different order: the fingerprint must not change.
    const a = fingerprint({ need: NEED, quotes: QUOTES })
    const b = fingerprint({ quotes: QUOTES, need: NEED })
    return { checks, a, same: a === b, at: new Date().toLocaleTimeString() }
  }, [])
  const score = run.checks.reduce((s, c) => s + (c.pass ? c.points : 0), 0)

  return (
    <PinnedChapter id="ch5" length={2} onProgress={setP}>
      <div className="mx-auto grid h-full max-w-6xl items-center gap-10 px-6 py-16 md:grid-cols-[1fr_1fr]">
        <div className="rise">
          <p className="label flex items-center gap-2 text-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-live" /> 05 · Proof · ran in this browser at {run.at}
          </p>
          <h2 className="display mt-1 text-[clamp(2rem,4.5vw,3.75rem)] leading-[1.05]">
            <span className="num">{score}</span> of 25 points, checked.
          </h2>
          <ul className="mt-6 space-y-3">
            {run.checks.map((c, i) => (
              <li
                key={c.name}
                className="flex gap-3 rounded-lg border border-line bg-surface p-3"
                style={{ opacity: seg(p, i * 0.2, i * 0.2 + 0.2) }}
              >
                {c.pass
                  ? <Check className="mt-0.5 shrink-0 text-success" size={18} strokeWidth={1.5} />
                  : <X className="mt-0.5 shrink-0 text-error" size={18} strokeWidth={1.5} />}
                <div>
                  <p className="text-[15px] text-bone">
                    {c.name} <span className="num text-muted">· {c.points} pts · {c.pass ? 'pass' : 'fail'}</span>
                  </p>
                  <p className="text-[14px] text-muted">{c.detail}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="num mt-4 text-[12px] text-muted" style={{ opacity: seg(p, 0.6, 0.8) }}>
            decision fingerprint {run.a} · {run.same ? 'same inputs, same fingerprint' : 'MISMATCH'}
          </p>
        </div>
        <div className="rounded-xl border border-line bg-surface p-4">
          <CostChart qty={NEED.qty} winnerId="B" />
          <p className="mt-2 text-[14px] text-muted">
            100 bolts by Friday: <span className="text-signal">B at ₹1,150</span>. C excluded as late, D blocked, A ₹50 dearer.
          </p>
        </div>
      </div>
    </PinnedChapter>
  )
}
