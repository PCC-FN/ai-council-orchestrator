import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sidebar } from "../components/layout/Sidebar";
import { VibeChatPanel } from "../components/vibe/VibeChatPanel";
import { VibeDetailPanel } from "../components/vibe/VibeDetailPanel";
import { VibeSidebar } from "../components/vibe/VibeSidebar";
import { Button } from "../components/ui/Button";
import { useTheme } from "../hooks/useTheme";
import { useVibeJob, useVibeWorkers } from "../hooks/useVibeJob";
import type { CodingMode, WorkerProject } from "../api/vibe";
import { ApiError } from "../api/client";
import { vibeApi } from "../api/vibe";

async function withGatewayRetry<T>(fn: () => Promise<T>, attempts = 3): Promise<T> {
  let last: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fn();
    } catch (err) {
      last = err;
      const retryable =
        err instanceof ApiError && (err.status === 502 || err.status === 503) && i < attempts - 1;
      if (!retryable) throw err;
      await new Promise((resolve) => window.setTimeout(resolve, 1500 * (i + 1)));
    }
  }
  throw last;
}

const MODES: { id: CodingMode; label: string; hint: string }[] = [
  { id: "direct", label: "Direkt", hint: "Schnell an Cursor, minimal strukturiert" },
  { id: "ai_review", label: "AI Review", hint: "Mehrere KI-Modelle prüfen die Aufgabe" },
  { id: "orchestra", label: "Orchestra", hint: "Vollständiger Multi-Agent-Prozess" },
  { id: "autonomous", label: "Autonom", hint: "Automatisch, gefährliche Aktionen brauchen Freigabe" },
];

export default function VibeCoding() {
  const { theme, toggle } = useTheme();
  const { workers, refresh: refreshWorkers, authError } = useVibeWorkers();
  const [projects, setProjects] = useState<WorkerProject[]>([]);
  const [jobs, setJobs] = useState<Awaited<ReturnType<typeof vibeApi.listJobs>>>([]);
  const [workerId, setWorkerId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [mode, setMode] = useState<CodingMode>("direct");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mobileNav, setMobileNav] = useState(false);

  const { job, setJob, events, connected } = useVibeJob(activeJobId);

  const refreshJobs = useCallback(() => {
    vibeApi.listJobs().then(setJobs).catch(() => {});
  }, []);

  useEffect(() => {
    refreshJobs();
    const t = window.setInterval(refreshJobs, 8000);
    return () => clearInterval(t);
  }, [refreshJobs]);

  useEffect(() => {
    if (!workerId) {
      setProjects([]);
      return;
    }
    vibeApi.listProjects(workerId).then(setProjects).catch(() => setProjects([]));
  }, [workerId]);

  const submitNewTask = async (prompt: string) => {
    if (!workerId || !projectId) {
      setError("Bitte Worker und Projekt auswählen.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let j = await withGatewayRetry(() =>
        vibeApi.createJob({
          worker_id: workerId,
          project_id: projectId,
          prompt,
          mode,
        }),
      );
      j = await withGatewayRetry(() => vibeApi.analyzeJob(j.id));
      if (j.status === "queued") {
        j = await withGatewayRetry(() => vibeApi.startJob(j.id));
      }
      setActiveJobId(j.id);
      setJob(j);
      refreshJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fehler beim Erstellen");
    } finally {
      setBusy(false);
    }
  };

  const handleSend = async (text: string) => {
    if (!activeJobId) {
      await submitNewTask(text);
      return;
    }
    setBusy(true);
    try {
      const j = await withGatewayRetry(() => vibeApi.sendMessage(activeJobId, text));
      setJob(j);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Senden fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  const handleApprove = async () => {
    if (!activeJobId) return;
    setBusy(true);
    try {
      const j = await vibeApi.approveJob(activeJobId);
      setJob(j);
      refreshJobs();
    } finally {
      setBusy(false);
    }
  };

  const handleApproveCorrection = async () => {
    if (!activeJobId) return;
    setBusy(true);
    try {
      const j = await vibeApi.approveCorrection(activeJobId);
      setJob(j);
      refreshJobs();
    } finally {
      setBusy(false);
    }
  };

  const handleAcceptResult = async () => {
    if (!activeJobId) return;
    setBusy(true);
    try {
      const j = await vibeApi.acceptResult(activeJobId);
      setJob(j);
      refreshJobs();
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    if (!activeJobId) return;
    setBusy(true);
    try {
      await vibeApi.rejectJob(activeJobId);
      refreshJobs();
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = async () => {
    if (!activeJobId) return;
    setBusy(true);
    try {
      const j = await vibeApi.cancelJob(activeJobId);
      setJob(j);
      refreshJobs();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full">
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-2 dark:border-slate-800 dark:bg-slate-900">
          <Button variant="ghost" size="sm" className="lg:hidden" onClick={() => setMobileNav(true)}>
            ☰
          </Button>
          <h1 className="text-base font-semibold">Vibe Coding</h1>
          <div className="flex flex-1 flex-wrap items-center gap-2 pl-2">
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                title={m.hint}
                onClick={() => setMode(m.id)}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  mode === m.id
                    ? "bg-brand-600 text-white"
                    : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <span className="text-xs text-slate-400">
            {activeJobId ? (connected ? "Job live" : "Job offline") : null}
          </span>
          <Button variant="ghost" size="sm" onClick={toggle}>
            {theme === "dark" ? "☀" : "☾"}
          </Button>
          <Button variant="ghost" size="sm" onClick={refreshWorkers}>
            ↻
          </Button>
        </header>

        {authError && (
          <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
            {authError}{" "}
            <Link to="/settings" className="font-medium underline">
              Zu den Einstellungen
            </Link>
          </div>
        )}

        {error && (
          <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
            {error}
          </div>
        )}

        <div className="flex min-h-0 flex-1">
          <VibeSidebar
            workers={workers}
            projects={projects}
            jobs={jobs}
            selectedWorkerId={workerId}
            selectedProjectId={projectId}
            activeJobId={activeJobId}
            onSelectWorker={(id) => {
              setWorkerId(id);
              setProjectId(null);
            }}
            onSelectProject={setProjectId}
            onSelectJob={(id) => {
              setActiveJobId(id);
              vibeApi.getJob(id).then(setJob).catch(() => {});
            }}
          />

          <div className="flex min-w-0 flex-1 flex-col p-3">
            {!workerId || !projectId ? (
              <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-600">
                <div>
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                    Worker und Projekt auswählen
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Links einen verbundenen Worker und ein freigegebenes Projekt wählen, dann die
                    Aufgabe im Chat eingeben.
                  </p>
                </div>
              </div>
            ) : !activeJobId ? (
              <div className="flex flex-1 flex-col">
                <VibeChatPanel
                  job={null}
                  onSend={submitNewTask}
                  onApprove={() => {}}
                  onReject={() => {}}
                  onCancel={() => {}}
                  busy={busy}
                />
              </div>
            ) : (
              <VibeChatPanel
                job={job}
                onSend={handleSend}
                onApprove={handleApprove}
                onApproveCorrection={handleApproveCorrection}
                onAcceptResult={handleAcceptResult}
                onReject={handleReject}
                onCancel={handleCancel}
                busy={busy}
              />
            )}
          </div>

          <VibeDetailPanel
            job={job}
            events={events}
            onRefresh={() => activeJobId && vibeApi.getJob(activeJobId).then(setJob)}
          />
        </div>
      </div>

      {mobileNav && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileNav(false)} />
          <div className="absolute left-0 top-0 h-full">
            <Sidebar onNavigate={() => setMobileNav(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
