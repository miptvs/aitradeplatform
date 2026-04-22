from time import perf_counter

import httpx

from app.core.crypto import decrypt_secret
from app.models.provider import ProviderConfig
from app.services.providers.base import BaseProviderAdapter, ProviderRunResult


class AnthropicProviderAdapter(BaseProviderAdapter):
    provider_type = "anthropic"

    def _headers(self, config: ProviderConfig) -> dict[str, str]:
        secret = decrypt_secret(config.encrypted_api_key)
        if not secret:
            raise ValueError("API key not configured")
        return {
            "x-api-key": secret,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def health_check(self, config: ProviderConfig) -> tuple[bool, str, int | None]:
        start = perf_counter()
        try:
            response = httpx.get(f"{config.base_url.rstrip('/')}/models", headers=self._headers(config), timeout=5)
            response.raise_for_status()
            return True, "Anthropic endpoint reachable", int((perf_counter() - start) * 1000)
        except Exception as exc:
            return False, str(exc), None

    def list_models(self, config: ProviderConfig) -> list[str]:
        response = httpx.get(f"{config.base_url.rstrip('/')}/models", headers=self._headers(config), timeout=10)
        response.raise_for_status()
        payload = response.json()
        return [
            item.get("id", item.get("display_name", "unknown"))
            for item in payload.get("data", payload.get("models", []))
            if item.get("id") or item.get("display_name")
        ]

    def run_task(
        self,
        config: ProviderConfig,
        *,
        prompt: str,
        task_name: str,
        model_name: str | None = None,
        timeout_seconds: int = 30,
    ) -> ProviderRunResult:
        chosen_model = model_name or config.default_model
        if not chosen_model:
            raise ValueError("No Anthropic model configured")
        start = perf_counter()
        response = httpx.post(
            f"{config.base_url.rstrip('/')}/messages",
            headers=self._headers(config),
            json={
                "model": chosen_model,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "system": f"You are assisting with the task: {task_name}.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        text = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
        usage = payload.get("usage", {})
        return ProviderRunResult(
            text=text,
            provider_type=self.provider_type,
            model_name=chosen_model,
            latency_ms=int((perf_counter() - start) * 1000),
            usage=usage,
            raw=payload,
        )
