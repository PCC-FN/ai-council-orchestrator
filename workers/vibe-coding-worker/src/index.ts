#!/usr/bin/env node
import os from "node:os";
import WebSocket from "ws";
import { CursorAdapter } from "./adapters/cursor-adapter.js";
import { MockCodingAdapter } from "./adapters/mock-adapter.js";
import type { AgentEvent, CodingAgentAdapter, CodingTask, EventEmitter } from "./adapters/types.js";
import { loadConfig } from "./config.js";
import {
  captureGitResults,
  commitAll,
  prepareGitWorkspace,
  pushBranch,
  restoreStash,
} from "./git.js";
import { assertCommandAllowed } from "./command-security.js";
import { discoverProjects, isPathWithinRoot } from "./path-security.js";
import { maskSecrets } from "./secret-mask.js";

const config = loadConfig();
const activeJobs = new Map<string, CodingAgentAdapter>();

function log(level: string, msg: string): void {
  if (config.logLevel === "debug" || level !== "debug") {
    console.log(`[worker] ${maskSecrets(msg)}`);
  }
}

function createAdapter(onEmit: EventEmitter): CodingAgentAdapter {
  if (config.adapterType === "cursor") {
    return new CursorAdapter(config.cursorCli, onEmit, config.cursorApiKey);
  }
  return new MockCodingAdapter(onEmit);
}

function capabilities() {
  return {
    cursor: config.adapterType === "cursor",
    git: true,
    node: true,
    python: true,
    powershell: os.platform() === "win32",
    mock: config.adapterType === "mock",
    adapter_type: config.adapterType,
  };
}

function connect(): WebSocket {
  if (!config.token) {
    console.error("[worker] ORCHESTRA_WORKER_TOKEN fehlt");
    process.exit(1);
  }

  const ws = new WebSocket(config.serverUrl);
  const projects = discoverProjects(config.projectRoots);

  ws.on("open", () => {
    log("info", `Verbunden mit ${config.serverUrl}`);
    ws.send(
      JSON.stringify({
        type: "auth",
        token: config.token,
        payload: {
          name: config.name,
          hostname: os.hostname(),
          operating_system: `${os.type()} ${os.release()}`,
          version: "1.0.0",
          capabilities: capabilities(),
          projects,
        },
      }),
    );
  });

  ws.on("message", async (raw) => {
    let msg: { type: string; payload?: Record<string, unknown> };
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      return;
    }

    if (msg.type === "job.execute" && msg.payload) {
      if (activeJobs.size >= config.maxParallelJobs) {
        log("warn", "Max parallel jobs reached — job wird ignoriert");
        return;
      }
      await executeJob(ws, msg.payload as Record<string, string>);
    } else if (msg.type === "job.message" && msg.payload) {
      const jobId = String(msg.payload.job_id || "");
      const message = String(msg.payload.message || "");
      const sessionId = String(msg.payload.session_id || sessionMap.get(jobId) || jobId);
      const adapter = activeJobs.get(jobId);
      if (adapter) {
        await adapter.sendMessage(sessionId, message);
      }
    } else if (msg.type === "job.cancel" && msg.payload) {
      const jobId = String(msg.payload.job_id || "");
      activeJobs.delete(jobId);
    } else if (msg.type === "git.commit" && msg.payload) {
      await handleGitCommit(ws, msg.payload as Record<string, string>);
    } else if (msg.type === "git.push" && msg.payload) {
      await handleGitPush(ws, msg.payload as Record<string, string>);
    } else if (msg.type === "git.rollback" && msg.payload) {
      await handleGitRollback(ws, msg.payload as Record<string, string>);
    } else if (msg.type === "job.pause") {
      log("info", "Job pausiert");
    } else if (msg.type === "job.resume") {
      log("info", "Job fortgesetzt");
    }
  });

  ws.on("close", () => {
    log("warn", "Verbindung getrennt — Reconnect in 5s");
    setTimeout(() => connect(), 5000);
  });

  ws.on("error", (err) => log("error", `WebSocket-Fehler: ${err.message}`));

  const heartbeat = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          type: "worker.heartbeat",
          payload: { status: activeJobs.size > 0 ? "busy" : "idle" },
        }),
      );
      ws.send(
        JSON.stringify({
          type: "worker.projects",
          payload: { projects: discoverProjects(config.projectRoots) },
        }),
      );
    } else {
      clearInterval(heartbeat);
    }
  }, 30000);

  return ws;
}

const sessionMap = new Map<string, string>();
const jobContext = new Map<
  string,
  { projectPath: string; branchName: string; stashMessage?: string; sessionId: string }
>();

