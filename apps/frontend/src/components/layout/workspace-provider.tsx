"use client";

import { createContext, useContext } from "react";

import type { WorkspaceConfig } from "@/lib/workspace";

const WorkspaceContext = createContext<WorkspaceConfig | null>(null);

export function WorkspaceProvider({ value, children }: { value: WorkspaceConfig; children: React.ReactNode }) {
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const workspace = useContext(WorkspaceContext);
  if (!workspace) {
    throw new Error("useWorkspace must be used within WorkspaceProvider");
  }
  return workspace;
}
