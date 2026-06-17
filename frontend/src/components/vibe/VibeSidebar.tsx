import { cn } from "../../utils/cn";
import type { CodingJob, VibeWorker, WorkerProject } from "../../api/vibe";
import { JobStatusBadge } from "./JobStatusBadge";

export function VibeSidebar({
  workers,
  projects,
  jobs,
  selectedWorkerId,
  selectedProjectId,
  activeJobId,
  onSelectWorker,
  onSelectProject,
  onSelectJob,
}: {
  workers: VibeWorker[];
  projects: WorkerProject[];
  jobs: CodingJob[];
  selectedWorkerId: string | null;
  selectedProjectId: string | null;
  activeJobId: string | null;
  onSelectWorker: (id: string) => void;
  onSelectProject: (id: string) => void;
  onSelectJob: (id: string) => void;
}) {
  const running = jobs.filter((j) =>
    ["running", "preparing", "testing", "awaiting_user_input", "queued"].includes(j.status),
  );
  const done = jobs.filter((j) => j.status === "completed");
  const failed = jobs.filter((j) => j.status === "failed");

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col overflow-y-auto border-r border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <section className="mb-4">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Worker</h2>
        <div className="space-y-1">
          {workers.length === 0 && (
            <p className="text-xs text-slate-500">Kein Worker verbunden</p>
          )}
          {workers.map((w) => (
            <button
              key={w.id}
              type="button"
              onClick={() => onSelectWorker(w.id)}
              className={cn(
                "w-full rounded-lg border px-3 py-2 text-left text-sm transition",
                selectedWorkerId === w.id
                  ? "border-brand-300 bg-brand-50 dark:border-brand-500/40 dark:bg-brand-500/10"
                  : "border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium truncate">{w.name}</span>
                <span
                  className={cn(
                    "h-2 w-2 shrink-0 rounded-full",
                    w.online ? "bg-emerald-500" : "bg-slate-300",
                  )}
                />
              </div>
              <p className="mt-0.5 truncate text-[11px] text-slate-500">{w.hostname}</p>
              <p className="text-[10px] text-slate-400">
                {w.operating_system || "—"} · v{w.version}
              </p>
            </button>
          ))}
        </div>
      </section>

      {selectedWorkerId && (
        <section className="mb-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Projekte
          </h2>
          <div className="space-y-1">
            {projects.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => onSelectProject(p.id)}
                className={cn(
                  "w-full rounded-lg px-3 py-2 text-left text-sm transition",
                  selectedProjectId === p.id
                    ? "bg-slate-200 dark:bg-slate-700"
                    : "hover:bg-slate-100 dark:hover:bg-slate-800",
                )}
              >
                <span className="font-medium">{p.name}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      <JobList title="Laufend" items={running} activeJobId={activeJobId} onSelect={onSelectJob} />
      <JobList title="Abgeschlossen" items={done.slice(0, 5)} activeJobId={activeJobId} onSelect={onSelectJob} />
      <JobList title="Fehlgeschlagen" items={failed.slice(0, 5)} activeJobId={activeJobId} onSelect={onSelectJob} />
    </aside>
  );
}

function JobList({
  title,
  items,
  activeJobId,
  onSelect,
}: {
  title: string;
  items: CodingJob[];
  activeJobId: string | null;
  onSelect: (id: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <section className="mb-4">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      <div className="space-y-1">
        {items.map((j) => (
          <button
            key={j.id}
            type="button"
            onClick={() => onSelect(j.id)}
            className={cn(
              "w-full rounded-lg px-3 py-2 text-left text-xs transition",
              activeJobId === j.id
                ? "bg-brand-50 dark:bg-brand-500/10"
                : "hover:bg-slate-100 dark:hover:bg-slate-800",
            )}
          >
            <div className="flex items-center justify-between gap-1">
              <span className="truncate font-medium">{j.title}</span>
              <JobStatusBadge status={j.status} />
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
