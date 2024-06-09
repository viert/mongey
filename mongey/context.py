import sys
import logging
from typing import Literal, Optional, TYPE_CHECKING
from logging import Logger, Formatter, StreamHandler
from mongey.errors import ConfigurationError
from mongey.config import DatabaseConfig
from mongey.types import TCache
if TYPE_CHECKING:
    from mongey.db import DB

DEFAULT_LOG_FORMAT = "[%(asctime)s] %(levelname)s %(filename)s:%(lineno)d %(message)s"


class Context:

    _log: Logger
    _l1_cache: Optional[TCache] = None
    _l2_cache: Optional[TCache] = None
    _db: Optional["DB"] = None

    def __init__(self):
        self.setup_logging()

    @property
    def db(self) -> "DB":
        if self._db is None:
            from mongey.db import DB
            self._db = DB()
        return self._db

    @property
    def l1_cache(self) -> TCache:
        from mongey.cache import NoCache
        if self._l1_cache is None:
            self.setup_cache(1, NoCache())
        return self._l1_cache

    @property
    def l2_cache(self) -> TCache:
        from mongey.cache import NoCache
        if self._l2_cache is None:
            self.setup_cache(2, NoCache())
        return self._l2_cache

    @property
    def log(self) -> Logger:
        return self._log

    def setup_db(self, db_cfg: DatabaseConfig):
        from .db import DB
        if self._db is None:
            self._db = DB()
        self._db.configure(db_cfg)

    def setup_logging(self, *, level: int = logging.DEBUG, fmt: str = DEFAULT_LOG_FORMAT):
        logger = logging.getLogger(__name__)
        logger.propagate = False
        logger.setLevel(level)
        for handler in logger.handlers:
            logger.removeHandler(handler)
        log_format = Formatter(fmt)
        handler = StreamHandler(stream=sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(log_format)
        logger.addHandler(handler)
        self._log = logger

    def setup_cache(self, level: Literal[1, 2], engine: TCache):
        match level:
            case 1:
                self._l1_cache = engine
            case 2:
                self._l2_cache = engine
            case _:
                raise ConfigurationError(f"invalid cache level \"{level}\"")


ctx = Context()
