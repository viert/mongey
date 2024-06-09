import logging
from typing import Dict, Any, Optional
from unittest import IsolatedAsyncioTestCase
from contextvars import ContextVar, Token
from ..context import ctx
from ..config import DatabaseConfig
from ..cache import TraceCache, RequestLocalCache


custom_cache_ctxvar: ContextVar[Optional[Dict[str, Any]]] = ContextVar("request_cache_test", default=None)


class MongoMockTest(IsolatedAsyncioTestCase):

    token: Optional[Token[Dict[str, Any]]] = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        from ..config import DatabaseConfig
        cfg: DatabaseConfig = {
            "meta": {
                "uri": "mongodb://127,0,0,1:27017/test",
                "kwargs": {}
            },
            "shards": {}
        }
        ctx.setup_logging(level=logging.INFO)
        ctx.db.configure(cfg, mock=True)

        # aiomcache conflicts with async tests as it seems to run
        # in its own async loop. This leads to "got Future attached to a different loop"
        # errors.
        #
        # Since mongo tests do not use memcached explicitly we override
        # all caches to avoid using MemcachedCache
        #
        # RequestLocalCache is created using a custom contextvar so that
        # L2 Cache resets after each test rather than after each request
        #
        # TraceCache does not store any data but is able to track its methods calls
        ctx._l1_cache = TraceCache()
        ctx._l2_cache = RequestLocalCache(custom_cache_ctxvar)

    async def asyncSetUp(self) -> None:
        self.token = custom_cache_ctxvar.set({})

    async def asyncTearDown(self) -> None:
        custom_cache_ctxvar.reset(self.token)
        self.token = None

