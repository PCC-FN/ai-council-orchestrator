import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { StatusBadge } from "../components/common/StatusBadge";
import { LoadingState, ErrorState, EmptyState, InlineError } from "../components/common/States";
import { Markdown } from "../components/common/Markdown";
import { RoundProgress } from "../components/session/RoundProgress";
import {
  AgentResponseCard,
  AgentPendingCard,
} from "../components/session/AgentResponseCard";
import { ConsensusPanel } from "../components/session/ConsensusPanel";
import { FinalPromptPanel } from "../components/session/FinalPromptPanel";
import { ImplementationPanel } from "../components/session/ImplementationPanel";
import { MarkdownExportButton } from "../components/session/MarkdownExportButton";
import { Api } from "../api/endpoints";
import { useSessionSocket } from "../hooks/useSessionSocket";
import { useSettings } from "../hooks/useSettings";
import { fetchTaskPhases } from "../api/orchestra";
import { STAGES, nextStepHint, phaseLabel } from "../utils/rounds";
import type { PhaseExecution } from "../api/orchestra";
import { agentMeta } from "../utils/agents";
import type { AgentResponse, AgentStatus, CouncilSession } from "../types";

const ROUND_TABS = STAGES.filter((s) => s.roundName);
const AGENTS_PER_ROUND: Record<string, string[]> = {
  initial_assessment: ["chatgpt_architect", "claude_reviewer", "compose2_implementation"],
  cross_review: ["chatgpt_architect", "claude_reviewer", "compose2_implementation"],
  consensus_approval: ["chatgpt_architect", "claude_reviewer", "compose2_implementation"],
  prompt_review: ["chatgpt_architect", "claude_reviewer", "compose2_implementation"],
  code_review: ["chatgpt_architect", "claude_reviewer"],
};

const WAITING = ["prompt_ready", "ready_for_implementation", "needs_revision", "completed"];

function RoundTabs({
  session,
  activeRound,
  activeAgent,
}: {
  session: CouncilSession;
  activeRound: string | null;
  activeAgent: string | null;
}) {
  const byRound = useMemo(() => {
    const map: Record<string, AgentResponse[]> = {};
    for (const r of session.agent_responses) {
      (map[r.round_name] ??= []).push(r);
    }
    return map;
  }, [session.agent_responses]);

  const availableTabs = ROUND_TABS.filter(
    (t) => (byRound[t.roundName!]?.length ?? 0) > 0 || activeRound === t.roundName,
  );

  const [tab, setTab] = useState<string>("");
  const effectiveTab =
    tab && availableTabs.some((t) => t.roundName === tab)
      ? tab
      : availableTabs[availableTabs.length - 1]?.roundName ?? "";

  if (availableTabs.length === 0) {
    return (
      <EmptyState
        title="Noch keine Agenten-Antworten"
        description="Starte das Council oder führe die nächste Runde aus, um Bewertungen zu sehen."
      />
    );
  }

  const responses = byRound[effectiveTab] ?? [];
  const running = activeRound === effectiveTab && responses.length === 0;
  const expectedAgents = AGENTS_PER_ROUND[effectiveTab] ?? [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-1.5">
        {availableTabs.map((t) => {
          const isActive = t.roundName === effectiveTab;
          const isRunning = activeRound === t.roundName;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.roundName!)}
              className={
                "rounded-lg px-3 py-1.5 text-xs font-medium transition " +
                (isActive
                  ? "bg-brand-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700")
              }
            >
              {t.label}
              {isRunning && <span className="ml-1.5 animate-pulse-fast">●</span>}
            </button>
          );
        })}
      </div>

      <div className="grid gap-3">
        {running
          ? expectedAgents.map((a) => (
              <AgentPendingCard
                key={a}
                agentName={a}
                status={(activeAgent === a ? "running" : "waiting") as AgentStatus}
              />
            ))
          : responses.map((r) => <AgentResponseCard key={r.id} response={r} />)}
      </div>
    </div>
  );
}

