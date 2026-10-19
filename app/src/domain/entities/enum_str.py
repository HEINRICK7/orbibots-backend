from enum import Enum


class EnumStr(str, Enum):
    """String enum whose string form is its persisted or public value."""

    def __str__(self) -> str:
        return self.value
