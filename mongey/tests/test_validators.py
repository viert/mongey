from unittest import IsolatedAsyncioTestCase
from typing import Type, TypeVar
from datetime import datetime
from ..models.fields import (
    StringField,
    IntField,
    FloatField,
    ListField,
    DictField,
    BoolField,
    DatetimeField,
)
from ..models.base_model import BaseModel
from ..errors import ValidationError

TException = TypeVar("TException", bound=Exception)
TExceptionType = Type[TException]


class TestValidators(IsolatedAsyncioTestCase):

    async def test_required(self):
        class Model(BaseModel):
            field = StringField(required=True)

        model = Model()
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = "string"
        await model.validate_all()

    async def test_string_field(self):
        class Model(BaseModel):
            field = StringField()

        model = Model({"field": 1})
        with self.assertRaises(ValidationError):
            await model.validate_all()

        model.field = "string"
        await model.validate_all()

        model.field = "   auto-trimmed   "
        self.assertEqual(model.field, "auto-trimmed")

        class Model(BaseModel):
            field = StringField(auto_trim=False)

        model = Model({"field": "    no-auto-trim    "})
        self.assertEqual(model.field, "    no-auto-trim    ")

        class Model(BaseModel):
            field = StringField(min_length=3, max_length=5, re_match=r"^\d+$")

        model = Model({"field": "1"})
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = "123456"
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = "1234a"
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = "1234"
        await model.validate_all()

    async def test_list_field(self):
        class Model(BaseModel):
            field = ListField()

        model = Model({"field": 1})
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = [1, 2, 3]
        await model.validate_all()

        class Model(BaseModel):
            field = ListField(min_length=3, max_length=5)

        model = Model({"field": [1]})
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = [1, 2, 3, 4, 5, 6]
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = [1, 2, 3, 4]
        await model.validate_all()

    async def test_bool_field(self):
        class Model(BaseModel):
            field = BoolField()

        model = Model({"field": 1})
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = False
        await model.validate_all()

    async def test_int_field(self):
        class Model(BaseModel):
            field = IntField()

        model = Model({"field": "string"})
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = -34
        await model.validate_all()

        class Model(BaseModel):
            field = IntField(min_value=0, max_value=10)

        model = Model({"field": -34})
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = 34
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = 5
        await model.validate_all()

    async def test_float_field(self):
        class Model(BaseModel):
            field = FloatField()

        model = Model({"field": "string"})
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = -34
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = 28.0
        await model.validate_all()

        class Model(BaseModel):
            field = FloatField(min_value=0, max_value=10)

        model = Model({"field": -15.5})
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = 15.5
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = 5.3
        await model.validate_all()

    async def test_dict_field(self):
        class Model(BaseModel):
            field = DictField()

        model = Model({"field": 1})
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = {}
        await model.validate_all()

    async def test_datetime_field(self):
        class Model(BaseModel):
            field = DatetimeField()

        model = Model({"field": 1})
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = datetime.now()
        await model.validate_all()

    async def test_choices(self):
        class Model(BaseModel):
            field = StringField(required=True, choices=["a", "b", "c"])

        class ModelNotRequired(BaseModel):
            field = StringField(required=False, choices=["a", "b", "c"])

        model = Model({"field": "a"})
        await model.validate_all()
        model.field = "b"
        await model.validate_all()
        model.field = "c"
        await model.validate_all()
        model.field = "d"
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = None
        with self.assertRaises(ValidationError):
            await model.validate_all()

        model = ModelNotRequired({"field": "a"})
        await model.validate_all()
        model.field = "b"
        await model.validate_all()
        model.field = "c"
        await model.validate_all()
        model.field = "d"
        with self.assertRaises(ValidationError):
            await model.validate_all()
        model.field = None
        await model.validate_all()
