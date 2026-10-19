from typing import Any, ContextManager

from sqlalchemy.orm import Session

from app.src.application.gateways.transactions import UnitOfWork


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:
        self._session = session

    def transaction(self) -> ContextManager[Any]:
        return self._session.begin()
