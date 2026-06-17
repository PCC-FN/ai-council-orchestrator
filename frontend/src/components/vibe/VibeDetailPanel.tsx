import { type ReactNode, useEffect, useState } from "react";
import type { CodingJob, VibeJobEvent } from "../../api/vibe";
import { vibeApi } from "../../api/vibe";
import { JobStatusBadge } from "./JobStatusBadge";
import { cn } from "../../utils/cn";

type Tab = "overview" | "files" | "diff" | "terminal" | "tests" | "history";

export function VibeDetailPanel({
  job,
  events,
  onRefresh,
}: {
  job: CodingJob | null;
  events: VibeJobEvent[];
  onRefresh?: () => void;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const [diff, setDiff] = useState("");
  const [tests, setTests] = useState<{
    build_status: string;
    lint_status: string;
    tests: { passed: number; failed: number; skipped: number };
  } | null>(null);
  const [termQuery, setTermQuery] = useState("");
  const [gitBusy, setGitBusy] = useState(false);

  useEffect(() => {
    if (!job?.id) return;
    if (tab === "diff") vibeApi.getDiff(job.id).then((d) => setDiff(d.diff)).catch(() => {});
    if (tab === "tests") vibeApi.getTests(job.id).then(setTests).catch(() => {});
  }, [job?.id, tab]);

  const terminalLines = events
    .filter((e) =>
      ["command.output", "agent.output", "command.started", "command.completed"].includes(
        e.event_type,
      ),
    )
    .map((e) => {
      const p = e.payload as Record<string, string>;
      return p.output || p.message || p.command || JSON.stringify(p);
    })
    .filter((line) => !termQuery || line.toLowerCase().includes(termQuery.toLowerCase()));

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Übersicht" },
    { id: "files", label: "Dateien" },
    { id: "diff", label: "Diff" },
    { id: "terminal", label: "Terminal" },
    { id: "tests", label: "Tests" },
    { id: "history", label: "Verlauf" },
  ];

  return (
    <aside className="flex h-full w-96 shrink-0 flex-col border-l border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap gap-1 border-b border-slate-200 p-2 dark:border-slate-700">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={cn(
              "rounded-md px-2 py-1 text-xs font-medium",
              tab === t.id
                ? "bg-brand-100 text-brand-800 dark:bg-brand-500/20 dark:text-brand-200"
                : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-3 text-sm">
        {!job && <p className="text-slate-500">Keine aktive Aufgabe</p>}

            {job && tab === "overview" && (
          <dl className="space-y-2 text-xs">
            <Row label="Status">
              <JobStatusBadge status={job.status} />
            </Row>
            {(job.implementation_plan as Record<string, unknown>)?.last_review != null && (
              <Row label="Review-Score">
                {String(
                  ((job.implementation_plan as Record<string, Record<string, unknown>>).last_review
                    ?.score as string | number) ?? "—",
                )}
                /100
              </Row>
            )}
            <Row label="Korrekturrunden">
              {job.review_rounds ?? 0}/{job.max_review_rounds ?? 3}
            </Row>
            <Row label="Schritt">{job.current_step || "—"}</Row>
            <Row label="Fortschritt">{job.progress_percent}%</Row>
            <Row label="Branch">{job.branch_name || "—"}</Row>
            <Row label="Modus">{job.mode}</Row>
            <Row label="Adapter">{job.adapter_type}</Row>
            <Row label="Gestartet">
              {job.started_at ? new Date(job.started_at).toLocaleString() : "—"}
            </Row>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
              <div
                className="h-full bg-brand-500 transition-all"
                style={{ width: `${job.progress_percent}%` }}
              />
            </div>
            {(job.implementation_plan as Record<string, unknown>)?.phases_completed != null && (
              <div className="mt-4">
                <p className="mb-1 text-xs font-semibold text-slate-500">Orchestra-Phasen</p>
                <ul className="space-y-1 text-xs">
                  {(
                    (job.implementation_plan as Record<string, Array<{ phase: string; summary: string }>>)
                      .phases_completed ?? []
                  ).map((p) => (
                    <li key={p.phase} className="rounded border border-slate-200 px-2 py-1 dark:border-slate-700">
                      {p.phase}: {p.summary?.slice(0, 60)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {job.status === "completed" && (
              <div className="mt-4 flex flex-wrap gap-2">
                <GitButton
                  label="Commit"
                  disabled={gitBusy}
                  onClick={async () => {
                    if (!job.id) return;
                    setGitBusy(true);
                    try {
                      await vibeApi.commitJob(job.id, `orchestra: ${job.title}`);
                      onRefresh?.();
                    } finally {
                      setGitBusy(false);
                    }
                  }}
                />
                <GitButton
                  label="Push"
                  disabled={gitBusy}
                  onClick={async () => {
                    if (!job.id) return;
                    setGitBusy(true);
                    try {
                      await vibeApi.pushJob(job.id);
                      onRefresh?.();
                    } finally {
                      setGitBusy(false);
                    }
                  }}
                />
                <GitButton
                  label="Rollback"
                  disabled={gitBusy}
                  onClick={async () => {
                    if (!job.id || !confirm("Stash wiederherstellen?")) return;
                    setGitBusy(true);
                    try {
                      await vibeApi.rollbackJob(job.id);
                      onRefresh?.();
                    } finally {
                      setGitBusy(false);
                    }
                  }}
                />
              </div>
            )}
          </dl>
        )}

        {job && tab === "files" && (
          <ul className="space-y-2 font-mono text-xs">
            {job.file_changes.length === 0 && (
              <li className="text-slate-500">Noch keine Dateiänderungen</li>
            )}
            {job.file_changes.map((f) => (
              <li key={f.id} className="rounded border border-slate-200 p-2 dark:border-slate-700">
                <span
                  className={cn(
                    "mr-2 rounded px-1 text-[10px] font-bold uppercase",
                    f.change_type === "created"
                      ? "bg-green-100 text-green-800"
                      : "bg-amber-100 text-amber-800",
                  )}
                >
                  {f.change_type}
                </span>
                {f.path}
              </li>
            ))}
          </ul>
        )}

        {job && tab === "diff" && (
          <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-slate-950 p-2 font-mono text-[11px] text-green-400">
            {diff || "Kein Diff verfügbar"}
          </pre>
        )}

        {job && tab === "terminal" && (
          <div>
            <input
              className="mb-2 w-full rounded border border-slate-200 px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-800"
              placeholder="Terminal durchsuchen…"
              value={termQuery}
              onChange={(e) => setTermQuery(e.target.value)}
            />
            <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded bg-slate-950 p-2 font-mono text-[11px] text-slate-200">
              {terminalLines.join("\n") || "Keine Ausgabe"}
            </pre>
          </div>
        )}

        {job && tab === "tests" && (
          <div className="space-y-2 text-xs">
            {!tests && <p className="text-slate-500">Keine Testergebnisse</p>}
            {tests && (
              <>
                <p>Build: {tests.build_status}</p>
                <p>Lint: {tests.lint_status}</p>
                <p>
                  Tests: {tests.tests.passed} OK, {tests.tests.failed} fehlgeschlagen,{" "}
                  {tests.tests.skipped} übersprungen
                </p>
              </>
            )}
          </div>
        )}

        {job && tab === "history" && (
          <ul className="space-y-1 text-xs">
            {events.map((e) => (
              <li key={e.id} className="border-b border-slate-100 py-1 dark:border-slate-800">
                <span className="text-slate-400">
                  {new Date(e.created_at).toLocaleTimeString()}
                </span>{" "}
                <span className="font-medium">{e.event_type}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

function GitButton({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-md border border-slate-200 px-2 py-1 text-xs font-medium hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:hover:bg-slate-800"
    >
      {label}
    </button>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800 dark:text-slate-200">{children}</dd>
    </div>
  );
}
