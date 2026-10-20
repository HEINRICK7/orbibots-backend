from contextlib import contextmanager
from typing import Any, ContextManager, Iterator

from sqlalchemy.orm import Session

from app.src.application.gateways.transactions import UnitOfWork


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:
        self._session = session

    def transaction(self) -> ContextManager[Any]:
        @contextmanager
        def begin() -> Iterator[None]:
            if not self._session.in_transaction():
                with self._session.begin():
                    yield
                return

            nested = self._session.begin_nested()
            try:
                yield
                nested.commit()
            except Exception:
                nested.rollback()
                raise
            else:
                self._session.commit()

        return begin()
