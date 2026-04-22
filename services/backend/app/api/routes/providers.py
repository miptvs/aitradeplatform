from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.provider import (
    ProviderConfigRead,
    ProviderConfigUpsert,
    ProviderHealthRead,
    ProviderModelsRead,
    ProviderRunRequest,
    TaskMappingRead,
)
from app.services.providers.service import provider_service

router = APIRouter()


@router.get("/", response_model=list[ProviderConfigRead])
def list_providers(db: Session = Depends(get_db)) -> list[ProviderConfigRead]:
    return [ProviderConfigRead.model_validate(provider_service.serialize_config(config)) for config in provider_service.list_configs(db)]


@router.get("/health", response_model=list[ProviderHealthRead])
def provider_health(db: Session = Depends(get_db)) -> list[ProviderHealthRead]:
    return [ProviderHealthRead.model_validate(item) for item in provider_service.get_health(db)]


@router.post("/{provider_type}", response_model=ProviderConfigRead)
def upsert_provider(provider_type: str, payload: ProviderConfigUpsert, db: Session = Depends(get_db)) -> ProviderConfigRead:
    if not provider_service.supports_profile(provider_type):
        raise HTTPException(status_code=404, detail="Provider type not supported")
    config = provider_service.upsert_config(db, provider_type, payload)
    db.commit()
    db.refresh(config)
    return ProviderConfigRead.model_validate(provider_service.serialize_config(config))


@router.post("/{provider_type}/test", response_model=ProviderHealthRead)
def test_provider(provider_type: str, db: Session = Depends(get_db)) -> ProviderHealthRead:
    try:
        result = provider_service.test_connection(db, provider_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return ProviderHealthRead.model_validate(result)


@router.get("/{provider_type}/models", response_model=ProviderModelsRead)
def provider_models(provider_type: str, db: Session = Depends(get_db)) -> ProviderModelsRead:
    try:
        models = provider_service.list_models(db, provider_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProviderModelsRead(provider_type=provider_type, models=models)


@router.post("/run")
def provider_run(payload: ProviderRunRequest, db: Session = Depends(get_db)) -> dict:
    result = provider_service.run_task(db, task_name=payload.task_name, prompt=payload.prompt, metadata=payload.metadata)
    db.commit()
    return {
        "provider_type": result.provider_type,
        "model_name": result.model_name,
        "latency_ms": result.latency_ms,
        "text": result.text,
    }


@router.get("/task-mappings", response_model=list[TaskMappingRead])
def list_mappings(db: Session = Depends(get_db)) -> list[TaskMappingRead]:
    return [TaskMappingRead.model_validate(item) for item in provider_service.list_task_mappings(db)]
