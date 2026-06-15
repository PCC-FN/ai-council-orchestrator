import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Field, Input, Textarea, Label } from "../components/ui/Field";
import { LoadingState, ErrorState, EmptyState, InlineError } from "../components/common/States";
import { Api } from "../api/endpoints";
import type { Project } from "../types";

export default function NewSession() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const preselected = params.get("project") ?? "";

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [projectId, setProjectId] = useState(preselected);
  const [title, setTitle] = useState("");
  const [task, setTask] = useState("");
  const [affected, setAffected] = useState("");
  const [outcome, setOutcome] = useState("");
  const [constraints, setConstraints] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [startNow, setStartNow] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Api.listProjects()
      .then((p) => {
        setProjects(p);
        if (!preselected && p.length === 1) setProjectId(p[0].id);
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [preselected]);

  const valid = useMemo(
    () => projectId && title.trim() && task.trim(),
    [projectId, title, task],
  );

  const submit = async () => {
    if (!valid) {
      setError("Projekt, Titel und Aufgabe sind erforderlich.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const session = await Api.createSession({
        project_id: projectId,
        title: title.trim(),
        original_user_task: task.trim(),
        affected_files: affected.trim(),
        desired_outcome: outcome.trim(),
        constraints: constraints.trim(),
      });
      if (startNow) {
        try {
          await Api.startSession(session.id);
        } catch {
          /* navigate anyway; user can start manually */
        }
      }
      nav(`/sessions/${session.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  };

  return (
    <AppLayout title="Neue Council-Session">
      {loading ? (
        <LoadingState />
      ) : loadError ? (
        <ErrorState message={loadError} />
      ) : projects.length === 0 ? (
        <EmptyState
          title="Kein Projekt vorhanden"
          description="Lege zuerst ein Projekt an, bevor du eine Session startest."
          action={<Button onClick={() => nav("/projects")}>Zu den Projekten</Button>}
        />
      ) : (
        <Card className="mx-auto max-w-3xl">
          <CardHeader title="Aufgabe für das Council" subtitle="Beschreibe die Coding-Aufgabe so konkret wie möglich" />
          <CardBody className="space-y-4">
            {error && <InlineError message={error} />}

            <Field label="Projekt">
              <select
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              >
                <option value="">– Projekt wählen –</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Titel">
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="z. B. Login-Formular mit Validierung ergänzen"
              />
            </Field>

            <Field label="Aufgabe / Beschreibung">
              <Textarea
                rows={4}
                value={task}
                onChange={(e) => setTask(e.target.value)}
                placeholder="Was soll umgesetzt werden?"
              />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Betroffene Dateien / Module" hint="optional">
                <Textarea
                  rows={3}
                  value={affected}
                  onChange={(e) => setAffected(e.target.value)}
                  placeholder="src/components/LoginForm.tsx"
                />
              </Field>
              <Field label="Gewünschtes Ergebnis" hint="optional">
                <Textarea
                  rows={3}
                  value={outcome}
                  onChange={(e) => setOutcome(e.target.value)}
                  placeholder="Erwartetes Verhalten / Akzeptanzkriterien"
                />
              </Field>
            </div>

            <Field label="Einschränkungen" hint="optional">
              <Textarea
                rows={2}
                value={constraints}
                onChange={(e) => setConstraints(e.target.value)}
                placeholder="z. B. keine neuen Abhängigkeiten"
              />
            </Field>

            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
              <input
                type="checkbox"
                checked={startNow}
                onChange={(e) => setStartNow(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              />
              Council direkt starten (normalisieren + Runde 1)
            </label>

            <div className="flex items-center gap-2 border-t border-slate-100 pt-4 dark:border-slate-800">
              <Button onClick={submit} loading={submitting} disabled={!valid}>
                Council starten
              </Button>
              <Button variant="secondary" onClick={() => nav(-1)} disabled={submitting}>
                Abbrechen
              </Button>
              {!valid && <Label>Projekt, Titel und Aufgabe ausfüllen.</Label>}
            </div>
          </CardBody>
        </Card>
      )}
    </AppLayout>
  );
}
