from mongey.util import now
from mongey.models.storable_model import StorableModel
from mongey.models.fields import DatetimeField


class TimestampedModel(StorableModel):

    created_at = DatetimeField(default=now, required=True, rejected=True)
    updated_at = DatetimeField(default=now, required=True, rejected=True)

    def touch(self):
        self.updated_at = now()

    async def _before_save(self) -> None:
        self.touch()
