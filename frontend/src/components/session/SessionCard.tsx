import { Link } from "react-router-dom";
import { Card, CardBody } from "../ui/Card";
import { StatusBadge } from "../common/StatusBadge";
import type { CouncilSessionSummary } from "../../types";

export function SessionCard({ session }: { session: CouncilSessionSummary }) {
  return (
    <Link to={`/sessions/${session.id}`} className="block">
      <Card className="transition hover:border-brand-300 hover:shadow-md dark:hover:border-brand-500/50">
        <CardBody className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
              {session.title}
            </h3>
            <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
              {session.project_name || "Projekt"} ·{" "}
              {new Date(session.updated_at).toLocaleString()}
            </p>
          </div>
          <StatusBadge status={session.status} />
        </CardBody>
      </Card>
    </Link>
  );
}
