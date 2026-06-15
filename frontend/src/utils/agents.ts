export type AgentMeta = {
  key: string;
  label: string;
  role: string;
  initials: string;
  accent: string; // tailwind classes for the avatar
};

const AGENTS: Record<string, AgentMeta> = {
  chatgpt_architect: {
    key: "chatgpt_architect",
    label: "ChatGPT Architect",
    role: "Architektur & Produktlogik",
    initials: "GA",
    accent: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300",
  },
  claude_reviewer: {
    key: "claude_reviewer",
    label: "Claude Reviewer",
    role: "Code-Qualität & Risiken",
    initials: "CR",
    accent: "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300",
  },
  compose2_implementation: {
    key: "compose2_implementation",
    label: "Compose2 Implementation",
    role: "Umsetzbarkeit & Implementierung",
    initials: "C2",
    accent: "bg-sky-100 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300",
  },
  prompt_optimizer: {
    key: "prompt_optimizer",
    label: "Prompt Optimizer",
    role: "Finaler Prompt",
    initials: "PO",
    accent: "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-500/20 dark:text-fuchsia-300",
  },
  orchestrator: {
    key: "orchestrator",
    label: "Orchestrator",
    role: "Moderation & Konsens",
    initials: "OR",
    accent: "bg-brand-100 text-brand-700 dark:bg-brand-500/20 dark:text-brand-300",
  },
};

export function agentMeta(name: string): AgentMeta {
  return (
    AGENTS[name] ?? {
      key: name,
      label: name,
      role: "Agent",
      initials: name.slice(0, 2).toUpperCase(),
      accent: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200",
    }
  );
}

export const ALL_AGENTS = Object.values(AGENTS);
