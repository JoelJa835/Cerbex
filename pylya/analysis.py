# File: analysis.py
import threading
import atexit
from typing import Any, List, Tuple
from pylya.hook_manager import Analysis
from time import perf_counter




class PerfAnalyzer(Analysis):
    """
    Measures execution time of each function call with zero I/O overhead during execution.
    Buffers timings in memory and dumps to file at program exit.
    """
    def __init__(self, outfile: str = "perf.log") -> None:
        self.outfile = outfile
        self._local = threading.local()
        self.exclude_prefixes = {
                'builtins', '__builtins__', 'fastapi', 'pydantic', 
                'starlette', '_json'
            }
        
        # Buffer for (module.func, duration) tuples
        self._buffer: List[Tuple[str, float]] = []
        # Register dump at program exit
        atexit.register(self._dump)


    def on_call(self, module, func, args, kwargs):
        if module.startswith(tuple(self.exclude_prefixes)):
            return
        stack = getattr(self._local, "stack", None)
        if stack is None:
            stack = []
            self._local.stack = stack
        stack.append(perf_counter())

    def on_return(self, module, func, result):
        if module.startswith(tuple(self.exclude_prefixes)):
            return
        stack = getattr(self._local, "stack", None)
        if not stack:
            return
        start = stack.pop()
        duration = perf_counter() - start
        self._buffer.append((f"{module}.{func}", duration))
    # def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None:
    #     if any(module.startswith(prefix) for prefix in self.exclude_prefixes):
    #         return
    #     stack = getattr(self._local, "stack", [])
    #     stack.append(time.time())
    #     self._local.stack = stack

    # def on_return(self, module: str, func: str, result: Any) -> None:
    #     if any(module.startswith(prefix) for prefix in self.exclude_prefixes):
    #         return
    #     stack = getattr(self._local, "stack", [])
    #     if not stack:
    #         return
    #     start = stack.pop()
    #     self._local.stack = stack
    #     duration = time.time() - start
    #     # Buffer the measurement; no file I/O here
    #     self._buffer.append((f"{module}.{func}", duration))

    def results(self) -> List[Tuple[str, float]]:
        """
        Returns the list of ("module.func", duration) tuples.
        """
        return list(self._buffer)

    def _dump(self) -> None:
        """
        Writes all buffered timings to the output file in one batch.
        """
        if not self._buffer:
            return
        lines = [f"[Perf] {name} took {dur:.6f}s\n" for name, dur in self._buffer]
        with open(self.outfile, "a") as f:
            f.writelines(lines)



class TypeExtractor(Analysis):
    def __init__(self, outfile: str = "types.log") -> None:
        self._f = open(outfile, "a")
        self.exclude_prefixes = {
                'builtins', '__builtins__', 'fastapi', 'pydantic', 
                'starlette','_json'
            }

    def on_return(self, module: str, func: str, result: Any) -> None:
        # Skip library internals, only log user code
        if any(module.startswith(prefix) for prefix in self.exclude_prefixes):
            return
        self._f.write(f"[Type] {module}.{func} returned {type(result).__name__}\n")
        self._f.flush()

    def __del__(self):
        self._f.close()





# class TypeExtractor(Analysis):
#     """
#     Logs the return type of each function to a file.
#     """
#     def __init__(self, outfile: str = "types.log") -> None:
#         self._f = open(outfile, "a")

#     def on_return(self, module: str, func: str, result: Any) -> None:
#         self._f.write(f"[Type] {module}.{func} returned {type(result).__name__}\n")
#         self._f.flush()

#     def __del__(self):
#         self._f.close()



# class PerfAnalyzer(Analysis):
#     """
#     Measures execution time of each function call and writes to a file.
#     """
#     def __init__(self, outfile: str = "perf.log") -> None:
#         self._local = threading.local()
#         # Open file in append mode
#         self._f = open(outfile, "a")

#     def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None:
#         stack = getattr(self._local, 'stack', []) + [time.time()]
#         self._local.stack = stack

#     def on_return(self, module: str, func: str, result: Any) -> None:
#         stack = getattr(self._local, 'stack', [])
#         if stack:
#             start = stack.pop()
#             self._local.stack = stack
#             duration = time.time() - start
#             # write to file instead of print
#             self._f.write(f"[Perf] {module}.{func} took {duration:.6f}s\n")
#             self._f.flush()      # ensure it’s written immediately

#     def __del__(self):
#         self._f.close()

# class PerfAnalyzer(Analysis):
#     def __init__(self, outfile: str = "perf.log", allowed_modules=None) -> None:
#         self._local = threading.local()
#         self._f = open(outfile, "a")
#         self.allowed = set(allowed_modules) if allowed_modules else None

#     def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None:
#         if self.allowed and module not in self.allowed:
#             return
#         stack = getattr(self._local, 'stack', []) + [time.time()]
#         self._local.stack = stack

#     def on_return(self, module: str, func: str, result: Any) -> None:
#         if self.allowed and module not in self.allowed:
#             return
#         stack = getattr(self._local, 'stack', [])
#         if stack:
#             start = stack.pop()
#             self._local.stack = stack
#             duration = time.time() - start
#             self._f.write(f"[Perf] {module}.{func} took {duration:.6f}s\n")
#             self._f.flush()

#     def __del__(self):
#         self._f.close()