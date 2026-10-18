/**
 * VoiceQuoteBar — mic button for the seller to dictate a quote.
 *
 * Flow:
 *   1. Seller taps the mic.
 *   2. Browser records via MediaRecorder (same pattern as buyer IntakePanel).
 *   3. Audio → POST /api/supplier/transcribe → transcript text.
 *   4. Text → POST /api/quote-voice/draft → structured fields (numbers cross-checked against transcript).
 *   5. onApply(fields) is called; the parent merges them into QuoteForm's initialValues.
 *   6. Seller sees the filled form, can edit any field, and presses Send themselves.
 *
 * Rules:
 * - Unstated fields are null and NOT applied; only real numbers from the transcript fill the form.
 * - A human always presses Send; this component never submits a quote.
 * - Warnings from the parser are shown so the seller knows what was and wasn't understood.
 */
import { useRef, useState } from "react";
import { Mic, Square, AlertTriangle, CheckCircle2, X } from "lucide-react";
import { transcribeSellerAudio, draftQuoteFromVoice, type VoiceQuoteDraftRow } from "../../api/client";

export interface VoiceQuoteFields {
  packPrice?: number;
  packSize?: number;
  freight?: number;
  leadDays?: number;
  moq?: number;
  maxQty?: number;
  taxRate?: number;
  priceIncludesTax?: boolean;
  notes?: string;
}

interface Props {
  /** Called when a draft is ready. Parent merges these into QuoteForm's initialValues. */
  onApply: (fields: VoiceQuoteFields) => void;
  disabled?: boolean;
}

type Phase = "idle" | "recording" | "transcribing" | "parsing" | "done" | "error";

function rowToFields(row: VoiceQuoteDraftRow): VoiceQuoteFields {
  const f: VoiceQuoteFields = {};
  if (row.pack_price != null)      f.packPrice       = row.pack_price;
  if (row.pack_size != null)       f.packSize        = row.pack_size;
  if (row.freight != null)         f.freight         = row.freight;
  if (row.lead_days != null)       f.leadDays        = row.lead_days;
  if (row.moq != null)             f.moq             = row.moq;
  if (row.max_qty != null)         f.maxQty          = row.max_qty;
  if (row.tax_rate != null)        f.taxRate         = row.tax_rate;
  if (row.price_includes_tax != null) f.priceIncludesTax = row.price_includes_tax;
  if (row.notes != null)           f.notes           = row.notes;
  return f;
}

