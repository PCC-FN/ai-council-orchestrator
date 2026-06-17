import { existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { maskSecrets } from "../secret-mask.js";
import type {
  AgentAvailability,
  AgentEvent,
  AgentSession,
  CodingAgentAdapter,
  CodingTask,
  EventEmitter,
} from "./types.js";

interface SessionState {
  task: CodingTask;
  emit: EventEmitter;
  process: ChildProcessWithoutNullStreams | null;
  cancelled: boolean;
  conversationLog: string[];
  pendingQuestion: string | null;
  questionResolver?: (answer: string) => void;
}

function resolveAgentExecutable(configured?: string): string | null {
  const candidates = [
    configured,
    process.env.CURSOR_CLI_EXECUTABLE,
    process.env.AGENT_EXECUTABLE,
    path.join(os.homedir(), ".local", "bin", "agent"),
    path.join(process.env.LOCALAPPDATA || "", "cursor-agent", "agent.cmd"),
    path.join(process.env.LOCALAPPDATA || "", "cursor-agent", "cursor-agent.cmd"),
    "agent",
    "cursor-agent",
  ].filter(Boolean) as string[];

  for (const c of candidates) {
    if (c.includes(path.sep) || c.includes("/")) {
      if (existsSync(c)) return c;
    } else {
      return c;
    }
  }
  return null;
}

export class CursorAdapter implements CodingAgentAdapter {
  private sessions = new Map<string, SessionState>();

  constructor(
    private cliPath: string,
    private onEmit: EventEmitter,
    private apiKey?: string,
  ) {}

  async checkAvailability(): Promise<AgentAvailability> {
    const exe = resolveAgentExecutable(this.cliPath);
    if (!exe && !this.apiKey) {
      return {
        available: false,
        adapterType: "cursor",
        message:
          "Cursor CLI nicht gefunden. Installieren: irm 'https://cursor.com/install?win32=true' | iex — oder CURSOR_CLI_EXECUTABLE setzen.",
      };
    }
    if (!process.env.CURSOR_API_KEY && !this.apiKey) {
      return {
        available: false,
        adapterType: "cursor",
        message: "CURSOR_API_KEY fehlt für Headless-Modus.",
      };
    }
    return {
      available: true,
      adapterType: "cursor",
      message: exe ? `Cursor CLI: ${exe}` : "Cursor SDK (API-Key)",
    };
  }

  async startTask(task: CodingTask): Promise<AgentSession> {
    const avail = await this.checkAvailability();
    if (!avail.available) throw new Error(avail.message);

    const emit: EventEmitter = (event) =>
      this.onEmit({ ...event, jobId: task.jobId, sessionId: task.sessionId });

    this.sessions.set(task.sessionId, {
      task,
      emit,
      process: null,
      cancelled: false,
      conversationLog: [],
      pendingQuestion: null,
    });

    void this.runAgent(task.sessionId, task.prompt, true);
    return { sessionId: task.sessionId, jobId: task.jobId };
  }

  async sendMessage(sessionId: string, message: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (!session) return;

    if (session.pendingQuestion && session.questionResolver) {
      session.emit({
        type: "agent.output",
        payload: { message: `Antwort an Cursor: ${message}` },
        jobId: session.task.jobId,
        sessionId,
      });
      session.pendingQuestion = null;
      const resolver = session.questionResolver;
      session.questionResolver = undefined;
      resolver(message);
      return;
    }

    session.conversationLog.push(`User: ${message}`);
    const followUp = [
      "Folgeanweisung des Benutzers (kontext aus vorheriger Session):",
      ...session.conversationLog.slice(-6),
      `Neue Anweisung: ${message}`,
    ].join("\n");
    await this.runAgent(sessionId, followUp, false);
  }

  async *streamEvents(_sessionId: string): AsyncIterable<AgentEvent> {
    yield { type: "agent.started", payload: {} };
  }

  async cancelTask(sessionId: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (!session) return;
    session.cancelled = true;
    session.process?.kill("SIGTERM");
  }

  async resumeTask(sessionId: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (session) session.cancelled = false;
  }

  private async runAgent(sessionId: string, prompt: string, isInitial: boolean): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (!session || session.cancelled) return;

    const { task, emit } = session;
    const exe = resolveAgentExecutable(this.cliPath);
    if (!exe) {
      emit({
        type: "job.failed",
        payload: { error: "Cursor CLI nicht gefunden" },
        jobId: task.jobId,
        sessionId,
      });
      return;
    }

    emit({ type: "agent.started", payload: {}, jobId: task.jobId, sessionId });
    if (isInitial) {
      emit({
        type: "agent.output",
        payload: {
          message: `Cursor gestartet in ${task.projectName}`,
          progress_percent: 15,
          current_step: "Cursor arbeitet…",
        },
        jobId: task.jobId,
        sessionId,
      });
    }

    const args = [
      "-p",
      "--force",
      "--output-format",
      "stream-json",
      "--stream-partial-output",
      prompt,
    ];

    const env = { ...process.env };
    if (this.apiKey) env.CURSOR_API_KEY = this.apiKey;

    const child = spawn(exe, args, {
      cwd: task.projectPath,
      env,
      shell: process.platform === "win32" && exe.endsWith(".cmd"),
      windowsHide: true,
    });
    session.process = child;

    emit({
      type: "command.started",
      payload: { command: `${path.basename(exe)} -p …` },
      jobId: task.jobId,
      sessionId,
    });

    let buffer = "";
    let assistantText = "";
    const changedFiles = new Set<string>();

    const handleLine = (line: string) => {
      if (!line.trim()) return;
      try {
        const evt = JSON.parse(line) as Record<string, unknown>;
        const type = String(evt.type || "");

        if (type === "assistant") {
          const msg = evt.message as { content?: Array<{ type: string; text?: string }> } | undefined;
          const text = msg?.content?.find((c) => c.type === "text")?.text || "";
          if (text) {
            assistantText += text;
            emit({
              type: "command.output",
              payload: { output: maskSecrets(text) },
              jobId: task.jobId,
              sessionId,
            });
          }
        } else if (type === "tool_call") {
          const subtype = String(evt.subtype || "");
          const tc = evt.tool_call as Record<string, Record<string, { args?: { path?: string } }>> | undefined;
          const writePath = tc?.writeToolCall?.args?.path;
          if (subtype === "started" && writePath) {
            changedFiles.add(writePath);
            emit({
              type: "file.changed",
              payload: { path: writePath },
              jobId: task.jobId,
              sessionId,
            });
          }
        } else if (type === "result") {
          const duration = evt.duration_ms;
          emit({
            type: "command.completed",
            payload: { exit_code: 0, duration_ms: duration },
            jobId: task.jobId,
            sessionId,
          });
        }
      } catch {
        emit({
          type: "command.output",
          payload: { output: maskSecrets(line) },
          jobId: task.jobId,
          sessionId,
        });
      }
    };

    child.stdout.on("data", (chunk) => {
      buffer += chunk.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) handleLine(line);
    });

    child.stderr.on("data", (chunk) => {
      emit({
        type: "command.output",
        payload: { output: maskSecrets(chunk.toString()) },
        jobId: task.jobId,
        sessionId,
      });
    });

    const exitCode = await new Promise<number>((resolve) => {
      child.on("close", (code) => resolve(code ?? 1));
      child.on("error", () => resolve(1));
    });

    if (buffer.trim()) handleLine(buffer);

    if (session.cancelled) return;

    const trimmed = assistantText.trim();
    session.conversationLog.push(`Cursor: ${trimmed.slice(0, 500)}`);

    const questionMatch = trimmed.match(/([^\n?]+\?)\s*$/);
    if (questionMatch && isInitial) {
      const question = questionMatch[1].trim();
      session.pendingQuestion = question;
      emit({
        type: "agent.question",
        payload: { message: question },
        jobId: task.jobId,
        sessionId,
      });
      const answer = await new Promise<string>((resolve) => {
        session.questionResolver = resolve;
      });
      if (session.cancelled) return;
      session.conversationLog.push(`User: ${answer}`);
      await this.runAgent(sessionId, `Antwort auf Rückfrage „${question}": ${answer}`, false);
      return;
    }

    if (trimmed) {
      emit({
        type: "agent.message",
        payload: {
          sender_type: "cursor",
          sender_name: "Cursor",
          message: trimmed.slice(0, 4000),
        },
        jobId: task.jobId,
        sessionId,
      });
    }

    if (exitCode !== 0) {
      emit({
        type: "job.failed",
        payload: { error: `Cursor beendet mit Exit-Code ${exitCode}` },
        jobId: task.jobId,
        sessionId,
      });
      this.sessions.delete(sessionId);
      return;
    }

    const { captureGitResults } = await import("../git.js");
    const gitResult = await captureGitResults(task.projectPath);
    for (const f of gitResult.changedFiles) changedFiles.add(f);

    if (gitResult.diff) {
      emit({
        type: "git.diff.updated",
        payload: {
          files: gitResult.changedFiles.map((p) => ({
            path: p,
            change_type: "modified",
            diff: "",
          })),
          diff: gitResult.diff,
        },
        jobId: task.jobId,
        sessionId,
      });
    }

    emit({
      type: "job.completed",
      payload: {
        summary: trimmed.slice(0, 500) || "Cursor-Aufgabe abgeschlossen",
        changed_files: [...changedFiles],
        build_status: "nicht geprüft",
        lint_status: "nicht geprüft",
        tests: { passed: 0, failed: 0, skipped: 0 },
        progress_percent: 100,
      },
      jobId: task.jobId,
      sessionId,
    });
    this.sessions.delete(sessionId);
  }
}
