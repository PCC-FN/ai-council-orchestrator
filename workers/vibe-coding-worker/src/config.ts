import os from "node:os";

export interface WorkerConfig {
  serverUrl: string;
  token: string;
  name: string;
  adapterType: string;
  projectRoots: string[];
  maxParallelJobs: number;
  logLevel: string;
  cursorCli: string;
  cursorApiKey: string;
}

export function loadConfig(): WorkerConfig {
  const projectRoots = (process.env.PROJECT_ROOTS || process.cwd())
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean);

  return {
    serverUrl: process.env.ORCHESTRA_SERVER_URL || "ws://127.0.0.1:8000/ws/worker",
    token: process.env.ORCHESTRA_WORKER_TOKEN || "",
    name: process.env.WORKER_NAME || os.hostname(),
    adapterType: process.env.ADAPTER_TYPE || "mock",
    projectRoots,
    maxParallelJobs: parseInt(process.env.MAX_PARALLEL_JOBS || "1", 10),
    logLevel: process.env.LOG_LEVEL || "info",
    cursorCli: process.env.CURSOR_CLI_EXECUTABLE || "",
    cursorApiKey: process.env.CURSOR_API_KEY || "",
  };
}
