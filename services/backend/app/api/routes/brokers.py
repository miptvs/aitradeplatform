from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.broker import BrokerAccountCreate, BrokerAccountRead, BrokerAdapterStatus
from app.services.brokers.service import broker_service

router = APIRouter()


@router.get("/adapters", response_model=list[BrokerAdapterStatus])
def adapters() -> list[BrokerAdapterStatus]:
    return [BrokerAdapterStatus.model_validate(item) for item in broker_service.list_adapter_statuses()]


@router.get("/accounts", response_model=list[BrokerAccountRead])
def accounts(db: Session = Depends(get_db)) -> list[BrokerAccountRead]:
    return [BrokerAccountRead.model_validate(broker_service.serialize_account(account)) for account in broker_service.list_accounts(db)]


@router.post("/accounts", response_model=BrokerAccountRead)
def upsert_account(payload: BrokerAccountCreate, db: Session = Depends(get_db)) -> BrokerAccountRead:
    account = broker_service.upsert_account(db, payload)
    db.commit()
    db.refresh(account)
    return BrokerAccountRead.model_validate(broker_service.serialize_account(account))


@router.post("/accounts/{account_id}/validate")
def validate_account(account_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        result = broker_service.validate_connection(db, account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result
