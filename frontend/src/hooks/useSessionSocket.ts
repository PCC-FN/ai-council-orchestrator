import { useEffect, useRef, useState } from "react";
import { sessionSocketUrl } from "../api/client";
import type { WsEvent } from "../types";

export type LiveLogEntry = {
  id: number;
  ts: string;
  event: string;
  detail: string;
};

export type SessionLive = {
  connected: boolean;
  log: LiveLogEntry[];
  /** Round currently running, derived from round_started/agent events. */
  activeRound: string | null;
  /** Agent currently running, if any. */
  activeAgent: string | null;
};

/**
 * Subscribe to a session's WebSocket. On every event we call `onEvent` (used to
 * refetch the session) and keep a small live log + derived active round/agent.
 */
export function useSessionSocket(
  sessionId: string | undefined,
  onEvent?: (evt: WsEvent) => void,
): SessionLive {
  const [connected, setConnected] = useState(false);
  const [log, setLog] = useState<LiveLogEntry[]>([]);
  const [activeRound, setActiveRound] = useState<string | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const counter = useRef(0);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!sessionId) return;
    const ws = new WebSocket(sessionSocketUrl(sessionId));

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (ev) => {
      let evt: WsEvent;
      try {
        evt = JSON.parse(ev.data as string) as WsEvent;
      } catch {
        return;
      }
      const name = evt.event ?? "event";
      if (name === "round_started" && typeof evt.round === "string") {
        setActiveRound(evt.round);
        setActiveAgent(null);
      } else if (name === "agent_started" && typeof evt.agent === "string") {
        setActiveAgent(evt.agent);
      } else if (name === "agent_finished" || name === "agent_failed") {
        setActiveAgent(null);
      } else if (
        ["implementation_reviewed", "prompt_approved", "submitted_to_compose2"].includes(name)
      ) {
        setActiveRound(null);
        setActiveAgent(null);
      }

      const detail =
        (evt.agent as string) ||
        (evt.round as string) ||
        (evt.error as string) ||
        "";
      counter.current += 1;
      setLog((l) => [
        ...l.slice(-100),
        {
          id: counter.current,
          ts: new Date().toLocaleTimeString(),
          event: name,
          detail,
        },
      ]);
      onEventRef.current?.(evt);
    };

    return () => ws.close();
  }, [sessionId]);

  return { connected, log, activeRound, activeAgent };
}
