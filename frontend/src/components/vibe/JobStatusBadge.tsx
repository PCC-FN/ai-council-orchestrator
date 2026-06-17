import { cn } from "../../utils/cn";
import type { CodingJobStatus } from "../../api/vibe";

const STATUS: Record<
  CodingJobStatus,
  { label: string; tone: string }
> = {
  draft: { label: "Entwurf", tone: "bg-slate-100 text-slate-700" },
  analyzing: { label: "KI analysiert", tone: "bg-purple-100 text-purple-800" },
  awaiting_approval: { label: "Wartet auf Freigabe", tone: "bg-amber-100 text-amber-900" },
  queued: { label: "In Warteschlange", tone: "bg-blue-100 text-blue-800" },
  preparing: { label: "Worker bereitet vor", tone: "bg-blue-100 text-blue-800" },
  running: { label: "Cursor arbeitet", tone: "bg-emerald-100 text-emerald-800" },
  awaiting_user_input: { label: "Rückfrage", tone: "bg-orange-100 text-orange-900" },
  testing: { label: "Tests laufen", tone: "bg-cyan-100 text-cyan-900" },
  reviewing: { label: "Nachprüfung", tone: "bg-indigo-100 text-indigo-800" },
  completed: { label: "Abgeschlossen", tone: "bg-green-100 text-green-800" },
  failed: { label: "Fehlgeschlagen", tone: "bg-red-100 text-red-800" },
  cancelled: { label: "Abgebrochen", tone: "bg-slate-100 text-slate-600" },
};

export function JobStatusBadge({ status }: { status: CodingJobStatus }) {
  const s = STATUS[status] ?? STATUS.draft;
  return (
    <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", s.tone)}>
      {s.label}
    </span>
  );
}

export function SenderBadge({ type }: { type: string }) {
  const tones: Record<string, string> = {
    user: "border-brand-200 bg-brand-50 text-brand-800",
    orchestra: "border-purple-200 bg-purple-50 text-purple-800",
    cursor: "border-orange-200 bg-orange-50 text-orange-900",
    worker: "border-slate-200 bg-slate-50 text-slate-700",
    system: "border-slate-200 bg-slate-100 text-slate-600",
    agent: "border-indigo-200 bg-indigo-50 text-indigo-800",
  };
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        tones[type] ?? tones.system,
      )}
    >
      {type}
    </span>
  );
}
