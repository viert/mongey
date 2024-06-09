from enum import Enum
from dataclasses import dataclass
from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .base_model import TBaseModel


class OnDestroy(Enum):
    CASCADE = "cascade"
    RAISE = "raise"
    DETACH = "detach"


@dataclass
class ModelReference:
    ref_class: Type["TBaseModel"]
    ref_field: str
    on_destroy: OnDestroy

    def __hash__(self):
        return hash(f"{self.ref_class.__name__}.{self.ref_field}")
