import type { Metadata } from "next";
import { headers } from "next/headers";

import "@/app/globals.css";
import { AppShell } from "@/components/layout/app-shell";
import { WorkspaceProvider } from "@/components/layout/workspace-provider";
import { resolveWorkspaceConfig } from "@/lib/workspace";

export const metadata: Metadata = {
  title: "AI Trader Platform",
  description: "Local-first AI trading terminal with strict simulation and live separation."
};

export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const requestHeaders = await headers();
  const workspace = resolveWorkspaceConfig(requestHeaders.get("host"));

  return (
    <html lang="en">
      <body className="font-[var(--font-sans)] antialiased">
        <WorkspaceProvider value={workspace}>
          <AppShell>{children}</AppShell>
        </WorkspaceProvider>
      </body>
    </html>
  );
}
