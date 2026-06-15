import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { ProjectCard } from "../components/project/ProjectCard";
import { ProjectForm } from "../components/project/ProjectForm";
import { LoadingState, ErrorState, EmptyState } from "../components/common/States";
import { Api } from "../api/endpoints";
import type { CouncilSessionSummary, Project, ProjectInput } from "../types";

export default function Projects() {
  const nav = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [sessions, setSessions] = useState<CouncilSessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Project | null>(null);

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

  const countFor = (id: string) => sessions.filter((s) => s.project_id === id).length;

  const create = async (input: ProjectInput) => {
    await Api.createProject(input);
    setCreating(false);
    await load();
  };

  const update = async (input: ProjectInput) => {
    if (!editing) return;
    await Api.updateProject(editing.id, input);
    setEditing(null);
    await load();
  };

  const remove = async (p: Project) => {
    if (!confirm(`Projekt „${p.name}“ und alle zugehörigen Sessions löschen?`)) return;
    try {
      await Api.deleteProject(p.id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <AppLayout
      title="Projekte"
      actions={
        <Button size="sm" onClick={() => setCreating(true)}>
          Neues Projekt
        </Button>
      }
    >
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : projects.length === 0 ? (
        <EmptyState
          title="Noch keine Projekte"
          description="Lege ein Projekt an, um Coding-Regeln und Repository zu hinterlegen."
          action={<Button onClick={() => setCreating(true)}>Projekt anlegen</Button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <ProjectCard
              key={p.id}
              project={p}
              sessionCount={countFor(p.id)}
              onEdit={() => setEditing(p)}
              onDelete={() => remove(p)}
              onNewSession={() => nav(`/sessions/new?project=${p.id}`)}
            />
          ))}
        </div>
      )}

      <Modal open={creating} title="Neues Projekt" onClose={() => setCreating(false)}>
        <ProjectForm submitLabel="Projekt anlegen" onSubmit={create} onCancel={() => setCreating(false)} />
      </Modal>

      <Modal open={!!editing} title="Projekt bearbeiten" onClose={() => setEditing(null)}>
        {editing && (
          <ProjectForm
            initial={editing}
            submitLabel="Änderungen speichern"
            onSubmit={update}
            onCancel={() => setEditing(null)}
          />
        )}
      </Modal>
    </AppLayout>
  );
}
