import inspect
from typing import Generic, List, Any, Dict, Callable, Type, Awaitable
from time import time
from functools import wraps
from mongey.errors import ObjectSaveRequired
from mongey.context import ctx
from mongey.types import TModel, T, RT


def save_required(func: Callable[..., T]) -> Callable[..., T]:
    """
    save_required decorator is meant to decorate model methods that
    require a model instance to be saved first.

    For example, StorableModel's own db_update method makes no sense
    until the instance is persisted in the database
    """
    @wraps(func)
    def wrapper(self, *args: List[Any], **kwargs: Dict[str, Any]) -> Any:
        if self.is_new:
            raise ObjectSaveRequired("This object must be saved first")
        return func(self, *args, **kwargs)

    return wrapper


class api_field(Generic[RT]):
    """
    api_field is a decorator for model no-args methods (including async),
    allowing API users to access certain methods, i.e. implementing computed fields
    """

    fn: Callable[..., RT]

    def __init__(self, fn: Callable[..., RT]):
        if not inspect.isfunction(fn):
            raise RuntimeError("only functions and methods can be decorated with api_field")
        self.fn = fn

    def __call__(self, *args: Any, **kwds: Any) -> RT:
        """
        This method is never called, it is only meant to trick type checkers.
        The actual handler is replaced with setattr in the __set_name__ method below
        """
        return self.fn(*args, **kwds)

    def __set_name__(self, owner, name):
        from .models.fields import ComputedField
        fd = ComputedField(is_async=inspect.iscoroutinefunction(self.fn))

        # computed_fields are inherited from MetaModel down the class tree
        # here we make sure every descendant does not modify parents' computed fields

        computed_fields = owner.computed_fields.copy()
        for base in owner.__bases__:
            if hasattr(base, "computed_fields"):
                computed_fields.update(base.computed_fields)
        computed_fields[name] = fd
        owner.computed_fields = computed_fields
        owner.computed_fields[name] = fd
        setattr(owner, name, self.fn)


class model_cached_method(Generic[RT]):
    """
    model_cached_method decorates model methods. The wrapper provided
    generates a unique cache key out of
    - model class name
    - model id
    - method name

    e.g. User.6433d2bfd5a353b0a6822d7f.full_name

    and tries to fetch the value from cache. If value is not there, the
    original method is called and the value is stored to cache before
    being returned

    The methods wrapped with this decorator are automatically added to a
    class property called _cached_methods: set. This allows StorableModel.invalidate
    method to invalidate these cached values along with other model-provided cache.
    """
    orig_func: Callable[..., Awaitable[RT]]

    def __init__(self, func: Callable[..., Awaitable[RT]]) -> None:
        self.orig_func = func

    def __call__(self, *args: Any, **kwds: Any) -> Awaitable[RT]:
        """
        This method is never called, it is only meant to trick type checkers.
        The actual handler is replaced with setattr in the __set_name__ method below
        """
        return self.orig_func(*args, **kwds)

    def __set_name__(self, owner: Type[TModel], name: str) -> None:

        @wraps(self.orig_func)
        async def wrapper(this: TModel, *args, **kwargs) -> RT:
            cache_key = f"{this.collection}.{this.id}.{self.orig_func.__name__}"

            t1 = time()
            value = await ctx.l1_cache.get(cache_key)
            if value is not None:
                td = time() - t1
                ctx.log.debug(
                    "%s L1 hit %s %.3f secs", ctx.l1_cache.NAME, cache_key, td
                )
                return value

            t1 = time()
            value = await ctx.l2_cache.get(cache_key)
            if value is not None:
                td = time() - t1
                ctx.log.debug(
                    "%s L2 hit %s %.3f secs", ctx.l2_cache.NAME, cache_key, td
                )
                await ctx.l1_cache.set(cache_key, value)
                return value

            t1 = time()
            value = await self.orig_func(this, *args, **kwargs)
            td = time() - t1
            ctx.log.debug("%s miss %s %.3f secs", ctx.l2_cache.NAME, cache_key, td)
            await ctx.l2_cache.set(cache_key, value)
            await ctx.l1_cache.set(cache_key, value)

            return value

        owner._cached_methods.add(name)
        setattr(owner, name, wrapper)
