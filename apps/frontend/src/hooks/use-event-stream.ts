"use client";

import { useEffect, useState } from "react";

const DEFAULT_SSE_URL = process.env.NEXT_PUBLIC_SSE_URL || "http://localhost:8000/api/v1/stream/events";

export function useEventStream() {
  const [events, setEvents] = useState<Array<{ event: string; timestamp: string; payload: Record<string, unknown> }>>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource(DEFAULT_SSE_URL);
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (message) => {
      try {
        const parsed = JSON.parse(message.data);
        setEvents((current) => [parsed, ...current].slice(0, 20));
      } catch {
        setEvents((current) => [{ event: "raw", timestamp: new Date().toISOString(), payload: { message: message.data } }, ...current].slice(0, 20));
      }
    };
    return () => {
      source.close();
    };
  }, []);

  return { events, connected };
}
