export type CommandRisk = "safe" | "confirmation" | "forbidden";

const FORBIDDEN = [
  /format\s+[a-z]:/i,
  /rm\s+-rf\s+\//i,
  /del\s+\/s/i,
  /remove-item\s+-recurse/i,
  /invoke-webrequest/i,
  /curl\s+.*\|\s*(bash|sh|powershell)/i,
];

const CONFIRMATION = [
  /\bgit\s+push\b/i,
  /\bgit\s+merge\b/i,
  /\bgit\s+reset\s+--hard\b/i,
  /\bgit\s+clean\s+-fd/i,
  /\bdrop\s+table\b/i,
  /\bmigrate.*--force/i,
  /\bdocker\s+compose\s+down\b/i,
  /\bnpm\s+install\s+-g\b/i,
  /\bpip\s+install\s+--user\b/i,
  /\brm\s+-rf\b/i,
  /\bdel\s+\/f/i,
];

const SAFE = [
  /\bgit\s+status\b/i,
  /\bgit\s+diff\b/i,
  /\bgit\s+log\b/i,
  /\bnpm\s+test\b/i,
  /\bnpm\s+run\s+(test|lint|build)\b/i,
  /\bpytest\b/i,
  /\btsc\b/i,
  /\beslint\b/i,
];

export function classifyCommand(command: string): CommandRisk {
  const cmd = command.trim();
  for (const p of FORBIDDEN) {
    if (p.test(cmd)) return "forbidden";
  }
  for (const p of CONFIRMATION) {
    if (p.test(cmd)) return "confirmation";
  }
  for (const p of SAFE) {
    if (p.test(cmd)) return "safe";
  }
  return "confirmation";
}

export function assertCommandAllowed(command: string, allowDangerous = false): void {
  const risk = classifyCommand(command);
  if (risk === "forbidden") {
    throw new Error(`Verbotener Befehl: ${command}`);
  }
  if (risk === "confirmation" && !allowDangerous) {
    throw new Error(`Befehl erfordert Freigabe: ${command}`);
  }
}
