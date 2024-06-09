import asyncio
import functools
import binascii
import pickle
from typing import Optional, Any, List, Tuple

import aiomcache
from aiomcache import Client
from .abc import AbstractCache

MAX_RETRIES: int = 5


def pick_and_retry(func):

    @functools.wraps(func)
    async def wrapper(self, key, *args, **kwargs):
        retry = 0
        while True:
            backend, key = self._get_backend(key, retry)
            try:
                data = await func(self, backend, key, *args, **kwargs)
                return data
            except Exception:
                retry += 1
                if retry > MAX_RETRIES:
                    raise
    return wrapper


def server_hash_func(key):
    return (((binascii.crc32(key) & 0xffffffff) >> 16) & 0x7fff) or 1


class MemcachedCache(AbstractCache):

    NAME = "MemcachedCache"
    _backends: List[Client]

    def __init__(self, backends: List[str]) -> None:
        clients: List[Client] = []

        for backend in backends:
            chunks = backend.split(":")
            if len(chunks) == 1:
                port = 11211
            else:
                port = chunks[1]
            client = Client(
                chunks[0],
                port,
                pool_size=2,
                pool_minsize=None,
            )
            clients.append(client)

        self._backends = clients

    def _get_backend(self, key: str | Tuple, retry: int = 0) -> Tuple[Optional[Client], Optional[str]]:
        if not self._backends:
            return None, None

        if isinstance(key, tuple):
            serverhash, key = key
        else:
            serverhash = server_hash_func(key.encode("utf-8"))

        if retry > 0:
            serverhash = str(serverhash) + str(retry)
            serverhash = server_hash_func(serverhash.encode('utf-8'))

        server = self._backends[serverhash % len(self._backends)]
        return server, key

    async def has(self, key: str) -> bool:
        value = await self.get(key)
        return value is not None

    @pick_and_retry
    async def _set(self, backend: Client, key: str, value: Any) -> None:
        await backend.set(key.encode(), value)

    async def set(self, key: str, value: Any) -> None:
        value = pickle.dumps(value)
        try:
            await self._set(key, value)
        except aiomcache.ValidationException:
            pass

    @pick_and_retry
    async def _get(self, backend: Client, key: str) -> Optional[Any]:
        return await backend.get(key.encode("utf-8"))

    async def get(self, key: str) -> Optional[Any]:
        try:
            res = await self._get(key)
        except aiomcache.ValidationException:
            return None
        if res is not None:
            try:
                value = pickle.loads(res)
                return value
            except Exception:
                return None

    async def delete(self, key: str) -> bool:
        try:
            tasks = [backend.delete(key.encode("utf-8")) for backend in self._backends]
            results = await asyncio.gather(*tasks)
        except aiomcache.ValidationException:
            return False
        return any(results)

    async def initialise(self) -> None:
        return
