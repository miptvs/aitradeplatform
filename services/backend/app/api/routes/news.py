from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.market import NewsArticleRead, NewsRefreshRequest, NewsRefreshResponse
from app.services.events.service import publish_event
from app.services.news.service import news_service

router = APIRouter()


@router.get("/", response_model=list[NewsArticleRead])
def list_news(db: Session = Depends(get_db)) -> list[NewsArticleRead]:
    return [NewsArticleRead.model_validate(article) for article in news_service.list_articles(db)]


@router.get("/diagnostics", response_model=NewsRefreshResponse)
def diagnostics(db: Session = Depends(get_db)) -> NewsRefreshResponse:
    return NewsRefreshResponse.model_validate(news_service.latest_refresh_diagnostics(db))


@router.post("/refresh", response_model=NewsRefreshResponse)
def refresh_news(payload: NewsRefreshRequest | None = None, db: Session = Depends(get_db)) -> NewsRefreshResponse:
    request_payload = payload or NewsRefreshRequest()
    refreshed = news_service.refresh_latest_news(
        db,
        force_refresh=request_payload.force_refresh,
        backfill_hours=request_payload.backfill_hours,
        run_type="manual",
    )
    db.commit()
    if refreshed.get("articles_added", 0):
        publish_event("news.refreshed", {"article_id": refreshed.get("latest_article_id"), "articles_added": refreshed["articles_added"]})
    return NewsRefreshResponse.model_validate(refreshed)


@router.post("/refresh-demo")
def refresh_demo_news_alias(db: Session = Depends(get_db)) -> dict:
    return refresh_news(NewsRefreshRequest(force_refresh=True), db)
