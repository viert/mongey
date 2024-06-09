from typing import Optional, Any, Dict, List, Literal, Tuple
from dataclasses import dataclass
from .abc import AbstractCache


CallMethod = Literal["has", "get", "set", "delete"]


@dataclass
class Call:
    args: List[Any]


class TraceCache(AbstractCache):
    """
    TraceCache is an equivalent of NoCache designed for testing purposes.
    Besides bypassing caching it actually traces
    all the calls and saves them for further checking / asserting
    """

    NAME = "TraceCache"

    calls: Dict[CallMethod, List[Call]]

    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        self.calls = {
            "has": [],
            "set": [],
            "get": [],
            "delete": [],
        }

    async def has(self, key: str) -> bool:
        self.calls["has"].append(Call(args=[key]))
        return False

    async def set(self, key: str, value: Any) -> None:
        self.calls["set"].append(Call(args=[key, value]))
        return

    async def get(self, key: str) -> Optional[Any]:
        self.calls["get"].append(Call(args=[key]))
        return None

    async def delete(self, key: str) -> bool:
        self.calls["delete"].append(Call(args=[key]))
        return False

    async def initialise(self) -> None:
        return

    @staticmethod
    def _setup_filter(args: Tuple[Any, ...]):
        if args:
            def flt(x: Call):
                return x.args == list(args)
        else:
            def flt(x: Call):
                return x
        return flt

    def called_once(self, method: CallMethod, *args: Any) -> None:
        flt = self._setup_filter(args)
        calls = list(filter(flt, self.calls[method]))
        args_message = f" with args {args}" if args else ""
        if len(calls) < 1:
            raise AssertionError(f"method {method} was not called{args_message}")
        if len(calls) > 1:
            raise AssertionError(f"method {method} was called {len(calls)} times{args_message}")

    def called_times(self, method: CallMethod, times: int, *args: Any) -> None:
        flt = self._setup_filter(args)
        calls = list(filter(flt, self.calls[method]))
        if len(calls) != times:
            args_message = f" with args {args}" if args else ""
            raise AssertionError(
                f"method {method} was called {len(calls)} times{args_message} ({times} times expected)"
            )

    def called(self, method: CallMethod, *args: Any) -> None:
        flt = self._setup_filter(args)
        calls = list(filter(flt, self.calls[method]))
        if len(calls) == 0:
            args_message = f" with args {args}" if args else ""
            raise AssertionError(f"method {method} was not called{args_message}")

    def not_called(self, method: CallMethod, *args: Any) -> None:
        flt = self._setup_filter(args)
        calls = list(filter(flt, self.calls[method]))
        if len(calls) != 0:
            args_message = f" with args {args}" if args else ""
            raise AssertionError(f"method {method} was called{args_message} {len(calls)} times")
