import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { SessionCard } from "../components/session/SessionCard";
import { LoadingState, ErrorState, EmptyState } from "../components/common/States";
import { Api } from "../api/endpoints";
import { isActiveSession } from "../utils/rounds";
import type { CouncilSessionSummary, Project } from "../types";

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, s] = await Promise.all([Api.listProjects(), Api.listSessions()]);
      setProjects(p);
      setSessions(s);
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
      title="Dashboard"
      actions={
        <>
          <Button variant="secondary" size="sm" onClick={() => nav("/projects")}>
            Neues Projekt
          </Button>
          <Button size="sm" onClick={() => nav("/sessions/new")}>
            Neue Council-Session
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
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Projekte" value={projects.length} />
            <Stat label="Aktive Sessions" value={active.length} />
            <Stat label="Abgeschlossen" value={completed.length} />
            <Stat label="Sessions gesamt" value={sessions.length} />
          </div>

          <Card>
            <CardHeader
              title="Aktive Council-Sessions"
              subtitle="Laufende oder pausierte Sessions"
            />
            <CardBody>
              {active.length === 0 ? (
                <EmptyState
                  title="Keine aktiven Sessions"
                  description="Starte eine neue Council-Session, um eine Coding-Aufgabe zu bearbeiten."
                  action={
                    <Button size="sm" onClick={() => nav("/sessions/new")}>
                      Neue Council-Session
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
