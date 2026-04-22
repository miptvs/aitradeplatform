export type WorkspaceScope = "remote" | "local";

export interface WorkspaceTheme {
  primary: string;
  secondary: string;
  accentSurface: string;
  accentBorder: string;
  shellBackground: string;
  sidebarBackground: string;
  panelGlow: string;
}

export interface WorkspaceLink {
  key: string;
  label: string;
  port: number;
  scope: WorkspaceScope;
  vendorKey: string;
  description: string;
  origin: string;
}

export interface WorkspaceConfig {
  key: string;
  label: string;
  port: number;
  scope: WorkspaceScope;
  vendorKey: string;
  description: string;
  simulationProviderType: string;
  liveProviderType: string;
  signalProviderType: string;
  host: string;
  origin: string;
  theme: WorkspaceTheme;
  links: WorkspaceLink[];
}

interface WorkspaceTemplate {
  key: string;
  label: string;
  port: number;
  scope: WorkspaceScope;
  vendorKey: string;
  description: string;
  simulationProviderType: string;
  liveProviderType: string;
  signalProviderType: string;
  theme: WorkspaceTheme;
}

const WORKSPACE_TEMPLATES: WorkspaceTemplate[] = [
  {
    key: "openai",
    label: "ChatGPT / OpenAI",
    port: 3000,
    scope: "remote",
    vendorKey: "openai",
    description: "Emerald terminal for OpenAI-backed simulation and guarded live review.",
    simulationProviderType: "openai_simulation",
    liveProviderType: "openai_live",
    signalProviderType: "openai_simulation",
    theme: {
      primary: "#34d399",
      secondary: "#22d3ee",
      accentSurface: "rgba(52, 211, 153, 0.14)",
      accentBorder: "rgba(52, 211, 153, 0.34)",
      shellBackground:
        "radial-gradient(circle at top left, rgba(52,211,153,0.18), transparent 34%), radial-gradient(circle at top right, rgba(34,211,238,0.13), transparent 30%), linear-gradient(180deg, #031016 0%, #020617 42%, #041018 100%)",
      sidebarBackground: "linear-gradient(160deg, rgba(16, 185, 129, 0.18), rgba(8, 47, 73, 0.16), rgba(2, 6, 23, 0.92))",
      panelGlow: "0 18px 70px rgba(16, 185, 129, 0.12)"
    }
  },
  {
    key: "anthropic",
    label: "Claude / Anthropic",
    port: 3001,
    scope: "remote",
    vendorKey: "anthropic",
    description: "Copper-and-ink workspace for Claude-style deep analysis and careful review.",
    simulationProviderType: "anthropic_simulation",
    liveProviderType: "anthropic_live",
    signalProviderType: "anthropic_simulation",
    theme: {
      primary: "#f59e0b",
      secondary: "#fb7185",
      accentSurface: "rgba(245, 158, 11, 0.15)",
      accentBorder: "rgba(245, 158, 11, 0.34)",
      shellBackground:
        "radial-gradient(circle at top left, rgba(245,158,11,0.16), transparent 34%), radial-gradient(circle at top right, rgba(251,113,133,0.1), transparent 28%), linear-gradient(180deg, #140c07 0%, #09090b 45%, #140b09 100%)",
      sidebarBackground: "linear-gradient(160deg, rgba(180, 83, 9, 0.22), rgba(76, 29, 36, 0.18), rgba(9, 9, 11, 0.92))",
      panelGlow: "0 18px 70px rgba(245, 158, 11, 0.1)"
    }
  },
  {
    key: "gemini",
    label: "Gemini / Google",
    port: 3002,
    scope: "remote",
    vendorKey: "gemini",
    description: "Blue-violet long-context console for Gemini research and watchlist work.",
    simulationProviderType: "gemini_simulation",
    liveProviderType: "gemini_live",
    signalProviderType: "gemini_simulation",
    theme: {
      primary: "#60a5fa",
      secondary: "#a78bfa",
      accentSurface: "rgba(96, 165, 250, 0.14)",
      accentBorder: "rgba(96, 165, 250, 0.34)",
      shellBackground:
        "radial-gradient(circle at top left, rgba(96,165,250,0.16), transparent 34%), radial-gradient(circle at top right, rgba(167,139,250,0.14), transparent 30%), linear-gradient(180deg, #040b1a 0%, #020617 44%, #0a1020 100%)",
      sidebarBackground: "linear-gradient(160deg, rgba(37, 99, 235, 0.2), rgba(91, 33, 182, 0.2), rgba(2, 6, 23, 0.92))",
      panelGlow: "0 18px 70px rgba(96, 165, 250, 0.11)"
    }
  },
  {
    key: "deepseek-api",
    label: "DeepSeek API",
    port: 3003,
    scope: "remote",
    vendorKey: "deepseek",
    description: "Magenta-crimson reasoning desk for DeepSeek remote analysis and review.",
    simulationProviderType: "deepseek_simulation",
    liveProviderType: "deepseek_live",
    signalProviderType: "deepseek_simulation",
    theme: {
      primary: "#f472b6",
      secondary: "#fb7185",
      accentSurface: "rgba(244, 114, 182, 0.14)",
      accentBorder: "rgba(244, 114, 182, 0.34)",
      shellBackground:
        "radial-gradient(circle at top left, rgba(244,114,182,0.15), transparent 34%), radial-gradient(circle at top right, rgba(251,113,133,0.12), transparent 30%), linear-gradient(180deg, #120611 0%, #020617 44%, #160912 100%)",
      sidebarBackground: "linear-gradient(160deg, rgba(190, 24, 93, 0.2), rgba(127, 29, 29, 0.18), rgba(2, 6, 23, 0.92))",
      panelGlow: "0 18px 70px rgba(244, 114, 182, 0.1)"
    }
  },
  {
    key: "gpt-oss",
    label: "GPT OSS Local",
    port: 4000,
    scope: "local",
    vendorKey: "gpt-oss",
    description: "Teal-lime local model workspace for GPT OSS experimentation and review.",
    simulationProviderType: "local_gpt_oss_simulation",
    liveProviderType: "local_gpt_oss_live",
    signalProviderType: "local_gpt_oss_simulation",
    theme: {
      primary: "#2dd4bf",
      secondary: "#a3e635",
      accentSurface: "rgba(45, 212, 191, 0.14)",
      accentBorder: "rgba(45, 212, 191, 0.34)",
      shellBackground:
        "radial-gradient(circle at top left, rgba(45,212,191,0.16), transparent 34%), radial-gradient(circle at top right, rgba(163,230,53,0.11), transparent 28%), linear-gradient(180deg, #041312 0%, #020617 46%, #07130b 100%)",
      sidebarBackground: "linear-gradient(160deg, rgba(13, 148, 136, 0.22), rgba(77, 124, 15, 0.16), rgba(2, 6, 23, 0.92))",
      panelGlow: "0 18px 70px rgba(45, 212, 191, 0.11)"
    }
  },
  {
    key: "qwen25",
    label: "Qwen 2.5 Local",
    port: 4001,
    scope: "local",
    vendorKey: "qwen2.5",
    description: "Indigo-sky local workspace for lighter-weight Qwen 2.5 workflows.",
    simulationProviderType: "local_qwen25_simulation",
    liveProviderType: "local_qwen25_live",
    signalProviderType: "local_qwen25_simulation",
    theme: {
      primary: "#818cf8",
      secondary: "#38bdf8",
      accentSurface: "rgba(129, 140, 248, 0.14)",
      accentBorder: "rgba(129, 140, 248, 0.34)",
      shellBackground:
        "radial-gradient(circle at top left, rgba(129,140,248,0.16), transparent 34%), radial-gradient(circle at top right, rgba(56,189,248,0.12), transparent 28%), linear-gradient(180deg, #070b1d 0%, #020617 46%, #061120 100%)",
      sidebarBackground: "linear-gradient(160deg, rgba(79, 70, 229, 0.22), rgba(3, 105, 161, 0.18), rgba(2, 6, 23, 0.92))",
      panelGlow: "0 18px 70px rgba(129, 140, 248, 0.1)"
    }
  },
  {
    key: "qwen3",
    label: "Qwen 3 Local",
    port: 4002,
    scope: "local",
    vendorKey: "qwen3",
    description: "Violet-neon local workspace for Qwen 3 broad research and synthesis.",
    simulationProviderType: "local_qwen3_simulation",
    liveProviderType: "local_qwen3_live",
    signalProviderType: "local_qwen3_simulation",
    theme: {
      primary: "#a78bfa",
      secondary: "#f472b6",
      accentSurface: "rgba(167, 139, 250, 0.15)",
      accentBorder: "rgba(167, 139, 250, 0.34)",
      shellBackground:
        "radial-gradient(circle at top left, rgba(167,139,250,0.16), transparent 34%), radial-gradient(circle at top right, rgba(244,114,182,0.11), transparent 28%), linear-gradient(180deg, #0b0719 0%, #020617 46%, #12061a 100%)",
      sidebarBackground: "linear-gradient(160deg, rgba(109, 40, 217, 0.22), rgba(190, 24, 93, 0.16), rgba(2, 6, 23, 0.92))",
      panelGlow: "0 18px 70px rgba(167, 139, 250, 0.1)"
    }
  },
  {
    key: "llama3",
    label: "Llama 3.1 / 3.2 Local",
    port: 4003,
    scope: "local",
    vendorKey: "llama3",
    description: "Copper-rose local workspace for Llama review, rationale, and commentary.",
    simulationProviderType: "local_llama3_simulation",
    liveProviderType: "local_llama3_live",
    signalProviderType: "local_llama3_simulation",
    theme: {
      primary: "#fb923c",
      secondary: "#f87171",
      accentSurface: "rgba(251, 146, 60, 0.14)",
      accentBorder: "rgba(251, 146, 60, 0.34)",
      shellBackground:
        "radial-gradient(circle at top left, rgba(251,146,60,0.16), transparent 34%), radial-gradient(circle at top right, rgba(248,113,113,0.12), transparent 28%), linear-gradient(180deg, #140a06 0%, #020617 46%, #170908 100%)",
      sidebarBackground: "linear-gradient(160deg, rgba(194, 65, 12, 0.22), rgba(159, 18, 57, 0.16), rgba(2, 6, 23, 0.92))",
      panelGlow: "0 18px 70px rgba(251, 146, 60, 0.1)"
    }
  },
  {
    key: "deepseek-r1",
    label: "DeepSeek-R1 Local",
    port: 4004,
    scope: "local",
    vendorKey: "deepseek-r1",
    description: "Red-hot local reasoning workspace for DeepSeek-R1 analysis and critique.",
    simulationProviderType: "local_deepseek_r1_simulation",
    liveProviderType: "local_deepseek_r1_live",
    signalProviderType: "local_deepseek_r1_simulation",
    theme: {
      primary: "#f87171",
      secondary: "#f59e0b",
      accentSurface: "rgba(248, 113, 113, 0.14)",
      accentBorder: "rgba(248, 113, 113, 0.34)",
      shellBackground:
        "radial-gradient(circle at top left, rgba(248,113,113,0.16), transparent 34%), radial-gradient(circle at top right, rgba(245,158,11,0.12), transparent 28%), linear-gradient(180deg, #160707 0%, #020617 46%, #180907 100%)",
      sidebarBackground: "linear-gradient(160deg, rgba(185, 28, 28, 0.24), rgba(180, 83, 9, 0.16), rgba(2, 6, 23, 0.92))",
      panelGlow: "0 18px 70px rgba(248, 113, 113, 0.1)"
    }
  }
];

function parseHost(hostHeader?: string | null) {
  try {
    const parsed = new URL(`http://${hostHeader || "localhost:3000"}`);
    return {
      hostname: parsed.hostname || "localhost",
      port: Number(parsed.port || "3000")
    };
  } catch {
    return {
      hostname: "localhost",
      port: 3000
    };
  }
}

export function resolveWorkspaceConfig(hostHeader?: string | null): WorkspaceConfig {
  const { hostname, port } = parseHost(hostHeader);
  const selected = WORKSPACE_TEMPLATES.find((workspace) => workspace.port === port) || WORKSPACE_TEMPLATES[0];

  return {
    ...selected,
    host: hostname,
    origin: `http://${hostname}:${selected.port}`,
    links: WORKSPACE_TEMPLATES.map((workspace) => ({
      key: workspace.key,
      label: workspace.label,
      port: workspace.port,
      scope: workspace.scope,
      vendorKey: workspace.vendorKey,
      description: workspace.description,
      origin: `http://${hostname}:${workspace.port}`
    }))
  };
}
