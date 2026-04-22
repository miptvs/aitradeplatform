from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.market import AssetRead, AssetSearchResponse
from app.services.market_data.service import market_data_service

router = APIRouter()


@router.get("/", response_model=list[AssetRead])
def list_assets(db: Session = Depends(get_db)) -> list[AssetRead]:
    return [AssetRead.model_validate(asset) for asset in market_data_service.list_asset_views(db)]


@router.get("/search", response_model=AssetSearchResponse)
def search_assets(q: str = Query(min_length=1), db: Session = Depends(get_db)) -> AssetSearchResponse:
    return AssetSearchResponse.model_validate(market_data_service.search_assets(db, q))
