from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Watchlist
from app.schemas.market import WatchlistRead

router = APIRouter()


class WatchlistCreate(BaseModel):
    name: str
    description: str | None = None
    is_default: bool = False


@router.get("/", response_model=list[WatchlistRead])
def list_watchlists(db: Session = Depends(get_db)) -> list[WatchlistRead]:
    return [WatchlistRead.model_validate(item) for item in db.scalars(select(Watchlist).order_by(Watchlist.name))]


@router.post("/", response_model=WatchlistRead)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db)) -> WatchlistRead:
    watchlist = Watchlist(name=payload.name, description=payload.description, is_default=payload.is_default)
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    return WatchlistRead.model_validate(watchlist)
