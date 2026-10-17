import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, BellRing, EyeOff, FileCheck2, IndianRupee, MessagesSquare, PackageSearch, Zap } from 'lucide-react'
import { Nav } from '../components/Nav'
import { prefersReducedMotion } from '../lib/motion'
import { evaluate, naivePick } from './engine'
import { NEED, QUOTES } from './fixture'

/** One short page: say what it is, show it working, let a buyer or a seller in. */
export function Landing() {
  return (
    <div className="landing grain min-h-screen bg-ink text-bone">
      <Nav />
      <Hero />
      <TwoSides />
      <Steps />
      <Proof />
      <Closing />
    </div>
  )
}

const inr = (n: number) => '₹' + Math.round(n).toLocaleString('en-IN')

/* ── Hero ─────────────────────────────────────────────────────────────── */

function Hero() {
  return (
    <header className="mx-auto grid max-w-6xl items-center gap-10 px-6 pb-16 pt-28 md:grid-cols-[1.05fr_1fr] md:pb-24 md:pt-36">
      <div>
        <p className="label text-live">Free for sellers · quotes in minutes</p>
        <h1 className="display mt-4 text-[clamp(2.4rem,6vw,4.6rem)] leading-[1.02] tracking-tight">
          Post what you need. Real quotes land while you wait.
        </h1>
        <p className="mt-5 max-w-[46ch] text-[clamp(1rem,1.6vw,1.2rem)] text-muted">
          Every seller who stocks your item is pinged. Their quotes come back without names, priced all the way to your
          door. Pick one, and only then see who they are.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link to="/login" className="flex items-center gap-2 rounded-full bg-signal px-6 py-3.5 text-[15px] font-semibold text-ink hover:opacity-95">
            I need to buy <ArrowRight size={17} />
          </Link>
          <Link to="/login" className="flex items-center gap-2 rounded-full border border-line bg-surface px-6 py-3.5 text-[15px] font-semibold text-bone hover:border-signal/60">
            I sell things
          </Link>
          <Link to="/signin" className="px-2 text-sm text-muted underline-offset-4 hover:text-bone hover:underline">Sign in</Link>
        </div>
      </div>
      <LiveFeed />
    </header>
  )
}

/** Quotes arriving one by one, then the pick. Same rules the product runs, on the C27 brief's four quotes. */
function LiveFeed() {
  const result = evaluate(QUOTES, NEED)
  const winner = result.winner?.quote.id
  const rank = (r: (typeof result.rows)[number]) => (r.status === 'eligible' ? 0 : r.status === 'exception' ? 1 : 2)
  const ranked = [...result.rows].sort((a, b) => rank(a) - rank(b) || (a.landed ?? 1e9) - (b.landed ?? 1e9))
  const [shown, setShown] = useState(() => (prefersReducedMotion() ? ranked.length : 0))

  useEffect(() => {
    if (prefersReducedMotion()) return
    const id = setInterval(() => setShown((s) => (s >= ranked.length + 2 ? 0 : s + 1)), 1100)
    return () => clearInterval(id)
  }, [ranked.length])

  const alias = (id: string) => `Seller ${QUOTES.findIndex((q) => q.id === id) + 1}`
  const done = shown > ranked.length

  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-[0_20px_60px_-30px_rgba(0,0,0,var(--shadow))]" aria-label="Example request with quotes arriving">
      <div className="flex items-center justify-between">
        <div>
          <p className="label text-muted">Your request</p>
          <p className="display text-xl">{NEED.qty} × {NEED.item} <span className="text-muted">· within {NEED.needInDays} days</span></p>
        </div>
        <span className="flex items-center gap-1.5 text-[12px] text-live"><span className="h-2 w-2 animate-pulse rounded-full bg-live" />Live</span>
      </div>
      <ul className="mt-4 space-y-2">
        {ranked.map((r, i) => {
          const visible = i < shown
          const best = r.quote.id === winner && done
          return (
            <li
              key={r.quote.id}
              className={`flex items-center justify-between rounded-xl border px-4 py-3 transition-all duration-500 ${visible ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'} ${best ? 'border-live bg-live/10' : 'border-line bg-raised/60'}`}
            >
              <div>
                <p className="text-[15px] font-medium">{alias(r.quote.id)}</p>
                <p className="text-[12px] text-muted">
                  {r.status === 'blocked' ? 'Pack size missing: cannot compare' : r.status === 'exception' ? `Needs sign-off: ${r.reason}` : `${r.quote.leadDays} days to you`}
                </p>
              </div>
              <div className="text-right">
                <p className="num text-[17px] font-semibold">{r.landed === null ? '—' : inr(r.landed)}</p>
                <p className="text-[11px] text-muted">{best ? 'Best total cost' : 'landed'}</p>
              </div>
            </li>
          )
        })}
      </ul>
      <p className="mt-3 text-[12px] text-muted">
        Names stay hidden until you choose. Landed means price, packs, freight and tax, all in.
      </p>
    </div>
  )
}

/* ── Two sides ────────────────────────────────────────────────────────── */

const BUYER = [
  [PackageSearch, 'One request, many sellers', 'No more calling around or chasing WhatsApp replies.'],
  [IndianRupee, 'The price you actually pay', 'Freight, pack sizes, minimum orders and GST counted for you.'],
  [EyeOff, 'Anonymous until you pick', 'Sellers compete on the offer, not the relationship.'],
  [FileCheck2, 'A decision you can defend', 'One page with the reason, ready to show your boss.'],
] as const

const SELLER = [
  [IndianRupee, 'Free. No listing fee, no commission', 'You pay nothing, and the buyer pays you directly.'],
  [BellRing, 'Only requests for what you stock', 'Matched against your catalog, so no junk leads.'],
  [Zap, 'Quote in under a minute', 'Your price and stock are filled in. Check it, send it.'],
  [MessagesSquare, 'Talk once you are chosen', 'The buyer’s details unlock when they pick you.'],
] as const

