from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings


@dataclass(frozen=True)
class ProviderProfileSpec:
    profile_key: str
    adapter_type: str
    vendor_key: str
    vendor_name: str
    deployment_scope: str
    trading_mode: str
    mode_label: str
    title: str
    description: str
    default_base_url: str
    default_model: str | None
    suggested_models: list[str] = field(default_factory=list)
    reasoning_modes: list[str] = field(default_factory=list)
    supports_api_key: bool = True
    tool_calling_default: bool = False
    enabled_by_default: bool = False
    temperature: float = 0.2
    max_tokens: int = 512
    context_window: int = 8192
    settings_defaults: dict[str, Any] = field(default_factory=dict)


def build_provider_catalog(settings: Settings) -> dict[str, ProviderProfileSpec]:
    local_families = [
        {
            "profile_prefix": "local_gpt_oss",
            "vendor_key": "gpt-oss",
            "vendor_name": "GPT OSS",
            "suggested_models": ["gpt-oss:20b"],
            "simulation_model": "gpt-oss:20b",
            "live_model": "gpt-oss:20b",
            "simulation_description": "Local GPT OSS profile for exploratory simulation commentary, ranking, and sandbox trade review.",
            "live_description": "Local GPT OSS profile reserved for guarded actual-trading commentary and review workflows.",
            "simulation_context_window": 131072,
            "live_context_window": 131072,
        },
        {
            "profile_prefix": "local_qwen25",
            "vendor_key": "qwen2.5",
            "vendor_name": "Qwen 2.5",
            "suggested_models": ["qwen2.5:7b-instruct"],
            "simulation_model": "qwen2.5:7b-instruct",
            "live_model": "qwen2.5:7b-instruct",
            "simulation_description": "Local Qwen 2.5 profile tuned for fast simulation research, event extraction, and sentiment classification.",
            "live_description": "Local Qwen 2.5 profile reserved for guarded actual-trading commentary when you want a lighter-weight local reviewer.",
            "simulation_context_window": 32768,
            "live_context_window": 32768,
        },
        {
            "profile_prefix": "local_qwen3",
            "vendor_key": "qwen3",
            "vendor_name": "Qwen 3",
            "suggested_models": ["qwen3:8b"],
            "simulation_model": "qwen3:8b",
            "live_model": "qwen3:8b",
            "simulation_description": "Local Qwen 3 profile for broad simulation work, news summarization, and candidate analysis.",
            "live_description": "Local Qwen 3 profile reserved for guarded actual-trading commentary with a stronger general-purpose local model.",
            "simulation_context_window": 40000,
            "live_context_window": 40000,
        },
        {
            "profile_prefix": "local_llama3",
            "vendor_key": "llama3",
            "vendor_name": "Llama 3.1 / 3.2",
            "suggested_models": ["llama3.1:8b", "llama3.2:3b"],
            "simulation_model": "llama3.2:3b",
            "live_model": "llama3.1:8b",
            "simulation_description": "Local Llama 3.1 / 3.2 profile for simulation rationale, chart commentary, and lighter-weight local experimentation.",
            "live_description": "Local Llama 3.1 / 3.2 profile reserved for guarded actual-trading rationale and portfolio commentary.",
            "simulation_context_window": 8192,
            "live_context_window": 8192,
        },
        {
            "profile_prefix": "local_deepseek_r1",
            "vendor_key": "deepseek-r1",
            "vendor_name": "DeepSeek-R1",
            "suggested_models": ["deepseek-r1:8b"],
            "simulation_model": "deepseek-r1:8b",
            "live_model": "deepseek-r1:8b",
            "simulation_description": "Local DeepSeek-R1 profile for reasoning-heavy simulation commentary and post-trade analysis.",
            "live_description": "Local DeepSeek-R1 profile reserved for guarded actual-trading review and reasoning-intensive local workflows.",
            "simulation_context_window": 32768,
            "live_context_window": 32768,
        },
    ]

    profiles: list[ProviderProfileSpec] = []
    for family in local_families:
        profiles.append(
            ProviderProfileSpec(
                profile_key=f"{family['profile_prefix']}_simulation",
                adapter_type="local",
                vendor_key=family["vendor_key"],
                vendor_name=family["vendor_name"],
                deployment_scope="local",
                trading_mode="simulation",
                mode_label="Simulation",
                title=f"{family['vendor_name']} / Simulation",
                description=family["simulation_description"],
                default_base_url=settings.provider_local_base_url,
                default_model=family["simulation_model"],
                suggested_models=family["suggested_models"],
                reasoning_modes=["standard", "reasoning"],
                supports_api_key=False,
                enabled_by_default=True,
                max_tokens=256,
                context_window=family["simulation_context_window"],
                settings_defaults={"route_guard": "simulation-only", "local_family": family["vendor_key"]},
            )
        )
        profiles.append(
            ProviderProfileSpec(
                profile_key=f"{family['profile_prefix']}_live",
                adapter_type="local",
                vendor_key=family["vendor_key"],
                vendor_name=family["vendor_name"],
                deployment_scope="local",
                trading_mode="live",
                mode_label="Actual Trading",
                title=f"{family['vendor_name']} / Actual Trading",
                description=family["live_description"],
                default_base_url=settings.provider_local_base_url,
                default_model=family["live_model"],
                suggested_models=family["suggested_models"],
                reasoning_modes=["standard", "reasoning"],
                supports_api_key=False,
                enabled_by_default=False,
                max_tokens=256,
                context_window=family["live_context_window"],
                settings_defaults={"route_guard": "actual-trading", "local_family": family["vendor_key"]},
            )
        )

    profiles.extend(
        [
            ProviderProfileSpec(
            profile_key="openai_simulation",
            adapter_type="openai",
            vendor_key="openai",
            vendor_name="ChatGPT / OpenAI",
            deployment_scope="remote",
            trading_mode="simulation",
            mode_label="Simulation",
            title="ChatGPT / OpenAI / Simulation",
            description="Paid remote profile for simulation research and commentary. Good for strong general reasoning with broad tool support.",
            default_base_url=settings.provider_openai_base_url,
            default_model="gpt-5-mini",
            suggested_models=["gpt-5-mini", "gpt-5-nano", "gpt-4.1", "gpt-4.1-mini"],
            reasoning_modes=["minimal", "low", "medium", "high"],
            supports_api_key=True,
            tool_calling_default=True,
            enabled_by_default=False,
            context_window=128000,
            settings_defaults={"billing": "paid-remote"},
        ),
        ProviderProfileSpec(
            profile_key="openai_live",
            adapter_type="openai",
            vendor_key="openai",
            vendor_name="ChatGPT / OpenAI",
            deployment_scope="remote",
            trading_mode="live",
            mode_label="Actual Trading",
            title="ChatGPT / OpenAI / Actual Trading",
            description="Higher-trust remote profile for guarded live-trading rationale, candidate review, and portfolio commentary.",
            default_base_url=settings.provider_openai_base_url,
            default_model="gpt-5.2",
            suggested_models=["gpt-5.2", "gpt-5", "gpt-5-mini", "o4-mini"],
            reasoning_modes=["minimal", "low", "medium", "high"],
            supports_api_key=True,
            tool_calling_default=True,
            enabled_by_default=False,
            context_window=400000,
            settings_defaults={"billing": "paid-remote"},
        ),
        ProviderProfileSpec(
            profile_key="anthropic_simulation",
            adapter_type="anthropic",
            vendor_key="anthropic",
            vendor_name="Claude / Anthropic",
            deployment_scope="remote",
            trading_mode="simulation",
            mode_label="Simulation",
            title="Claude / Anthropic / Simulation",
            description="Paid remote profile for deep analysis and simulation planning with strong coding and reasoning performance.",
            default_base_url="https://api.anthropic.com/v1",
            default_model="claude-sonnet-4-5",
            suggested_models=["claude-sonnet-4-5", "claude-haiku-4-5", "claude-opus-4-6"],
            reasoning_modes=["low", "medium", "high", "max"],
            supports_api_key=True,
            enabled_by_default=False,
            max_tokens=2048,
            context_window=200000,
            settings_defaults={"billing": "paid-remote"},
        ),
        ProviderProfileSpec(
            profile_key="anthropic_live",
            adapter_type="anthropic",
            vendor_key="anthropic",
            vendor_name="Claude / Anthropic",
            deployment_scope="remote",
            trading_mode="live",
            mode_label="Actual Trading",
            title="Claude / Anthropic / Actual Trading",
            description="Paid remote profile aimed at careful live-trading review, policy-heavy reasoning, and guarded decision support.",
            default_base_url="https://api.anthropic.com/v1",
            default_model="claude-opus-4-6",
            suggested_models=["claude-opus-4-6", "claude-sonnet-4-5", "claude-haiku-4-5"],
            reasoning_modes=["low", "medium", "high", "max"],
            supports_api_key=True,
            enabled_by_default=False,
            max_tokens=2048,
            context_window=200000,
            settings_defaults={"billing": "paid-remote"},
        ),
        ProviderProfileSpec(
            profile_key="gemini_simulation",
            adapter_type="gemini",
            vendor_key="gemini",
            vendor_name="Gemini / Google",
            deployment_scope="remote",
            trading_mode="simulation",
            mode_label="Simulation",
            title="Gemini / Google / Simulation",
            description="Paid remote profile optimized for long-context simulation research, large watchlists, and fast cost-aware experimentation.",
            default_base_url="https://generativelanguage.googleapis.com/v1beta",
            default_model="gemini-2.5-flash",
            suggested_models=["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"],
            reasoning_modes=["balanced", "thinking"],
            supports_api_key=True,
            tool_calling_default=True,
            enabled_by_default=False,
            max_tokens=2048,
            context_window=1048576,
            settings_defaults={"billing": "paid-remote"},
        ),
        ProviderProfileSpec(
            profile_key="gemini_live",
            adapter_type="gemini",
            vendor_key="gemini",
            vendor_name="Gemini / Google",
            deployment_scope="remote",
            trading_mode="live",
            mode_label="Actual Trading",
            title="Gemini / Google / Actual Trading",
            description="Paid remote profile for live-trading oversight when you want maximum context and stronger review-oriented reasoning.",
            default_base_url="https://generativelanguage.googleapis.com/v1beta",
            default_model="gemini-2.5-pro",
            suggested_models=["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
            reasoning_modes=["balanced", "thinking"],
            supports_api_key=True,
            tool_calling_default=True,
            enabled_by_default=False,
            max_tokens=2048,
            context_window=1048576,
            settings_defaults={"billing": "paid-remote"},
        ),
        ProviderProfileSpec(
            profile_key="deepseek_simulation",
            adapter_type="deepseek",
            vendor_key="deepseek",
            vendor_name="DeepSeek API",
            deployment_scope="remote",
            trading_mode="simulation",
            mode_label="Simulation",
            title="DeepSeek API / Simulation",
            description="Cost-efficient paid remote profile for simulation commentary, batch analysis, and reasoning-heavy sandbox experiments.",
            default_base_url=settings.provider_deepseek_base_url,
            default_model="deepseek-chat",
            suggested_models=["deepseek-chat", "deepseek-reasoner"],
            reasoning_modes=["chat", "reasoning"],
            supports_api_key=True,
            enabled_by_default=False,
            max_tokens=1024,
            context_window=64000,
            settings_defaults={"billing": "paid-remote"},
        ),
        ProviderProfileSpec(
            profile_key="deepseek_live",
            adapter_type="deepseek",
            vendor_key="deepseek",
            vendor_name="DeepSeek API",
            deployment_scope="remote",
            trading_mode="live",
            mode_label="Actual Trading",
            title="DeepSeek API / Actual Trading",
            description="Separate paid remote reasoning profile for actual-trading review, guarded trade rationale, and lower-cost live support.",
            default_base_url=settings.provider_deepseek_base_url,
            default_model="deepseek-reasoner",
            suggested_models=["deepseek-reasoner", "deepseek-chat"],
            reasoning_modes=["chat", "reasoning"],
            supports_api_key=True,
            enabled_by_default=False,
            max_tokens=1024,
            context_window=64000,
            settings_defaults={"billing": "paid-remote"},
        ),
        ]
    )

    return {profile.profile_key: profile for profile in profiles}
