/**
 * In-browser copy of the Crossover rules (brief p.6-8), used by the landing only.
 * The backend engine stays the source of truth; this mirrors its formulas so the story
 * can run live with no network.
 *
 *   packs  = ceil(max(q, MOQ) / units per pack)
 *   landed = packs * pack price + freight
 */

export type Quote = {
  id: string
  supplier: string
  item: string
  packPrice: number
  /** null = the supplier never said how many units are in a pack. */
  packSize: number | null
  freight: number
  leadDays: number
  moq?: number
  /** Stock / capacity cap. Undefined = unlimited. */
  maxQty?: number
  /** The quote as it arrived, for the messy card. */
  raw: string
  channel: string
}

export type Need = { item: string; qty: number; needInDays: number }
export type Exception = { reason: string; approver: string }
export type Mode = 'cheapest' | 'fastest' | 'balanced'
export const MODES: Mode[] = ['cheapest', 'fastest', 'balanced']
/** Our assumption: balanced pays up to 5% over the lowest landed cost to arrive sooner. */
export const BALANCED_THRESHOLD = 0.05
export type Status = 'eligible' | 'exception' | 'blocked'

export type Row = {
  quote: Quote
  status: Status
  reason: string | null
  /** True when a late quote holds a valid written exception. */
  approved: boolean
  packs: number
  units: number
  overbuy: number
  landed: number | null
  /** Units the seller can cover when stock is below the need. */
  fillQty?: number
}

export function order(q: Quote, qty: number) {
  if (!q.packSize) return null
  const packs = Math.ceil(Math.max(qty, q.moq ?? 0) / q.packSize)
  const units = packs * q.packSize
  return { packs, units, overbuy: units - qty, landed: packs * q.packPrice + q.freight }
}

export const landed = (q: Quote, qty: number) => order(q, qty)?.landed ?? null

/** A blank reason or approver never unlocks a gate. */
export const validException = (e?: Exception) =>
  !!e && e.reason.trim().length > 0 && e.approver.trim().length > 0

const blocked = (quote: Quote, reason: string): Row => ({
  quote, status: 'blocked', reason, approved: false, packs: 0, units: 0, overbuy: 0, landed: null,
})

/** Cheapest landed wins; ties break on shorter lead time, then less overbuy. */
const rank = (a: Row, b: Row) =>
  a.landed! - b.landed! || a.quote.leadDays - b.quote.leadDays || a.overbuy - b.overbuy

const fastRank = (a: Row, b: Row) =>
  a.quote.leadDays - b.quote.leadDays || a.landed! - b.landed! || a.overbuy - b.overbuy

/** Order the eligible pool for a mode. */
export function rankPool(pool: Row[], mode: Mode, threshold = BALANCED_THRESHOLD): Row[] {
  if (mode === 'fastest') return [...pool].sort(fastRank)
  const ordered = [...pool].sort(rank)
  if (mode === 'balanced' && ordered.length) {
    const limit = ordered[0].landed! * (1 + threshold)
    const near = ordered.filter((r) => r.landed! <= limit).sort(fastRank)
    return [...near, ...ordered.filter((r) => !near.includes(r))]
  }
  return ordered
}

export function evaluate(
  quotes: Quote[],
  need: Need,
  exceptions: Record<string, Exception> = {},
  mode: Mode = 'cheapest',
  threshold = BALANCED_THRESHOLD,
) {
  const rows: Row[] = quotes.map((q) => {
    if (q.item !== need.item) return blocked(q, 'different item')
    const short = q.maxQty !== undefined && q.maxQty < need.qty
    const o = order(q, short ? q.maxQty! : need.qty)
    if (!o) return blocked(q, 'pack size unknown')
    const late = q.leadDays > need.needInDays
    const reasons = [
      late && `arrives in ${q.leadDays} days, needed in ${need.needInDays}`,
      short && `stock covers ${q.maxQty} of ${need.qty} units`,
    ].filter(Boolean)
    return {
      quote: q,
      status: late || short ? 'exception' : 'eligible',
      reason: reasons.length ? reasons.join('; ') : null,
      approved: (late || short) && validException(exceptions[q.id]),
      fillQty: short ? q.maxQty : undefined,
      ...o,
    }
  })
  const eligible = rows.filter((r) => r.status === 'eligible' || r.approved)
  const pool = rankPool(eligible, mode, threshold)
  const winners = Object.fromEntries(
    MODES.map((m) => [m, rankPool(eligible, m, threshold)[0] ?? null]),
  ) as Record<Mode, Row | null>
  const winner = pool[0] ?? null
  const cmp = mode === 'fastest' ? fastRank : rank
  const tie = pool.length > 1 && cmp(pool[0], pool[1]) === 0
  const cheaperExcluded = winner
    ? rows.filter((r) => !pool.includes(r) && r.landed !== null && r.landed < winner.landed!)
    : []
  return { rows, pool, winner, tie, cheaperExcluded, mode, winners }
}

/** One line on what a mode costs against the cheapest pick. Numbers come from the engine rows. */
export function giveUp(mode: Mode, winners: Record<Mode, Row | null>): string | null {
  const base = winners.cheapest
  const w = winners[mode]
  if (!base || !w) return null
  if (mode === 'cheapest') return 'Lowest landed cost. Nothing given up on price.'
  if (w.quote.id === base.quote.id) return 'Same supplier as the cheapest pick. Nothing given up.'
  const extra = Math.round(w.landed! - base.landed!)
  const days = base.quote.leadDays - w.quote.leadDays
  const when = days > 0 ? `arrives ${days} day${days === 1 ? '' : 's'} earlier` : 'arrives no earlier'
  return `${mode === 'fastest' ? 'Fastest' : 'Balanced'} costs ${inr(extra)} more and ${when}.`
}

/** What a losing quote must cut to win this order: freight alone if that is enough, and per unit. */
export function negotiation(loser: Row, winner: Row) {
  const cut = Math.floor(loser.landed! - winner.landed!) + 1
  if (cut <= 0) return null
  return {
    cut,
    freight: cut <= loser.quote.freight ? cut : null,
    perUnit: Math.ceil((cut / loser.units) * 100) / 100,
  }
}

/** What a sheet sorted by sticker price picks: ignores freight, and reads "per pack" as per unit. */
export function naivePick(quotes: Quote[], need: Need) {
  return quotes
    .filter((q) => q.leadDays <= need.needInDays)
    .map((q) => ({ q, perUnit: q.packPrice / (q.packSize ?? 1) }))
    .sort((a, b) => a.perUnit - b.perUnit)[0]?.q ?? null
}

/** Stable key order + FNV-1a. Same inputs, same fingerprint. */
export function fingerprint(value: unknown) {
  const stable = (v: unknown): string =>
    Array.isArray(v) ? `[${v.map(stable).join(',')}]`
    : v && typeof v === 'object'
      ? `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${stable((v as Record<string, unknown>)[k])}`).join(',')}}`
      : JSON.stringify(v)
  let h = 0x811c9dc5
  for (const c of stable(value)) h = Math.imul(h ^ c.charCodeAt(0), 0x01000193)
  return (h >>> 0).toString(16).padStart(8, '0')
}

export const inr = (n: number) => `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
