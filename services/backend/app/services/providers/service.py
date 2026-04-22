import logging
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.crypto import encrypt_secret
from app.core.config import get_settings
from app.models.provider import ModelRun, ModelTaskMapping, ProviderConfig
from app.schemas.provider import ProviderConfigUpsert, TaskMappingUpsert
from app.services.providers.anthropic_provider import AnthropicProviderAdapter
from app.services.providers.base import ProviderRunResult
from app.services.providers.catalog import ProviderProfileSpec, build_provider_catalog
from app.services.providers.deepseek_compatible import DeepSeekCompatibleProviderAdapter
from app.services.providers.gemini_provider import GeminiProviderAdapter
from app.services.providers.local_provider import LocalProviderAdapter
from app.services.providers.openai_compatible import OpenAICompatibleProviderAdapter
from app.utils.time import utcnow

logger = logging.getLogger(__name__)
settings = get_settings()


class ProviderService:
    def __init__(self) -> None:
        self.adapters = {
            "local": LocalProviderAdapter(),
            "openai": OpenAICompatibleProviderAdapter(),
            "deepseek": DeepSeekCompatibleProviderAdapter(),
            "anthropic": AnthropicProviderAdapter(),
            "gemini": GeminiProviderAdapter(),
        }
        self.catalog = build_provider_catalog(settings)

    def list_configs(self, db: Session) -> list[ProviderConfig]:
        configs = [
            config
            for config in db.scalars(select(ProviderConfig).where(ProviderConfig.provider_type.in_(list(self.catalog.keys()))))
        ]
        return sorted(configs, key=lambda config: list(self.catalog).index(config.provider_type))

    def get_config(self, db: Session, provider_type: str) -> ProviderConfig | None:
        return db.scalar(select(ProviderConfig).where(ProviderConfig.provider_type == provider_type))

    def supports_profile(self, provider_type: str) -> bool:
        return provider_type in self.catalog

    def get_profile(self, provider_type: str) -> ProviderProfileSpec:
        if provider_type not in self.catalog:
            raise ValueError(f"Provider profile not supported: {provider_type}")
        return self.catalog[provider_type]

    def _family_profiles(self, provider_type: str) -> list[ProviderProfileSpec]:
        profile = self.get_profile(provider_type)
        return [
            sibling
            for key, sibling in self.catalog.items()
            if key != provider_type
            and sibling.vendor_key == profile.vendor_key
            and sibling.deployment_scope == profile.deployment_scope
        ]

    def _ensure_config(self, db: Session, provider_type: str) -> ProviderConfig:
        profile = self.get_profile(provider_type)
        config = self.get_config(db, provider_type)
        if config is None:
            config = ProviderConfig(
                provider_type=provider_type,
                name=profile.title,
                enabled=profile.enabled_by_default,
                base_url=profile.default_base_url,
                default_model=profile.default_model,
                temperature=profile.temperature,
                max_tokens=profile.max_tokens,
                context_window=profile.context_window,
                tool_calling_enabled=profile.tool_calling_default,
                reasoning_mode=profile.reasoning_modes[0] if profile.reasoning_modes else None,
                task_defaults={},
                settings_json=profile.settings_defaults,
            )
            db.add(config)
            db.flush()
        return config

    def _resolve_family_secret(
        self,
        db: Session,
        *,
        provider_type: str,
        explicit_api_key: str | None,
        current_encrypted_api_key: str | None,
    ) -> str | None:
        if explicit_api_key:
            return encrypt_secret(explicit_api_key)
        if current_encrypted_api_key:
            return current_encrypted_api_key
        for sibling_profile in self._family_profiles(provider_type):
            sibling = self.get_config(db, sibling_profile.profile_key)
            if sibling and sibling.encrypted_api_key:
                return sibling.encrypted_api_key
        return None

    def _sync_family_connection_state(
        self,
        db: Session,
        *,
        provider_type: str,
        enabled: bool,
        base_url: str,
        shared_secret: str | None,
    ) -> None:
        for sibling_profile in self._family_profiles(provider_type):
            sibling = self._ensure_config(db, sibling_profile.profile_key)
            sibling.name = sibling_profile.title
            sibling.base_url = base_url
            if enabled:
                sibling.enabled = True
            if shared_secret:
                sibling.encrypted_api_key = shared_secret

    def _get_adapter(self, provider_type: str):
        profile = self.get_profile(provider_type)
        adapter = self.adapters.get(profile.adapter_type)
        if adapter is None:
            raise ValueError(f"No adapter configured for profile {provider_type}")
        return adapter

    def serialize_config(self, config: ProviderConfig) -> dict[str, Any]:
        profile = self.get_profile(config.provider_type)
        data = {
            "id": config.id,
            "provider_type": config.provider_type,
            "adapter_type": profile.adapter_type,
            "vendor_key": profile.vendor_key,
            "vendor_name": profile.vendor_name,
            "deployment_scope": profile.deployment_scope,
            "trading_mode": profile.trading_mode,
            "mode_label": profile.mode_label,
            "name": config.name,
            "description": profile.description,
            "enabled": config.enabled,
            "base_url": config.base_url,
            "default_model": config.default_model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "context_window": config.context_window,
            "tool_calling_enabled": config.tool_calling_enabled,
            "reasoning_mode": config.reasoning_mode,
            "reasoning_modes": profile.reasoning_modes,
            "task_defaults": config.task_defaults,
            "settings_json": config.settings_json,
            "suggested_models": profile.suggested_models,
            "supports_api_key": profile.supports_api_key,
            "has_secret": bool(config.encrypted_api_key),
            "last_health_status": config.last_health_status,
            "last_health_message": config.last_health_message,
            "last_checked_at": config.last_checked_at,
        }
        return data

    def upsert_config(self, db: Session, provider_type: str, payload: ProviderConfigUpsert) -> ProviderConfig:
        profile = self.get_profile(provider_type)
        config = self._ensure_config(db, provider_type)
        shared_secret = self._resolve_family_secret(
            db,
            provider_type=provider_type,
            explicit_api_key=payload.api_key,
            current_encrypted_api_key=config.encrypted_api_key,
        )
        config.name = profile.title
        config.enabled = payload.enabled
        config.base_url = payload.base_url
        config.default_model = payload.default_model
        config.temperature = payload.temperature
        config.max_tokens = payload.max_tokens
        config.context_window = payload.context_window
        config.tool_calling_enabled = payload.tool_calling_enabled
        config.reasoning_mode = payload.reasoning_mode
        config.task_defaults = payload.task_defaults
        config.settings_json = payload.settings_json
        if shared_secret:
            config.encrypted_api_key = shared_secret
        self._sync_family_connection_state(
            db,
            provider_type=provider_type,
            enabled=payload.enabled,
            base_url=payload.base_url,
            shared_secret=shared_secret,
        )
        db.flush()
        return config

    def list_task_mappings(self, db: Session) -> list[ModelTaskMapping]:
        return list(db.scalars(select(ModelTaskMapping).order_by(ModelTaskMapping.task_name)))

    def upsert_task_mapping(self, db: Session, payload: TaskMappingUpsert) -> ModelTaskMapping:
        mapping = db.scalar(select(ModelTaskMapping).where(ModelTaskMapping.task_name == payload.task_name))
        if mapping is None:
            mapping = ModelTaskMapping(task_name=payload.task_name, provider_type=payload.provider_type, model_name=payload.model_name)
            db.add(mapping)
        mapping.provider_type = payload.provider_type
        mapping.model_name = payload.model_name
        mapping.fallback_chain = payload.fallback_chain
        mapping.timeout_seconds = payload.timeout_seconds
        db.flush()
        return mapping

    def test_connection(self, db: Session, provider_type: str) -> dict[str, Any]:
        config = self.get_config(db, provider_type)
        if config is None:
            raise ValueError("Provider config not found")
        adapter = self._get_adapter(provider_type)
        ok, message, latency_ms = adapter.health_check(config)
        config.last_health_status = "ok" if ok else "error"
        config.last_health_message = message
        config.last_checked_at = utcnow()
        db.flush()
        return {
            "provider_type": provider_type,
            "status": config.last_health_status,
            "message": message,
            "latency_ms": latency_ms,
        }

    def list_models(self, db: Session, provider_type: str) -> list[str]:
        config = self.get_config(db, provider_type)
        if config is None:
            raise ValueError("Provider config not found")
        profile = self.get_profile(provider_type)
        try:
            models = self._get_adapter(provider_type).list_models(config)
            return models or profile.suggested_models
        except Exception:
            return profile.suggested_models

    def get_health(self, db: Session) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for config in self.list_configs(db):
            payloads.append(
                {
                    "provider_type": config.provider_type,
                    "vendor_name": self.get_profile(config.provider_type).vendor_name,
                    "trading_mode": self.get_profile(config.provider_type).trading_mode,
                    "status": config.last_health_status or ("ok" if config.enabled else "disabled"),
                    "message": config.last_health_message or ("Configured" if config.enabled else "Disabled"),
                    "latency_ms": None,
                }
            )
        return payloads

    def run_task(
        self,
        db: Session,
        *,
        task_name: str,
        prompt: str,
        provider_type: str | None = None,
        model_name: str | None = None,
        timeout_seconds: int | None = None,
        allow_fallback: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderRunResult:
        candidates: list[tuple[str, str | None, int]] = []

        if provider_type:
            config = self.get_config(db, provider_type)
            if config is None:
                raise ValueError(f"Provider config not found for {provider_type}")
            if not config.enabled:
                raise ValueError(f"Provider profile {provider_type} is disabled")
            candidates.append((provider_type, model_name or config.default_model, timeout_seconds or 30))
        else:
            mapping = db.scalar(select(ModelTaskMapping).where(ModelTaskMapping.task_name == task_name))
            if mapping:
                candidates.append((mapping.provider_type, mapping.model_name, mapping.timeout_seconds))
                for fallback in mapping.fallback_chain:
                    candidates.append(
                        (
                            fallback.get("provider_type", ""),
                            fallback.get("model_name"),
                            int(fallback.get("timeout_seconds", mapping.timeout_seconds)),
                        )
                    )
            else:
                for config in self.list_configs(db):
                    if config.enabled:
                        candidates.append((config.provider_type, config.default_model, 30))

        for provider_type, model_name, timeout_seconds in candidates:
            if not provider_type:
                continue
            config = self.get_config(db, provider_type)
            if config is None or not config.enabled:
                continue
            try:
                result = self._run_with_retry(
                    adapter=self._get_adapter(provider_type),
                    config=config,
                    prompt=prompt,
                    task_name=task_name,
                    model_name=model_name,
                    timeout_seconds=timeout_seconds,
                )
                result.provider_type = config.provider_type
                self._log_run(
                    db,
                    task_name=task_name,
                    provider_type=config.provider_type,
                    model_name=result.model_name,
                    status="success",
                    latency_ms=result.latency_ms,
                    output_summary=result.text[:500],
                    metadata={"usage": result.usage, **(metadata or {})},
                )
                return result
            except Exception as exc:
                logger.warning("Provider task failed for %s via %s: %s", task_name, provider_type, exc)
                self._log_run(
                    db,
                    task_name=task_name,
                    provider_type=provider_type,
                    model_name=model_name or config.default_model or "unknown",
                    status="failed",
                    latency_ms=None,
                    error_message=str(exc),
                    metadata=metadata or {},
                )

        if not allow_fallback:
            raise ValueError(f"No provider run succeeded for task {task_name}")

        fallback_text = (
            f"Template fallback for {task_name}: based on local rules, the most relevant takeaway is "
            f"{prompt[:240].replace(chr(10), ' ')}"
        )
        self._log_run(
            db,
            task_name=task_name,
            provider_type="system",
            model_name="template",
            status="success",
            latency_ms=0,
            output_summary=fallback_text[:500],
            metadata=metadata or {},
        )
        return ProviderRunResult(
            text=fallback_text,
            provider_type="system",
            model_name="template",
            latency_ms=0,
        )

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
    def _run_with_retry(
        self,
        *,
        adapter: Any,
        config: ProviderConfig,
        prompt: str,
        task_name: str,
        model_name: str | None,
        timeout_seconds: int,
    ) -> ProviderRunResult:
        return adapter.run_task(
            config,
            prompt=prompt,
            task_name=task_name,
            model_name=model_name,
            timeout_seconds=timeout_seconds,
        )

    def _log_run(
        self,
        db: Session,
        *,
        task_name: str,
        provider_type: str,
        model_name: str,
        status: str,
        latency_ms: int | None,
        output_summary: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        run = ModelRun(
            task_name=task_name,
            provider_type=provider_type,
            model_name=model_name,
            status=status,
            latency_ms=latency_ms,
            output_summary=output_summary,
            error_message=error_message,
            metadata_json=metadata or {},
        )
        db.add(run)
        db.flush()

    def recent_runs(self, db: Session) -> list[ModelRun]:
        return list(db.scalars(select(ModelRun).order_by(desc(ModelRun.created_at)).limit(50)))


provider_service = ProviderService()
