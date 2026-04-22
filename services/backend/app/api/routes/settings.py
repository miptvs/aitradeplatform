from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.provider import TaskMappingRead, TaskMappingUpsert
from app.schemas.risk import RiskRuleRead
from app.schemas.settings import SettingsOverview
from app.services.providers.service import provider_service
from app.services.risk.service import risk_service

router = APIRouter()
settings = get_settings()


@router.get("/overview", response_model=SettingsOverview)
def overview(db: Session = Depends(get_db)) -> SettingsOverview:
    providers = [provider_service.serialize_config(config) for config in provider_service.list_configs(db)]
    mappings = provider_service.list_task_mappings(db)
    rules = risk_service.list_rules(db)
    return SettingsOverview(
        providers=providers,
        task_mappings=[TaskMappingRead.model_validate(mapping) for mapping in mappings],
        risk_rules=[RiskRuleRead.model_validate(rule) for rule in rules],
        live_trading_enabled=settings.enable_live_trading,
    )


@router.get("/task-mappings", response_model=list[TaskMappingRead])
def task_mappings(db: Session = Depends(get_db)) -> list[TaskMappingRead]:
    return [TaskMappingRead.model_validate(item) for item in provider_service.list_task_mappings(db)]


@router.post("/task-mappings", response_model=TaskMappingRead)
def upsert_task_mapping(payload: TaskMappingUpsert, db: Session = Depends(get_db)) -> TaskMappingRead:
    mapping = provider_service.upsert_task_mapping(db, payload)
    db.commit()
    db.refresh(mapping)
    return TaskMappingRead.model_validate(mapping)