export function VoiceQuoteBar({ onApply, disabled = false }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [transcript, setTranscript] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [appliedFields, setAppliedFields] = useState<VoiceQuoteFields | null>(null);

  const recorder  = useRef<MediaRecorder | null>(null);
  const chunks    = useRef<Blob[]>([]);

  const reset = () => {
    setPhase("idle");
    setTranscript(null);
    setWarnings([]);
    setNotice(null);
    setAppliedFields(null);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunks.current = [];
      rec.ondataavailable = e => chunks.current.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        await processSpeech(new Blob(chunks.current, { type: rec.mimeType || "audio/webm" }));
      };
      recorder.current = rec;
      rec.start();
      setPhase("recording");
      setNotice(null);
    } catch {
      setNotice("Microphone unavailable. Type values into the form instead.");
      setPhase("error");
    }
  };

  const stopRecording = () => {
    recorder.current?.stop();
    setPhase("transcribing");
  };

  const processSpeech = async (blob: Blob) => {
    // Step 1: transcribe
    setPhase("transcribing");
    const text = await transcribeSellerAudio(blob);
    if (!text) {
      setNotice("Couldn't hear that clearly. Type values into the form instead.");
      setPhase("error");
      return;
    }
    setTranscript(text);

    // Step 2: parse into fields
    setPhase("parsing");
    const result = await draftQuoteFromVoice(text);
    if (!result || result.fallback || result.rows.length === 0) {
      setNotice("No quote numbers found in that sentence. Say something like: ten rupees per unit, freight two hundred, three days.");
      setPhase("error");
      return;
    }

    const fields = rowToFields(result.rows[0]);
    const fieldCount = Object.keys(fields).length;
    if (fieldCount === 0) {
      setNotice("No numbers could be verified against what you said. Try again or fill the form.");
      setPhase("error");
      return;
    }

    setWarnings(result.warnings);
    setAppliedFields(fields);
    setPhase("done");
    onApply(fields);
  };

  const isBusy = phase === "transcribing" || phase === "parsing";

  return (
    <div className="rounded-xl border border-line bg-raised/40 p-4 space-y-3">
      {/* Label row */}
      <div className="flex items-center justify-between">
        <span className="label text-muted flex items-center gap-1.5">
          <Mic size={12} className="text-signal" />
          Say your quote
        </span>
        {phase !== "idle" && (
          <button
            type="button"
            onClick={reset}
            className="text-[11px] text-muted hover:text-bone flex items-center gap-1"
          >
            <X size={11} />
            <span>Clear</span>
          </button>
        )}
      </div>

      {/* Instruction hint */}
      {phase === "idle" && (
        <p className="text-[12px] text-muted">
          e.g. "ten rupees a unit, freight two hundred, three days" — only the numbers you say will fill the form.
        </p>
      )}

      {/* Mic / Stop button */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={phase === "recording" ? stopRecording : startRecording}
          disabled={disabled || isBusy}
          aria-label={phase === "recording" ? "Stop recording" : "Start voice quote"}
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full border transition-all disabled:opacity-40 ${
            phase === "recording"
              ? "border-error bg-error/20 text-error animate-pulse"
              : "border-signal/50 bg-signal/10 text-signal hover:bg-signal/20"
          }`}
        >
          {phase === "recording" ? <Square size={16} /> : <Mic size={18} />}
        </button>

        {phase === "idle" && (
          <span className="text-[13px] text-muted">Tap to start</span>
        )}
        {phase === "recording" && (
          <span className="text-[13px] text-bone animate-pulse">Listening… tap to stop</span>
        )}
        {isBusy && (
          <span className="flex items-center gap-2 text-[13px] text-muted">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-signal" />
            {phase === "transcribing" ? "Transcribing…" : "Reading numbers…"}
          </span>
        )}
      </div>

      {/* Transcript */}
      {transcript && phase !== "recording" && (
        <div className="rounded-lg border border-line bg-surface/60 px-3 py-2 text-[12px] text-muted italic">
          "{transcript}"
        </div>
      )}

      {/* Applied fields summary */}
      {phase === "done" && appliedFields && (
        <div className="rounded-lg border border-success/40 bg-success/10 p-3 space-y-1.5">
          <div className="flex items-center gap-1.5 text-[12px] font-medium text-success">
            <CheckCircle2 size={14} />
            <span>Applied to form — check each field before sending</span>
          </div>
          <ul className="text-[12px] text-muted space-y-0.5 pl-1">
            {appliedFields.packPrice  != null && <li>Pack price: ₹{appliedFields.packPrice}</li>}
            {appliedFields.packSize   != null && <li>Units per pack: {appliedFields.packSize}</li>}
            {appliedFields.freight    != null && <li>Freight: ₹{appliedFields.freight}</li>}
            {appliedFields.leadDays   != null && <li>Lead time: {appliedFields.leadDays} days</li>}
            {appliedFields.moq        != null && <li>MOQ: {appliedFields.moq}</li>}
            {appliedFields.taxRate    != null && <li>GST: {appliedFields.taxRate}%</li>}
            {appliedFields.notes      != null && <li>Notes: {appliedFields.notes}</li>}
          </ul>
        </div>
      )}

      {/* Warnings from the parser (unstated fields, dropped numbers, etc.) */}
      {warnings.length > 0 && (
        <div className="rounded-lg border border-warn/40 bg-warn/10 p-3 space-y-1">
          {warnings.map((w, i) => (
            <p key={i} className="flex items-start gap-1.5 text-[12px] text-warn">
              <AlertTriangle size={13} className="shrink-0 mt-0.5" />
              {w}
            </p>
          ))}
        </div>
      )}

      {/* Hard error / fallback notice */}
      {notice && (
        <p className="text-[12px] text-warn flex items-start gap-1.5">
          <AlertTriangle size={13} className="shrink-0 mt-0.5" />
          {notice}
        </p>
      )}
    </div>
  );
}
