import { Badge } from "../ui/Badge";
import { statusLabel } from "../../utils/rounds";
import type { RoundStatus } from "../../types";

const STATUS_TONES: Record<string, "neutral" | "info" | "success" | "warning" | "danger"> = {
  created: "neutral",
  normalized: "info",
  round_1_done: "info",
  round_2_done: "info",
  consensus_draft: "info",
  consensus_blocked: "danger",
  consensus_approved: "success",
  prompt_draft: "info",
  prompt_revisions: "warning",
  prompt_ready: "success",
  ready_for_implementation: "info",
  implemented: "info",
  needs_revision: "warning",
  completed: "success",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONES[status] ?? "neutral"}>{statusLabel(status)}</Badge>;
}

const ROUND_TONES: Record<RoundStatus, "neutral" | "info" | "success" | "danger"> = {
  pending: "neutral",
  running: "info",
  completed: "success",
  error: "danger",
};

const ROUND_LABELS: Record<RoundStatus, string> = {
  pending: "wartet",
  running: "läuft",
  completed: "abgeschlossen",
  error: "Fehler",
};

export function RoundStatusBadge({ status }: { status: RoundStatus }) {
  return (
    <Badge tone={ROUND_TONES[status]}>
      {status === "running" && (
        <span className="h-1.5 w-1.5 animate-pulse-fast rounded-full bg-current" />
      )}
      {ROUND_LABELS[status]}
    </Badge>
  );
}

const APPROVAL_TONES: Record<string, "neutral" | "success" | "danger" | "warning"> = {
  pending: "neutral",
  approved: "success",
  rejected: "danger",
  revisions_requested: "warning",
};

const APPROVAL_LABELS: Record<string, string> = {
  pending: "ausstehend",
  approved: "Zustimmung",
  rejected: "Ablehnung",
  revisions_requested: "Änderungen nötig",
};

export function ApprovalBadge({ status }: { status: string }) {
  return (
    <Badge tone={APPROVAL_TONES[status] ?? "neutral"}>
      {APPROVAL_LABELS[status] ?? status}
    </Badge>
  );
}
