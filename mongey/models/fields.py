import re
import inspect
from abc import ABC
from typing import Callable, Generic, Hashable, Protocol, Tuple, TypeVar, Type, Iterable, overload
from numbers import Real
from bson import ObjectId
from datetime import datetime
from dataclasses import dataclass
from ..errors import ValidationError
from ..types import TModel
from .index import IndexSpec, IndexOptions, IndexDirection
from .reference import OnDestroy, ModelReference

T = TypeVar("T")

TBaseFieldDescriptor = TypeVar(
    "TBaseFieldDescriptor",
    bound="BaseFieldDescriptor",
)


class BaseFieldDescriptor(Generic[T]):
    name: str = ""

    def __set__(self, obj: object, value: T | None) -> None:
        obj.__dict__[self.name] = value

    def __set_name__(self, owner: Type[object], name: str) -> None:
        self.name = name

    @overload
    def __get__(
        self: "TBaseFieldDescriptor[T]",
        obj: None,
        objtype: Type[object] | None = None
    ) -> "TBaseFieldDescriptor[T]": ...

    @overload
    def __get__(
        self: "TBaseFieldDescriptor[T]",
        obj: object,
        objtype: Type[object] | None = None
    ) -> T | None: ...

    def __get__(
        self: "TBaseFieldDescriptor[T]",
        obj: object | None,
        objtype: Type[object] | None = None
    ) -> T | None | "TBaseFieldDescriptor[T]":
        if obj is None:
            return self
        return obj.__dict__[self.name]


class FieldProto(Protocol):
    rejected: bool
    restricted: bool
    index: IndexSpec | None
    index_options: IndexOptions

    def set_default(self, obj: object) -> None: ...
    async def validate(self, obj: object) -> None: ...


IndexInput = bool | IndexSpec | None


class Field(BaseFieldDescriptor[T]):

    required: bool
    rejected: bool
    restricted: bool
    index: IndexSpec | None
    index_options: IndexOptions
    choices: set[T] | None
    def_value: T | Callable[[], T] | None

    __explicit_types__: Iterable[Type] = []

    def __init__(
        self,
        *,
        required: bool = False,
        rejected: bool = False,
        restricted: bool = False,
        default: T | Callable[[], T] | None = None,
        index: IndexInput | None = None,
        unique: bool = False,
        choices: Iterable[T] | None = None,
    ) -> None:
        self.required = required
        self.rejected = rejected
        self.restricted = restricted
        if choices:
            self.choices = set(choices)
        else:
            self.choices = None
        self.def_value = default
        self.index, self.index_options = self.__generate_index(index, unique)

    def set_default(self, obj: object) -> None:
        value = self.def_value
        if callable(value):
            value = value()
        setattr(obj, self.name, value)

    @staticmethod
    def __generate_index(
        index: IndexInput, unique: bool
    ) -> Tuple[IndexSpec | None, IndexOptions]:
        options = IndexOptions()
        if unique:
            if not isinstance(index, IndexSpec):
                index = IndexDirection.ASCENDING
            options["unique"] = True

        if not isinstance(index, IndexDirection):
            if index:
                index = IndexDirection.ASCENDING
            else:
                index = None

        return index, options

    def set_name(self, name: str) -> None:
        self.name = name

    async def validate(self, obj: object) -> None:
        value = self.__get__(obj)
        if self.required and value is None:
            raise ValidationError(f"field {self.name} is required")

        if value is not None and self.__explicit_types__:
            if not any([isinstance(value, _type) for _type in self.__explicit_types__]):
                type_names = [x.__name__ for x in self.__explicit_types__]
                raise ValidationError(f"field {self.name} must be any of {type_names}")

        if self.choices and value not in self.choices:
            if value is None:
                # at this point the value can be None only if it's not required
                # thus, if it's not required, it's ok to be None even if choices are defined
                return

            raise ValidationError(f"field {self.name} must be one of {self.choices}")


class ObjectIdField(Field[ObjectId]):
    pass


class ReferenceField(ObjectIdField, Generic[TModel]):

    on_destroy: OnDestroy

    _reference_model: Type[TModel]

    def register_ref(self, owner: Type[object], name: str) -> None:
        if not inspect.isabstract(owner) and ABC not in owner.__bases__:
            self._reference_model.add_ref(
                ModelReference(ref_class=owner, ref_field=name, on_destroy=self.on_destroy)
            )

    def __init__(
        self,
        *,
        reference_model: Type[TModel],
        required: bool = False,
        rejected: bool = False,
        restricted: bool = False,
        default: str | Callable[[], str] | None = None,
        index: IndexInput | None = True,
        unique: bool = False,
        on_destroy: OnDestroy = OnDestroy.RAISE,
    ) -> None:
        if on_destroy == OnDestroy.DETACH and required:
            raise RuntimeError("cannot auto-detach a required reference")
        super().__init__(
            required=required,
            rejected=rejected,
            restricted=restricted,
            index=index,
            default=default,
            unique=unique,
        )
        self.on_destroy = on_destroy
        self._reference_model = reference_model

    async def validate(self, obj: object) -> None:
        await super().validate(obj)
        value = self.__get__(obj)
        if value is None:
            return
        ref = await self._reference_model.get(value)
        if ref is None:
            raise ValidationError(
                f"Broken reference {self.name}: no {self._reference_model.__name__} found"
            )


