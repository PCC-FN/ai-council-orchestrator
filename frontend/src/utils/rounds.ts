import type { CouncilSession, RoundStatus } from "../types";

export type Stage = {
  key: string;
  label: string;
  /** round_name values in agent_responses that belong to this stage */
  roundName?: string;
  /** current_round value(s) that mean this stage is active */
  currentRounds: string[];
};

export const STAGES: Stage[] = [
  { key: "initial_assessment", label: "Initial Assessment", roundName: "initial_assessment", currentRounds: ["initial_assessment"] },
  { key: "cross_review", label: "Cross Review", roundName: "cross_review", currentRounds: ["cross_review"] },
  { key: "consensus", label: "Consensus", currentRounds: ["consensus_build"] },
  { key: "consensus_approval", label: "Approval", roundName: "consensus_approval", currentRounds: ["consensus_approval"] },
  { key: "prompt_engineering", label: "Prompt Engineering", currentRounds: ["prompt_engineering"] },
  { key: "prompt_review", label: "Prompt Review", roundName: "prompt_review", currentRounds: ["prompt_review"] },
  { key: "implementation", label: "Implementation", currentRounds: ["implementation"] },
  { key: "code_review", label: "Code Review", roundName: "code_review", currentRounds: ["code_review"] },
];

function hasRound(session: CouncilSession, roundName?: string): boolean {
  if (!roundName) return false;
  return session.agent_responses.some((r) => r.round_name === roundName);
}

function stageCompleted(session: CouncilSession, stage: Stage): boolean {
  switch (stage.key) {
    case "consensus":
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
    default:
      return hasRound(session, stage.roundName);
  }
}

/**
 * Derive a status for each stage. `activeRound` (from a live WS round_started
 * event) takes precedence so the user sees exactly which round is running.
 */
export function deriveRoundStatuses(
  session: CouncilSession,
  activeRound?: string | null,
): Record<string, RoundStatus> {
  const out: Record<string, RoundStatus> = {};
  for (const stage of STAGES) {
    const completed = stageCompleted(session, stage);
    const isActive =
      (!!activeRound && stage.currentRounds.includes(activeRound)) ||
      (!activeRound && stage.currentRounds.includes(session.current_round) && !completed);
    if (isActive) out[stage.key] = "running";
    else if (completed) out[stage.key] = "completed";
    else out[stage.key] = "pending";
  }
  // Surface a blocked approval as an error so it stands out.
  if (session.consensus?.approval_status === "revisions_requested") {
    out["consensus_approval"] = "error";
  }
  return out;
}

const STATUS_LABELS: Record<string, string> = {
  created: "Erstellt",
  normalized: "Aufgabe normalisiert",
  round_1_done: "Runde 1 abgeschlossen",
  round_2_done: "Runde 2 abgeschlossen",
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
  switch (session.status) {
    case "created":
      return "Klicke „Council starten“, um die Aufgabe zu normalisieren und Runde 1 auszuführen.";
    case "normalized":
    case "round_1_done":
    case "round_2_done":
      return "Führe die nächste Runde aus, um die Bewertung fortzusetzen.";
    case "consensus_draft":
      return "Lass den Konsens von den Agenten freigeben oder gib ihn manuell frei.";
    case "consensus_blocked":
      return "Der Konsens wurde nicht freigegeben — überarbeiten oder manuell freigeben.";
    case "consensus_approved":
      return "Erzeuge jetzt den finalen Coding-Prompt.";
    case "prompt_draft":
      return "Lass den finalen Prompt von den Agenten prüfen.";
    case "prompt_revisions":
      return "Der Prompt benötigt Änderungen — neu erzeugen oder manuell freigeben.";
    case "prompt_ready":
      return "Der Prompt ist freigegeben und kann an Compose2 übergeben werden.";
    case "ready_for_implementation":
      return "Trage das Umsetzungsergebnis ein, sobald Compose2 fertig ist.";
    case "implemented":
      return "Starte das Code-Review der Umsetzung.";
    case "needs_revision":
      return "Erzeuge einen Verbesserungs-Prompt für die offenen Punkte.";
    case "completed":
      return "Session abgeschlossen. Du kannst sie als Markdown exportieren.";
    default:
      return "Nächsten Schritt ausführen.";
  }
}

export const ACTIVE_STATUSES = [
  "created",
  "normalized",
  "round_1_done",
  "round_2_done",
  "consensus_draft",
  "consensus_blocked",
  "consensus_approved",
  "prompt_draft",
  "prompt_revisions",
  "prompt_ready",
  "ready_for_implementation",
  "implemented",
  "needs_revision",
];

export function isActiveSession(status: string): boolean {
  return status !== "completed";
}
