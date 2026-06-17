import { maskSecrets } from "../secret-mask.js";
import type {
  AgentAvailability,
  AgentEvent,
  AgentSession,
  CodingAgentAdapter,
  CodingTask,
  EventEmitter,
} from "./types.js";

export class MockCodingAdapter implements CodingAgentAdapter {
  private sessions = new Map<
    string,
    {
      task: CodingTask;
      emit: EventEmitter;
      cancelled: boolean;
      paused: boolean;
      waitingForAnswer: boolean;
      answerResolver?: (value: string) => void;
    }
  >();

  constructor(private onEmit: EventEmitter) {}

  async checkAvailability(): Promise<AgentAvailability> {
    return {
      available: true,
      adapterType: "mock",
      message: "Mock-Adapter bereit (Simulation ohne Cursor)",
    };
  }

  async startTask(task: CodingTask): Promise<AgentSession> {
    const emit: EventEmitter = (event) =>
      this.onEmit({ ...event, jobId: task.jobId, sessionId: task.sessionId });

    this.sessions.set(task.sessionId, {
      task,
      emit,
      cancelled: false,
      paused: false,
      waitingForAnswer: false,
    });

    void this.runSimulation(task.sessionId);
    return { sessionId: task.sessionId, jobId: task.jobId };
  }

  async sendMessage(sessionId: string, message: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (!session) return;
    if (session.waitingForAnswer && session.answerResolver) {
      session.waitingForAnswer = false;
      session.emit({
        type: "agent.output",
        payload: { message: maskSecrets(`Antwort erhalten: ${message}`) },
        jobId: session.task.jobId,
        sessionId,
      });
      session.answerResolver(message);
      session.answerResolver = undefined;
    } else {
      session.emit({
        type: "agent.message",
        payload: {
          sender_type: "cursor",
          sender_name: "Cursor (Mock)",
          message: `Folgeanweisung verarbeitet: ${message}`,
        },
        jobId: session.task.jobId,
        sessionId,
      });
    }
  }

  async *streamEvents(_sessionId: string): AsyncIterable<AgentEvent> {
    /* Events are pushed via onEmit callback during simulation */
    yield { type: "agent.started", payload: {} };
  }

  async cancelTask(sessionId: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (session) session.cancelled = true;
  }

  async resumeTask(sessionId: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (session) session.paused = false;
  }

  private async runSimulation(sessionId: string): Promise<void> {
    const session = this.sessions.get(sessionId);
    if (!session) return;
    const { task, emit } = session;
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
    const step = async (pct: number, msg: string) => {
      emit({
        type: "agent.output",
        payload: { message: msg, progress_percent: pct, current_step: msg },
        jobId: task.jobId,
        sessionId,
      });
      await sleep(400);
    };

    emit({ type: "agent.started", payload: {}, jobId: task.jobId, sessionId });
    await step(5, `Cursor (Mock) gestartet im Projekt „${task.projectName}"`);
    await step(10, `Branch vorbereitet: ${task.branchName}`);
    emit({
      type: "command.started",
      payload: { command: "git status" },
      jobId: task.jobId,
      sessionId,
    });
    emit({
      type: "command.output",
      payload: { output: "On branch main\nnothing to commit, working tree clean" },
      jobId: task.jobId,
      sessionId,
    });
    emit({
      type: "command.completed",
      payload: { exit_code: 0 },
      jobId: task.jobId,
      sessionId,
    });

    await step(25, "Analysiere Aufgabe…");
    emit({
      type: "agent.message",
      payload: {
        sender_type: "cursor",
        sender_name: "Cursor (Mock)",
        message: "Ich beginne mit der Umsetzung der Anforderungen.",
      },
      jobId: task.jobId,
      sessionId,
    });

    await step(40, "Erstelle Dateien…");
    const files = [
      {
        path: "src/features/example.ts",
        diff: "@@ -0,0 +1,5 @@\n+export function example() {\n+  return 'implemented';\n+}\n",
        content: "export function example() {\n  return 'implemented';\n}\n",
      },
      {
        path: "tests/example.test.ts",
        diff: "@@ -0,0 +1,6 @@\n+import { example } from '../src/features/example';\n+\n+test('example', () => {\n+  expect(example()).toBe('implemented');\n+});\n",
        content: "",
      },
    ];
    for (const f of files) {
      if (session.cancelled) return;
      emit({
        type: "file.created",
        payload: { path: f.path, diff: f.diff, content: f.content },
        jobId: task.jobId,
        sessionId,
      });
      await sleep(300);
    }

    emit({
      type: "git.diff.updated",
      payload: {
        files: files.map((f) => ({ path: f.path, change_type: "created", diff: f.diff })),
      },
      jobId: task.jobId,
      sessionId,
    });

    await step(55, "Rückfrage an Benutzer…");
    emit({
      type: "agent.question",
      payload: {
        message: "Soll die neue Funktion auch für Administratoren gelten?",
      },
      jobId: task.jobId,
      sessionId,
    });
    session.waitingForAnswer = true;
    const answer = await new Promise<string>((resolve) => {
      session.answerResolver = resolve;
    });
    if (session.cancelled) return;

    emit({
      type: "agent.message",
      payload: {
        sender_type: "cursor",
        sender_name: "Cursor (Mock)",
        message: `Verstanden (${answer}). Setze Umsetzung fort.`,
      },
      jobId: task.jobId,
      sessionId,
    });

    await step(70, "Führe Tests aus…");
    emit({ type: "test.started", payload: {}, jobId: task.jobId, sessionId });
    emit({
      type: "command.output",
      payload: { output: "PASS tests/example.test.ts\nTests: 4 passed, 4 total" },
      jobId: task.jobId,
      sessionId,
    });
    emit({
      type: "test.completed",
      payload: { passed: 4, failed: 0, skipped: 0 },
      jobId: task.jobId,
      sessionId,
    });

    await step(90, "Abschlussprüfung…");
    emit({
      type: "job.completed",
      payload: {
        summary: "Mock-Implementierung erfolgreich abgeschlossen",
        changed_files: files.map((f) => f.path),
        build_status: "erfolgreich",
        lint_status: "erfolgreich",
        tests: { passed: 4, failed: 0, skipped: 0 },
        progress_percent: 100,
      },
      jobId: task.jobId,
      sessionId,
    });
    this.sessions.delete(sessionId);
  }
}