class SelfReferenceField(ReferenceField):

    def register_ref(self, owner: Type[object], name: str) -> None:
        if not inspect.isabstract(owner) and ABC not in owner.__bases__:
            self._reference_model = owner
            self._reference_model.add_ref(
                ModelReference(ref_class=owner, ref_field=name, on_destroy=self.on_destroy)
            )

    def __init__(
        self,
        *,
        required: bool = False,
        rejected: bool = False,
        restricted: bool = False,
        default: str | Callable[[], str] | None = None,
        index: IndexInput | None = True,
        unique: bool = False,
        on_destroy: OnDestroy = OnDestroy.RAISE,
    ) -> None:
        if on_destroy == OnDestroy.DETACH and required:
            raise RuntimeError("cannot auto-detach a required reference")
        super().__init__(
            required=required,
            rejected=rejected,
            restricted=restricted,
            index=index,
            default=default,
            unique=unique,
            reference_model=None,
        )
        self.on_destroy = on_destroy


class StringField(Field[str]):

    min_length: int | None
    max_length: int | None
    re_match: re.Pattern[str] | None
    auto_trim: bool

    __explicit_types__ = [str]

    def __init__(
        self,
        *,
        min_length: int | None = None,
        max_length: int | None = None,
        re_match: str | None = None,
        auto_trim: bool = True,
        required: bool = False,
        rejected: bool = False,
        restricted: bool = False,
        default: str | Callable[[], str] | None = None,
        index: IndexInput | None = None,
        unique: bool = False,
        choices: Iterable[str] | None = None,
    ) -> None:
        super().__init__(
            required=required,
            rejected=rejected,
            restricted=restricted,
            default=default,
            index=index,
            unique=unique,
            choices=choices,
        )

        self.auto_trim = auto_trim
        self.min_length = min_length
        self.max_length = max_length
        if re_match:
            self.re_match = re.compile(re_match)
        else:
            self.re_match = None

    def __set__(self, obj: object, value: str | None) -> None:
        # user can accidentally put something other than string to a string field
        # we must allow him to do that and only complain at validation
        # thus the hasattr check
        if hasattr(value, "strip") and self.auto_trim:
            value = value.strip()
        return super().__set__(obj, value)

    async def validate(self, obj: object) -> None:
        await super().validate(obj)
        value = self.__get__(obj)
        if value is None:
            return
        min_length = self.min_length
        if min_length is not None and len(value) < min_length:
            raise ValidationError(
                f"field {self.name} must be at least {self.min_length} characters long"
            )

        max_length = self.max_length
        if max_length is not None and len(value) > max_length:
            raise ValidationError(
                f"field {self.name} must be at most {self.max_length} characters long"
            )

        re_match = self.re_match
        if re_match is not None and not re_match.match(value):
            raise ValidationError(
                f'field {self.name} must match pattern "{re_match.pattern}"'
            )


TNumber = TypeVar("TNumber", bound=Real)


class NumberField(Field[TNumber]):

    min_value: TNumber | None
    max_value: TNumber | None

    __explicit_types__ = [int, float]

    def __init__(
        self,
        *,
        min_value: TNumber | None = None,
        max_value: TNumber | None = None,
        required: bool = False,
        rejected: bool = False,
        restricted: bool = False,
        default: TNumber | Callable[[], TNumber] | None = None,
        index: IndexInput | None = None,
        unique: bool = False,
        choices: Iterable[TNumber] | None = None,
    ) -> None:
        super().__init__(
            required=required,
            rejected=rejected,
            restricted=restricted,
            default=default,
            index=index,
            unique=unique,
            choices=choices,
        )
        self.min_value = min_value
        self.max_value = max_value

    async def validate(self, obj: object) -> None:
        await super().validate(obj)
        value = self.__get__(obj)
        if value is None:
            return
        min_value = self.min_value
        max_value = self.max_value
        if min_value is not None and value < min_value:
            raise ValidationError(f"field {self.name} must be >= {min_value}")
        if max_value is not None and value > max_value:
            raise ValidationError(f"field {self.name} must be <= {max_value}")


class IntField(NumberField[int]):
    __explicit_types__ = [int]


class FloatField(NumberField[float]):
    __explicit_types__ = [float]


class ListField(Generic[T], Field[list[T]]):

    min_length: int | None

    __explicit_types__ = [list, set, tuple]

    def __init__(
        self,
        min_length: int | None = None,
        max_length: int | None = None,
        required: bool = False,
        rejected: bool = False,
        restricted: bool = False,
        default: Callable[[], list[T]] | None = None,
        index: IndexInput | None = None,
    ) -> None:
        super().__init__(
            required=required,
            rejected=rejected,
            restricted=restricted,
            default=default,
            index=index,
            unique=False,
            choices=None,
        )
        if min_length is not None:
            assert isinstance(min_length, int)
        if max_length is not None:
            assert isinstance(max_length, int)
        self.min_length = min_length
        self.max_length = max_length

    async def validate(self, obj: object) -> None:
        await super().validate(obj)
        value = self.__get__(obj)
        if value is None:
            return
        min_length = self.min_length
        max_length = self.max_length
        if min_length is not None and len(value) < min_length:
            raise ValidationError(
                f"field {self.name} must be at least {min_length} items long"
            )

        if max_length is not None and len(value) > max_length:
            raise ValidationError(
                f"field {self.name} must be at most {self.max_length} items long"
            )


class DatetimeField(Field[datetime]):
    __explicit_types__ = [datetime]


K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class DictField(Field[dict[K, V]]):

    __explicit_types__ = [dict]

    def __init__(
        self,
        required: bool = False,
        rejected: bool = False,
        restricted: bool = False,
        default: Callable[[], dict[K, V]] | None = None,
        index: IndexInput | None = None,
    ) -> None:
        super().__init__(
            required=required,
            rejected=rejected,
            restricted=restricted,
            default=default,
            index=index,
            unique=False,
            choices=None,
        )


class BoolField(Field[bool]):
    __explicit_types__ = [bool]


@dataclass
class ComputedField:
    is_async: bool
