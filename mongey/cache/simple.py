from typing import Any, Optional, Dict
from .abc import AbstractCache

__static_cache__: Dict[str, Any] = {}


class SimpleCache(AbstractCache):

    NAME = "SimpleCache"

    async def initialise(self) -> None:
        from mongey.context import ctx
        ctx.log.warn("SimpleCache is not suitable for production, use with caution")

    async def get(self, key: str) -> Optional[Any]:
        return __static_cache__.get(key)

    async def set(self, key: str, value: Any) -> None:
        global __static_cache__
        __static_cache__[key] = value

    async def has(self, key: str) -> bool:
        return key in __static_cache__

    async def delete(self, key: str) -> None:
        if key in __static_cache__:
            del __static_cache__[key]
