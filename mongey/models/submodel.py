from typing import Optional, Dict, Any, TypeVar, Type
from bson import ObjectId
from .fields import StringField
from .storable_model import StorableModel
from ..errors import IntegrityError, MissingSubmodel, WrongSubmodel, UnknownSubmodel

TStorableSubmodel = TypeVar("TStorableSubmodel", bound="StorableSubmodel")
TStorableSubmodelType = Type[TStorableSubmodel]


class StorableSubmodel(StorableModel):
    """
    - Make the base class first. Set COLLECTION explicitly - it is not
      generated automatically from the class name but inherited instead.
    - Subclass your base class to define submodels. Set SUBMODEL to a string
      that will identify your submodel in the DB.
    - You can further subclass your submodels. To avoid saving such abstract
      intermediate models do not set SUBMODEL.
    - Register the submodel with the base model

    It is possible to register an arbitrary function instead of a proper class.
    It may be particularly useful if the correct class depends on something
    other than `submodel` field. The function will get **data from the DB and
    should return an model object.

    If you decide to do it you will likely have to override _preprocess_query()
    on your submodels to keep the expected find/destroy/update behaviour

    """

    SUBMODEL: Optional[str] = None

    submodel = StringField(required=True)

    __submodel_loaders__: Dict[str, TStorableSubmodelType] = None

    def __init__(self, attrs: Optional[Dict[str, Any]] = None, **_kwargs: Dict[str, Any]) -> None:
        if attrs is None:
            attrs = {}
        super().__init__(attrs)

        if self.is_new:
            if not self.SUBMODEL:
                raise IntegrityError(f"Attempted to create an object of abstract model {self.__class__.__name__}")
            if "submodel" in attrs:
                raise IntegrityError("Attempt to override submodel for a new object")
            self.submodel = self.SUBMODEL
        else:
            if not self.submodel:
                raise MissingSubmodel(f"{self.__class__.__name__} has no submodel in the DB. A bug?")
            self._check_submodel()

    def _check_submodel(self):
        if self.submodel != self.SUBMODEL:
            raise WrongSubmodel(f"Attempted to load {self.submodel} as"
                                f" {self.__class__.__name__}. Correct submodel"
                                f" would be {self.SUBMODEL}. A bug?")

    async def validate(self):
        await super().validate()
        self._check_submodel()

    @classmethod
    def register_submodel(cls, name: str, ctor: TStorableSubmodelType) -> None:
        """
        name arg is required to provide a way of registering constructor functions
        instead of model classes. While a submodel class has a SUBMODEL property, a
        function will unlikely have it.

        :param name: submodel name
        :param ctor: class or constructor function
        :return:
        """
        if cls.SUBMODEL:
            raise IntegrityError("Attempted to register submodel with another submodel")
        if not cls.__submodel_loaders__:
            cls.__submodel_loaders__ = {}
        if name in cls.__submodel_loaders__:
            raise IntegrityError(f"Submodel {name} already registered")
        cls.__submodel_loaders__[name] = ctor

    @classmethod
    def _preprocess_query(cls, query: Dict[str, Any]) -> Dict[str, Any]:
        if cls.SUBMODEL:
            query.update({"submodel": cls.SUBMODEL})
        return query

    @classmethod
    def _ctor(cls: TStorableSubmodelType, attrs: dict[str, Any] | None, **kwargs: Dict[str, Any]) -> TStorableSubmodel:
        if "submodel" not in attrs:
            raise MissingSubmodel(f"{cls.__name__} has no submodel in the DB. Bug?")
        if not cls.__submodel_loaders__:
            return cls(attrs, **kwargs)
        submodel_name = attrs["submodel"]
        if submodel_name not in cls.__submodel_loaders__:
            raise UnknownSubmodel(f"Submodel {submodel_name} is not registered with {cls.__name__}")
        return cls.__submodel_loaders__[submodel_name](attrs, **kwargs)

    @classmethod
    async def get(cls: TStorableSubmodelType,
                  expression: str | ObjectId | None,
                  raise_if_none: Optional[Exception] = None,
                  *,
                  submodel: Optional[str] = None) -> Optional[TStorableSubmodel]:
        query = cls._resolve_get_query(expression)
        if query is None:
            if raise_if_none:
                raise raise_if_none
            return None

        # submodel extra filter works only on base submodel class
        if not cls.SUBMODEL and submodel is not None:
            query["submodel"] = submodel

        res = await cls.find_one(query)
        if res is None and raise_if_none is not None:
            raise raise_if_none
        return res
