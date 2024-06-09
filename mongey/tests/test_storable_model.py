from ..models.storable_model import StorableModel
from ..models.fields import StringField, Field, ObjectIdField
from ..db import ObjectsCursor
from ..decorators import api_field, model_cached_method
from .mongo_mock_test import MongoMockTest
from mongey.cache import TraceCache


CALLABLE_DEFAULT_VALUE = 4


def callable_default():
    return CALLABLE_DEFAULT_VALUE


class TestModel(StorableModel):
    field1 = StringField(rejected=True, index=True, default="default_value")
    field2 = Field(required=True)
    field3 = Field(required=True, default="required_default_value")
    callable_default_field = Field(default=callable_default)


class TestStorableModel(MongoMockTest):

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await TestModel.destroy_all()

    async def asyncTearDown(self) -> None:
        await TestModel.destroy_all()
        await super().asyncTearDown()

    async def test_defaults(self):
        model = TestModel()
        self.assertEqual("default_value", model.field1)
        self.assertEqual("required_default_value", model.field3)
        self.assertEqual(CALLABLE_DEFAULT_VALUE, model.callable_default_field)

    async def test_eq(self):
        model = TestModel({"field2": "mymodel"})
        await model.save()
        model2 = await TestModel.find_one({"field2": "mymodel"})
        self.assertEqual(model, model2)

    async def test_reject_on_update(self):
        model = TestModel.create(field1="original_value", field2="mymodel_reject_test")
        await model.save()
        id_ = model.id
        await model.update({"field1": "new_value"})
        model = await TestModel.find_one({"_id": id_})
        self.assertEqual(model.field1, "original_value")

    async def test_update_many(self):
        model1 = TestModel.create(field1="original_value", field2="mymodel_update_test")
        await model1.save()
        model2 = TestModel.create(field1="original_value", field2="mymodel_update_test")
        await model2.save()
        model3 = TestModel.create(field1="do_not_modify", field2="mymodel_update_test")
        await model3.save()

        await TestModel.update_many(
            {"field1": "original_value"}, {"$set": {"field2": "mymodel_updated"}}
        )
        await model1.reload()
        await model2.reload()
        await model3.reload()

        self.assertEqual(model1.field2, "mymodel_updated")
        self.assertEqual(model2.field2, "mymodel_updated")
        self.assertEqual(model3.field2, "mymodel_update_test")

    async def test_invalidate(self):
        from mongey.context import ctx
        tc: TraceCache = ctx.l1_cache

        class Model(StorableModel):
            field1 = StringField()
            KEY_FIELD = "field1"

        model = Model({"field1": "value"})
        await model.save()

        tc.called_once("delete", "model.value")
        tc.reset()

        await model.save()
        tc.called_once("delete", f"model.{model.id}")
        tc.called_once("delete", f"model.value")

    async def test_invalidate_cached_method(self):
        from mongey.context import ctx
        tc: TraceCache = ctx.l1_cache

        class User(StorableModel):
            first_name = StringField()
            last_name = StringField()

            KEY_FIELD = "last_name"

            @model_cached_method
            async def full_name(self):
                return f"{self.first_name} {self.last_name}"

        user = User.create(first_name="Bob", last_name="Dilan")
        await user.save()

        tc.called_once("delete", "user.Dilan")

        _ = await user.full_name()
        tc.called_once("get", f"user.{user.id}.full_name")
        tc.reset()

        await user.save()
        tc.called_once("delete", "user.Dilan")
        tc.called_once("delete", f"user.{user.id}")
        tc.called_once("delete", f"user.{user.id}.full_name")

    async def test_update(self):
        model = TestModel.create(field1="original_value", field2="mymodel_update_test")
        await model.save()
        id_ = model.id
        await model.update({"field2": "mymodel_updated"})
        model = await TestModel.find_one({"_id": id_})
        self.assertEqual(model.field2, "mymodel_updated")

    async def test_count(self):
        class Model(StorableModel):
            a = Field()

        for i in range(100):
            m = Model.create(a=i)
            await m.save()

        cur = Model.find({})
        count = await cur.count()
        self.assertEqual(count, 100)

        cur = Model.find({"a": {"$lt": 10}})
        count = await cur.count()
        self.assertEqual(count, 10)

    async def test_to_dict_ext_cursor_properties(self):
        class DepModel(StorableModel):
            a = Field()
            master_id = ObjectIdField(required=True)

        class MasterModel(StorableModel):
            name = Field()

            @api_field
            def deps(self) -> ObjectsCursor["DepModel"]:
                return DepModel.find({"master_id": self.id})

        master = MasterModel.create(name="master")
        await master.save()

        for i in range(10):
            dep = DepModel.create(a=i, master_id=master.id)
            await dep.save()

        # check normal method usage
        deps = await master.deps().all()
        self.assertEqual(len(deps), 10)

        # check deps are accessible via API
        dct = await master.to_dict_ext(fields=["id", "name", "deps"])
        self.assertEqual(len(dct["deps"]), 10)

    async def test_find_by_none_raises(self):
        with self.assertRaises(ValueError):
            _ = await TestModel.get(None, ValueError("value error"))
        with self.assertRaises(ValueError):
            _ = await TestModel.cache_get(None, ValueError("value error"))

    async def test_find_ids(self):
        tma = TestModel.create(field2="a")
        await tma.save()
        tmb = TestModel.create(field2="b")
        await tmb.save()
        tmc = TestModel.create(field2="c")
        await tmc.save()

        self.assertCountEqual([tma.id, tmb.id, tmc.id], await TestModel.find_ids({}))
        self.assertCountEqual([tma.id], await TestModel.find_ids({"field2": "a"}))
