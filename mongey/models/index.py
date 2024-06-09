import enum
import pymongo.collation
from typing import Iterable, NamedTuple, Type, TypeVar, TypedDict


class IndexDirection(int, enum.Enum):
    ASCENDING = pymongo.ASCENDING
    DESCENDING = pymongo.DESCENDING

    def __str__(self) -> str:
        """This is necessary to unbreak pymongo.helpers._gen_index_name"""
        return str(self.value)


class IndexType(str, enum.Enum):
    GEO2D = pymongo.GEO2D
    GEOSPHERE = pymongo.GEOSPHERE
    HASHED = pymongo.HASHED
    TEXT = pymongo.TEXT

    def __str__(self) -> str:
        """This is necessary to unbreak pymongo.helpers._gen_index_name"""
        return str(self.value)


IndexSpec = IndexDirection | IndexType


class IndexKey(NamedTuple):
    key: str
    spec: IndexSpec


class IndexOptions(TypedDict, total=False):
    """NB: This is not a full list of possible options
    See https://www.mongodb.com/docs/manual/reference/command/createIndexes/
    """
    name: str
    unique: bool
    background: bool
    sparse: bool
    bucketSize: int
    bits: int
    min: float
    max: float
    expireAfterSeconds: int
    collation: pymongo.collation.Collation


class _Index(NamedTuple):
    keys: Iterable[IndexKey]
    options: IndexOptions


TIndex = TypeVar("TIndex", bound=_Index)


# This is to apply default value generator, impossible directly in NamedTuple
class Index(_Index):
    def __new__(
        cls: Type[TIndex],
        keys: Iterable[IndexKey],
        options: IndexOptions | None = None
    ) -> TIndex:
        if options is None:
            options = IndexOptions()
        return super().__new__(cls, keys, options)
