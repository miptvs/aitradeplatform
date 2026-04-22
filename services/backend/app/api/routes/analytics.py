from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analytics import AnalyticsOverview, SimulationVsLiveComparison
from app.services.analytics.service import analytics_service

router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverview)
def overview(db: Session = Depends(get_db)) -> AnalyticsOverview:
    return AnalyticsOverview.model_validate(analytics_service.overview(db))


@router.get("/equity-curve")
def equity_curve(
    mode: str | None = Query(default=None),
    simulation_account_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    return analytics_service.equity_curve(db, mode=mode, simulation_account_id=simulation_account_id)


@router.get("/simulation-vs-live", response_model=SimulationVsLiveComparison)
def simulation_vs_live(db: Session = Depends(get_db)) -> SimulationVsLiveComparison:
    return SimulationVsLiveComparison.model_validate(analytics_service.simulation_vs_live(db))
