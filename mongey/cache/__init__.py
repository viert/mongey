from typing import Dict, Type
from .abc import AbstractCache
from .nocache import NoCache
from .simple import SimpleCache
from .request_local import RequestLocalCache
from .memcached import MemcachedCache
from .trace import TraceCache
from ..types import TCache


CACHE_ENGINE_MAP: Dict[str, Type[TCache]] = {
    "no_cache": NoCache,
    "simple": SimpleCache,
    "request_local": RequestLocalCache,
    "memcached": MemcachedCache,
    "trace": TraceCache
}