export default function SessionDetail() {
  const { sessionId } = useParams();
  const settings = useSettings();
  const [session, setSession] = useState<CouncilSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const [phaseExecutions, setPhaseExecutions] = useState<PhaseExecution[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const loadPhases = useCallback(async () => {
    if (!sessionId) return;
    try {
      setPhaseExecutions(await fetchTaskPhases(sessionId));
    } catch {
      /* optional */
    }
  }, [sessionId]);

  const load = useCallback(async () => {
    if (!sessionId) return;
    try {
      setSession(await Api.getSession(sessionId));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
    void loadPhases();
  }, [load, loadPhases]);

  // Any live event triggers a refetch so the UI always reflects backend state.
  const { connected, log, activeRound, activeAgent } = useSessionSocket(sessionId, () => {
    void load();
    void loadPhases();
  });

  const latestPrompt = useMemo(() => {
    if (!session?.final_prompts.length) return null;
    return [...session.final_prompts].sort((a, b) => b.version - a.version)[0];
  }, [session]);

  const runAction = (key: string, fn: () => Promise<CouncilSession>) => async () => {
    setBusy(key);
    setActionError("");
    try {
      setSession(await fn());
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const runAll = async () => {
    if (!sessionId) return;
    setBusy("all");
    setActionError("");
    try {
      setSession(await Api.orchestrateTask(sessionId));
      await loadPhases();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <AppLayout title="Session">
        <LoadingState />
      </AppLayout>
    );
  }
  if (error || !session) {
    return (
      <AppLayout title="Session">
        <ErrorState message={error ?? "Session nicht gefunden"} onRetry={load} />
      </AppLayout>
    );
  }

  const canStart = session.status === "created";
  const advanceable = !canStart && !WAITING.includes(session.status);
  const showApproveConsensus = ["consensus_draft", "consensus_blocked"].includes(session.status);
  const showImplementation = [
    "prompt_ready",
    "ready_for_implementation",
    "implemented",
    "needs_revision",
    "completed",
  ].includes(session.status);

  return (
    <AppLayout
      title={
        <span className="flex items-center gap-2">
          <Link to="/" className="text-slate-400 hover:text-brand-600">
            Sessions
          </Link>
          <span className="text-slate-300">/</span>
          <span className="truncate">{session.title}</span>
        </span>
      }
      actions={<MarkdownExportButton sessionId={session.id} title={session.title} />}
    >
      <div className="space-y-5">
        {/* Status + controls */}
        <Card>
          <CardBody className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={session.status} />
              <Badge tone="info">
                Phase {STAGES.findIndex((s) => s.key === session.current_phase) + 1 || "?"}:{" "}
                {phaseLabel(session.current_phase)}
              </Badge>
              <Badge tone={connected ? "success" : "neutral"}>
                <span
                  className={
                    "h-1.5 w-1.5 rounded-full " +
                    (connected ? "bg-current animate-pulse-fast" : "bg-slate-400")
                  }
                />
                {connected ? "Live verbunden" : "offline"}
              </Badge>
            </div>

            <div className="rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800 dark:bg-brand-500/10 dark:text-brand-200">
              <span className="font-medium">Nächster Schritt: </span>
              {nextStepHint(session)}
            </div>

            {actionError && <InlineError message={actionError} />}

            <div className="flex flex-wrap gap-2">
              {canStart && (
                <Button loading={busy === "start"} onClick={runAction("start", () => Api.startSession(session.id))}>
                  Orchestrierung starten
                </Button>
              )}
              {advanceable && (
                <>
                  <Button
                    loading={busy === "next"}
                    onClick={runAction("next", () => Api.advancePhase(session.id))}
                  >
                    Nächste Phase
                  </Button>
                  <Button variant="secondary" loading={busy === "all"} onClick={runAll}>
                    Auto-Orchestrierung
                  </Button>
                </>
              )}
              {showApproveConsensus && (
                <Button
                  variant="secondary"
                  loading={busy === "approve"}
                  onClick={runAction("approve", () => Api.approveConsensus(session.id))}
                >
                  Konsens manuell freigeben
                </Button>
              )}
            </div>
          </CardBody>
        </Card>

        {/* Round progress */}
        <Card>
          <CardBody>
            <RoundProgress session={session} activeRound={activeRound} phaseExecutions={phaseExecutions} />
            {activeAgent && (
              <p className="mt-3 text-xs text-brand-600 dark:text-brand-300">
                <span className="animate-pulse-fast">●</span> {agentMeta(activeAgent).label} arbeitet…
              </p>
            )}
          </CardBody>
        </Card>

        <div className="grid gap-5 lg:grid-cols-3">
          {/* Main column */}
          <div className="space-y-5 lg:col-span-2">
            <Card>
              <CardHeader title="Agenten-Runden" subtitle="Bewertungen, Bedenken und Zustimmungen" />
              <CardBody>
                <RoundTabs session={session} activeRound={activeRound} activeAgent={activeAgent} />
              </CardBody>
            </Card>

            {session.consensus && <ConsensusPanel consensus={session.consensus} />}

            {latestPrompt && (
              <FinalPromptPanel
                session={session}
                prompt={latestPrompt}
                settings={settings}
                onUpdated={setSession}
                onError={setActionError}
              />
            )}

            {showImplementation && (
              <ImplementationPanel session={session} onUpdated={setSession} onError={setActionError} />
            )}
          </div>

          {/* Side column */}
          <div className="space-y-5">
            <Card>
              <CardHeader title="Aufgabe" />
              <CardBody className="space-y-3">
                <div>
                  <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Originalaufgabe
                  </h4>
                  <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/50">
                    <Markdown content={session.original_user_task} />
                  </div>
                </div>
                {session.normalized_task && (
                  <div>
                    <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Normalisierte Aufgabe
                    </h4>
                    <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/50">
                      <Markdown content={session.normalized_task} />
                    </div>
                  </div>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Live-Aktivität" subtitle="WebSocket-Events" />
              <CardBody>
                {log.length === 0 ? (
                  <p className="text-xs text-slate-400">Noch keine Events.</p>
                ) : (
                  <ul className="max-h-72 space-y-1 overflow-y-auto text-xs">
                    {[...log].reverse().map((e) => (
                      <li key={e.id} className="flex gap-2">
                        <span className="shrink-0 font-mono text-slate-400">{e.ts}</span>
                        <span className="font-medium text-slate-700 dark:text-slate-300">
                          {e.event}
                        </span>
                        {e.detail && <span className="truncate text-slate-500">{e.detail}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
