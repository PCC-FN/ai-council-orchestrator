import { Card, CardHeader, CardBody } from "../ui/Card";
import { Markdown } from "../common/Markdown";
import { ApprovalBadge } from "../common/StatusBadge";
import type { Consensus } from "../../types";

function Section({ title, content }: { title: string; content: string }) {
  if (!content?.trim()) return null;
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {title}
      </h4>
      <Markdown content={content} />
    </div>
  );
}

export function ConsensusPanel({ consensus }: { consensus: Consensus }) {
  return (
    <Card>
      <CardHeader
        title="Konsens"
        subtitle="Konsolidiertes Ergebnis aller Agenten"
        actions={<ApprovalBadge status={consensus.approval_status} />}
      />
      <CardBody className="space-y-4">
        <Section title="Kurzfazit" content={consensus.summary} />
        <Section title="Empfohlene Lösung" content={consensus.agreed_solution} />
        <Section title="Abgelehnte Alternativen" content={consensus.rejected_alternatives} />
        <Section title="Risiken" content={consensus.risks} />
        <Section title="Umsetzungsschritte" content={consensus.implementation_plan} />
        <Section title="Testplan" content={consensus.test_plan} />
        <Section title="Offene Fragen" content={consensus.open_questions} />
      </CardBody>
    </Card>
  );
}
