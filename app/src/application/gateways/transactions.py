from typing import Any, ContextManager, Protocol


class UnitOfWork(Protocol):
    def transaction(self) -> ContextManager[Any]: ...