async function executeJob(ws: WebSocket, payload: Record<string, string>): Promise<void> {
  const jobId = payload.job_id;
  const sessionId = payload.session_id;
  const projectPath = payload.project_path;

  const allowed = config.projectRoots.some((root) => isPathWithinRoot(projectPath, root));
  if (!allowed) {
    sendEvent(ws, jobId, sessionId, "job.failed", {
      error: "Projektpfad liegt außerhalb der freigegebenen PROJECT_ROOTS",
    });
    return;
  }

  const onEmit: EventEmitter = (event: AgentEvent & { jobId: string; sessionId: string }) => {
    sendEvent(ws, event.jobId, event.sessionId, event.type, event.payload);
    if (event.type === "job.completed" || event.type === "job.failed") {
      cleanupJob(event.jobId);
    }
  };

  sessionMap.set(jobId, sessionId);

  const branchName = payload.branch_name || `orchestra/job-${jobId.slice(0, 8)}`;
  sendEvent(ws, jobId, sessionId, "command.started", { command: "git prepare" });
  const gitPrep = await prepareGitWorkspace(projectPath, branchName, jobId);
  if (!gitPrep.ok) {
    sendEvent(ws, jobId, sessionId, "job.failed", { error: gitPrep.error || "Git-Vorbereitung fehlgeschlagen" });
    return;
  }
  if (gitPrep.status && !gitPrep.status.clean) {
    sendEvent(ws, jobId, sessionId, "agent.output", {
      message: `Vorhandene Änderungen gesichert (Stash: ${gitPrep.stashMessage})`,
    });
  }
  sendEvent(ws, jobId, sessionId, "command.output", {
    output: `Branch: ${branchName}${gitPrep.previousBranch ? ` (vorher: ${gitPrep.previousBranch})` : ""}`,
  });

  jobContext.set(jobId, {
    projectPath,
    branchName,
    stashMessage: gitPrep.stashMessage,
    sessionId,
  });

  const adapter = createAdapter(onEmit);
  activeJobs.set(jobId, adapter);

  const task: CodingTask = {
    jobId,
    sessionId,
    projectPath,
    projectName: payload.project_name || "project",
    branchName,
    prompt: payload.prompt || "",
  };

  log("info", `Starte Job ${jobId} (${config.adapterType})`);
  try {
    await adapter.startTask(task);
  } catch (err) {
    sendEvent(ws, jobId, sessionId, "job.failed", {
      error: err instanceof Error ? err.message : String(err),
    });
    activeJobs.delete(jobId);
    sessionMap.delete(jobId);
  }
}

function cleanupJob(jobId: string): void {
  activeJobs.delete(jobId);
  sessionMap.delete(jobId);
}

async function handleGitCommit(ws: WebSocket, payload: Record<string, string>): Promise<void> {
  const jobId = payload.job_id;
  const ctx = jobContext.get(jobId);
  if (!ctx) return;
  try {
    assertCommandAllowed("git commit", Boolean(payload.allow_dangerous));
    const hash = await commitAll(ctx.projectPath, payload.message || "orchestra: changes");
    sendEvent(ws, jobId, ctx.sessionId, "agent.output", {
      message: `Commit erstellt: ${hash.slice(0, 8)}`,
    });
  } catch (err) {
    sendEvent(ws, jobId, ctx.sessionId, "agent.error", {
      error: err instanceof Error ? err.message : String(err),
    });
  }
}

async function handleGitPush(ws: WebSocket, payload: Record<string, string>): Promise<void> {
  const jobId = payload.job_id;
  const ctx = jobContext.get(jobId);
  if (!ctx) return;
  try {
    assertCommandAllowed("git push", Boolean(payload.allow_dangerous));
    await pushBranch(ctx.projectPath, ctx.branchName);
    sendEvent(ws, jobId, ctx.sessionId, "agent.output", { message: `Push auf ${ctx.branchName} erfolgreich` });
  } catch (err) {
    sendEvent(ws, jobId, ctx.sessionId, "agent.error", {
      error: err instanceof Error ? err.message : String(err),
    });
  }
}

async function handleGitRollback(ws: WebSocket, payload: Record<string, string>): Promise<void> {
  const jobId = payload.job_id;
  const ctx = jobContext.get(jobId);
  if (!ctx) return;
  try {
    if (ctx.stashMessage) await restoreStash(ctx.projectPath);
    const gitResult = await captureGitResults(ctx.projectPath);
    sendEvent(ws, jobId, ctx.sessionId, "agent.output", {
      message: "Rollback: Stash wiederhergestellt (falls vorhanden)",
    });
    sendEvent(ws, jobId, ctx.sessionId, "git.diff.updated", {
      files: gitResult.changedFiles.map((p) => ({ path: p, change_type: "modified" })),
    });
  } catch (err) {
    sendEvent(ws, jobId, ctx.sessionId, "agent.error", {
      error: err instanceof Error ? err.message : String(err),
    });
  }
}

function sendEvent(
  ws: WebSocket,
  jobId: string,
  sessionId: string,
  type: string,
  payload: Record<string, unknown>,
): void {
  if (ws.readyState !== WebSocket.OPEN) return;
  ws.send(
    JSON.stringify({
      version: 1,
      type: "worker.event",
      jobId,
      sessionId,
      payload: { type, payload },
    }),
  );
}

log("info", `AI Orchestra Vibe Worker (${config.adapterType}) → ${config.serverUrl}`);
connect();
