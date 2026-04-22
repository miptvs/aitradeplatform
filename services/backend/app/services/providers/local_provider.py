from time import perf_counter

import httpx

from app.models.provider import ProviderConfig
from app.services.providers.base import BaseProviderAdapter, ProviderRunResult


class LocalProviderAdapter(BaseProviderAdapter):
    provider_type = "local"

    def health_check(self, config: ProviderConfig) -> tuple[bool, str, int | None]:
        start = perf_counter()
        try:
            response = httpx.get(f"{config.base_url.rstrip('/')}/api/tags", timeout=5)
            response.raise_for_status()
            latency = int((perf_counter() - start) * 1000)
            return True, "Ollama-compatible endpoint reachable", latency
        except Exception as exc:
            return False, str(exc), None

    def list_models(self, config: ProviderConfig) -> list[str]:
        response = httpx.get(f"{config.base_url.rstrip('/')}/api/tags", timeout=10)
        response.raise_for_status()
        payload = response.json()
        return [item["name"] for item in payload.get("models", [])]

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
            raise ValueError("No local model configured")
        start = perf_counter()
        response = httpx.post(
            f"{config.base_url.rstrip('/')}/api/generate",
            json={
                "model": chosen_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": config.temperature,
                    "num_ctx": config.context_window,
                    "num_predict": config.max_tokens,
                },
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return ProviderRunResult(
            text=payload.get("response", ""),
            provider_type=self.provider_type,
            model_name=chosen_model,
            latency_ms=int((perf_counter() - start) * 1000),
            raw=payload,
        )
