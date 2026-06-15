import { STAGES, deriveRoundStatuses } from "../../utils/rounds";
import type { CouncilSession, RoundStatus } from "../../types";
import type { PhaseExecution } from "../../api/orchestra";
import { cn } from "../../utils/cn";

const DOT: Record<RoundStatus, string> = {
  completed: "bg-emerald-500 border-emerald-500 text-white",
  running: "bg-brand-500 border-brand-500 text-white animate-pulse-fast",
  error: "bg-rose-500 border-rose-500 text-white",
  pending: "bg-white border-slate-300 text-slate-400 dark:bg-slate-800 dark:border-slate-600",
};

const LABEL: Record<RoundStatus, string> = {
  completed: "text-slate-900 dark:text-slate-100",
  running: "text-brand-600 dark:text-brand-300 font-semibold",
  error: "text-rose-600 dark:text-rose-300",
  pending: "text-slate-400",
};

export function RoundProgress({
  session,
  activeRound,
  phaseExecutions = [],
}: {
  session: CouncilSession;
  activeRound?: string | null;
  phaseExecutions?: PhaseExecution[];
}) {
  const statuses = deriveRoundStatuses(session, activeRound, phaseExecutions);
  const completed = STAGES.filter((s) => statuses[s.key] === "completed").length;
  const pct = Math.round((completed / STAGES.length) * 100);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between text-xs text-slate-500">
        <span>Fortschritt</span>
        <span>
          {completed}/{STAGES.length} Runden · {pct}%
        </span>
      </div>
      <div className="mb-4 h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className="h-full rounded-full bg-brand-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>

      <ol className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-3 lg:grid-cols-4">
        {STAGES.map((stage, i) => {
          const st = statuses[stage.key];
          return (
            <li key={stage.key} className="flex items-center gap-2">
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                  DOT[st],
                )}
              >
                {st === "completed" ? "✓" : st === "error" ? "!" : i + 1}
              </span>
              <span className={cn("text-xs leading-tight", LABEL[st])}>{stage.label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