function TwoSides() {
  return (
    <section className="mx-auto grid max-w-6xl gap-5 px-6 py-12 md:grid-cols-2">
      <Side title="If you buy" tone="signal" items={BUYER} cta="Start a request" />
      <Side title="If you sell" tone="live" items={SELLER} cta="Get requests" />
    </section>
  )
}

function Side({ title, items, cta, tone }: { title: string; items: readonly (readonly [React.ElementType, string, string])[]; cta: string; tone: 'signal' | 'live' }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-6 md:p-7">
      <h2 className="display text-[clamp(1.6rem,3vw,2.2rem)]">{title}</h2>
      <ul className="mt-5 space-y-4">
        {items.map(([Icon, head, body]) => (
          <li key={head} className="flex gap-3">
            <span className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${tone === 'signal' ? 'bg-signal/10 text-signal' : 'bg-live/10 text-live'}`}>
              <Icon size={16} />
            </span>
            <div>
              <p className="font-medium">{head}</p>
              <p className="text-[14px] text-muted">{body}</p>
            </div>
          </li>
        ))}
      </ul>
      <Link to="/login" className="mt-6 inline-flex items-center gap-2 text-[15px] font-semibold text-bone underline-offset-4 hover:underline">
        {cta} <ArrowRight size={15} />
      </Link>
    </div>
  )
}

/* ── How it works ─────────────────────────────────────────────────────── */

const STEPS = [
  ['1', 'Say what you need', 'Type it, speak it, or fill a short form. Item, quantity, date.'],
  ['2', 'Sellers quote', 'Everyone who stocks it is notified and replies from their catalog.'],
  ['3', 'Compare and pick', 'See true cost side by side, reveal your choice, place the order.'],
] as const

function Steps() {
  return (
    <section className="mx-auto max-w-6xl px-6 py-12">
      <h2 className="display text-[clamp(1.6rem,3vw,2.2rem)]">How it works</h2>
      <ol className="mt-6 grid gap-4 md:grid-cols-3">
        {STEPS.map(([n, head, body]) => (
          <li key={n} className="rounded-2xl border border-line bg-surface p-5">
            <span className="num grid h-8 w-8 place-items-center rounded-full bg-bone text-sm font-semibold text-ink">{n}</span>
            <p className="mt-3 text-lg font-medium">{head}</p>
            <p className="mt-1 text-[14px] text-muted">{body}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}

/* ── Proof ────────────────────────────────────────────────────────────── */

/** The brief's own example: sorting by price per bolt picks the wrong seller. Numbers come from the rules engine. */
function Proof() {
  const a = QUOTES.slice(0, 2)
  const sheetId = naivePick(a, NEED)?.id
  const res = evaluate(a, NEED)
  const row = (id?: string) => res.rows.find((r) => r.quote.id === id)
  const sheet = row(sheetId)
  const best = row(res.winner?.quote.id)
  if (!sheet?.landed || !best?.landed) return null
  const saved = sheet.landed - best.landed
  const name = (id: string) => `Seller ${a.findIndex((q) => q.id === id) + 1}`

  return (
    <section className="mx-auto max-w-6xl px-6 py-12">
      <div className="rounded-2xl border border-line bg-surface p-6 md:p-8">
        <p className="label text-muted">Why not just use a spreadsheet?</p>
        <h2 className="display mt-2 max-w-[24ch] text-[clamp(1.6rem,3.2vw,2.4rem)] leading-tight">
          Cheapest per bolt is not cheapest to buy.
        </h2>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-line bg-raised/60 p-5">
            <p className="label text-muted">Sorted by price per bolt</p>
            <p className="mt-2 text-lg">Picks <strong>{name(sheet.quote.id)}</strong> at ₹{sheet.quote.packPrice} each</p>
            <p className="num mt-1 text-3xl font-semibold">{inr(sheet.landed)}</p>
            <p className="text-[13px] text-muted">once ₹{sheet.quote.freight} freight is added</p>
          </div>
          <div className="rounded-xl border border-live bg-live/10 p-5">
            <p className="label text-live">Crossover</p>
            <p className="mt-2 text-lg">Picks <strong>{name(best.quote.id)}</strong> at ₹{best.quote.packPrice} each</p>
            <p className="num mt-1 text-3xl font-semibold">{inr(best.landed)}</p>
            <p className="text-[13px] text-muted">{inr(saved)} less on a single order of {NEED.qty}</p>
          </div>
        </div>
        <p className="mt-4 text-[13px] text-muted">Example from the C27 problem brief. Order more than 150 and the answer flips again; Crossover recomputes it every time.</p>
      </div>
    </section>
  )
}

/* ── Closing ──────────────────────────────────────────────────────────── */

function Closing() {
  return (
    <footer className="mx-auto max-w-6xl px-6 pb-16 pt-6">
      <div className="rounded-2xl bg-bone px-6 py-10 text-center text-ink md:py-14">
        <h2 className="display mx-auto max-w-[22ch] text-[clamp(1.8rem,4vw,3rem)] leading-tight">Get your first quote in the time it takes to make tea.</h2>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link to="/login" className="rounded-full bg-signal px-6 py-3.5 text-[15px] font-semibold text-white hover:opacity-95">Start as a buyer</Link>
          <Link to="/login" className="rounded-full border border-ink/30 px-6 py-3.5 text-[15px] font-semibold hover:border-ink">Join as a seller</Link>
        </div>
      </div>
      <p className="mt-6 text-center text-[12px] text-muted">Crossover · FyndHacks C27 · Supplier Quote Comparison Desk</p>
    </footer>
  )
}
