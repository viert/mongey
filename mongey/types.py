from typing import Type, TypeVar, TYPE_CHECKING, Literal
from pydantic import BaseModel as PydanticModel
if TYPE_CHECKING:
    from .models.storable_model import StorableModel
    from .models.base_model import BaseModel
    from .cache.abc import AbstractCache

TModel = TypeVar("TModel", bound="StorableModel")
TBaseModel = TypeVar("TBaseModel", bound="BaseModel")
TModelType = Type[TModel]
TPydanticModel = TypeVar("TPydanticModel", bound=PydanticModel)

CacheEngineName = Literal["no_cache", "simple", "request_local", "memcached", "trace"]
TCache = TypeVar("TCache", bound="AbstractCache")

T = TypeVar("T")  # any type
RT = TypeVar("RT")  # function return type
