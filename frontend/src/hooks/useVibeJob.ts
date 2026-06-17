import { useEffect, useRef, useState } from "react";
import type { ChatMessage, CodingJob, VibeJobEvent } from "../api/vibe";
import { vibeApi, vibeJobSocketUrl } from "../api/vibe";

export function useVibeJob(jobId: string | null) {
  const [job, setJob] = useState<CodingJob | null>(null);
  const [events, setEvents] = useState<VibeJobEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    vibeApi
      .getJob(jobId)
      .then((j) => {
        if (!cancelled) setJob(j);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    vibeApi
      .listEvents(jobId)
      .then((ev) => {
        if (!cancelled) setEvents(ev);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    const ws = new WebSocket(vibeJobSocketUrl(jobId));
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string) as {
          type: string;
          payload?: Record<string, unknown> & ChatMessage;
          jobStatus?: string;
        };
        if (data.type === "chat.message" && data.payload) {
          const msg = data.payload as unknown as ChatMessage;
          setJob((prev) =>
            prev
              ? { ...prev, messages: [...prev.messages, msg] }
              : prev,
          );
        } else if (data.type && data.type !== "chat.message") {
          setEvents((prev) => [
            ...prev,
            {
              id: String(data.payload?.eventId ?? crypto.randomUUID()),
              job_id: jobId,
              event_type: data.type,
              payload: data.payload ?? {},
              created_at: new Date().toISOString(),
            },
          ]);
          if (data.jobStatus) {
            setJob((prev) => (prev ? { ...prev, status: data.jobStatus as CodingJob["status"] } : prev));
          }
          vibeApi.getJob(jobId).then(setJob).catch(() => {});
        }
      } catch {
        /* ignore malformed */
      }
    };
    return () => ws.close();
  }, [jobId]);

  return { job, setJob, events, connected, error };
}

export function useVibeWorkers(pollMs = 10000) {
  const [workers, setWorkers] = useState<Awaited<ReturnType<typeof vibeApi.listWorkers>>>([]);
  const timer = useRef<number>();

  const refresh = () => {
    vibeApi.listWorkers().then(setWorkers).catch(() => {});
  };

  useEffect(() => {
    refresh();
    timer.current = window.setInterval(refresh, pollMs);
    return () => clearInterval(timer.current);
  }, [pollMs]);

  return { workers, refresh };
}
