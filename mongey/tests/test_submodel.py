import itertools
from bson import ObjectId
from mongey.models.submodel import StorableSubmodel
from mongey.models.fields import Field
from .mongo_mock_test import MongoMockTest
from ..errors import WrongSubmodel, MissingSubmodel, IntegrityError


class TestBaseModel(StorableSubmodel):
    COLLECTION = "test"
    field1 = Field()
    field2 = Field()


class Submodel1(TestBaseModel):
    SUBMODEL = "submodel1"
    field3 = Field()


class Submodel2(TestBaseModel):
    SUBMODEL = "submodel2"
    field4 = Field()


TestBaseModel.register_submodel(Submodel1.SUBMODEL, Submodel1)
TestBaseModel.register_submodel(Submodel2.SUBMODEL, Submodel2)


class TestSubmodel(MongoMockTest):

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await TestBaseModel.destroy_all()

    async def test_wrong_input(self):
        with self.assertRaises(WrongSubmodel):
            Submodel1({"_id": ObjectId(), "field1": "value", "submodel": "wrong"})
        with self.assertRaises(MissingSubmodel):
            Submodel1({"_id": ObjectId(), "field1": "value"})
        with self.assertRaises(IntegrityError):
            Submodel1({"field1": "value", "submodel": "my_submodel"})
        with self.assertRaises(WrongSubmodel):
            obj = Submodel1({"field1": "value"})
            obj.submodel = "wrong"
            await obj.save()

    async def test_submodel_field(self):
        obj = Submodel1({})
        self.assertTrue(hasattr(obj, "submodel"))
        self.assertEqual(obj.submodel, Submodel1.SUBMODEL)
        await obj.save()
        await obj.reload()
        self.assertEqual(obj.submodel, Submodel1.SUBMODEL)
        db_obj = await Submodel1.get(obj.id)
        self.assertEqual(db_obj.submodel, Submodel1.SUBMODEL)

    async def test_inheritance(self):
        class Submodel1(TestBaseModel):
            SUBMODEL = "submodel1"

        class Submodel1_1(Submodel1):
            pass

        self.assertEqual(TestBaseModel.collection, Submodel1.collection)
        self.assertEqual(Submodel1.collection, Submodel1_1.collection)
        self.assertEqual(Submodel1.SUBMODEL, Submodel1_1.SUBMODEL)

    async def test_abstract(self):
        with self.assertRaises(IntegrityError):
            TestBaseModel({})

        with self.assertRaises(IntegrityError):
            class C(TestBaseModel):
                pass  # no SUBMODEL
            C({})

        with self.assertRaises(IntegrityError):
            class C(TestBaseModel):
                SUBMODEL = "c"
            Submodel1.register_submodel("c", C)

    async def test_fields_inheritance(self):
        m1 = Submodel1({})
        m2 = Submodel2({})

        self.assertCountEqual(m1._fields, ["id", "submodel", "field1", "field2", "field3"])
        self.assertCountEqual(m2._fields, ["id", "submodel", "field1", "field2", "field4"])

    @staticmethod
    async def _create_objs():
        """Returns two lists of objects. Objects in the same positions only differ in their submodel"""
        values = [1, 2, 3]
        objs1 = [Submodel1({"field1": v, "field2": v}) for v in values]
        objs2 = [Submodel2({"field1": v, "field2": v}) for v in values]
        for obj in itertools.chain(objs1, objs2):
            await obj.save()
        return objs1, objs2

    async def test_isolation_find(self):
        self.maxDiff = None
        objs1, objs2 = await self._create_objs()
        self.assertCountEqual(
            await Submodel1.find().all(),
            objs1,
        )
        self.assertCountEqual(
            await Submodel2.find().all(),
            objs2,
        )
        self.assertCountEqual(
            await TestBaseModel.find().all(),
            objs1 + objs2,
        )

        self.assertCountEqual(
            await Submodel1.find({"field1": objs1[0].field1}).all(),
            [objs1[0]],
        )
        self.assertCountEqual(
            await TestBaseModel.find({"field1": objs1[0].field1}).all(),
            [objs1[0], objs2[0]],
        )

    async def test_isolation_update(self):
        objs1, objs2 = await self._create_objs()
        obj1 = objs2[0]
        obj1.field2 = "new_value"
        await Submodel2.update_many(
            {"field1": obj1.field1},
            {"$set": {"field2": obj1.field2}}
        )
        self.assertCountEqual(
            await TestBaseModel.find({"field2": obj1.field2}).all(),
            [obj1]
        )

        obj1 = objs1[1]
        obj2 = objs2[1]
        obj1.field2 = "newer_value"
        obj2.field2 = "newer_value"
        await TestBaseModel.update_many(
            {"field1": obj1.field1},
            {"$set": {"field2": obj1.field2}}
        )
        self.assertCountEqual(
            await TestBaseModel.find({"field2": obj1.field2}).all(),
            [obj1, obj2]
        )

    async def test_isolation_destroy(self):
        objs1, objs2 = await self._create_objs()
        to_destroy = objs2.pop()
        to_keep = objs1[-1]
        await Submodel2.destroy_many({"field1": to_destroy.field1})
        self.assertListEqual(
            await Submodel2.find({"field1": to_destroy.field1}).all(),
            []
        )
        self.assertListEqual(
            await TestBaseModel.find({"field1": to_destroy.field1}).all(),
            [to_keep]
        )

        to_destroy = objs1[0]
        objs1 = objs1[1:]
        objs2 = objs2[1:]
        await TestBaseModel.destroy_many({"field1": to_destroy.field1})
        self.assertCountEqual(
            await TestBaseModel.find().all(),
            objs1 + objs2,
        )

    async def test_filtered_get(self):
        obj1 = Submodel1.create(field1="obj1")
        await obj1.save()
        obj2 = Submodel2.create(field1="obj2")
        await obj2.save()

        obj = await TestBaseModel.get(obj1.id)
        self.assertIsNotNone(obj)
        obj = await TestBaseModel.get(obj1.id, submodel=obj1.submodel)
        self.assertIsNotNone(obj)
        obj = await TestBaseModel.get(obj1.id, submodel=obj2.submodel)
        self.assertIsNone(obj)

        obj = await TestBaseModel.get(obj2.id)
        self.assertIsNotNone(obj)
        obj = await TestBaseModel.get(obj2.id, submodel=obj2.submodel)
        self.assertIsNotNone(obj)
        obj = await TestBaseModel.get(obj2.id, submodel=obj1.submodel)
        self.assertIsNone(obj)
