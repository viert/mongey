import pymongo
from bson.objectid import ObjectId, InvalidId
from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorCursor
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.results import DeleteResult, UpdateResult
from pymongo.errors import ServerSelectionTimeoutError
from mongomock_motor import (
    AsyncMongoMockClient,
    AsyncMongoMockDatabase,
    AsyncCursor
)
from typing import (
    Generic,
    Callable,
    Optional,
    List,
    Type,
    AsyncIterator,
    Any,
    Dict,
    Sequence,
    Union,
    Mapping,
    Tuple,
)
from time import sleep
from datetime import datetime
from mongey.context import ctx
from mongey.config import DatabaseConfig, ShardConfig
from mongey.errors import ConfigurationError
from mongey.types import TModel, RT

MONGO_RETRY_MAX: int = 6
MONGO_RETRY_SLEEP: int = 3


QueryType = Dict[str, Any]
QueryExpression = QueryType | str


def intercept_pymongo_errors(func: Callable[..., RT]) -> Callable[..., RT]:
    def wrapper(self: "Shard", *args: List[Any], **kwargs: Dict[str, Any]) -> RT:
        retries = MONGO_RETRY_MAX
        while True:
            retries -= 1
            try:
                return func(self, *args, **kwargs)
            except ServerSelectionTimeoutError:
                ctx.log.error(
                    "ServerSelectionTimeoutError in db module, retries left = %d",
                    retries,
                )
                if retries == MONGO_RETRY_MAX // 2:
                    ctx.log.error("trying to reinstantiate connection")
                    db_inst = self
                    db_inst.reset_conn()
                elif retries == 0:
                    ctx.log.error(
                        "ServerSelectionTimeoutError max retries exceeded, giving up"
                    )
                    raise
                sleep(MONGO_RETRY_SLEEP)

    return wrapper


