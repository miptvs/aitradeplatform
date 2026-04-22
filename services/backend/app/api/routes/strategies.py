from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.market import StrategyRead
from app.services.strategies.service import strategy_service

router = APIRouter()


@router.get("/", response_model=list[StrategyRead])
def list_strategies(db: Session = Depends(get_db)) -> list[StrategyRead]:
    return [StrategyRead.model_validate(item) for item in strategy_service.list_strategies(db)]
