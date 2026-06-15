import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { SessionCard } from "../components/session/SessionCard";
import { LoadingState, ErrorState, EmptyState } from "../components/common/States";
import { Api } from "../api/endpoints";
import { fetchOrchestraDashboard } from "../api/orchestra";
import { isActiveSession } from "../utils/rounds";
import type { CouncilSessionSummary, Project } from "../types";
import type { OrchestraDashboard } from "../api/orchestra";
import { Badge } from "../components/ui/Badge";

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardBody>
        <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
        <p className="mt-1 text-xs text-slate-500">{label}</p>
      </CardBody>
    </Card>
  );
}

export default function Dashboard() {
  const nav = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [sessions, setSessions] = useState<CouncilSessionSummary[]>([]);
  const [orchestra, setOrchestra] = useState<OrchestraDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, s, o] = await Promise.all([
        Api.listProjects(),
        Api.listSessions(),
        fetchOrchestraDashboard(),
      ]);
      setProjects(p);
      setSessions(s);
      setOrchestra(o);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const active = sessions.filter((s) => isActiveSession(s.status));
  const completed = sessions.filter((s) => !isActiveSession(s.status));

  return (
    <AppLayout
      title="AI Orchestra — Dashboard"
      actions={
        <>
          <Button variant="secondary" size="sm" onClick={() => nav("/projects")}>
            Neues Projekt
          </Button>
          <Button size="sm" onClick={() => nav("/sessions/new")}>
            Neues Feature
          </Button>
        </>
      }
    >
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label="Projekte" value={projects.length} />
            <Stat label="Aktive Features" value={orchestra?.active_tasks ?? active.length} />
            <Stat label="Agenten aktiv" value={orchestra?.agents.length ?? 0} />
            <Stat label="Worker online" value={orchestra?.active_workers ?? 0} />
            <Stat label="Jobs wartend" value={orchestra?.pending_jobs ?? 0} />
            <Stat label="Jobs laufen" value={orchestra?.running_jobs ?? 0} />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader title="Registrierte Worker" subtitle="Coding-Worker im Netzwerk" />
              <CardBody>
                {!orchestra?.workers.length ? (
                  <EmptyState
                    title="Kein Worker verbunden"
                    description="Starte den AI Orchestra Worker auf deinem Notebook, um Implementierungs-Jobs auszuführen."
                  />
                ) : (
                  <ul className="space-y-2">
                    {orchestra.workers.map((w) => (
                      <li
                        key={w.id}
                        className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-800"
                      >
                        <div>
                          <p className="text-sm font-medium">{w.name}</p>
                          <p className="text-xs text-slate-500">
                            {w.worker_type} · {w.hostname || "—"}
                          </p>
                        </div>
                        <Badge tone={w.status === "offline" ? "neutral" : w.status === "busy" ? "info" : "success"}>
                          {w.status}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="KI-Agenten" subtitle="Konfigurierte Agenten im Orchestra" />
              <CardBody>
                <ul className="space-y-2">
                  {(orchestra?.agents ?? []).map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-800"
                    >
                      <div>
                        <p className="text-sm font-medium">{a.display_name}</p>
                        <p className="text-xs text-slate-500">{a.role}</p>
                      </div>
                      <Badge tone="neutral">{a.provider}</Badge>
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          </div>

          {orchestra && orchestra.recent_events.length > 0 && (
            <Card>
              <CardHeader title="Live-Events" subtitle="Persistenter Event-Stream" />
              <CardBody>
                <ul className="max-h-48 space-y-1 overflow-y-auto text-xs">
                  {orchestra.recent_events.slice(0, 20).map((e) => (
                    <li key={e.id} className="flex gap-2">
                      <span className="shrink-0 text-slate-400">
                        {new Date(e.created_at).toLocaleTimeString()}
                      </span>
                      <span className="font-medium">{e.event_type}</span>
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          )}

          <Card>
            <CardHeader
              title="Aktive Features"
              subtitle="Laufende Orchestrierungen"
            />
            <CardBody>
              {active.length === 0 ? (
                <EmptyState
                  title="Keine aktiven Features"
                  description="Beschreibe ein neues Feature — AI Orchestra übernimmt die komplette Orchestrierung."
                  action={
                    <Button size="sm" onClick={() => nav("/sessions/new")}>
                      Neues Feature
                    </Button>
                  }
                />
              ) : (
                <div className="grid gap-3">
                  {active.map((s) => (
                    <SessionCard key={s.id} session={s} />
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          {completed.length > 0 && (
            <Card>
              <CardHeader title="Abgeschlossene Sessions" />
              <CardBody>
                <div className="grid gap-3">
                  {completed.map((s) => (
                    <SessionCard key={s.id} session={s} />
                  ))}
                </div>
              </CardBody>
            </Card>
          )}

          <Card>
            <CardHeader
              title="Projekte"
              subtitle="Übersicht aller Projekte"
              actions={
                <Button size="sm" variant="secondary" onClick={() => nav("/projects")}>
                  Verwalten
                </Button>
              }
            />
            <CardBody>
              {projects.length === 0 ? (
                <EmptyState
                  title="Noch keine Projekte"
                  description="Lege ein Projekt an, um Council-Sessions zu starten."
                  action={
                    <Button size="sm" onClick={() => nav("/projects")}>
                      Projekt anlegen
                    </Button>
                  }
                />
              ) : (
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {projects.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => nav("/projects")}
                      className="rounded-lg border border-slate-200 px-3 py-2 text-left text-sm transition hover:border-brand-300 hover:bg-brand-50/50 dark:border-slate-800 dark:hover:border-brand-500/40 dark:hover:bg-brand-500/5"
                    >
                      <p className="truncate font-medium text-slate-900 dark:text-slate-100">
                        {p.name}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {p.description || "Keine Beschreibung"}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      )}
    </AppLayout>
  );
}
