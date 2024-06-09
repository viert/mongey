from contextvars import ContextVar
from typing import Optional, Dict, Any
from .abc import AbstractCache

REQUEST_CACHE_CONTEXT_KEY = "request_cache"

req_cache_ctx: ContextVar[Optional[Dict[str, Any]]] = ContextVar(REQUEST_CACHE_CONTEXT_KEY, default=None)


class RequestLocalCache(AbstractCache):

    NAME = "RequestLocalCache"

    ctxvar: ContextVar[Optional[Dict[str, Any]]]

    def __init__(self, ctxvar: Optional[ContextVar[Optional[Dict[str, Any]]]] = None):
        self.ctxvar = req_cache_ctx if ctxvar is None else ctxvar

    async def initialise(self) -> None:
        pass

    async def get(self, key: str) -> Optional[Any]:
        cache = self.ctxvar.get()
        if cache is None:
            return None
        return cache.get(key)

    async def set(self, key: str, value: Any) -> None:
        cache = self.ctxvar.get()
        if cache is None:
            return None
        cache[key] = value
        self.ctxvar.set(cache)

    async def has(self, key: str) -> bool:
        cache = self.ctxvar.get()
        if cache is None:
            return False
        return key in cache

    async def delete(self, key: str) -> None:
        cache = self.ctxvar.get()
        if cache is None:
            return None
        if key in cache:
            del cache[key]
            self.ctxvar.set(cache)
