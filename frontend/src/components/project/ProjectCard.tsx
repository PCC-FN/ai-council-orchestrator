import { Card, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import type { Project } from "../../types";

export function ProjectCard({
  project,
  sessionCount,
  onEdit,
  onDelete,
  onNewSession,
}: {
  project: Project;
  sessionCount?: number;
  onEdit: () => void;
  onDelete: () => void;
  onNewSession: () => void;
}) {
  return (
    <Card>
      <CardBody className="flex h-full flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
              {project.name}
            </h3>
            <p className="mt-0.5 line-clamp-2 text-xs text-slate-500 dark:text-slate-400">
              {project.description || "Keine Beschreibung"}
            </p>
          </div>
          {typeof sessionCount === "number" && (
            <Badge tone="info">{sessionCount} Sessions</Badge>
          )}
        </div>

        {project.tech_stack && (
          <div className="flex flex-wrap gap-1">
            {project.tech_stack
              .split(/[,\n]/)
              .map((t) => t.trim())
              .filter(Boolean)
              .slice(0, 6)
              .map((t) => (
                <Badge key={t} tone="neutral">
                  {t}
                </Badge>
              ))}
          </div>
        )}

        {project.repository_path && (
          <p className="truncate font-mono text-xs text-slate-400" title={project.repository_path}>
            {project.repository_path}
          </p>
        )}

        <div className="mt-auto flex flex-wrap gap-2 pt-2">
          <Button size="sm" onClick={onNewSession}>
            Neue Session
          </Button>
          <Button size="sm" variant="secondary" onClick={onEdit}>
            Bearbeiten
          </Button>
          <Button size="sm" variant="ghost" onClick={onDelete}>
            Löschen
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
