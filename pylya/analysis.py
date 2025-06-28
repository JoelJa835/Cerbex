# File: analysis.py
import threading
import time
from typing import Any
from hook_manager import Analysis


class PerfAnalyzer(Analysis):
    """
    Measures execution time of each function call.
    """
    def __init__(self) -> None:
        self._local = threading.local()

    def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None:
        stack = getattr(self._local, 'stack', []) + [time.time()]
        self._local.stack = stack

    def on_return(self, module: str, func: str, result: Any) -> None:
        stack = getattr(self._local, 'stack', [])
        if stack:
            start = stack.pop()
            self._local.stack = stack
            duration = time.time() - start
            print(f"[Perf] {module}.{func} took {duration:.6f}s")


class TypeExtractor(Analysis):
    """
    Logs the return type of each function.
    """
    def on_return(self, module: str, func: str, result: Any) -> None:
        print(f"[Type] {module}.{func} returned {type(result).__name__}")