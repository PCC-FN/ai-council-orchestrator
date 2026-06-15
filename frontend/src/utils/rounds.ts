import type { PhaseExecution } from "../api/orchestra";
import type { CouncilSession, RoundStatus } from "../types";

export type Stage = {
  key: string;
  label: string;
  roundName?: string;
  currentRounds: string[];
};

/** 12-phase AI Orchestra workflow. */
export const STAGES: Stage[] = [
  { key: "understand_problem", label: "Problem verstehen", currentRounds: ["understand_problem", "pending"] },
  { key: "develop_architecture", label: "Architektur", roundName: "initial_assessment", currentRounds: ["develop_architecture", "initial_assessment"] },
  { key: "agent_discussion", label: "Diskussion", roundName: "cross_review", currentRounds: ["agent_discussion", "cross_review"] },
  { key: "find_consensus", label: "Konsens", currentRounds: ["find_consensus", "consensus_build", "consensus_approval"] },
  { key: "prompt_engineering", label: "Prompt Engineering", currentRounds: ["prompt_engineering"] },
  { key: "prompt_review", label: "Prompt Review", roundName: "prompt_review", currentRounds: ["prompt_review"] },
  { key: "handoff_worker", label: "Worker-Übergabe", currentRounds: ["handoff_worker"] },
  { key: "implementation", label: "Implementierung", currentRounds: ["implementation"] },
  { key: "code_review", label: "Code Review", roundName: "code_review", currentRounds: ["code_review"] },
  { key: "improvement_rounds", label: "Verbesserung", currentRounds: ["improvement_rounds"] },
  { key: "git_commit", label: "Git Commit", currentRounds: ["git_commit"] },
  { key: "pull_request", label: "Pull Request", currentRounds: ["pull_request"] },
];

function hasRound(session: CouncilSession, roundName?: string): boolean {
  if (!roundName) return false;
  return session.agent_responses.some((r) => r.round_name === roundName);
}

function phaseExecStatus(
  executions: PhaseExecution[],
  key: string,
): PhaseExecution | undefined {
  return executions.find((e) => e.phase_key === key);
}

function stageCompleted(
  session: CouncilSession,
  stage: Stage,
  executions: PhaseExecution[],
): boolean {
  const ex = phaseExecStatus(executions, stage.key);
  if (ex?.status === "completed") return true;
  switch (stage.key) {
    case "find_consensus":
      return !!session.consensus;
    case "prompt_engineering":
      return session.final_prompts.length > 0;
    case "implementation":
      return (
        !!session.implementation &&
        ["implemented", "reviewed"].includes(session.implementation.status)
      );
    case "code_review":
      return !!session.implementation?.review_result;
    case "pull_request":
      return session.status === "completed";
    default:
      return hasRound(session, stage.roundName);
  }
}

export function deriveRoundStatuses(
  session: CouncilSession,
  activeRound?: string | null,
  executions: PhaseExecution[] = [],
): Record<string, RoundStatus> {
  const out: Record<string, RoundStatus> = {};
  for (const stage of STAGES) {
    const ex = phaseExecStatus(executions, stage.key);
    const completed = stageCompleted(session, stage, executions);
    const isActive =
      session.current_phase === stage.key ||
      (!!activeRound && stage.currentRounds.includes(activeRound)) ||
      ex?.status === "running";
    if (ex?.status === "failed") out[stage.key] = "error";
    else if (isActive && !completed) out[stage.key] = "running";
    else if (completed) out[stage.key] = "completed";
    else out[stage.key] = "pending";
  }
  if (session.consensus?.approval_status === "revisions_requested") {
    out["find_consensus"] = "error";
  }
  return out;
}

export function phaseLabel(key: string): string {
  return STAGES.find((s) => s.key === key)?.label ?? key;
}

const STATUS_LABELS: Record<string, string> = {
  created: "Erstellt",
  normalized: "Normalisiert",
  waiting_worker: "Wartet auf Worker",
  round_1_done: "Architektur fertig",
  round_2_done: "Diskussion fertig",
  consensus_draft: "Konsens-Entwurf",
  consensus_blocked: "Konsens blockiert",
  consensus_approved: "Konsens freigegeben",
  prompt_draft: "Prompt-Entwurf",
  prompt_revisions: "Prompt überarbeiten",
  prompt_ready: "Prompt bereit",
  ready_for_implementation: "Bereit für Umsetzung",
  implemented: "Umgesetzt",
  needs_revision: "Überarbeitung nötig",
  completed: "Abgeschlossen",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function nextStepHint(session: CouncilSession): string {
  switch (session.current_phase) {
    case "understand_problem":
      return "AI Orchestra analysiert die Feature-Beschreibung.";
    case "handoff_worker":
    case "implementation":
      return "Ein registrierter Coding-Worker holt den Implementierungs-Job ab.";
    case "git_commit":
    case "pull_request":
      return "Git Commit und Pull Request werden über Worker-Jobs vorbereitet.";
    default:
      break;
  }
  if (session.status === "waiting_worker") {
    return "Worker-Implementierung ausstehend — AI Orchestra Worker auf dem Notebook starten.";
  }
  if (session.status === "completed") {
    return "Feature-Workflow abgeschlossen.";
  }
  return "Nächste Phase starten oder vollständig orchestrieren lassen.";
}

export function isActiveSession(status: string): boolean {
  return status !== "completed";
}
