import { useState } from "react";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { Markdown } from "../common/Markdown";
import { MarkdownExportButton } from "./MarkdownExportButton";
import { Api } from "../../api/endpoints";
import { copyToClipboard } from "../../utils/clipboard";
import type { CouncilSession, FinalPrompt, RuntimeSettings } from "../../types";

function ApprovalDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge tone={ok ? "success" : "neutral"}>
      {ok ? "✓" : "○"} {label}
    </Badge>
  );
}

export function FinalPromptPanel({
  session,
  prompt,
  settings,
  onUpdated,
  onError,
}: {
  session: CouncilSession;
  prompt: FinalPrompt;
  settings: RuntimeSettings | null;
  onUpdated: (s: CouncilSession) => void;
  onError: (msg: string) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const run = (key: string, fn: () => Promise<CouncilSession>) => async () => {
    setBusy(key);
    onError("");
    try {
      onUpdated(await fn());
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const copy = async () => {
    const ok = await copyToClipboard(prompt.prompt_text);
    setCopied(ok);
    setTimeout(() => setCopied(false), 1500);
  };

  const allApproved =
    prompt.approved_by_chatgpt && prompt.approved_by_claude && prompt.approved_by_compose2;
  const manual = settings?.compose2_mode === "manual";
  const submitted = ["ready_for_implementation", "implemented", "needs_revision", "completed"].includes(
    session.status,
  );

  return (
    <Card>
      <CardHeader
        title={`Finaler Prompt · v${prompt.version}`}
        subtitle="Optimierter Coding-Prompt für Compose2"
        actions={
          <div className="flex items-center gap-1.5">
            <ApprovalDot ok={prompt.approved_by_chatgpt} label="GPT" />
            <ApprovalDot ok={prompt.approved_by_claude} label="Claude" />
            <ApprovalDot ok={prompt.approved_by_compose2} label="C2" />
          </div>
        }
      />
      <CardBody className="space-y-4">
        <div className="max-h-96 overflow-y-auto rounded-lg bg-slate-50 p-3 dark:bg-slate-800/50">
          <Markdown content={prompt.prompt_text} />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={copy}>
            {copied ? "Kopiert ✓" : "Prompt kopieren"}
          </Button>
          <MarkdownExportButton sessionId={session.id} title={session.title} />
          <Button
            size="sm"
            variant="secondary"
            loading={busy === "regen"}
            onClick={run("regen", () => Api.generateFinalPrompt(session.id))}
          >
            Erneut optimieren
          </Button>
          {!allApproved && (
            <>
              <Button
                size="sm"
                variant="secondary"
                loading={busy === "review"}
                onClick={run("review", () => Api.reviewFinalPrompt(session.id))}
              >
                Prüfen lassen
              </Button>
              <Button
                size="sm"
                variant="secondary"
                loading={busy === "approve"}
                onClick={run("approve", () => Api.approveFinalPrompt(session.id))}
              >
                Manuell freigeben
              </Button>
            </>
          )}
        </div>

        {manual && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
            <span className="font-semibold">Compose2 läuft im manuellen Modus.</span> Kopiere den
            Prompt, führe ihn in Compose2 aus und markiere die Umsetzung anschließend unten.
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
          <Button
            loading={busy === "submit"}
            disabled={!allApproved || submitted}
            onClick={run("submit", () => Api.submitToCompose2(session.id))}
          >
            An Compose2 übergeben
          </Button>
          {!allApproved && (
            <span className="text-xs text-slate-500">
              Alle drei Freigaben nötig (oder „Manuell freigeben“).
            </span>
          )}
          {submitted && <Badge tone="success">Übergeben</Badge>}
        </div>
      </CardBody>
    </Card>
  );
}
