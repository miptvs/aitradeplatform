from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models.provider import ProviderConfig


@dataclass
class ProviderRunResult:
    text: str
    provider_type: str
    model_name: str
    latency_ms: int | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class BaseProviderAdapter(ABC):
    provider_type: str

    @abstractmethod
    def health_check(self, config: ProviderConfig) -> tuple[bool, str, int | None]:
        raise NotImplementedError

    @abstractmethod
    def list_models(self, config: ProviderConfig) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def run_task(
        self,
        config: ProviderConfig,
        *,
        prompt: str,
        task_name: str,
        model_name: str | None = None,
        timeout_seconds: int = 30,
    ) -> ProviderRunResult:
        raise NotImplementedError
