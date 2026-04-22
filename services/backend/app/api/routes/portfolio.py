from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.portfolio import PortfolioSnapshotRead, PortfolioSummary
from app.services.portfolio.service import portfolio_service

router = APIRouter()


@router.get("/summary", response_model=PortfolioSummary)
def summary(mode: str | None = Query(default=None), db: Session = Depends(get_db)) -> PortfolioSummary:
    return PortfolioSummary.model_validate(portfolio_service.get_portfolio_summary(db, mode=mode))


@router.get("/snapshots", response_model=list[PortfolioSnapshotRead])
def snapshots(mode: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[PortfolioSnapshotRead]:
    return [PortfolioSnapshotRead.model_validate(snapshot) for snapshot in portfolio_service.list_snapshots(db, mode)]
