import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'
import { ArrowRight, Check, ChevronDown } from 'lucide-react'
import { prefersReducedMotion } from '../lib/motion'
import { LiveFeed } from './Landing'

gsap.registerPlugin(ScrollTrigger)

/** The camera's journey, in px of depth. Each scene sits at its own depth and you fly through them as you scroll. */
const END = 6200

/** The messages a purchase manager actually gets. They drift past you in 3D on the way in. */
const CHAOS = [
  { t: '₹10 per bolt + ₹200 delivery', from: 'WhatsApp · 9:42', x: -34, y: -22, z: 900, r: -6 },
  { t: 'box of 50 for ₹400, free delivery, 7 days', from: 'Email', x: 30, y: -26, z: 1050, r: 5 },
  { t: '₹95 “per pack”', from: 'Phone call', x: -26, y: 24, z: 1250, r: 4 },
  { t: '₹11/pc, only ₹50 shipping', from: 'WhatsApp · 10:15', x: 36, y: 20, z: 1400, r: -4 },
  { t: 'GST extra 🙏', from: 'WhatsApp', x: -40, y: 2, z: 1600, r: -8 },
  { t: 'rate kal bataunga', from: 'Voice note', x: 12, y: -34, z: 1750, r: 3 },
  { t: 'min order 500 pcs', from: 'Email', x: 38, y: -4, z: 1900, r: 6 },
  { t: 'send PO first then price', from: 'WhatsApp', x: -18, y: 34, z: 2050, r: -3 },
  { t: 'delivery 5–7 days approx', from: 'SMS', x: 26, y: 32, z: 2200, r: 5 },
]

const SELLERS = Array.from({ length: 10 }, (_, i) => {
  const a = (i / 10) * Math.PI * 2 - Math.PI / 2
  return { x: Math.cos(a) * 38, y: Math.sin(a) * 30 }
})

/** Fade in from the distance, stay solid near you, fade as you pass through it. */
function visibility(rel: number) {
  if (rel < -1300 || rel > 650) return 0
  if (rel < -600) return (rel + 1300) / 700
  if (rel > 220) return 1 - (rel - 220) / 430
  return 1
}

