from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.strategy import Strategy


class StrategyService:
    def list_strategies(self, db: Session) -> list[Strategy]:
        return list(db.scalars(select(Strategy).order_by(Strategy.name)))


strategy_service = StrategyService()
