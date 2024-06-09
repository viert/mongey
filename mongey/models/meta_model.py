import inspect
from typing import Optional, Sequence
from .fields import Field, FieldProto, ComputedField
from .index import Index, IndexKey, IndexDirection
from .reference import ModelReference


def snake_case(name: str) -> str:
    result = ""
    for i, l in enumerate(name):
        if 65 <= ord(l) <= 90:
            if i != 0:
                result += "_"
            result += l.lower()
        else:
            result += l
    return result


class MetaModel:

    _fields: dict[str, FieldProto]
    # every write to computed_fields is preceded by copying, so it's
    # all right to have a mutable initializer here
    computed_fields: dict[str, ComputedField] = {}
    _cached_methods: set[str] = None
    _indexes: Sequence[Index]
    _cache_key_fields: set[str]
    _references: set[ModelReference] = None

    collection: str

    # You will usually need INDEXES only for defining compound ones, as
    # simple single-field indexes including "unique" have a shortcut arg
    # in a field definition, i.e.
    #
    # username = StringField(unique=True)
    # owner_id = ReferenceField(index=True)
    INDEXES: Sequence[Index] | None = None

    COLLECTION: str = ""
    KEY_FIELD: str = "id"
    CACHE_KEY_FIELDS: Optional[Sequence[str]] = None

    def __init_subclass__(cls) -> None:
        cls._fields = {
            name: obj
            for name, obj in inspect.getmembers(cls)
            if isinstance(obj, Field)
        }

        for field_name, field in cls._fields.items():
            # register ReferenceFields
            if hasattr(field, "register_ref"):
                field.register_ref(cls, field_name)

        cls._indexes = cls.__get_indexes()
        cls._cache_key_fields = cls.__get_cache_key_fields()

        if not cls._cached_methods:
            cls._cached_methods = set()

        if not cls._references:
            cls._references = set()

        cls.collection = cls.COLLECTION if cls.COLLECTION else snake_case(cls.__name__)  # TODO: Remove one of the two

    @classmethod
    def add_ref(cls, ref: ModelReference):
        cls._references.add(ref)

    @classmethod
    def __get_indexes(cls) -> Sequence[Index]:
        if cls.KEY_FIELD != "id":
            yield Index(
                keys=[
                    IndexKey(key=cls.KEY_FIELD, spec=IndexDirection.ASCENDING)
                ],
                options={"unique": True}
            )

        for field, descriptor in cls._fields.items():
            if descriptor.index is None:
                continue
            yield Index(
                keys=[IndexKey(key=field, spec=descriptor.index)],
                options=descriptor.index_options,
            )

        seen = set()
        for base in reversed(inspect.getmro(cls)):
            if not issubclass(base, MetaModel):
                continue
            if id(base.INDEXES) not in seen and base.INDEXES:
                seen.add(id(base.INDEXES))
                yield from base.INDEXES

    @classmethod
    def __get_cache_key_fields(cls) -> set[str]:
        cache_fields = set()
        for base in inspect.getmro(cls):
            if not issubclass(base, MetaModel):
                continue

            key_field = base.KEY_FIELD

            # _id field renaming. cache operates model props, not mongodb fields
            if key_field == "_id":
                key_field = "id"
            cache_fields.add(key_field)
            if base.CACHE_KEY_FIELDS:
                cache_fields.update(base.CACHE_KEY_FIELDS)
        return cache_fields
