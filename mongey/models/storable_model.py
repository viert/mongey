from typing import Coroutine, Dict, Any, Tuple, Optional, Type, List, Callable
from functools import partial
from time import time
from motor.motor_asyncio import AsyncIOMotorCursor
from bson.objectid import ObjectId
from .base_model import BaseModel, TPydanticModel
from ..db import ObjectsCursor, Shard
from ..errors import ModelDestroyed
from ..util import resolve_id
from ..decorators import save_required
from ..context import ctx
from ..types import TModel


class StorableModel(BaseModel):

    @staticmethod
    def _db() -> Shard:
        return ctx.db.meta

    async def _save_to_db(self) -> None:
        await self._db().save_obj(self)

    async def update(self: TModel,
                     data: Dict[str, Any],
                     *,
                     skip_callback: bool = False,
                     invalidate_cache: bool = True) -> TModel:
        for field, descriptor in self._fields.items():
            if (
                field in data
                and not descriptor.rejected
                and field != "_id"
            ):
                self.__dict__[field] = data[field]
        return await self.save(skip_callback=skip_callback, invalidate_cache=invalidate_cache)

    async def update_from_pydantic(self: TModel,
                                   data: TPydanticModel,
                                   *,
                                   skip_callback: bool = False,
                                   invalidate_cache: bool = True) -> TModel:
        return await self.update(
            data.model_dump(exclude_unset=True),
            skip_callback=skip_callback,
            invalidate_cache=invalidate_cache
        )

    @save_required
    async def db_update(self,
                        update: Dict[str, Any],
                        when: Optional[Dict[str, Any]] = None,
                        *,
                        reload: bool = True,
                        invalidate_cache: bool = True) -> bool:
        """
        :param update: MongoDB update query
        :param when: filter query. No update will happen if it does not match
        :param reload: Load the new stat into the object (Caution: if you do not do this
                        the next save() will overwrite updated fields)
        :param invalidate_cache: whether to run cache invalidation for the model if the model is changed
        :return: True if the document was updated. Otherwise - False
        """
        new_data = await self._db().find_and_update_obj(self, update, when)
        if invalidate_cache and new_data:
            await self.invalidate()

        if reload and new_data:
            tmp = self.__class__(new_data)
            self._reload_from_model(tmp)

        return bool(new_data)

    async def _delete_from_db(self) -> None:
        await self._db().delete_obj(self)

    async def _refetch_from_db(self: TModel) -> Optional[TModel]:
        return await self.find_one({"_id": self.id})

    async def reload(self) -> None:
        if self.is_new:
            return
        tmp = await self._refetch_from_db()
        if tmp is None:
            raise ModelDestroyed("model has been deleted from db")
        self._reload_from_model(tmp)

    @classmethod
    def _preprocess_query(cls, query: Dict[str, Any]) -> Dict[str, Any]:
        return query


    @classmethod
    def find(cls: Type[TModel],
             query: Optional[Dict[str, Any]] = None,
             **kwargs: Dict[str, Any]) -> ObjectsCursor[TModel]:
        if not query:
            query = {}
        return cls._db().get_objs(
            cls._ctor, cls.collection, cls._preprocess_query(query), **kwargs
        )

    @classmethod
    def aggregate(cls,
                  pipeline: List[Dict[str, Any]],
                  query: Optional[Dict[str, Any]] = None,
                  **kwargs: Dict[str, Any]) -> AsyncIOMotorCursor:
        if not query:
            query = {}
        pipeline = [{"$match": cls._preprocess_query(query)}] + pipeline
        return cls._db().get_aggregated(cls.collection, pipeline, **kwargs)

    @classmethod
    def find_projected(cls,
                       query: Optional[Dict[str, Any]] = None,
                       projection: Tuple[str] = ("_id",),
                       **kwargs: Dict[str, Any]) -> AsyncIOMotorCursor:
        if not query:
            query = {}
        return cls._db().get_objs_projected(
            cls.collection,
            cls._preprocess_query(query),
            projection=projection,
            **kwargs,
        )
    
    @classmethod
    async def find_ids(cls,
                       query: Optional[Dict[str, Any]] = None,
                       max_count: Optional[int] = None,
                       **kwargs: Dict[str, Any]) -> List[ObjectId]:
        objs = await cls.find_projected(query, **kwargs).to_list(max_count)
        return [obj["_id"] for obj in objs]

    @classmethod
    async def find_one(cls: Type[TModel], query: Dict[str, Any], **kwargs: Dict[str, Any]) -> Optional[TModel]:
        return await cls._db().get_obj(
            cls._ctor, cls.collection, cls._preprocess_query(query), **kwargs
        )

    @classmethod
    async def all(cls: Type[TModel], query: Optional[Dict[str, Any]] = None, **kwargs: Dict[str, Any]) -> List[TModel]:
        if query is None:
            query = {}
        return await cls.find(query, **kwargs).all()

    @classmethod
    def _default_get_query(cls, expr: str) -> Dict[str, Any]:
        return {cls.KEY_FIELD: expr}

    @classmethod
    def _resolve_get_query(cls, expression: str | ObjectId | None) -> Optional[Dict[str, Any]]:
        if expression is None:
            return None

        resolved_expr = resolve_id(expression)
        if isinstance(resolved_expr, ObjectId):
            return {"_id": resolved_expr}

        return cls._default_get_query(resolved_expr)

    @classmethod
    async def get(cls: Type[TModel],
                  expression: str | ObjectId | None,
                  raise_if_none: Optional[Exception] = None, **kwargs) -> Optional[TModel]:
        query = cls._resolve_get_query(expression)
        if query is None:
            if raise_if_none:
                raise raise_if_none
            return None

        res = await cls.find_one(query)
        if res is None and raise_if_none is not None:
            raise raise_if_none
        return res

    @classmethod
    async def count(cls, query: Optional[Dict[str, Any]] = None) -> int:
        if query is None:
            query = {}
        return await cls._db().count_docs(cls.collection, query)

    @classmethod
    async def destroy_all(cls) -> None:
        await cls._db().delete_query(cls.collection, cls._preprocess_query({}))

    @classmethod
    async def destroy_many(cls, query: Dict[str, Any], invalidate: bool = True) -> None:
        # warning: being a faster method than traditional model manipulation,
        # this method doesn't provide any lifecycle callback for independent
        # objects
        await cls.invalidate_many(query)
        await cls._db().delete_query(cls.collection, cls._preprocess_query(query))

    @classmethod
    async def update_many(cls, query: Dict[str, Any], attrs: Dict[str, Any], invalidate: bool = True) -> None:
        # warning: being a faster method than traditional model manipulation,
        # this method doesn't provide any lifecycle callback for independent
        # objects
        await cls.invalidate_many(query)
        await cls._db().update_query(cls.collection, cls._preprocess_query(query), attrs)

    @classmethod
    async def cache_get(cls: Type[TModel],
                        expression: str | None,
                        raise_if_none: Optional[Exception] = None) -> Optional[TModel]:
        if expression is None:
            if raise_if_none:
                raise raise_if_none
            return None
        cache_key = f"{cls.collection}.{expression}"
        getter = partial(cls.get, expression, raise_if_none)
        return await cls._cache_get(cache_key, getter)

    @classmethod
    async def _cache_get(cls: Type[TModel],
                         cache_key: str,
                         getter: partial[Coroutine[None, None, TModel | None]],
                         ctor: Optional[Callable[..., TModel]] = None) -> Optional[TModel]:
        t1 = time()
        if not ctor:
            ctor = cls

        if await ctx.l1_cache.has(cache_key):
            data = await ctx.l1_cache.get(cache_key)
            td = time() - t1
            ctx.log.debug(
                "%s L1 hit %s %.3f secs", ctx.l1_cache.__class__.__name__, cache_key, td
            )
            return ctor(data)

        if await ctx.l2_cache.has(cache_key):
            data = await ctx.l2_cache.get(cache_key)
            await ctx.l1_cache.set(cache_key, data)
            td = time() - t1
            ctx.log.debug(
                "%s L2 hit %s %.3f secs", ctx.l2_cache.NAME, cache_key, td
            )
            return ctor(data)

        obj: Optional[TModel] = await getter()
        if obj:
            data = obj.to_dict(include_restricted=True, convert_id=True)
            await ctx.l2_cache.set(cache_key, data)
            await ctx.l1_cache.set(cache_key, data)

        td = time() - t1
        ctx.log.debug("%s miss %s %.3f secs", ctx.l2_cache.NAME, cache_key, td)
        return obj

    async def invalidate(self, **kwargs: Dict[str, Any]) -> None:
        for field in self._cache_key_fields:
            value = self._initial_state.get(field)
            if value is not None:
                cache_key = f"{self.collection}.{value}"
                await self._invalidate(cache_key)
        if not self.is_new:
            for method in self._cached_methods:
                cache_key = f"{self.collection}.{self.id}.{method}"
                await self._invalidate(cache_key)

    @classmethod
    async def invalidate_many(cls, query: Dict[str, Any],):
        models = await cls.find(query).all()
        for model in models:
            for field in cls._cache_key_fields:
                value = getattr(model, field)
                if value is not None:
                    cache_key = f"{cls.collection}.{value}"
                    await cls._invalidate(cache_key)
            for method in cls._cached_methods:
                cache_key = f"{cls.collection}.{model.id}.{method}"
                await cls._invalidate(cache_key)

    @staticmethod
    async def _invalidate(cache_key: str) -> None:
        if await ctx.l1_cache.delete(cache_key):
            ctx.log.debug("%s delete %s", ctx.l1_cache.NAME, cache_key)
        if await ctx.l2_cache.delete(cache_key):
            ctx.log.debug("%s delete %s", ctx.l2_cache.NAME, cache_key)
