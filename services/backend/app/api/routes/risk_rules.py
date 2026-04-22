from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.risk import RiskRuleRead, RiskRuleUpsert, RiskValidationRequest, RiskValidationResponse
from app.services.risk.service import risk_service

router = APIRouter()


@router.get("/", response_model=list[RiskRuleRead])
def list_rules(db: Session = Depends(get_db)) -> list[RiskRuleRead]:
    return [RiskRuleRead.model_validate(rule) for rule in risk_service.list_rules(db)]


@router.post("/", response_model=RiskRuleRead)
def upsert_rule(payload: RiskRuleUpsert, db: Session = Depends(get_db)) -> RiskRuleRead:
    rule = risk_service.upsert_rule(db, payload)
    db.commit()
    db.refresh(rule)
    return RiskRuleRead.model_validate(rule)


@router.post("/validate-order", response_model=RiskValidationResponse)
def validate_order(payload: RiskValidationRequest, db: Session = Depends(get_db)) -> RiskValidationResponse:
    return risk_service.validate_order(db, payload)
