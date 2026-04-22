"use client";

import { TradingWorkspace } from "@/components/trading/trading-workspace";

export default function LiveTradingPage() {
  return (
    <TradingWorkspace
      mode="live"
      title="Live trading workspace"
      description="Guarded real-money workspace for manual execution, semi-automatic review, and broker-aware automation. Live trading stays backend-disabled by default until explicitly allowed."
    />
  );
}
