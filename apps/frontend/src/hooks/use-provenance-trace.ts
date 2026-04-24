"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import type { Signal, SignalTrace } from "@/types";

export type TraceTarget = { type: "signal" | "order" | "trade" | "position"; id: string; signal?: Signal | null };

export function useProvenanceTrace() {
  const [target, setTarget] = useState<TraceTarget | null>(null);
  const [trace, setTrace] = useState<SignalTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function openTrace(nextTarget: TraceTarget) {
    setTarget(nextTarget);
    setLoading(true);
    setError(null);
    try {
      const result =
        nextTarget.type === "signal"
          ? await api.getSignalTrace(nextTarget.id)
          : nextTarget.type === "order"
            ? await api.getOrderTrace(nextTarget.id)
            : nextTarget.type === "trade"
              ? await api.getTradeTrace(nextTarget.id)
              : await api.getPositionTrace(nextTarget.id);
      setTrace(result);
    } catch (err) {
      setTrace(null);
      setError(err instanceof Error ? err.message : "Decision trail failed to load.");
    } finally {
      setLoading(false);
    }
  }

  function closeTrace() {
    setTarget(null);
    setTrace(null);
    setError(null);
  }

  return {
    target,
    signal: target?.signal || null,
    trace,
    loading,
    error,
    openTrace,
    closeTrace,
    setError,
  };
}
