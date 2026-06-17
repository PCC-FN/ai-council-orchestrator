import { useMemo, useState } from "react";
import { Markdown } from "../common/Markdown";
import { Button } from "../ui/Button";
import { SenderBadge } from "./JobStatusBadge";
import type { ChatMessage, CodingJob } from "../../api/vibe";
import { cn } from "../../utils/cn";

export function VibeChatPanel({
  job,
  onSend,
  onApprove,
  onApproveCorrection,
  onAcceptResult,
  onReject,
  onCancel,
  busy,
}: {
  job: CodingJob | null;
  onSend: (text: string) => void;
  onApprove: () => void;
  onApproveCorrection?: () => void;
  onAcceptResult?: () => void;
  onReject: () => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  const [text, setText] = useState("");

  const messages = job?.messages ?? [];
  const pendingCorrection = Boolean(
    job?.implementation_plan && (job.implementation_plan as Record<string, unknown>).pending_correction,
  );
  const showPlanApproval = job?.status === "awaiting_approval" && !pendingCorrection;
  const showCorrectionApproval = job?.status === "awaiting_approval" && pendingCorrection;
  const isReviewing = job?.status === "reviewing";
  const isQuestion = job?.status === "awaiting_user_input";

  const handleSubmit = () => {
    if (!text.trim()) return;
    onSend(text.trim());
    setText("");
  };

  const placeholder = useMemo(() => {
    if (isQuestion) return "Antwort an Cursor…";
    if (!job) return "Aufgabe beschreiben…";
    return "Folgeanweisung oder Nachricht…";
  }, [isQuestion, job]);

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="text-sm text-slate-500">
            Beschreiben Sie Ihre Programmieraufgabe. AI Orchestra analysiert sie und leitet sie an
            den Worker weiter.
          </p>
        )}
        {messages.map((m) => (
          <ChatBubble key={m.id} message={m} />
        ))}
        {isReviewing && (
          <div className="rounded-lg border border-purple-200 bg-purple-50 p-3 text-sm text-purple-900 dark:border-purple-500/30 dark:bg-purple-500/10 dark:text-purple-100">
            AI Orchestra prüft das Ergebnis…
          </div>
        )}
        {showPlanApproval && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/30 dark:bg-amber-500/10">
            <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
              Umsetzungsplan zur Freigabe
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" onClick={onApprove} disabled={busy}>
                Plan freigeben und starten
              </Button>
              <Button size="sm" variant="secondary" onClick={onReject} disabled={busy}>
                Abbrechen
              </Button>
            </div>
          </div>
        )}
        {showCorrectionApproval && (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-500/30 dark:bg-indigo-500/10">
            <p className="text-sm font-medium text-indigo-900 dark:text-indigo-100">
              Korrekturauftrag zur Freigabe
            </p>
            <p className="mt-1 text-xs text-indigo-700 dark:text-indigo-200">
              Runde {(job?.implementation_plan as Record<string, number>)?.review_rounds ?? job?.review_rounds ?? 0} — die
              Nachprüfung hat Probleme gefunden.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" onClick={onApproveCorrection} disabled={busy}>
                Korrektur starten
              </Button>
              <Button size="sm" variant="secondary" onClick={onAcceptResult} disabled={busy}>
                Ergebnis trotzdem akzeptieren
              </Button>
              <Button size="sm" variant="ghost" onClick={onReject} disabled={busy}>
                Abbrechen
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-slate-200 p-3 dark:border-slate-700">
        <textarea
          className="min-h-[88px] w-full resize-y rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm outline-none focus:border-brand-500 dark:border-slate-600 dark:bg-slate-800"
          placeholder={placeholder}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={handleSubmit} disabled={busy || !text.trim()}>
            Senden
          </Button>
          {job && !["completed", "cancelled", "failed"].includes(job.status) && (
            <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
              Abbrechen
            </Button>
          )}
          {isQuestion && (
            <span className="text-xs font-medium text-orange-600">
              Cursor wartet auf Ihre Antwort
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const isQuestion = message.message_type === "question";
  const isReview = message.message_type === "review" || message.message_type === "correction_plan";
  return (
    <div
      className={cn(
        "rounded-lg border p-3",
        isQuestion
          ? "border-orange-300 bg-orange-50 dark:border-orange-500/40 dark:bg-orange-500/10"
          : isReview
            ? "border-purple-300 bg-purple-50 dark:border-purple-500/40 dark:bg-purple-500/10"
            : "border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50",
      )}
    >
      <div className="mb-1 flex items-center gap-2">
        <SenderBadge type={message.sender_type} />
        <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
          {message.sender_name}
        </span>
        {isQuestion && (
          <span className="text-xs font-semibold text-orange-700">Rückfrage</span>
        )}
        {message.message_type === "correction_plan" && (
          <span className="text-xs font-semibold text-indigo-700">Korrektur nötig</span>
        )}
        {message.message_type === "review" && (
          <span className="text-xs font-semibold text-purple-700">Nachprüfung</span>
        )}
      </div>
      <div className="prose prose-sm max-w-none dark:prose-invert">
        <Markdown content={message.content} />
      </div>
    </div>
  );
}
