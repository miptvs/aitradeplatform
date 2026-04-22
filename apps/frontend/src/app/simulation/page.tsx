"use client";

import { TradingWorkspace } from "@/components/trading/trading-workspace";

export default function SimulationPage() {
  return (
    <TradingWorkspace
      mode="simulation"
      title="Simulation trading workspace"
      description="Train the exact same workflow you plan to use in live trading, including manual tickets, automation policies, stop management, and post-trade review."
    />
  );
}
