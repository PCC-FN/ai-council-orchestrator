import { Link, Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type Project,
  type Session,
} from "./api";

function Dashboard() {
  const nav = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("Mein Projekt");
  const [repo, setRepo] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    const list = await api<Project[]>("/projects");
    setProjects(list);
  }, []);

  useEffect(() => {
    load().catch((e) => setErr(String(e)));
  }, [load]);

  const create = async () => {
    setErr(null);
    const p = await api<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({
        name,
        repository_path: repo,
        description: "",
        coding_rules: "",
        security_rules: "",
      }),
    });
    nav(`/project/${p.id}`);
  };

  return (
    <div className="layout">
      <h1>AI Council Coding Orchestrator</h1>
      <p className="badge">MVP · strukturierte Agenten-Runden · Markdown-Export</p>

      {err && <p className="err">{err}</p>}

      <div className="card">
        <h2>Neues Projekt</h2>
        <div className="grid2">
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            Repository-Pfad (absolut)
            <input
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
              placeholder="z. B. /home/me/proj"
            />
          </label>
        </div>
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <button type="button" onClick={() => create().catch((e) => setErr(String(e)))}>
            Projekt anlegen
          </button>
          <button type="button" className="secondary" onClick={() => load()}>
            Liste aktualisieren
          </button>
        </div>
      </div>

      <h2>Projekte</h2>
      <ul className="plain">
        {projects.map((p) => (
          <li key={p.id}>
            <Link to={`/project/${p.id}`}>{p.name}</Link>
            <span className="badge" style={{ marginLeft: 8 }}>
              {p.id.slice(0, 8)}…
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProjectView() {
  const { projectId } = useParams();
  const nav = useNavigate();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [title, setTitle] = useState("Session");
  const [task, setTask] = useState("Beschreibe die Coding-Aufgabe…");
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!projectId) return;
    setErr(null);
    const list = await api<Session[]>(`/projects/${projectId}/sessions`);
    setSessions(list);
  }, [projectId]);

  useEffect(() => {
    load().catch((e) => setErr(String(e)));
  }, [load]);

  const createSession = async () => {
    if (!projectId) return;
    setErr(null);
    const s = await api<Session>(`/projects/${projectId}/sessions`, {
      method: "POST",
      body: JSON.stringify({ title, original_user_task: task }),
    });
    nav(`/session/${s.id}`);
  };

  const openSessions = sessions.filter((s) =>
    ["created", "normalized", "running", "round_1_done", "round_2_done", "consensus_draft", "consensus_blocked", "consensus_approved", "prompt_draft", "prompt_revisions", "prompt_ready", "ready_for_implementation", "implemented", "needs_revision"].includes(
      s.status
    )
  );
  const done = sessions.filter((s) => s.status === "completed");

  return (
    <div className="layout">
      <p>
        <Link to="/">← Dashboard</Link>
      </p>
      <h1>Projekt-Sessions</h1>
      {err && <p className="err">{err}</p>}

      <div className="card">
        <h2>Neue Session</h2>
        <label>
          Titel
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label style={{ display: "block", marginTop: 8 }}>
          Aufgabe
          <textarea value={task} onChange={(e) => setTask(e.target.value)} />
        </label>
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <button type="button" onClick={() => createSession().catch((e) => setErr(String(e)))}>
            Session erstellen
          </button>
        </div>
      </div>

      <h2>Offen / laufend</h2>
      <ul className="plain">
        {openSessions.map((s) => (
          <li key={s.id}>
            <Link to={`/session/${s.id}`}>{s.title}</Link>{" "}
            <span className="badge">{s.status}</span>
          </li>
        ))}
      </ul>

      <h2>Abgeschlossen</h2>
      <ul className="plain">
        {done.map((s) => (
          <li key={s.id}>
            <Link to={`/session/${s.id}`}>{s.title}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SessionView() {
  const { sessionId } = useParams();
  const [sess, setSess] = useState<Session | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [files, setFiles] = useState("");
  const [summary, setSummary] = useState("");

  const pushLog = (m: string) => setLog((l) => [...l.slice(-80), m]);

  const load = useCallback(async () => {
    if (!sessionId) return;
    const s = await api<Session>(`/sessions/${sessionId}`);
    setSess(s);
  }, [sessionId]);

  useEffect(() => {
    load().catch((e) => setErr(String(e)));
  }, [load]);

  useEffect(() => {
    if (!sessionId) return;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const host = location.host;
    const ws = new WebSocket(`${proto}//${host}/ws/sessions/${sessionId}`);
    ws.onmessage = (ev) => {
      try {
        const j = JSON.parse(ev.data as string);
        pushLog(`evt: ${j.event || "?"} ${JSON.stringify(j).slice(0, 160)}`);
      } catch {
        pushLog(String(ev.data));
      }
    };
    ws.onerror = () => pushLog("ws error");
    return () => ws.close();
  }, [sessionId]);

  const act = async (path: string) => {
    if (!sessionId) return;
    setErr(null);
    await api(`/sessions/${sessionId}${path}`, { method: "POST", body: "{}" });
    await load();
  };

  const runAll = async () => {
    if (!sessionId) return;
    setErr(null);
    await act("/actions/run-all-to-prompt");
  };

  const exportMd = async () => {
    if (!sessionId) return;
    const r = await api<{ markdown: string }>(`/sessions/${sessionId}/export.md`);
    const blob = new Blob([r.markdown], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `council-${sessionId!.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const latestPrompt = useMemo(() => {
    if (!sess?.final_prompts?.length) return null;
    return [...sess.final_prompts].sort((a, b) => b.version - a.version)[0];
  }, [sess]);

  const copyPrompt = async () => {
    if (!latestPrompt) return;
    await navigator.clipboard.writeText(latestPrompt.prompt_text);
    pushLog("Prompt in Zwischenablage kopiert.");
  };

  const markImpl = async () => {
    if (!sessionId) return;
    setErr(null);
    const list = files
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    await api(`/sessions/${sessionId}/actions/mark-implemented`, {
      method: "POST",
      body: JSON.stringify({ changed_files: list, summary }),
    });
    await load();
  };

  if (!sess) {
    return (
      <div className="layout">
        <p>Lade Session…</p>
        {err && <p className="err">{err}</p>}
      </div>
    );
  }

  const canHandoff =
    latestPrompt?.approved_by_chatgpt &&
    latestPrompt?.approved_by_claude &&
    latestPrompt?.approved_by_compose2;

  return (
    <div className="layout">
      <p>
        <Link to={`/project/${sess.project_id}`}>← Projekt</Link>
      </p>
      <h1>{sess.title}</h1>
      <p>
        <span className="badge">{sess.status}</span>{" "}
        <span className="badge">Runde: {sess.current_round}</span>
      </p>
      {err && <p className="err">{err}</p>}

      <div className="card">
        <h2>Originalaufgabe</h2>
        <pre className="log" style={{ maxHeight: 120 }}>
          {sess.original_user_task}
        </pre>
        {sess.normalized_task && (
          <>
            <h2>Normalisierte Aufgabe</h2>
            <pre className="log" style={{ maxHeight: 160 }}>
              {sess.normalized_task}
            </pre>
          </>
        )}
      </div>

      <div className="card">
        <h2>Orchestrierung</h2>
        <div className="row">
          <button type="button" className="secondary" onClick={() => act("/actions/normalize").catch((e) => setErr(String(e)))}>
            1 · Normalisieren
          </button>
          <button type="button" className="secondary" onClick={() => act("/actions/run-round-1").catch((e) => setErr(String(e)))}>
            2 · Runde 1
          </button>
          <button type="button" className="secondary" onClick={() => act("/actions/run-round-2").catch((e) => setErr(String(e)))}>
            3 · Runde 2
          </button>
          <button type="button" className="secondary" onClick={() => act("/actions/build-consensus").catch((e) => setErr(String(e)))}>
            4 · Konsens
          </button>
          <button type="button" className="secondary" onClick={() => act("/actions/consensus-approval").catch((e) => setErr(String(e)))}>
            5 · Konsens-Freigabe
          </button>
        </div>
        <div className="row" style={{ marginTop: 8 }}>
          <button type="button" className="secondary" onClick={() => act("/actions/build-final-prompt").catch((e) => setErr(String(e)))}>
            6 · Finaler Prompt
          </button>
          <button type="button" className="secondary" onClick={() => act("/actions/prompt-review").catch((e) => setErr(String(e)))}>
            7 · Prompt-Review
          </button>
          <button type="button" onClick={() => runAll().catch((e) => setErr(String(e)))}>
            Alles bis Prompt-Review
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Compose2 · manuell</h2>
        <p style={{ fontSize: "0.88rem", color: "#9fb0c3" }}>
          Freigabe nötig: ChatGPT, Claude, Compose2 müssen im letzten Prompt <code>true</code> sein.
        </p>
        <div className="row">
          <button
            type="button"
            disabled={!canHandoff}
            onClick={() => act("/actions/submit-compose2").catch((e) => setErr(String(e)))}
          >
            Prompt an Compose2 übergeben
          </button>
          <button type="button" className="secondary" disabled={!latestPrompt} onClick={() => copyPrompt().catch(() => {})}>
            Prompt kopieren
          </button>
          <button type="button" className="secondary" onClick={() => exportMd().catch((e) => setErr(String(e)))}>
            Als Markdown exportieren
          </button>
        </div>
        {latestPrompt && (
          <pre className="log" style={{ marginTop: "0.75rem" }}>
            Freigaben: GPT {String(latestPrompt.approved_by_chatgpt)} · Claude{" "}
            {String(latestPrompt.approved_by_claude)} · C2 {String(latestPrompt.approved_by_compose2)}
            {"\n\n"}
            {latestPrompt.prompt_text}
          </pre>
        )}
      </div>

      {sess.consensus && (
        <div className="card">
          <h2>Konsens ({sess.consensus.approval_status})</h2>
          <pre className="log">{sess.consensus.summary}</pre>
          <pre className="log">{sess.consensus.agreed_solution}</pre>
        </div>
      )}

      <div className="card">
        <h2>Agenten-Antworten</h2>
        {sess.agent_responses.map((a) => (
          <details key={a.id} style={{ marginBottom: "0.5rem" }}>
            <summary>
              <strong>{a.agent_name}</strong> · {a.round_name}{" "}
              <span className="badge">{a.approval_status}</span>
            </summary>
            <pre className="log" style={{ maxHeight: 200 }}>
              {a.content}
            </pre>
          </details>
        ))}
      </div>

      <div className="card">
        <h2>Umsetzung (manuell)</h2>
        <label>
          Geänderte Dateien (eine Zeile pro Pfad)
          <textarea value={files} onChange={(e) => setFiles(e.target.value)} />
        </label>
        <label style={{ display: "block", marginTop: 8 }}>
          Kurz-Zusammenfassung
          <textarea value={summary} onChange={(e) => setSummary(e.target.value)} />
        </label>
        <div className="row" style={{ marginTop: 8 }}>
          <button type="button" onClick={() => markImpl().catch((e) => setErr(String(e)))}>
            Als umgesetzt markieren
          </button>
          <button type="button" className="secondary" onClick={() => act("/actions/code-review").catch((e) => setErr(String(e)))}>
            Code-Review (GPT+Claude)
          </button>
        </div>
        {sess.implementation?.review_result && (
          <>
            <h2>Review</h2>
            <pre className="log">{sess.implementation.review_result}</pre>
            <button
              type="button"
              className="secondary"
              onClick={async () => {
                const r = await api<{ markdown: string }>(`/sessions/${sessionId}/improvement-prompt`);
                await navigator.clipboard.writeText(r.markdown);
                pushLog("Verbesserungs-Prompt kopiert.");
              }}
            >
              Verbesserungs-Prompt holen & kopieren
            </button>
          </>
        )}
      </div>

      <div className="card">
        <h2>Live (WebSocket)</h2>
        <pre className="log" style={{ maxHeight: 140 }}>
          {log.join("\n")}
        </pre>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/project/:projectId" element={<ProjectView />} />
      <Route path="/session/:sessionId" element={<SessionView />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
