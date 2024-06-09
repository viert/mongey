## Mongey

Mongey is a successor of [Glasskit MongoDB ORM](https://gitlab.com/viert/glasskit) based on Motor MongoDB driver.
Unlike GlassKit, Mongey is a stand-alone module detached from any web framework.

Mongey is based on Motor AsyncIO, meaning it is fully asynchronous.

### Example

```python
import asyncio
from mongey.context import ctx
from mongey.models import StorableModel
from mongey.models.fields import StringField, IntField, DictField
from mongey.decorators import api_field


class User(StorableModel):
    COLLECTION = "users"
    KEY_FIELD = "username"

    username = StringField(required=True)
    first_name = StringField(required=True)
    last_name = StringField(required=True)
    age = IntField(default=None)
    user_settings = DictField(default=dict)

    @api_field
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


async def run():
    ctx.setup_db({"meta": {"uri": "mongodb://127.0.0.1:27017/mydb", "kwargs": {}}, "shards": {}})
    user = User({"username": "superuser", "first_name": "Joe", "last_name": "White"})
    await user.save()


if __name__ == "__main__":
    asyncio.run(run())

```

### Context

Mongey context is a global variable holding configuration bits and the global database object.
Global context allows Mongey to behave more like ActiveRecord rather than Django ORM or SQLAlchemy.
In other words you do `user.save()` instead of `db.save(user)`.


### Configuration

The global context object is created on import but stays not configured until you do so explicitly.

Logging and caching have their default versions and are pre-configured for you while `db` does not.

Use `ctx.setup_db(...)` to configure the database when your application starts, accessing the `db` property
prior to database configuration will raise a `ConfigurationError` exception.


### Caching

Persistent models, like `StorableModel` have `cache_get` method along with the original `get`. This method
fetches the model and if it succeeds, the model is stored to level1+level2 caches. 

L1 cache is usually request local while the L2 is more "persistent", e.g. stored in memcached. 

If you're developing a web app, this allows Mongey to get the same model
multiple times within one web request quickly and "for free" from your app memory,
while for new requests the L2 cache will be used.

Cache invalidation is a complex topic being considered one of the main problems in coding (along with naming of variables)
so this is to be covered in a full documentation which is currently WIP.

### Computed fields

`@api_field` decorator can be added to arg-less sync or async methods of your model which will expose the method
to the sync `to_dict()` and async `to_dict_ext()` methods of the model which are the primary methods for further 
model serialization.
 