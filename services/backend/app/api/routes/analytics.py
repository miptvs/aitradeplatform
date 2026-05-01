from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analytics import AnalyticsOverview, ModelMetricRead, SimulationVsLiveComparison
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


@router.get("/model-comparison", response_model=list[ModelMetricRead])
def model_comparison(
    scope: str | None = Query(default=None),
    replay_run_id: str | None = Query(default=None),
    simulation_account_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ModelMetricRead]:
    return [
        ModelMetricRead.model_validate(item)
        for item in analytics_service.model_comparison(
            db,
            scope=scope,
            replay_run_id=replay_run_id,
            simulation_account_id=simulation_account_id,
        )
    ]


@router.get("/model-comparison.csv")
def model_comparison_csv(
    scope: str | None = Query(default=None),
    replay_run_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    content = analytics_service.model_comparison_csv(db, scope=scope, replay_run_id=replay_run_id)
    return Response(content=content, media_type="text/csv")
