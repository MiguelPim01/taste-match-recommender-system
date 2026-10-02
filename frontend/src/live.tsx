import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

// Server-sent events from GET /api/stream (backend/src/tastematch_api/realtime/hub.py).

export interface InteractionSummary {
  event_id: string;
  type: string;
  user_id: string;
  restaurant_id: string;
  occurred_at: string;
  stars: number | null;
  text: string | null;
}

export interface LiveEvents {
  ready: { user_id: string | null };
  "interaction.recorded": InteractionSummary;
  activity: { interval_s: number; counts: Record<string, number>; recent: InteractionSummary[] };
  "recommendations.updated": { run_id: string; generated_at: string; count: number };
  "retrain.requested": { event_id: string; requested_at: string; source: string | null; force: boolean; observed_total: number | null };
  "model.ready": { run_id: string; metric_name: string; metric_value: number; created_at: string; trained_until_total: number };
}

type EventName = keyof LiveEvents;
type Handler = (data: never) => void;

interface Live {
  connected: boolean;
  subscribe: <E extends EventName>(event: E, handler: (data: LiveEvents[E]) => void) => () => void;
}

const LiveContext = createContext<Live | null>(null);
const EVENT_NAMES: EventName[] = [
  "ready", "interaction.recorded", "activity", "recommendations.updated", "retrain.requested", "model.ready",
];

/** One EventSource per profile: the stream knows who you are from the session cookie at connect time. */
export function LiveProvider({ profileId, children }: { profileId: string | null; children: ReactNode }) {
  const handlers = useRef(new Map<EventName, Set<Handler>>());
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource("/api/stream");
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    for (const name of EVENT_NAMES) {
      source.addEventListener(name, (message) => {
        const data = JSON.parse((message as MessageEvent<string>).data);
        handlers.current.get(name)?.forEach((handler) => (handler as (value: unknown) => void)(data));
      });
    }
    return () => source.close();
  }, [profileId]);

  const subscribe = useCallback<Live["subscribe"]>((event, handler) => {
    const set = handlers.current.get(event) ?? new Set<Handler>();
    handlers.current.set(event, set);
    set.add(handler as Handler);
    return () => set.delete(handler as Handler);
  }, []);

  const value = useMemo(() => ({ connected, subscribe }), [connected, subscribe]);
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export function useLive(): Live {
  const live = useContext(LiveContext);
  if (!live) throw new Error("useLive precisa de LiveProvider");
  return live;
}

/** Subscribes for the component's lifetime; the latest handler always runs, without resubscribing. */
export function useLiveEvent<E extends EventName>(event: E, handler: (data: LiveEvents[E]) => void): void {
  const { subscribe } = useLive();
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  });
  useEffect(() => subscribe(event, (data) => latest.current(data)), [event, subscribe]);
}

/** Runs once after a burst settles: a simulation publishes dozens of events in a second. */
export function useLiveRefresh(event: EventName, refresh: () => void, delayMs = 400): void {
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  useLiveEvent(event, () => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(refresh, delayMs);
  });
}
