from time import perf_counter

import httpx

from app.core.crypto import decrypt_secret
from app.models.provider import ProviderConfig
from app.services.providers.base import BaseProviderAdapter, ProviderRunResult


class OpenAICompatibleProviderAdapter(BaseProviderAdapter):
    provider_type = "openai"

    def _headers(self, config: ProviderConfig) -> dict[str, str]:
        secret = decrypt_secret(config.encrypted_api_key)
        if not secret:
            raise ValueError("API key not configured")
        return {"Authorization": f"Bearer {secret}"}

    def health_check(self, config: ProviderConfig) -> tuple[bool, str, int | None]:
        start = perf_counter()
        try:
            response = httpx.get(
                f"{config.base_url.rstrip('/')}/models",
                headers=self._headers(config),
                timeout=5,
            )
            response.raise_for_status()
            return True, "OpenAI-compatible endpoint reachable", int((perf_counter() - start) * 1000)
        except Exception as exc:
            return False, str(exc), None

    def list_models(self, config: ProviderConfig) -> list[str]:
        response = httpx.get(
            f"{config.base_url.rstrip('/')}/models",
            headers=self._headers(config),
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        return [item["id"] for item in payload.get("data", [])]

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
            raise ValueError("No OpenAI-compatible model configured")
        start = perf_counter()
        payload = self._build_payload(
            config=config,
            chosen_model=chosen_model,
            prompt=prompt,
            task_name=task_name,
        )
        response = httpx.post(
            f"{config.base_url.rstrip('/')}/chat/completions",
            headers=self._headers(config),
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        return ProviderRunResult(
            text=message,
            provider_type=self.provider_type,
            model_name=chosen_model,
            latency_ms=int((perf_counter() - start) * 1000),
            usage=usage,
            raw=payload,
        )

    def _build_payload(
        self,
        *,
        config: ProviderConfig,
        chosen_model: str,
        prompt: str,
        task_name: str,
    ) -> dict:
        payload = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": f"You are assisting with the task: {task_name}."},
                {"role": "user", "content": prompt},
            ],
        }

        if self.provider_type != "openai" or not chosen_model.startswith("gpt-5"):
            payload["temperature"] = config.temperature

        if self.provider_type == "openai":
            payload["max_completion_tokens"] = config.max_tokens
            if config.reasoning_mode:
                payload["reasoning_effort"] = config.reasoning_mode
            if task_name == "signal_generation":
                payload["response_format"] = {"type": "json_object"}
        else:
            payload["max_tokens"] = config.max_tokens

        return payload
