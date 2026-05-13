from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.provider import ProviderConfig
from app.schemas.provider import ProviderConfigUpsert
from app.services.providers.openai_compatible import OpenAICompatibleProviderAdapter
from app.services.providers.service import provider_service


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_enabling_live_remote_profile_enables_simulation_sibling_and_shares_secret() -> None:
    db = build_session()

    provider_service.upsert_config(
        db,
        "openai_live",
        ProviderConfigUpsert(
            enabled=True,
            base_url="https://api.openai.com/v1",
            default_model="gpt-5.2",
            temperature=0.2,
            max_tokens=512,
            context_window=400000,
            tool_calling_enabled=True,
            reasoning_mode="minimal",
            task_defaults={},
            settings_json={"billing": "paid-remote"},
            api_key="sk-test-shared",
        ),
    )
    db.commit()

    live = provider_service.get_config(db, "openai_live")
    simulation = provider_service.get_config(db, "openai_simulation")

    assert live is not None
    assert simulation is not None
    assert live.enabled is True
    assert simulation.enabled is True
    assert live.base_url == "https://api.openai.com/v1"
    assert simulation.base_url == "https://api.openai.com/v1"
    assert bool(live.encrypted_api_key) is True
    assert live.encrypted_api_key == simulation.encrypted_api_key


def test_disabling_one_profile_does_not_force_disable_sibling() -> None:
    db = build_session()

    provider_service.upsert_config(
        db,
        "openai_simulation",
        ProviderConfigUpsert(
            enabled=True,
            base_url="https://api.openai.com/v1",
            default_model="gpt-5-mini",
            temperature=0.2,
            max_tokens=512,
            context_window=128000,
            tool_calling_enabled=True,
            reasoning_mode="minimal",
            task_defaults={},
            settings_json={"billing": "paid-remote"},
            api_key="sk-test-shared",
        ),
    )
    db.commit()

    provider_service.upsert_config(
        db,
        "openai_live",
        ProviderConfigUpsert(
            enabled=False,
            base_url="https://api.openai.com/v1",
            default_model="gpt-5.2",
            temperature=0.2,
            max_tokens=512,
            context_window=400000,
            tool_calling_enabled=True,
            reasoning_mode="minimal",
            task_defaults={},
            settings_json={"billing": "paid-remote"},
            api_key=None,
        ),
    )
    db.commit()

    live = provider_service.get_config(db, "openai_live")
    simulation = provider_service.get_config(db, "openai_simulation")

    assert live is not None
    assert simulation is not None
    assert live.enabled is False
    assert simulation.enabled is True
    assert live.encrypted_api_key == simulation.encrypted_api_key


def test_openai_adapter_uses_max_completion_tokens_for_openai_signal_generation() -> None:
    adapter = OpenAICompatibleProviderAdapter()
    config = ProviderConfig(
        provider_type="openai_simulation",
        name="OpenAI Simulation",
        enabled=True,
        base_url="https://api.openai.com/v1",
        default_model="gpt-5-mini",
        temperature=0.2,
        max_tokens=512,
        context_window=128000,
        tool_calling_enabled=True,
        reasoning_mode="minimal",
        task_defaults={},
        settings_json={},
        encrypted_api_key="encrypted",
    )

    payload = adapter._build_payload(
        config=config,
        chosen_model="gpt-5-mini",
        prompt="Return strict JSON.",
        task_name="signal_generation",
    )

    assert payload["max_completion_tokens"] == 512
    assert "max_tokens" not in payload
    assert "temperature" not in payload
    assert payload["reasoning_effort"] == "minimal"
    assert payload["response_format"] == {"type": "json_object"}


def test_provider_usage_metrics_estimate_model_cost_from_configured_rates() -> None:
    metrics = provider_service._usage_metrics(
        {"prompt_tokens": 1000, "completion_tokens": 500},
        {"input_cost_per_million": 2.0, "output_cost_per_million": 10.0},
    )

    assert metrics["prompt_tokens"] == 1000
    assert metrics["completion_tokens"] == 500
    assert metrics["total_tokens"] == 1500
    assert metrics["estimated_cost"] == 0.007
