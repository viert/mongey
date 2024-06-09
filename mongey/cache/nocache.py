from typing import Any, Optional
from .abc import AbstractCache


class NoCache(AbstractCache):

    NAME = "NoCache"

    async def initialise(self) -> None:
        pass

    async def get(self, key: str) -> Optional[Any]:
        return None

    async def set(self, key: str, value: Any) -> None:
        pass

    async def has(self, key: str) -> bool:
        return False

    async def delete(self, key: str) -> None:
        pass
