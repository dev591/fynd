import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Mic, Square, Send, Check, AlertTriangle } from "lucide-react";
import { dateFromDays, daysFromToday, tomorrow } from "../lib/dates";
import {
  confirmRFQ, draftIntake, getIntakeStatus, transcribeAudio,
  type IntakeResultDTO, type PriorityMode, type RFQCreateResponse,
} from "../api/client";

interface Props {
  buyer: { company: string; name: string; city: string; state: string };
  onCreated: (res: RFQCreateResponse) => void;
}

const PRIORITIES: PriorityMode[] = ["cheapest", "fastest", "balanced"];

/** Say or type what you need. The model proposes; a person checks the card; only Confirm creates a request. */
export function IntakePanel({ buyer, onCreated }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voiceOk, setVoiceOk] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<IntakeResultDTO | null>(null);
  const [source, setSource] = useState<"chat" | "voice">("chat");
  const [item, setItem] = useState("");
  const [qty, setQty] = useState<number | "">("");
  const [needBy, setNeedBy] = useState("");          // YYYY-MM-DD
  const days = needBy ? daysFromToday(needBy) : "";
  const [priority, setPriority] = useState<PriorityMode>("cheapest");
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => {
    getIntakeStatus().then(s => setVoiceOk(s.voice_enabled && !!navigator.mediaDevices?.getUserMedia));
  }, []);

  const runDraft = async (input: string, via: "chat" | "voice") => {
    if (!input.trim()) return;
    setBusy(true); setNotice(null); setError(null); setResult(null);
    const r = await draftIntake(input);
    setBusy(false);
    if (r.fallback) {
      setNotice("Couldn't read that automatically. Use the form below, it works the same.");
      return;
    }
    setSource(via);
    setResult(r);
    setItem(r.draft.item ?? "");
    setQty(r.draft.qty ?? "");
    setNeedBy(r.draft.need_in_days ? dateFromDays(r.draft.need_in_days) : "");
    setPriority(r.draft.priority_mode ?? "cheapest");
  };

  const toggleRecording = async () => {
    if (recording) { recorder.current?.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunks.current = [];
      rec.ondataavailable = e => chunks.current.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        setRecording(false);
        setBusy(true);
        const heard = await transcribeAudio(new Blob(chunks.current, { type: rec.mimeType || "audio/webm" }));
        setBusy(false);
        if (!heard) { setNotice("Couldn't hear that clearly. Type it instead, or use the form below."); return; }
        setText(heard);
        runDraft(heard, "voice");
      };
      recorder.current = rec;
      rec.start();
      setRecording(true);
      setNotice(null);
    } catch {
      setNotice("Microphone unavailable. Type it instead, or use the form below.");
    }
  };

  const valid = item.trim() && typeof qty === "number" && qty > 0 && typeof days === "number" && days >= 1;

  const confirm = async () => {
    if (!valid) return;
    setConfirming(true); setError(null);
    try {
      const res = await confirmRFQ({
        item: item.trim(), qty: Number(qty), need_in_days: Number(days), priority_mode: priority, source,
        buyer_company: buyer.company, buyer_name: buyer.name, buyer_city: buyer.city, buyer_state: buyer.state,
        intake_id: result?.request_id || undefined,
      });
      onCreated(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create the request. Use the form below.");
    } finally {
      setConfirming(false);
    }
  };

  const missing = (k: string) => result?.missing.includes(k);
  const field = "w-full rounded-lg border bg-raised px-3 py-2 text-[14px] text-bone focus:border-signal focus:outline-none";

  return (
    <section className="relative overflow-hidden rounded-3xl border border-line bg-surface p-6 sm:p-8 space-y-5">
      <div aria-hidden className="pointer-events-none absolute -right-20 -top-28 h-72 w-72 rounded-full bg-signal/10 blur-3xl" />
      <div className="relative flex flex-col items-center gap-5 text-center">
        <div>
          <span className="label text-signal">SAY IT OR TYPE IT</span>
          <h2 className="display mt-1 text-[clamp(1.8rem,4vw,2.6rem)] leading-tight text-bone">What do you need?</h2>
          <p className="mt-1 text-[13px] text-muted">English or Hinglish. You check the card before anything is sent.</p>
        </div>

        <button
          type="button"
          onClick={toggleRecording}
          disabled={!voiceOk || busy}
          aria-label={recording ? "Stop and send" : "Speak your request"}
          title={voiceOk ? (recording ? "Stop and send" : "Speak your request") : "Voice needs the server key. Type instead."}
          className={`relative grid h-24 w-24 place-items-center rounded-full transition-all disabled:opacity-40 ${
            recording ? "bg-error text-white" : "bg-signal text-ink hover:scale-105"
          }`}
        >
          {recording && [0, 1, 2].map(k => (
            <motion.span key={k} aria-hidden className="absolute inset-0 rounded-full border-2 border-error"
              initial={{ scale: 1, opacity: 0.6 }} animate={{ scale: 1.9, opacity: 0 }}
              transition={{ duration: 1.8, repeat: Infinity, delay: k * 0.6, ease: "easeOut" }} />
          ))}
          {!recording && voiceOk && (
            <motion.span aria-hidden className="absolute inset-0 rounded-full bg-signal/30"
              animate={{ scale: [1, 1.18, 1], opacity: [0.5, 0, 0.5] }} transition={{ duration: 2.6, repeat: Infinity }} />
          )}
          {recording ? <Square size={26} className="relative" /> : <Mic size={30} className="relative" />}
        </button>
        <p className="-mt-2 text-[12px] text-muted">{recording ? "Listening… tap to stop" : voiceOk ? "Tap and speak" : "Voice is off on this server. Type below."}</p>
      </div>

      <form onSubmit={e => { e.preventDefault(); runDraft(text, "chat"); }} className="relative flex items-center gap-2">
        <input
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder={recording ? "Listening…" : "Type your request"}
          aria-label="Type your request"
          className={`flex-1 rounded-full border border-line bg-raised px-5 py-3 text-[15px] text-bone focus:border-signal focus:outline-none ${recording ? "placeholder:text-muted/50" : "placeholder:text-transparent"}`}
        />
        {!text && !recording && <TypingHint />}
        <button
          type="submit"
          disabled={!text.trim() || busy}
          aria-label="Read my request"
          className="flex h-12 w-12 items-center justify-center rounded-full bg-signal text-ink disabled:opacity-40"
        >
          <Send size={17} />
        </button>
      </form>

      {busy && <p className="text-[12px] text-muted">Reading your request…</p>}
      {notice && <p className="text-[12px] text-warn">{notice}</p>}

      {result && (
        <div className="rounded-xl border border-signal/40 bg-signal/5 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="label text-signal">CONFIRM YOUR REQUEST</span>
            <span className="text-[11px] text-muted">from {source === "voice" ? "voice" : "chat"} · AI draft, you decide</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-3">
              <label className="label mb-1 block text-muted">Item</label>
              <input value={item} onChange={e => setItem(e.target.value)}
                className={`${field} ${missing("item") ? "border-warn" : "border-line"}`} />
              {item && result.draft.catalog_match && (
                <p className="mt-1 text-[11px] text-live">Matches an item sellers stock.</p>
              )}
              {item && !result.draft.catalog_match && (
                <p className="mt-1 text-[11px] text-warn">No seller stocks this exact name yet. You can still send it.</p>
              )}
            </div>
            <div>
              <label className="label mb-1 block text-muted">Quantity</label>
              <input type="number" min="1" value={qty} onChange={e => setQty(e.target.value === "" ? "" : Number(e.target.value))}
                className={`num ${field} ${missing("qty") ? "border-warn" : "border-line"}`} />
            </div>
            <div>
              <label className="label mb-1 block text-muted">Need by (date)</label>
              <input type="date" min={tomorrow()} value={needBy} onChange={e => setNeedBy(e.target.value)}
                className={`num ${field} ${missing("need_in_days") ? "border-warn" : "border-line"}`} />
              {typeof days === "number" && days >= 1 && (
                <p className="mt-1 text-[11px] text-muted">
                  {days} day{days === 1 ? "" : "s"} from today
                  {result.draft.need_by_phrase ? `. You said "${result.draft.need_by_phrase}".` : "."}
                </p>
              )}
            </div>
            <div>
              <label className="label mb-1 block text-muted">Priority</label>
              <div className="flex gap-1">
                {PRIORITIES.map(p => (
                  <button key={p} type="button" onClick={() => setPriority(p)}
                    className={`flex-1 rounded-lg border px-2 py-2 text-[12px] capitalize ${
                      priority === p ? "border-signal bg-signal/15 text-signal" : "border-line bg-raised text-muted"
                    }`}>{p}</button>
                ))}
              </div>
            </div>
          </div>

          {result.missing.length > 0 && (
            <p className="flex items-center gap-1.5 text-[12px] text-warn">
              <AlertTriangle size={13} /> Not stated, please fill in: {result.missing.map(m => m === "qty" ? "quantity" : m === "need_in_days" ? "deadline" : m).join(", ")}.
            </p>
          )}
          {result.warnings.map(w => <p key={w} className="text-[12px] text-warn">{w}</p>)}
          {error && <p className="text-[12px] text-error">{error}</p>}

          <button type="button" onClick={confirm} disabled={!valid || confirming}
            className="flex w-full items-center justify-center gap-2 rounded-full bg-signal py-2.5 text-[14px] font-semibold text-ink disabled:opacity-40">
            <Check size={16} /><span>{confirming ? "Creating…" : "Confirm & notify sellers"}</span>
          </button>
        </div>
      )}
    </section>
  );
}

const HINTS = ["100 M10 bolts by Friday, fastest", "500 M8 nuts kal tak chahiye", "2 hazaar washers within two weeks", "300 hex bolts, cheapest is fine"];

/** Example requests typing themselves inside the empty box, so a first-time user knows what to say. */
function TypingHint() {
  const [k, setK] = useState(0);
  const [n, setN] = useState(0);
  useEffect(() => {
    const full = HINTS[k % HINTS.length];
    const t = setTimeout(() => {
      if (n < full.length) setN(n + 1);
      else { setN(0); setK(k + 1); }
    }, n < full.length ? 55 : 1600);
    return () => clearTimeout(t);
  }, [k, n]);
  return (
    <span aria-hidden className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[15px] text-muted/60">
      e.g. “{HINTS[k % HINTS.length].slice(0, n)}<span className="animate-pulse">|</span>”
    </span>
  );
}