class ObjectsCursor(Generic[TModel], AsyncIterator[TModel]):
    cursor: Union[AsyncIOMotorCursor, AsyncCursor]

    def __init__(self, cursor: Union[AsyncIOMotorCursor, AsyncCursor], ctor: Type[TModel], query: QueryType,
                 shard_id: Optional[str] = None) -> None:
        self.ctor = ctor
        self.cursor = cursor
        self.stored_query = query
        self._shard_id = shard_id

    async def all(self, max_length: Optional[int] = None) -> List[TModel]:
        return [self.ctor(x) for x in await self.cursor.to_list(max_length)]

    async def as_map(self, max_length: Optional[int] = None) -> Dict[ObjectId, TModel]:
        items = await self.all(max_length)
        item_map = {}
        for item in items:
            item_map[item.id] = item
        return item_map

    async def all_dict(self,
                       max_length: Optional[int] = None,
                       fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        return [self.ctor(x).to_dict(fields=fields) for x in await self.cursor.to_list(max_length)]

    def limit(self, limit: int) -> "ObjectsCursor[TModel]":
        self.cursor.limit(limit)
        return self

    def skip(self, skip: int) -> "ObjectsCursor[TModel]":
        self.cursor.skip(skip)
        return self

    def sort(self, key_or_list: Union[str, Sequence[Tuple[str, Union[int, str, Mapping[str, Any]]]]],
             direction: Optional[Union[int, str]] = None) -> "ObjectsCursor[TModel]":
        if isinstance(key_or_list, str) and direction is None:
            direction = pymongo.ASCENDING
        self.cursor.sort(key_or_list, direction)
        return self

    async def count(self) -> int:
        # usually self.ctor contains a classmethod `ctor` of a StorableModel
        # hence this hack
        ctor = self.ctor.__self__
        return await ctor.count(self.stored_query)

    def __aiter__(self) -> AsyncIterator["TModel"]:
        return self

    async def __anext__(self) -> "TModel":
        item = await self.cursor.__anext__()
        if self._shard_id:
            return self.ctor(shard_id=self._shard_id, attrs=item)
        else:
            return self.ctor(attrs=item)

    def __getattr__(self, item: str) -> Any:
        return getattr(self.cursor, item)


class Shard:
    _config: ShardConfig
    _client: Optional[Union[AsyncIOMotorClient, AsyncMongoMockClient]]
    _conn: Optional[Union[AsyncIOMotorDatabase, AsyncMongoMockDatabase]]
    _mock: bool

    def __init__(self, config: ShardConfig, mock: bool = False) -> None:
        self._config = config
        self._client = None
        self._conn = None
        self._mock = mock

    def get_client(self) -> Union[AsyncIOMotorClient, AsyncMongoMockClient]:
        if not self._client:
            if self._mock:
                self._client = AsyncMongoMockClient(self._config["uri"])
            else:
                self._client = AsyncIOMotorClient(self._config["uri"])
        return self._client

    def reset_conn(self) -> None:
        self._client = None
        self._conn = None

    def init_conn(self) -> None:
        if not self._mock:
            ctx.log.info("creating a new mongo connection")
        client = self.get_client()
        self._conn = client.get_database()

    @property
    def conn(self) -> Union[AsyncIOMotorDatabase, AsyncMongoMockDatabase]:
        if self._conn is None:
            self.init_conn()
        return self._conn

    @intercept_pymongo_errors
    async def get_obj(self,
                      ctor: Callable[..., "TModel"],
                      collection: str,
                      query: QueryExpression) -> Optional["TModel"]:
        if not isinstance(query, dict):
            try:
                query = {"_id": ObjectId(query)}
            except InvalidId:
                pass
        data = await self.conn[collection].find_one(query)
        if data:
            return ctor(attrs=data)

        return None

    @intercept_pymongo_errors
    async def get_obj_id(self, collection: str, query: QueryType) -> Optional[ObjectId]:
        obj = await self.conn[collection].find_one(
            query, projection=()
        )
        if obj:
            return obj["_id"]
        return None

    @intercept_pymongo_errors
    def get_objs(self,
                 ctor: Callable[..., "TModel"],
                 collection: str,
                 query: QueryType,
                 **kwargs: Dict[str, Any]) -> ObjectsCursor[TModel]:
        cursor = self.conn[collection].find(query, **kwargs)
        return ObjectsCursor(cursor, ctor, query)

    @intercept_pymongo_errors
    def get_objs_projected(
        self,
        collection: str,
        query: Dict[str, Any],
        projection: Dict[str, Any],
        **kwargs: Dict[str, Any]
    ) -> AsyncIOMotorCursor:
        cursor = self.conn[collection].find(query, projection=projection, **kwargs)
        return cursor

    @intercept_pymongo_errors
    def get_aggregated(
        self,
        collection: str,
        pipeline: List[Dict[str, Any]],
        **kwargs: Dict[str, Any]
    ) -> AsyncIOMotorCursor:
        cursor = self.conn[collection].aggregate(pipeline, **kwargs)
        return cursor

    @intercept_pymongo_errors
    async def count_docs(self, collection: str, query: Dict[str, Any], **kwargs: Dict[str, Any]) -> int:
        coll = self.conn[collection]
        if query == {}:
            return await coll.estimated_document_count(**kwargs)
        else:
            return await coll.count_documents(query, **kwargs)

    def get_objs_by_field_in(
        self,
        ctor: Type[TModel],
        collection: str,
        field: str,
        values: List[str],
        **kwargs: Dict[str, Any]
    ) -> ObjectsCursor[TModel]:
        return self.get_objs(ctor, collection, {field: {"$in": values}}, **kwargs)

    @intercept_pymongo_errors
    async def save_obj(self, obj: "TModel") -> None:
        if obj.is_new:
            # object to_dict() method should always return all fields
            data = obj.to_dict(include_restricted=True, convert_id=True)
            # although with the new object we shouldn"t pass _id=null to mongo
            del data["_id"]
            insert_result = await self.conn[obj.collection].insert_one(data)
            obj.id = insert_result.inserted_id
        else:
            await self.conn[obj.collection].replace_one(
                {"_id": obj.id},
                obj.to_dict(include_restricted=True, convert_id=True),
                upsert=True,
            )

    @intercept_pymongo_errors
    async def delete_obj(self, obj: "TModel") -> None:
        if obj.is_new:
            return
        await self.conn[obj.collection].delete_one({"_id": obj.id})

    @intercept_pymongo_errors
    async def find_and_update_obj(
        self,
        obj: "TModel",
        update: Dict[str, Any],
        when: Optional[Dict[str, Any]] = None
    ) -> None:
        query = {"_id": obj.id}
        if when:
            assert "_id" not in when
            query.update(when)

        new_data = await self.conn[obj.collection].find_one_and_update(
            query, update, return_document=ReturnDocument.AFTER
        )
        return new_data

    @intercept_pymongo_errors
    async def delete_query(self, collection: str, query: Dict[str, Any]) -> DeleteResult:
        return await self.conn[collection].delete_many(query)

    @intercept_pymongo_errors
    async def update_query(self, collection: str, query: Dict[str, Any], update: Dict[str, Any]) -> UpdateResult:
        return await self.conn[collection].update_many(query, update)

    # SESSIONS
    @intercept_pymongo_errors
    async def get_session(self, sid: str, collection: str = "sessions") -> Dict[str, Any]:
        return await self.conn[collection].find_one({"sid": sid})

    @intercept_pymongo_errors
    async def update_session(self, sid: str, data: Dict[str, Any], expiration: datetime,
                             collection: str = "sessions") -> None:
        await self.conn[collection].update_one(
            {"sid": sid}, {"$set": {"sid": sid, "data": data, "expiration": expiration}}, True
        )

    @intercept_pymongo_errors
    async def cleanup_sessions(self, collection: str = "sessions") -> int:
        result = await self.conn[collection].delete_one({"expiration": {"$lt": datetime.now()}})
        return result.deleted_count


class DB:
    MONGODB_INFO_FIELDS = (
        "allocator",
        "bits",
        "debug",
        "gitVersion",
        "javascriptEngine",
        "maxBsonObjectSize",
        "modules",
        "ok",
        "openssl",
        "storageEngines",
        "sysInfo",
        "version",
        "versionArray",
    )

    __meta: Optional[Shard]
    __shards: Dict[str, Shard]

    def __init__(self) -> None:
        self.__meta = None
        self.__shards = {}

    def configure(self, config: DatabaseConfig, mock: bool = False) -> None:
        self.__meta = Shard(config["meta"], mock=mock)
        self.__shards = {}
        for shard, shard_config in config["shards"].items():
            self.__shards[shard] = Shard(shard_config, mock)

    @property
    def meta(self) -> Shard:
        if self.__meta is None:
            raise ConfigurationError("attempt to access an uninitialized database, use db.configure(config)")
        return self.__meta

    def shard(self, shard_id: str) -> Shard:
        raise NotImplemented("sharding is not implemented yet")
