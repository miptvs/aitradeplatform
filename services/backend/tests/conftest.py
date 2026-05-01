import pytest


class _FakeRedis:
    def ping(self) -> bool:
        return True

    def publish(self, *_args, **_kwargs) -> int:
        return 0

    def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def isolate_external_event_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests independent from the Docker Redis hostname."""

    def _noop_publish_event(*_args, **_kwargs) -> None:
        return None

    def _fake_get_redis() -> _FakeRedis:
        return _FakeRedis()

    monkeypatch.setattr("app.core.redis.get_redis", _fake_get_redis)
    monkeypatch.setattr("app.services.events.service.get_redis", _fake_get_redis)
    monkeypatch.setattr("app.services.events.service.publish_event", _noop_publish_event)
    monkeypatch.setattr("app.services.simulation.service.publish_event", _noop_publish_event)
    monkeypatch.setattr("app.services.portfolio.service.publish_event", _noop_publish_event)
    monkeypatch.setattr("app.api.routes.health.get_redis", _fake_get_redis)
    monkeypatch.setattr("app.api.routes.market_data.publish_event", _noop_publish_event)
    monkeypatch.setattr("app.api.routes.news.publish_event", _noop_publish_event)
    monkeypatch.setattr("app.api.routes.signals.publish_event", _noop_publish_event)
    monkeypatch.setattr("app.tasks.periodic.publish_event", _noop_publish_event)
