import { useState } from "react";
import { Camera, Check } from "lucide-react";
import { recordDelivery, type DeliveryDTO } from "../api/client";

const MAX_BYTES = 2_000_000;
const OK_TYPES = ["image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm"];

/** After the goods arrive: did they match the quote, were they on time. The buyer's own record. */
export function DeliveryCheck({ rfqId, saved, onSaved }: { rfqId: string; saved: DeliveryDTO | null; onSaved: () => void }) {
  const [matches, setMatches] = useState<boolean | null>(saved?.matches_quote ?? null);
  const [onTime, setOnTime] = useState<boolean | null>(saved?.on_time ?? null);
  const [note, setNote] = useState(saved?.note ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(!saved);

  const pick = (f: File | undefined) => {
    setError(null);
    if (!f) return setFile(null);
    if (!OK_TYPES.includes(f.type)) return setError("Use a photo (jpeg, png, webp) or a short video (mp4, webm).");
    if (f.size > MAX_BYTES) return setError("That file is over 2 MB. Use a smaller photo or a shorter clip.");
    setFile(f);
  };

  const submit = async () => {
    if (matches === null || onTime === null) return;
    setBusy(true); setError(null);
    try {
      let media;
      if (file) {
        const data = await new Promise<string>((resolve, reject) => {
          const r = new FileReader();
          r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
          r.onerror = () => reject(new Error("Could not read the file."));
          r.readAsDataURL(file);
        });
        media = { name: file.name, mime: file.type, data };
      }
      await recordDelivery(rfqId, { matches_quote: matches, on_time: onTime, note: note.trim() || undefined, media });
      setEditing(false);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message.replace(/^API \d+: /, "") : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  const yn = (value: boolean | null, set: (v: boolean) => void, label: string) => (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[13px] text-bone">{label}</span>
      <div role="group" aria-label={label} className="flex rounded-full border border-line p-0.5 text-[12px]">
        {[true, false].map(v => (
          <button key={String(v)} type="button" aria-pressed={value === v} onClick={() => set(v)}
            className={`rounded-full px-3 py-0.5 ${value === v ? (v ? "bg-success text-ink" : "bg-error text-ink") : "text-muted hover:text-bone"}`}>
            {v ? "Yes" : "No"}
          </button>
        ))}
      </div>
    </div>
  );

  if (saved && !editing) {
    return (
      <div className="space-y-1 rounded-xl border border-line bg-surface/70 p-3 text-[13px]">
        <p className="label text-muted">Delivery recorded</p>
        <p className="text-bone">
          Matched the quote: <strong>{saved.matches_quote ? "Yes" : "No"}</strong> · On time: <strong>{saved.on_time ? "Yes" : "No"}</strong>
          {saved.media ? ` · ${saved.media.name} attached` : ""}
        </p>
        {saved.note && <p className="text-muted">“{saved.note}”</p>}
        <p className="text-[11px] text-muted">{saved.disclaimer}</p>
        <button type="button" onClick={() => setEditing(true)} className="text-[11px] text-muted underline hover:text-bone">Change</button>
      </div>
    );
  }
  return (
    <div className="space-y-3 rounded-xl border border-line bg-surface/70 p-3">
      <p className="label text-muted">When it arrives</p>
      {yn(matches, setMatches, "Did it match the quote?")}
      {yn(onTime, setOnTime, "Did it arrive on time?")}
      <textarea value={note} onChange={e => setNote(e.target.value)} rows={2} maxLength={500} placeholder="Anything that was off (optional)"
        className="w-full rounded-lg border border-line bg-raised px-3 py-2 text-[12px] text-bone" />
      <label className="flex cursor-pointer items-center gap-2 text-[12px] text-muted hover:text-bone">
        <Camera size={13} />
        <span>{file ? file.name : "Attach a photo or short video (optional, up to 2 MB)"}</span>
        <input type="file" accept={OK_TYPES.join(",")} className="hidden" onChange={e => pick(e.target.files?.[0])} />
      </label>
      {error && <p role="alert" className="text-[12px] text-error">{error}</p>}
      <p className="text-[11px] text-muted">This is your own record. Crossover does not inspect the goods.</p>
      <button type="button" onClick={submit} disabled={busy || matches === null || onTime === null}
        className="flex items-center gap-1.5 rounded-full bg-signal px-4 py-1.5 text-[12px] font-semibold text-ink disabled:opacity-40">
        <Check size={13} /><span>{busy ? "Saving…" : "Save delivery record"}</span>
      </button>
    </div>
  );
}
