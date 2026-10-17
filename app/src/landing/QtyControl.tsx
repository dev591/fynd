import { RotateCcw } from 'lucide-react'

type Props = {
  qty: number
  onQty: (q: number) => void
  sheet: boolean
  onSheet: (on: boolean) => void
  onReset: () => void
}

const CHIPS = [100, 150, 200]

/** The judge's turn: drag quantity, flip spreadsheet mode, reset. */
export function QtyControl({ qty, onQty, sheet, onSheet, onReset }: Props) {
  return (
    <div className="space-y-3">
      <label className="block">
        <span className="label flex justify-between text-muted">
          <span>Drag the quantity</span>
          <span className="num text-bone">{qty} units</span>
        </span>
        <input
          type="range"
          min={1}
          max={300}
          value={qty}
          onChange={(e) => onQty(Number(e.target.value))}
          className="mt-2 h-8 w-full cursor-pointer accent-(--signal)"
          aria-label="Order quantity"
        />
      </label>
      <div className="flex flex-wrap items-center gap-2">
        {CHIPS.map((c) => (
          <button
            key={c}
            onClick={() => onQty(c)}
            className={`num rounded-full border px-3 py-1.5 text-[13px] transition-colors ${qty === c ? 'border-bone text-bone' : 'border-line text-muted hover:text-bone'}`}
          >
            {c}
          </button>
        ))}
        <button
          onClick={() => onSheet(!sheet)}
          aria-pressed={sheet}
          className={`rounded-full border px-3 py-1.5 text-[13px] transition-colors ${sheet ? 'border-bone bg-bone text-ink' : 'border-line text-muted hover:text-bone'}`}
        >
          Spreadsheet mode
        </button>
        <button
          onClick={onReset}
          className="ml-auto flex items-center gap-1.5 rounded-full px-2 py-1.5 text-[13px] text-muted hover:text-bone"
        >
          <RotateCcw size={14} strokeWidth={1.5} /> Reset
        </button>
      </div>
    </div>
  )
}
