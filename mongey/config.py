from typing import TypedDict, Dict, Any
from mongey.types import CacheEngineName


class ShardConfig(TypedDict):
    uri: str
    kwargs: Dict[str, Any]


class DatabaseConfig(TypedDict):
    meta: ShardConfig
    shards: Dict[str, ShardConfig]


class CacheConfig(TypedDict):
    l1: CacheEngineName
    l2: CacheEngineName
