from collections.abc import Iterator

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker


class DatabaseSessionDependency:
    def __call__(self, request: Request) -> Iterator[Session]:
        session_factory: sessionmaker[Session] | None = (
            request.app.state.session_factory
        )
        if session_factory is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is not configured.",
            )
        with session_factory() as session:
            yield session


database_session_dependency = DatabaseSessionDependency()
