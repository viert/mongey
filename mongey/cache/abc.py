from typing import Optional, Any, TypeVar
from abc import ABC, abstractmethod


class AbstractCache(ABC):

    NAME: str

    @abstractmethod
    async def initialise(self) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]: ...

    @abstractmethod
    async def set(self, key: str, value: Any) -> None: ...

    @abstractmethod
    async def has(self, key: str) -> bool: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...
