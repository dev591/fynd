import { useState } from "react";
import { Lock, Send, User, MessageSquare, Zap } from "lucide-react";
import type { ChatMessageDTO } from "../../api/client";
import { NegotiationTargetCard } from "./NegotiationTargetCard";

interface SupplierChatProps {
  messages: ChatMessageDTO[];
  currentRole: "buyer" | "supplier";
  currentUserName: string;
  onSendMessage: (text: string) => void;
  onReviseFromTarget?: () => void;
  /** When set, typing is locked and this explains why (chat opens after the buyer reveals the seller). */
  locked?: string;
  className?: string;
}

export function SupplierChat({ messages, currentRole, currentUserName, onSendMessage, onReviseFromTarget, locked, className = "" }: SupplierChatProps) {
  const [text, setText] = useState("");

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    onSendMessage(text.trim());
    setText("");
  };

  return (
    <div className={`flex flex-col rounded-2xl border border-line bg-surface/80 backdrop-blur-sm ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-live" />
          <span className="text-[13px] font-semibold text-bone">Negotiation Thread</span>
        </div>
        <span className="label text-muted">As {currentUserName}</span>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-3.5 overflow-y-auto p-4 max-h-80 min-h-[220px]">
        {messages.length === 0 ? (
          <div className="py-8 text-center text-muted text-[13px]">
            No messages yet. Negotiation counter-offers and quote revisions will appear here.
          </div>
        ) : (
          messages.map(m => {
            const isMe = m.sender === currentRole;
            return (
              <div key={m.id} className={`flex flex-col ${isMe ? "items-end" : "items-start"}`}>
                <div className="flex items-center gap-1.5 mb-1 text-[11px] text-muted">
                  <User size={11} /><span>{m.sender_name}</span><span>·</span><span>{m.timestamp}</span>
                </div>
                {m.target ? (
                  <div className="max-w-[85%] w-full">
                    <NegotiationTargetCard target={m.target} onRevise={() => onReviseFromTarget?.()} />
                  </div>
                ) : (
                  <div className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed shadow-sm ${
                    isMe ? "bg-bone text-ink font-medium" : "bg-raised border border-line/70 text-bone"
                  }`}>
                    {m.text}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Suggested replies (buyer only): fixed text, not AI. A person picks, edits and sends. */}
      {currentRole === "buyer" && (
        <div className="border-t border-line/60 bg-raised/30 px-3 py-2 flex items-center gap-2 overflow-x-auto text-[11px]">
          <span className="text-muted flex items-center gap-1 shrink-0">
            <MessageSquare size={12} className="text-signal" /> Suggested replies:
          </span>
          <button type="button" onClick={() => setText("Can you waive or discount freight to ₹50? We can issue the PO today.")}
            className="shrink-0 rounded-full border border-line bg-surface px-2.5 py-0.5 text-muted hover:text-bone hover:border-signal/50">
            "Discount freight to ₹50"
          </button>
          <button type="button" onClick={() => setText("Need confirmed Friday delivery. Can you guarantee dispatch tomorrow?")}
            className="shrink-0 rounded-full border border-line bg-surface px-2.5 py-0.5 text-muted hover:text-bone hover:border-signal/50">
            "Confirm Friday dispatch"
          </button>
        </div>
      )}

      {/* Supplier quick action */}
      {currentRole === "supplier" && onReviseFromTarget && (
        <div className="border-t border-line/60 bg-signal/10 px-3 py-2 flex items-center justify-between text-[11px]">
          <span className="text-signal font-medium flex items-center gap-1">
            <Zap size={12} fill="currentColor" /> Counter-offer received:
          </span>
          <button type="button" onClick={onReviseFromTarget}
            className="rounded-full bg-signal px-2.5 py-0.5 font-semibold text-ink hover:opacity-90">
            Revise Quote
          </button>
        </div>
      )}

      {/* Input, or why it is locked */}
      {locked ? (
        <p className="flex items-center gap-2 border-t border-line p-3 text-[12px] text-muted"><Lock size={13} className="shrink-0" />{locked}</p>
      ) : (
      <form onSubmit={handleSend} className="flex items-center gap-2 border-t border-line p-3">
        <input type="text" value={text}
          onChange={e => setText(e.target.value)}
          placeholder={`Type message to ${currentRole === "buyer" ? "supplier" : "buyer"}...`}
          className="flex-1 rounded-full border border-line bg-surface px-4 py-2 text-[13px] text-bone placeholder:text-muted/50 focus:border-signal focus:outline-none"
        />
        <button type="submit" disabled={!text.trim()}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-signal text-ink transition-all hover:opacity-95 disabled:opacity-40">
          <Send size={14} />
        </button>
      </form>
      )}
    </div>
  );
}
