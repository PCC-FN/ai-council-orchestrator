import { useState } from "react";
import { Field, Input, Textarea } from "../ui/Field";
import { Button } from "../ui/Button";
import { InlineError } from "../common/States";
import type { Project, ProjectInput } from "../../types";

const EMPTY: ProjectInput = {
  name: "",
  description: "",
  repository_path: "",
  coding_rules: "",
  security_rules: "",
  tech_stack: "",
  excluded_paths: "",
};

export function ProjectForm({
  initial,
  submitLabel = "Speichern",
  onSubmit,
  onCancel,
}: {
  initial?: Project;
  submitLabel?: string;
  onSubmit: (input: ProjectInput) => Promise<void>;
  onCancel?: () => void;
}) {
  const [form, setForm] = useState<ProjectInput>(
    initial
      ? {
          name: initial.name,
          description: initial.description,
          repository_path: initial.repository_path,
          coding_rules: initial.coding_rules,
          security_rules: initial.security_rules,
          tech_stack: initial.tech_stack,
          excluded_paths: initial.excluded_paths,
        }
      : EMPTY,
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof ProjectInput) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async () => {
    if (!form.name.trim()) {
      setError("Bitte einen Projektnamen angeben.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit(form);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && <InlineError message={error} />}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Projektname">
          <Input value={form.name} onChange={set("name")} placeholder="z. B. Beispiel React App" />
        </Field>
        <Field label="Bevorzugter Tech-Stack" hint="kommagetrennt">
          <Input
            value={form.tech_stack}
            onChange={set("tech_stack")}
            placeholder="React, Vite, TypeScript"
          />
        </Field>
      </div>

      <Field label="Beschreibung">
        <Textarea rows={2} value={form.description} onChange={set("description")} />
      </Field>

      <Field label="Repository-Pfad" hint="absoluter Pfad, optional">
        <Input
          value={form.repository_path}
          onChange={set("repository_path")}
          placeholder="/opt/projekte/app"
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Coding-Regeln">
          <Textarea rows={4} value={form.coding_rules} onChange={set("coding_rules")} />
        </Field>
        <Field label="Security-Regeln">
          <Textarea rows={4} value={form.security_rules} onChange={set("security_rules")} />
        </Field>
      </div>

      <Field label="Ausgeschlossene Dateien/Ordner" hint="kommagetrennt">
        <Input
          value={form.excluded_paths}
          onChange={set("excluded_paths")}
          placeholder="node_modules, dist, .env"
        />
      </Field>

      <div className="flex gap-2">
        <Button onClick={submit} loading={saving}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button variant="secondary" onClick={onCancel} disabled={saving}>
            Abbrechen
          </Button>
        )}
      </div>
    </div>
  );
}
