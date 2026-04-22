"use client";

import type { ReactNode } from "react";
import { ArrowRight, Blocks, Bot, BrainCircuit, Database, HardDriveDownload, Newspaper, Server, ShieldCheck, TimerReset, Waves } from "lucide-react";

import { useWorkspace } from "@/components/layout/workspace-provider";
import { StatusBadge } from "@/components/ui/status-badge";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";

export default function ArchitecturePage() {
  const workspace = useWorkspace();
  const { data, loading, error } = useApi(async () => {
    const [settings, health, ready, brokerAccounts, brokerAdapters, simulationAccounts, mcpStatus] = await Promise.all([
      api.getSettingsOverview(),
      api.getHealth(),
      api.getHealthReady(),
      api.getBrokerAccounts(),
      api.getBrokerAdapters(),
      api.getSimulationAccounts(),
      api.getMcpStatus(),
    ]);
    return { settings, health, ready, brokerAccounts, brokerAdapters, simulationAccounts, mcpStatus };
  }, [workspace.key]);

  if (loading || !data) return <div className="text-sm text-slate-400">Loading architecture...</div>;
  if (error) return <div className="text-sm text-rose-300">Architecture failed to load: {error}</div>;

  const workspaceProviders = data.settings.providers.filter(
    (provider) => provider.deployment_scope === workspace.scope && provider.vendor_key === workspace.vendorKey
  );
  const simulationProvider = workspaceProviders.find((provider) => provider.provider_type === workspace.simulationProviderType);
  const liveProvider = workspaceProviders.find((provider) => provider.provider_type === workspace.liveProviderType);
  const currentHealth = data.health.providers.filter((provider) =>
    [workspace.simulationProviderType, workspace.liveProviderType].includes(provider.provider_type)
  );
  const activeSimulationAccount = data.simulationAccounts.find((account) => account.is_active) || data.simulationAccounts[0];
  const currentModelRuntimeTitle = workspace.scope === "local" ? "Ollama :11434" : "Remote model API";
  const currentModelRuntimeSubtitle = workspace.scope === "local" ? simulationProvider?.default_model || "Local family runtime" : simulationProvider?.base_url || "Provider endpoint";
  const currentModelRuntimeDescription =
    workspace.scope === "local"
      ? "Local workspaces call Ollama directly for model inference."
      : "Remote workspaces call the configured vendor endpoint with backend-only credentials.";
  const modelRuntimeStatus = simulationProvider?.enabled ? simulationProvider?.last_health_status || "ok" : "disabled";
  const backendStatus = data.ready.status === "ok" ? "ok" : "error";
  const databaseStatus = data.ready.details.database === "ok" ? "ok" : "error";
  const redisStatus = data.ready.details.redis === "ok" ? "ok" : "error";
  const frontendStatus = "ok";
  const mcpStatus = data.mcpStatus.reachable ? "ok" : "error";

  return (
    <div className="space-y-6">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Architecture</div>
        <h1 className="mt-1 text-2xl font-semibold text-slate-100">Runtime map for {workspace.label}</h1>
        <div className="mt-2 text-sm text-slate-400">
          This view shows how the current frontend port, backend services, model profiles, data stores, and automation lanes fit together.
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em]" style={{ color: workspace.theme.primary }}>
            Active Topology
          </div>
          <div className="mt-4 grid gap-3 xl:grid-cols-[1fr_auto_1fr_auto_1fr]">
            <ArchitectureNode
              icon={<Waves size={18} />}
              title={`Frontend :${workspace.port}`}
              subtitle={workspace.label}
              description="Next.js terminal UI for this model workspace."
              accent={workspace.theme.primary}
            />
            <ArrowColumn />
            <ArchitectureNode
              icon={<Server size={18} />}
              title="Backend :8000"
              subtitle="FastAPI + SSE"
              description="Central API, risk checks, signal orchestration, broker adapters."
              accent={workspace.theme.secondary}
            />
            <ArrowColumn />
            <ArchitectureNode
              icon={<Bot size={18} />}
              title={currentModelRuntimeTitle}
              subtitle={currentModelRuntimeSubtitle}
              description={currentModelRuntimeDescription}
              accent={workspace.theme.primary}
            />
          </div>

          <div className="mt-4 grid gap-3 xl:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr_auto_1fr_auto_1fr]">
            <ArchitectureNode
              icon={<Blocks size={18} />}
              title="Docker Compose"
              subtitle="Local orchestration"
              description="Starts the frontend ports, backend, workers, Redis, Postgres, and Ollama together."
              accent="#94a3b8"
            />
            <ArrowColumn />
            <ArchitectureNode
              icon={<Database size={18} />}
              title="Postgres"
              subtitle="Primary persistence"
              description="Positions, orders, trades, signals, news, audit logs, settings."
              accent="#94a3b8"
            />
            <ArrowColumn />
            <ArchitectureNode
              icon={<TimerReset size={18} />}
              title="Redis"
              subtitle="Queues + stream"
              description="Celery broker/result store and SSE event fan-out."
              accent="#f59e0b"
            />
            <ArrowColumn />
            <ArchitectureNode
              icon={<HardDriveDownload size={18} />}
              title="Worker + Scheduler"
              subtitle="Celery + periodic tasks"
              description="Refreshes market data, RSS news, provider health, and signal jobs."
              accent="#38bdf8"
            />
            <ArrowColumn />
            <ArchitectureNode
              icon={<ShieldCheck size={18} />}
              title="Broker Layer"
              subtitle="Paper + Trading212 scaffold"
              description="Validation, sync scaffolding, strict live-trading separation."
              accent="#f87171"
            />
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em]" style={{ color: workspace.theme.primary }}>
            Current Workspace
          </div>
          <div className="mt-4 space-y-3">
            <InfoCard label="Frontend origin" value={`http://${workspace.host}:${workspace.port}`} status={frontendStatus} helper="This page is already being served, so the active frontend is up." />
            <InfoCard label="Backend origin" value="http://localhost:8000/api/v1" status={backendStatus} helper="Checked via the backend readiness endpoint." />
            <InfoCard label="Database" value={data.ready.details.database || "unknown"} status={databaseStatus} />
            <InfoCard label="Redis" value={data.ready.details.redis || "unknown"} status={redisStatus} />
            <InfoCard
              label="MCP transport"
              value="http://localhost:8000/mcp/"
              status={mcpStatus}
              helper={`Machine-to-machine endpoint. Internal Docker client uses ${data.mcpStatus.server_url}.`}
            />
            <InfoCard
              label="MCP browser check"
              value="http://localhost:8000/api/v1/mcp/status"
              status={mcpStatus}
              helper="Use this JSON endpoint in a browser. The raw /mcp/ transport speaks MCP, not a normal web page."
            />
            <InfoCard label="Model runtime" value={currentModelRuntimeSubtitle} status={modelRuntimeStatus} helper={currentModelRuntimeDescription} />
            <InfoCard label="Signal profile" value={workspace.signalProviderType} />
            <InfoCard label="Simulation profile" value={workspace.simulationProviderType} />
            <InfoCard label="Actual trading profile" value={workspace.liveProviderType} />
            <InfoCard label="Active simulation account" value={activeSimulationAccount ? `${activeSimulationAccount.name} (${activeSimulationAccount.starting_cash.toFixed(2)} starting cash)` : "No simulation account"} />
          </div>

          <div className="mt-4 rounded-xl border border-border bg-black/20 p-3 text-sm leading-6 text-slate-300">
            <div>
              <span className="text-slate-100">Why `http://localhost:8000/mcp/` looks odd:</span> MCP streamable HTTP is a protocol transport, so a plain browser GET can show an accept-header error instead of a page.
            </div>
            <div className="mt-2">
              <span className="text-slate-100">Why `http://backend:8000/mcp/` does not load:</span> `backend` is the Docker-internal hostname, so it only resolves from containers on the Compose network, not from your host browser.
            </div>
          </div>

          <div className="mt-4 rounded-xl border border-border bg-black/20 p-3">
            <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Provider health</div>
            <div className="mt-3 space-y-2">
              {currentHealth.length ? (
                currentHealth.map((provider) => (
                  <div key={provider.provider_type} className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm text-slate-100">{provider.provider_type}</div>
                      <div className="text-xs text-slate-400">{provider.message}</div>
                    </div>
                    <StatusBadge status={provider.status} />
                  </div>
                ))
              ) : (
                <div className="text-sm text-slate-400">No provider health events recorded yet for this workspace.</div>
              )}
            </div>
          </div>

          <div className="mt-4 rounded-xl border border-border bg-black/20 p-3">
            <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Broker accounts</div>
            <div className="mt-3 space-y-2">
              {data.brokerAccounts.length ? (
                data.brokerAccounts.map((account) => (
                  <div key={account.id} className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm text-slate-100">{account.name}</div>
                      <div className="text-xs text-slate-400">
                        {account.broker_type} · {account.mode} · {account.enabled ? "enabled" : "disabled"}
                      </div>
                    </div>
                    <StatusBadge status={account.status || "disabled"} />
                  </div>
                ))
              ) : (
                <div className="text-sm text-slate-400">No broker accounts configured yet.</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
        <div className="text-sm font-semibold uppercase tracking-[0.18em]" style={{ color: workspace.theme.primary }}>
          Data And Decision Flow
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr_auto_1fr]">
          <ArchitectureNode
            icon={<Newspaper size={18} />}
            title="RSS News"
            subtitle="Real articles only"
            description="Google News RSS and symbol-aware feed searches."
            accent="#fbbf24"
          />
          <ArrowColumn />
          <ArchitectureNode
            icon={<HardDriveDownload size={18} />}
            title="Market Data"
            subtitle="Quote history refresh"
            description="Yahoo Finance daily history plus manual price captures update the technical-data layer."
            accent="#60a5fa"
          />
          <ArrowColumn />
          <ArchitectureNode
            icon={<BrainCircuit size={18} />}
            title="Signal Engine"
            subtitle="Technical votes + model synthesis"
            description="Strategies produce candidate votes, then the selected model turns them into one workspace-scoped signal."
            accent={workspace.theme.primary}
          />
          <ArrowColumn />
          <ArchitectureNode
            icon={<ShieldCheck size={18} />}
            title="Risk Engine"
            subtitle="Mandatory gate"
            description="Daily loss, per-trade risk, exposure, duplicate-order, and mode checks."
            accent="#f87171"
          />
          <ArrowColumn />
          <ArchitectureNode
            icon={<Server size={18} />}
            title="Execution Lanes"
            subtitle="Simulation vs live"
            description="Simulation can fill locally. Live remains guarded and disabled by default."
            accent="#c084fc"
          />
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em]" style={{ color: workspace.theme.primary }}>
            Extension And Ops Lane
          </div>
          <div className="mt-4 grid gap-3 xl:grid-cols-[1fr_auto_1fr_auto_1fr]">
            <ArchitectureNode
              icon={<Blocks size={18} />}
              title="MCP / Agent Tools"
              subtitle={data.mcpStatus.reachable ? "Live streamable HTTP server" : "Configured but unavailable"}
              description="The backend now mounts a real MCP server and uses an MCP client to fetch standardized trading context tools before model signal generation."
              accent="#fbbf24"
            />
            <ArrowColumn />
            <ArchitectureNode
              icon={<Server size={18} />}
              title="FastAPI services"
              subtitle="Controlled integration boundary"
              description="Any external assistant or MCP bridge should still go through backend rules, audit logging, and broker guards."
              accent={workspace.theme.secondary}
            />
            <ArrowColumn />
            <ArchitectureNode
              icon={<ShieldCheck size={18} />}
              title="Audit + Risk"
              subtitle="Non-bypassable controls"
              description="Critical actions stay logged and risk-validated regardless of whether they come from the UI, a scheduler, or future agent integrations."
              accent="#f87171"
            />
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em]" style={{ color: workspace.theme.primary }}>
            Broker And Adapter Capabilities
          </div>
          <div className="mt-4 space-y-3">
            {data.brokerAdapters.map((adapter) => (
              <div key={adapter.broker_type} className="rounded-xl border border-border bg-black/20 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm text-slate-100">{adapter.broker_type}</div>
                  <StatusBadge status={adapter.supports_execution ? "ok" : "disabled"} />
                </div>
                <div className="mt-2 text-xs leading-5 text-slate-400">{adapter.message}</div>
                <div className="mt-2 text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  Sync: {adapter.supports_sync ? "yes" : "no"} · Execution: {adapter.supports_execution ? "yes" : "guarded/off"}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em]" style={{ color: workspace.theme.primary }}>
            MCP Client Status
          </div>
          <div className="mt-4 space-y-3">
            <InfoCard label="Reachable" value={data.mcpStatus.reachable ? "Yes" : "No"} />
            <InfoCard label="Transport" value={data.mcpStatus.transport} />
            <InfoCard label="Server name" value={data.mcpStatus.server_name || "Unknown"} />
            <div className="rounded-xl border border-border bg-black/20 p-3 text-sm text-slate-300">
              {data.mcpStatus.message}
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
          <div className="text-sm font-semibold uppercase tracking-[0.18em]" style={{ color: workspace.theme.primary }}>
            Exposed MCP Tools
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {data.mcpStatus.tools.map((tool) => (
              <div key={tool.name} className="rounded-xl border border-border bg-black/20 p-3">
                <div className="text-sm text-slate-100">{tool.name}</div>
                <div className="mt-2 text-xs leading-5 text-slate-400">{tool.description || "No description provided."}</div>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-xl border border-border bg-black/20 p-3">
            <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Resources</div>
            <div className="mt-2 space-y-2">
              {data.mcpStatus.resources.map((resource) => (
                <div key={resource.uri} className="text-sm text-slate-300">
                  <span className="text-slate-100">{resource.uri}</span>
                  {resource.description ? <span className="text-slate-500"> · {resource.description}</span> : null}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <ProviderModeCard
          title="Simulation profile"
          provider={simulationProvider}
          accent={workspace.theme.primary}
        />
        <ProviderModeCard
          title="Actual trading profile"
          provider={liveProvider}
          accent={workspace.theme.secondary}
        />
      </div>
    </div>
  );
}

function ArchitectureNode({
  icon,
  title,
  subtitle,
  description,
  accent,
}: {
  icon: ReactNode;
  title: string;
  subtitle: string;
  description: string;
  accent: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-black/20 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: accent }}>
        {icon}
        {title}
      </div>
      <div className="mt-1 text-sm text-slate-100">{subtitle}</div>
      <div className="mt-2 text-xs leading-5 text-slate-400">{description}</div>
    </div>
  );
}

function ArrowColumn() {
  return (
    <div className="hidden items-center justify-center xl:flex">
      <ArrowRight className="text-slate-500" size={20} />
    </div>
  );
}

function InfoCard({
  label,
  value,
  status,
  helper,
}: {
  label: string;
  value: string;
  status?: string;
  helper?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-black/20 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</div>
        {status ? <StatusBadge status={status} /> : null}
      </div>
      <div className="mt-1 text-sm text-slate-100">{value}</div>
      {helper ? <div className="mt-2 text-xs leading-5 text-slate-400">{helper}</div> : null}
    </div>
  );
}

function ProviderModeCard({
  title,
  provider,
  accent,
}: {
  title: string;
  provider?: {
    provider_type: string;
    enabled: boolean;
    default_model?: string | null;
    base_url: string;
    last_health_status?: string | null;
    description: string;
    mode_label: string;
  };
  accent: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-panel/90 p-4 shadow-panel">
      <div className="text-sm font-semibold uppercase tracking-[0.18em]" style={{ color: accent }}>
        {title}
      </div>
      {provider ? (
        <div className="mt-4 space-y-3">
          <InfoCard label="Provider type" value={provider.provider_type} />
          <InfoCard label="Mode" value={provider.mode_label} />
          <InfoCard label="Default model" value={provider.default_model || "Not configured"} />
          <InfoCard label="Base URL" value={provider.base_url} />
          <div className="rounded-xl border border-border bg-black/20 p-3 text-sm text-slate-300">{provider.description}</div>
          <div className="flex items-center justify-between rounded-xl border border-border bg-black/20 p-3">
            <span className="text-sm text-slate-100">Enabled</span>
            <StatusBadge status={provider.enabled ? provider.last_health_status || "ok" : "disabled"} />
          </div>
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-border bg-black/20 p-3 text-sm text-slate-400">
          No provider config found for this mode yet.
        </div>
      )}
    </div>
  );
}
