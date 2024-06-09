from abc import ABC
from ..models.storable_model import StorableModel
from ..models.meta_model import ModelReference
from ..models.fields import ReferenceField, SelfReferenceField, StringField, OnDestroy
from ..errors import ValidationError, ObjectHasReferences
from .mongo_mock_test import MongoMockTest


class TestReference(MongoMockTest):

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        from mongey.context import ctx
        await ctx.db.meta.conn.master.delete_many({})
        await ctx.db.meta.conn.minion.delete_many({})

    async def test_reference_field_raise(self):
        class Master(StorableModel):
            KEY_FIELD = "name"
            name = StringField()

        class Minion(StorableModel):
            KEY_FIELD = "name"
            name = StringField()
            master_id: ReferenceField[Master] = ReferenceField(reference_model=Master, required=True)

        m = Master.create(name="master")
        await m.save()

        mi1 = Minion.create(name="mi1", master_id="abc")

        with self.assertRaises(ValidationError) as cx:
            await mi1.save()

        mi1.master_id = m.id
        await mi1.save()

        self.assertEqual("Broken reference master_id: no Master found", cx.exception.detail)

        with self.assertRaises(ObjectHasReferences) as cx:
            await m.destroy()

    async def test_reference_field_cascade(self):
        class Master(StorableModel):
            KEY_FIELD = "name"
            name = StringField()

        class Minion(StorableModel):
            KEY_FIELD = "name"
            name = StringField()
            master_id: ReferenceField[Master] = ReferenceField(reference_model=Master, required=True,
                                                               on_destroy=OnDestroy.CASCADE)

        m = Master.create(name="master")
        await m.save()
        mi1 = Minion.create(name="mi1", master_id=m.id)
        await mi1.save()
        self.assertEqual(1, await Minion.find({}).count())

        await m.destroy()
        self.assertEqual(0, await Minion.find({}).count())

    async def test_references_to_subclasses(self):
        class Master(StorableModel):
            KEY_FIELD = "name"
            name = StringField()

        class Minion(StorableModel):
            KEY_FIELD = "name"
            name = StringField()
            master_id: ReferenceField[Master] = ReferenceField(reference_model=Master, required=True)

        class SubMinion(Minion):
            other_field = StringField()

        self.assertCountEqual(
            [
                ModelReference(ref_class=Minion, ref_field="master_id", on_destroy=OnDestroy.RAISE),
                ModelReference(ref_class=SubMinion, ref_field="master_id", on_destroy=OnDestroy.RAISE)
            ],
            Master._references
        )

    async def test_references_to_subclasses_of_abc(self):
        class Master(StorableModel):
            KEY_FIELD = "name"
            name = StringField()

        class Minion(StorableModel, ABC):
            KEY_FIELD = "name"
            name = StringField()
            master_id: ReferenceField[Master] = ReferenceField(reference_model=Master, required=True)

        class SubMinion(Minion):
            other_field = StringField()

        self.assertCountEqual(
            [ModelReference(ref_class=SubMinion, ref_field="master_id", on_destroy=OnDestroy.RAISE)],
            Master._references
        )

    async def test_detach(self):
        class Master(StorableModel):
            KEY_FIELD = "name"
            name = StringField()

        class Minion(StorableModel):
            KEY_FIELD = "name"
            name = StringField()
            master_id: ReferenceField[Master] = ReferenceField(reference_model=Master, on_destroy=OnDestroy.DETACH)

        m = Master.create(name="master")
        await m.save()
        mi1 = Minion.create(name="mi1", master_id=m.id)
        await mi1.save()

        await m.destroy()
        await mi1.reload()
        self.assertEqual(mi1.master_id, None)

    async def test_self_reference(self):

        class Model(StorableModel):
            KEY_FIELD = "name"
            name = StringField()
            parent_id = SelfReferenceField(on_destroy=OnDestroy.RAISE)

        self.assertEqual(1, len(Model._references))

        ref = list(Model._references)[0]
        self.assertEqual(ref.ref_class, Model)

        p = Model.create(name="parent")
        await p.save()
        c = Model.create(name="child", parent_id=p.id)
        await c.save()

        with self.assertRaises(ObjectHasReferences):
            await p.destroy()
