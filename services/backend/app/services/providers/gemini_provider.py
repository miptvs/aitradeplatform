from time import perf_counter
from urllib.parse import quote_plus

import httpx

from app.core.crypto import decrypt_secret
from app.models.provider import ProviderConfig
from app.services.providers.base import BaseProviderAdapter, ProviderRunResult


class GeminiProviderAdapter(BaseProviderAdapter):
    provider_type = "gemini"

    def _api_key(self, config: ProviderConfig) -> str:
        secret = decrypt_secret(config.encrypted_api_key)
        if not secret:
            raise ValueError("API key not configured")
        return secret

    def _models_url(self, config: ProviderConfig) -> str:
        return f"{config.base_url.rstrip('/')}/models?key={quote_plus(self._api_key(config))}"

    def health_check(self, config: ProviderConfig) -> tuple[bool, str, int | None]:
        start = perf_counter()
        try:
            response = httpx.get(self._models_url(config), timeout=5)
            response.raise_for_status()
            return True, "Gemini endpoint reachable", int((perf_counter() - start) * 1000)
        except Exception as exc:
            return False, str(exc), None

    def list_models(self, config: ProviderConfig) -> list[str]:
        response = httpx.get(self._models_url(config), timeout=10)
        response.raise_for_status()
        payload = response.json()
        models: list[str] = []
        for item in payload.get("models", []):
            name = item.get("name", "")
            if name.startswith("models/"):
                models.append(name.removeprefix("models/"))
            elif name:
                models.append(name)
        return models

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
            raise ValueError("No Gemini model configured")
        model_path = chosen_model if chosen_model.startswith("models/") else f"models/{chosen_model}"
        url = f"{config.base_url.rstrip('/')}/{model_path}:generateContent?key={quote_plus(self._api_key(config))}"
        start = perf_counter()
        response = httpx.post(
            url,
            json={
                "systemInstruction": {"parts": [{"text": f"You are assisting with the task: {task_name}."}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": config.temperature,
                    "maxOutputTokens": config.max_tokens,
                },
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        text_parts: list[str] = []
        candidate = (payload.get("candidates") or [{}])[0]
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                text_parts.append(text)
        usage = payload.get("usageMetadata", {})
        return ProviderRunResult(
            text="".join(text_parts),
            provider_type=self.provider_type,
            model_name=chosen_model,
            latency_ms=int((perf_counter() - start) * 1000),
            usage=usage,
            raw=payload,
        )
