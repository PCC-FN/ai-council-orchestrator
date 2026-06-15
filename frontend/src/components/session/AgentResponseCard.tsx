import { Card } from "../ui/Card";
import { Markdown } from "../common/Markdown";
import { ApprovalBadge } from "../common/StatusBadge";
import { Badge } from "../ui/Badge";
import { agentMeta } from "../../utils/agents";
import type { AgentResponse, AgentStatus } from "../../types";
import { cn } from "../../utils/cn";

function Stars({ rating }: { rating: number | null }) {
  if (rating == null) return null;
  return (
    <span className="text-xs text-amber-500" title={`Bewertung: ${rating}/5`}>
      {"★".repeat(Math.max(0, Math.min(5, rating)))}
      <span className="text-slate-300 dark:text-slate-600">
        {"★".repeat(Math.max(0, 5 - rating))}
      </span>
    </span>
  );
}

/** A placeholder card shown while an agent is still working. */
export function AgentPendingCard({
  agentName,
  status,
}: {
  agentName: string;
  status: AgentStatus;
}) {
  const meta = agentMeta(agentName);
  return (
    <Card className={cn(status === "running" && "ring-2 ring-brand-400/50")}>
      <div className="flex items-center gap-3 px-4 py-3">
        <span
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold",
            meta.accent,
          )}
        >
          {meta.initials}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
            {meta.label}
          </p>
          <p className="truncate text-xs text-slate-500">{meta.role}</p>
        </div>
        {status === "running" ? (
          <Badge tone="info">
            <span className="h-1.5 w-1.5 animate-pulse-fast rounded-full bg-current" />
            arbeitet…
          </Badge>
        ) : (
          <Badge tone="neutral">wartet</Badge>
        )}
      </div>
    </Card>
  );
}

export function AgentResponseCard({ response }: { response: AgentResponse }) {
  const meta = agentMeta(response.agent_name);
  return (
    <Card>
      <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        <span
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold",
            meta.accent,
          )}
        >
          {meta.initials}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
            {meta.label}
          </p>
          <p className="truncate text-xs text-slate-500">{meta.role}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Stars rating={response.rating} />
          {response.approval_status !== "pending" && (
            <ApprovalBadge status={response.approval_status} />
          )}
        </div>
      </div>
      <div className="px-4 py-3">
        <Markdown content={response.content} />
        {response.concerns && (
          <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-500/10 dark:text-amber-200">
            <span className="font-semibold">Bedenken: </span>
            {response.concerns}
          </div>
        )}
      </div>
    </Card>
  );
}