export function Dive() {
  const track = useRef<HTMLDivElement>(null)
  const scene = useRef<HTMLDivElement>(null)
  const glow = useRef<HTMLDivElement>(null)
  const rail = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (prefersReducedMotion() || !track.current || !scene.current) return
    const lenis = new Lenis({ lerp: 0.085, wheelMultiplier: 0.9 })
    lenis.on('scroll', ScrollTrigger.update)
    const raf = (t: number) => lenis.raf(t * 1000)
    gsap.ticker.add(raf)
    gsap.ticker.lagSmoothing(0)

    const layers = Array.from(scene.current.querySelectorAll<HTMLElement>('[data-z]')).map(el => ({
      el, z: Number(el.dataset.z), x: Number(el.dataset.x ?? 0), y: Number(el.dataset.y ?? 0), r: Number(el.dataset.r ?? 0),
    }))
    const place = (p: number) => {
      const cam = p * END
      for (const l of layers) {
        const rel = cam - l.z
        const o = visibility(rel)
        l.el.style.opacity = String(o)
        l.el.style.visibility = o <= 0.001 ? 'hidden' : 'visible'
        l.el.style.transform = `translate3d(calc(-50% + ${l.x}vw), calc(-50% + ${l.y}vh), ${rel}px) rotate(${l.r * (1 - p)}deg)`
      }
      if (glow.current) glow.current.style.background =
        `radial-gradient(60% 50% at 50% 50%, color-mix(in srgb, var(--signal) ${8 + p * 22}%, transparent), transparent 70%)`
      if (rail.current) rail.current.style.transform = `scaleY(${p})`
    }
    place(0)
    const st = ScrollTrigger.create({ trigger: track.current, start: 'top top', end: 'bottom bottom', onUpdate: s => place(s.progress) })
    return () => { st.kill(); gsap.ticker.remove(raf); lenis.destroy() }
  }, [])

  const reduced = typeof window !== 'undefined' && prefersReducedMotion()

  return (
    <div ref={track} className={reduced ? '' : 'h-[760vh]'}>
      <div className={reduced ? 'space-y-24 py-24' : 'sticky top-0 h-screen overflow-hidden'} style={reduced ? undefined : { perspective: '1000px' }}>
        <div ref={glow} aria-hidden className="pointer-events-none absolute inset-0" />
        {!reduced && (
          <div aria-hidden className="absolute right-5 top-1/2 h-40 w-px -translate-y-1/2 bg-line">
            <div ref={rail} className="h-full w-px origin-top bg-signal" style={{ transform: 'scaleY(0)' }} />
          </div>
        )}
        <div ref={scene} className={reduced ? 'relative' : 'absolute inset-0'} style={{ transformStyle: 'preserve-3d' }}>
          <Scene z={0} reduced={reduced}>
            <p className="label mx-auto text-signal">For small manufacturers</p>
            <h1 className="display mt-3 text-[clamp(3rem,11vw,9rem)] leading-[0.92] tracking-tight">Stop chasing<br />quotes.</h1>
            <p className="mx-auto mt-5 max-w-[34ch] text-[clamp(1rem,1.8vw,1.25rem)] text-muted">
              Dive in. Watch one order go from a mess of messages to the right seller.
            </p>
            <ChevronDown className="mx-auto mt-10 animate-bounce text-muted" size={28} />
          </Scene>

          {CHAOS.map(m => (
            <div key={m.t} data-z={m.z} data-x={m.x} data-y={m.y} data-r={m.r}
              className={`${reduced ? 'mx-auto my-3 max-w-xs' : 'absolute left-1/2 top-1/2 w-[min(19rem,70vw)]'} rounded-2xl rounded-bl-sm border border-line bg-surface px-4 py-3 shadow-[0_20px_50px_-20px_rgba(0,0,0,.8)]`}>
              <p className="text-[15px] text-bone">{m.t}</p>
              <p className="mt-1 text-[11px] text-muted">{m.from}</p>
            </div>
          ))}
          <Scene z={1650} reduced={reduced}>
            <h2 className="display text-[clamp(2.2rem,6vw,4.8rem)] leading-tight">Every seller quotes<br />differently.</h2>
            <p className="mx-auto mt-4 max-w-[38ch] text-muted">Per piece, per box, GST or not, freight hidden in a voice note. A spreadsheet picks the wrong one.</p>
          </Scene>

          <Scene z={3200} reduced={reduced}>
            <div className="relative mx-auto h-[min(70vh,34rem)] w-[min(92vw,56rem)]">
              <svg className="absolute inset-0 h-full w-full" viewBox="-50 -50 100 100" preserveAspectRatio="none" aria-hidden>
                {SELLERS.map((s, i) => (
                  <line key={i} x1="0" y1="0" x2={s.x} y2={s.y} stroke="var(--signal)" strokeWidth="0.25" strokeDasharray="1.2 1.2" className="dive-beam" style={{ animationDelay: `${i * 0.12}s` }} />
                ))}
              </svg>
              {SELLERS.map((s, i) => (
                <span key={i} className="absolute grid h-9 w-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-live/60 bg-live/15 text-[10px] font-semibold text-live"
                  style={{ left: `${50 + s.x}%`, top: `${50 + s.y}%` }}>
                  <span className="absolute inset-0 animate-ping rounded-full bg-live/20" style={{ animationDelay: `${i * 0.2}s` }} />S{i + 1}
                </span>
              ))}
              <div className="absolute left-1/2 top-1/2 w-[min(22rem,80vw)] -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-signal/60 bg-surface p-6 text-left shadow-[0_30px_80px_-30px_var(--signal)]">
                <p className="label text-signal">Your request</p>
                <p className="display mt-1 text-[clamp(1.6rem,3.4vw,2.4rem)] leading-tight">100 × M10 bolt</p>
                <p className="text-muted">by Friday · fastest</p>
              </div>
            </div>
            <h2 className="display mt-6 text-[clamp(1.8rem,4.5vw,3.4rem)]">Say it once. Every seller who stocks it hears it.</h2>
          </Scene>

          <Scene z={4700} reduced={reduced} wide>
            <div className="grid items-center gap-8 text-left md:grid-cols-[1fr_1.1fr]">
              <div>
                <h2 className="display text-[clamp(2rem,5vw,4rem)] leading-tight">Quotes land side by side.</h2>
                <p className="mt-3 max-w-[34ch] text-muted">Names stay hidden, so sellers compete on the offer. Freight, packs and GST are already counted.</p>
              </div>
              <LiveFeed />
            </div>
          </Scene>

          <Scene z={END} reduced={reduced}>
            <p className="label mx-auto text-signal">The answer</p>
            <h2 className="display mt-2 text-[clamp(2.6rem,8vw,6.5rem)] leading-[0.95]">Seller 2.<br /><span className="text-signal">₹1,150</span> to your door.</h2>
            <ul className="mx-auto mt-6 flex max-w-3xl flex-wrap justify-center gap-2">
              {['₹50 less than the spreadsheet’s pick', 'Arrives before Friday', 'No extra units to pay for'].map(t => (
                <li key={t} className="flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2 text-[14px]">
                  <Check size={15} className="text-success" />{t}
                </li>
              ))}
            </ul>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link to="/login" className="flex items-center gap-2 rounded-full bg-signal px-7 py-4 text-[16px] font-semibold text-ink shadow-[0_18px_40px_-16px_var(--signal)] transition-transform hover:-translate-y-0.5">
                I need to buy <ArrowRight size={18} />
              </Link>
              <Link to="/login" className="rounded-full border border-line bg-surface px-7 py-4 text-[16px] font-semibold text-bone hover:border-signal/60">I sell things</Link>
            </div>
          </Scene>
        </div>
      </div>
    </div>
  )
}

function Scene({ z, children, reduced, wide = false }: { z: number; children: React.ReactNode; reduced: boolean; wide?: boolean }) {
  return (
    <section data-z={z} className={`${reduced ? 'mx-auto px-6' : 'absolute left-1/2 top-1/2'} ${wide ? 'w-[min(94vw,72rem)]' : 'w-[min(94vw,60rem)]'} text-center`}>
      {children}
    </section>
  )
}
