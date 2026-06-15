import { useState } from "react";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import { Field, Textarea } from "../ui/Field";
import { Markdown } from "../common/Markdown";
import { Badge } from "../ui/Badge";
import { Api } from "../../api/endpoints";
import { copyToClipboard } from "../../utils/clipboard";
import type { CouncilSession } from "../../types";

export function ImplementationPanel({
  session,
  onUpdated,
  onError,
}: {
  session: CouncilSession;
  onUpdated: (s: CouncilSession) => void;
  onError: (msg: string) => void;
}) {
  const impl = session.implementation;
  const existingFiles = Array.isArray(impl?.changed_files)
    ? (impl?.changed_files as string[]).join("\n")
    : "";
  const [files, setFiles] = useState(existingFiles);
  const [summary, setSummary] = useState(impl?.summary ?? "");
  const [busy, setBusy] = useState<string | null>(null);
  const [improvement, setImprovement] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const markImplemented = async () => {
    setBusy("mark");
    onError("");
    try {
      const list = files
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      onUpdated(await Api.markImplemented(session.id, list, summary));
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const review = async () => {
    setBusy("review");
    onError("");
    try {
      onUpdated(await Api.reviewImplementation(session.id));
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const getImprovement = async () => {
    setBusy("improve");
    onError("");
    try {
      const { markdown } = await Api.improvementPrompt(session.id);
      setImprovement(markdown);
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const copyImprovement = async () => {
    if (!improvement) return;
    const ok = await copyToClipboard(improvement);
    setCopied(ok);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Card>
      <CardHeader
        title="Implementation Review"
        subtitle="Umsetzungsergebnis eintragen und prüfen lassen"
        actions={impl?.status ? <Badge tone="info">{impl.status}</Badge> : undefined}
      />
      <CardBody className="space-y-4">
        <Field label="Geänderte Dateien" hint="eine Zeile pro Pfad">
          <Textarea
            rows={4}
            value={files}
            onChange={(e) => setFiles(e.target.value)}
            placeholder={"src/components/LoginForm.tsx\ntests/login_form.test.tsx"}
          />
        </Field>
        <Field label="Zusammenfassung der Umsetzung">
          <Textarea
            rows={3}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="Was wurde umgesetzt?"
          />
        </Field>

        <div className="flex flex-wrap gap-2">
          <Button loading={busy === "mark"} onClick={markImplemented}>
            Als umgesetzt markieren
          </Button>
          <Button
            variant="secondary"
            loading={busy === "review"}
            disabled={!impl || impl.status === "pending"}
            onClick={review}
          >
            Review starten
          </Button>
        </div>

        {impl?.review_result && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Review-Ergebnis
            </h4>
            <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/50">
              <Markdown content={impl.review_result} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" loading={busy === "improve"} onClick={getImprovement}>
                Verbesserungs-Prompt generieren
              </Button>
              {improvement && (
                <Button size="sm" variant="ghost" onClick={copyImprovement}>
                  {copied ? "Kopiert ✓" : "Kopieren"}
                </Button>
              )}
            </div>
            {improvement && (
              <div className="mt-3 max-h-72 overflow-y-auto rounded-lg border border-slate-200 p-3 dark:border-slate-700">
                <Markdown content={improvement} />
              </div>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
