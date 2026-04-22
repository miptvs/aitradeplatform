from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.market import ExtractedEventRead
from app.services.news.service import news_service

router = APIRouter()


@router.get("/", response_model=list[ExtractedEventRead])
def list_events(db: Session = Depends(get_db)) -> list[ExtractedEventRead]:
    return [ExtractedEventRead.model_validate(item) for item in news_service.list_events(db)]
