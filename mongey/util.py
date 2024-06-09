from bson.objectid import ObjectId, InvalidId
from datetime import datetime
from logging import getLogger

NilObjectId: ObjectId = ObjectId("000000000000000000000000")

log = getLogger("mongey")


# Mongo stores datetime rounded to milliseconds as its datetime
# capabilities are limited by v8 engine
def now() -> datetime:
    dt = datetime.utcnow()
    dt = dt.replace(microsecond=dt.microsecond // 1000 * 1000)
    return dt


def resolve_id(obj_id: str | ObjectId | None) -> ObjectId | str | None:
    # ObjectId(None) generates a new unique object id
    # We need to override that and return None instead
    if obj_id is not None and not isinstance(obj_id, ObjectId):
        try:
            obj_id_expr = ObjectId(obj_id)
            if str(obj_id_expr) == obj_id:
                return obj_id_expr
        except (InvalidId, TypeError):
            pass
    return obj_id
