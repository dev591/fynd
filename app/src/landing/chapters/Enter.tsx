import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { Magnetic } from '../../components/Magnetic'
import { PinnedChapter } from '../../components/PinnedChapter'
import { CostChart } from '../CostChart'
import { NEED } from '../fixture'
import { ease, lerp, seg } from '../scrub'

/** Chapter 6: the chart shrinks into a card, and the card is the way in. */
export function Enter() {
  const [p, setP] = useState(0)
  const shrink = ease(seg(p, 0, 0.5))
  const cta = seg(p, 0.45, 0.75)

  return (
    <PinnedChapter id="ch6" length={1.6} onProgress={setP}>
      <div className="grid h-full place-items-center px-6 py-16">
        <div className="rise w-full text-center" style={{ maxWidth: `${lerp(960, 440, shrink)}px` }}>
          <div
            className="rounded-2xl border p-5 text-left"
            style={{
              borderColor: `color-mix(in srgb, var(--line) ${shrink * 100}%, transparent)`,
              background: `color-mix(in srgb, var(--surface) ${shrink * 100}%, transparent)`,
            }}
          >
            <p className="label text-muted" style={{ opacity: shrink }}>Crossover · Ramesh's desk</p>
            <CostChart qty={NEED.qty} winnerId="B" className="mt-2" />
            <div style={{ opacity: cta }} inert={cta < 0.5}>
              <p className="mt-3 text-[15px] text-muted">
                100 bolts by Friday → <span className="text-bone">Supplier B, ₹1,150</span>, with every rejected quote explained.
              </p>
              <Magnetic className="mt-4 block" pull={0.15}>
                <Link
                  to="/login"
                  className="flex items-center justify-center gap-2 rounded-full bg-signal px-5 py-3 font-medium text-ink"
                >
                  Open the desk <ArrowRight size={18} strokeWidth={1.5} />
                </Link>
              </Magnetic>
            </div>
          </div>
          <p className="display mx-auto mt-8 max-w-[36ch] text-[clamp(1.25rem,2.4vw,1.75rem)] leading-snug" style={{ opacity: cta }}>
            Ramesh doesn't need more data. He needs the right order and a reason he can show his boss.
          </p>
        </div>
      </div>
    </PinnedChapter>
  )
}
