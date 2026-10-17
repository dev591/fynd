import { evaluate, naivePick, type Need, type Quote } from './engine'

/** Ramesh's four quotes from the C27 brief. Lead times for A and B are not in the brief (assumed 3 days). */
export const QUOTES: Quote[] = [
  { id: 'A', supplier: 'Supplier A', item: 'M10 bolt', packPrice: 10, packSize: 1, freight: 200, leadDays: 3,
    raw: '₹10 per bolt + ₹200 delivery', channel: 'WhatsApp' },
  { id: 'B', supplier: 'Supplier B', item: 'M10 bolt', packPrice: 11, packSize: 1, freight: 50, leadDays: 3,
    raw: '₹11/pc, only ₹50 shipping', channel: 'Email' },
  { id: 'C', supplier: 'Supplier C', item: 'M10 bolt', packPrice: 400, packSize: 50, freight: 0, leadDays: 7,
    raw: '₹400 per box of 50, free delivery, 7 days', channel: 'Email' },
  { id: 'D', supplier: 'Supplier D', item: 'M10 bolt', packPrice: 95, packSize: null, freight: 0, leadDays: 3,
    raw: '₹95 "per pack"', channel: 'Phone' },
]

export const NEED: Need = { item: 'M10 bolt', qty: 100, needInDays: 5 }

export type Check = { name: string; points: number; pass: boolean; detail: string }

/** The three scored PS case checks, run against the engine above. */
export function caseChecks(): Check[] {
  const [A, B, C, D] = QUOTES

  const c1 = evaluate([A, B], NEED)
  const pass1 = c1.rows[0].landed === 1200 && c1.rows[1].landed === 1150
    && c1.winner?.quote.id === 'B' && naivePick([A, B], NEED)?.id === 'A'

  const plain = evaluate(QUOTES, NEED)
  const blank = evaluate(QUOTES, NEED, { C: { reason: '  ', approver: 'Plant head' } })
  const signed = evaluate(QUOTES, NEED, { C: { reason: 'Saves ₹350, stock covers the gap', approver: 'Plant head' } })
  const pass2 = plain.winner?.quote.id !== 'C' && plain.rows[2].status === 'exception'
    && blank.winner?.quote.id !== 'C' && signed.winner?.quote.id === 'C'

  const cheapD = { ...D, packPrice: 1 }
  const d = evaluate([A, B, C, cheapD], NEED)
  const pass3 = d.rows[3].status === 'blocked' && d.rows[3].reason === 'pack size unknown'
    && d.winner?.quote.id !== 'D'

  return [
    { name: 'Landed cost', points: 10, pass: pass1,
      detail: 'A ₹1,200 · B ₹1,150 → B wins. Sorted by unit price, the sheet picks A.' },
    { name: 'Late supplier', points: 10, pass: pass2,
      detail: '7-day supplier never recommended. Blank reason rejected; signed reason unlocks it.' },
    { name: 'Unknown pack', points: 5, pass: pass3,
      detail: 'No pack size → blocked. Never wins, even priced at ₹1.' },
  ]
}
