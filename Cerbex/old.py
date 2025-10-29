# # File: analysis.py
# import threading
# import time
# import atexit
# from typing import Any, List, Tuple
# from pylya.hook_manager import Analysis




# class PerfAnalyzer(Analysis):
#     """
#     Measures execution time of each function call with zero I/O overhead during execution.
#     Buffers timings in memory and dumps to file at program exit.
#     """
#     def __init__(self, outfile: str = "perf.log") -> None:
#         self.outfile = outfile
#         self._local = threading.local()
#         # Buffer for (module.func, duration) tuples
#         self._buffer: List[Tuple[str, float]] = []
#         # Register dump at program exit
#         atexit.register(self._dump)

#     def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None:
#         stack = getattr(self._local, "stack", [])
#         stack.append(time.time())
#         self._local.stack = stack

#     def on_return(self, module: str, func: str, result: Any) -> None:
#         stack = getattr(self._local, "stack", [])
#         if not stack:
#             return
#         start = stack.pop()
#         self._local.stack = stack
#         duration = time.time() - start
#         # Buffer the measurement; no file I/O here
#         self._buffer.append((f"{module}.{func}", duration))

#     def results(self) -> List[Tuple[str, float]]:
#         """
#         Returns the list of ("module.func", duration) tuples.
#         """
#         return list(self._buffer)

#     def _dump(self) -> None:
#         """
#         Writes all buffered timings to the output file in one batch.
#         """
#         if not self._buffer:
#             return
#         lines = [f"[Perf] {name} took {dur:.6f}s\n" for name, dur in self._buffer]
#         with open(self.outfile, "a") as f:
#             f.writelines(lines)



# class TypeExtractor(Analysis):
#     def __init__(self, outfile: str = "types.log", allowed_modules=None) -> None:
#         self._f = open(outfile, "a")
#         self.allowed = set(allowed_modules) if allowed_modules else None

#     def on_return(self, module: str, func: str, result: Any) -> None:
#         if self.allowed and module not in self.allowed:
#             return
#         self._f.write(f"[Type] {module}.{func} returned {type(result).__name__}\n")
#         self._f.flush()

#     def __del__(self):
#         self._f.close()


# class AttrAccessAnalyzer(Analysis):

#     def __init__(self, outfile: str = "attr_access.log") -> None:
#         self._f = open(outfile, "a")
#         # (Other initialization as needed)

#     def on_attr_read(self, module: str, obj: any, attr: str) -> None:
#         # Record read access
#         self._f.write(f"READ {module} | {obj!r}.{attr}\n")
#         self._f.flush()

#     def on_attr_write(self, module: str, obj: any, attr: str, value: any) -> None:
#         # Record write access
#         self._f.write(f"WRITE {module} | {obj!r}.{attr} = {value!r}\n")
#         self._f.flush()

#     def __del__(self):
#         try:
#             self._f.close()
#         except Exception:
#             pass






# # File: hook_loader.py
# """
# Standalone hook loader for your project. Import this at startup to enable Lyapy instrumentation.
# """
# import sys
# import atexit
# import json
# from typing import Dict, List, Tuple

# from pylya.hook_manager import HookManager ,Analysis
# from pylya.importer import install_import_hook, rewrap_existing_targets



# def _load_config(path: str = 'config.json') -> Tuple[list, None]:
#     """
#     Load 'targets' from JSON config file.  Allowlist is now handled separately.
#     """
#     try:
#         with open(path, 'r') as f:
#             data = json.load(f)
#         return data.get('targets', []), None
#     except FileNotFoundError:
#         return [], None


# def _load_allowlist(path: str = 'allowlist.json') -> Dict[str, list]:
#     """
#     Load generated allowlist for enforce mode.
#     """
#     try:
#         with open(path, 'r') as f:
#             data = json.load(f)
#         # Expect top-level 'allowlist' key
#         return data.get('allowlist', {})
#     except FileNotFoundError:
#         return {}


# def install_hooks(
#     config_path: str = 'config.json',
#     mode: str       = 'learn',
#     analyses        = None,
#     allowlist_path: str = 'allowlist.json'
# ) -> HookManager:
#     # 1) load config & allowlist

#     # print(mode)
#     # print(allowlist_path)
#     targets, _   = _load_config(config_path)
#     raw_allowlist = mode == 'enforce' and _load_allowlist(allowlist_path) or {}

#     if analyses is None:
#         analyses = []

#     # 2) always create a HookManager
#     hook_mgr = HookManager(targets, analyses, mode=mode, allowlist=raw_allowlist,)


#     # 4) install hooks
#     install_import_hook(hook_mgr, targets)
#     rewrap_existing_targets(hook_mgr, targets)
#     sys.setprofile(hook_mgr.c_profile)

#     # 5) register the exit handler
  
#     atexit.register(hook_mgr.write_reports)

#     return hook_mgr


# # File: hook_manager.py
# import json
# import threading
# from typing import Any, Dict, List, Optional, Set

# class Analysis:
#     """
#     Base hook interface: override any of these methods.
#     """
#     def on_import(self, parent: Optional[str], name: str) -> None: ...
#     def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None: ...
#     def on_return(self, module: str, func: str, result: Any) -> None: ...
#     def on_attr_read(self, module: str, obj: Any, attr: str) -> None: ...
#     def on_attr_write(self, module: str, obj: Any, attr: str, value: Any) -> None: ...

# class HookManager:
#     def __init__(
#         self,
#         targets: List[str],
#         analyses: List[Analysis],
#         mode: str = 'learn',
#         allowlist: Optional[Dict[str, List[str]]] = None,
#     ) -> None:
#         self.analyses = analyses
#         self.mode = mode
#         self.allowlist = allowlist or {}
#         self.targets  = targets
#         self.dep_graph: Dict[str, Set[str]] = {}
#         self.events: Dict[str, Set[str]] = {}
#         self._local = threading.local()

#     def _record_event(self, module: str, tag: str) -> None:
#         mod = module or '__main__'
#         self.events.setdefault(mod, set()).add(tag)

#     def on_import(self, parent: Optional[str], name: str) -> None:
#         # print(f"🧭 [on_import] {parent} imports {name}")
#         parent_mod = parent or '__main__'
#         self.dep_graph.setdefault(parent_mod, set()).add(name)
#         if self.mode == 'learn':
#             self._record_event(parent_mod, f"import:{name}")
#         if self.mode == 'enforce' and parent and name not in self.allowlist.get(parent, []):
#             raise ImportError(f"Import of {name} not allowed in module {parent}")
#         for a in self.analyses:
#             a.on_import(parent, name)

#     def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None:
#         if self.mode == 'learn':
#             self._record_event(module, f"call:{func}")

#         # ❗ ENFORCE FUNCTION CALLS
#         elif self.mode == 'enforce':
#             allowed = self.allowlist.get(module, [])
#             if func not in allowed:
#                 raise RuntimeError(f"[SECURITY] Blocked unauthorized call: {module}.{func}()")

#         for a in self.analyses:
#             a.on_call(module, func, args, kwargs)

#     def on_return(self, module: str, func: str, result: Any) -> None:
#         if self.mode == 'learn':
#             self._record_event(module, f"return:{func}")
#         for a in self.analyses:
#             a.on_return(module, func, result)

#     def on_attr_read(self, module: str, obj: Any, attr: str) -> None:
#         if self.mode == 'learn':
#             self._record_event(module, f"read:{attr}")
#         for a in self.analyses:
#             a.on_attr_read(module, obj, attr)

#     def on_attr_write(self, module: str, obj: Any, attr: str, value: Any) -> None:
#         if self.mode == 'learn':
#             self._record_event(module, f"write:{attr}")
#         for a in self.analyses:
#             a.on_attr_write(module, obj, attr, value)

#     def c_profile(self, frame, event, arg):
#         # 1) Reentrancy guard first
#         if getattr(self._local, 'in_hook', False):
#             return

#         # 2) Now mark that we’re in the hook
#         self._local.in_hook = True
#         try:
#             # 3) Filter events immediately
#             if event not in ("c_call", "c_return"):
#                 return

#             fn = arg
#             mod = getattr(fn, '__module__', '__builtins__') or '__builtins__'
#             name = getattr(fn, '__name__', '<c_func>')
#             if event == 'c_call':
#                 self.on_call(mod, name, (), {})
#             else:
#                 # pass the real return value through!
#                 real_result = arg
#                 self.on_return(mod, name, real_result)
#         finally:
#             self._local.in_hook = False



#     def record_allowlist(self) -> Dict[str, List[str]]:
#         return {m: sorted(list(deps)) for m, deps in self.dep_graph.items()}


#     def write_reports(
#         self,
#         deps_path: str = 'dependencies.json',
#         events_path: str = 'events.json',
#         allowlist_path: str = 'allowlist.json'
#     ) -> None:

#         if self.mode == 'enforce':
#             return
#         # Inline original write_reports behavior from BaseHookManager
#         # 1) Write dependencies.json
#         deps = self.record_allowlist()
#         with open(deps_path, 'w') as f:
#             json.dump({'dependencies': deps}, f, indent=2)

#         # 2) Write events.json
#         events_out = {module: {event: True for event in tags}
#                       for module, tags in getattr(self, 'events', {}).items()}
#         with open(events_path, 'w') as f:
#             json.dump(events_out, f, indent=2)

#         # 3) Build allowlist.json for enforce mode
#         try:
#             with open(events_path, 'r') as f:
#                 events = json.load(f)
#         except FileNotFoundError:
#             return

#         # Start with import allowlist from dep_graph
#         allow = {m: sorted(deps) for m, deps in self.dep_graph.items()}

#         # Augment with call-based allowlist from events.json
#         for module, tags in events.items():
#             calls = [tag.split(':', 1)[1]
#                     for tag, seen in tags.items()
#                     if seen and tag.startswith('call:')]
#             if calls:
#                 allow.setdefault(module, []).extend(calls)
#                 allow[module] = sorted(set(allow[module]))  # remove duplicates

#         with open(allowlist_path, 'w') as f:
#             json.dump({'allowlist': allow}, f, indent=2)



# # File: importer.py
# import builtins
# import sys
# import importlib
# import importlib.abc
# import importlib.machinery
# import inspect
# from types import ModuleType, FunctionType, MethodType
# from typing import List
# from weakref import WeakKeyDictionary

# from pylya.hook_manager import HookManager
# from pylya.utils import make_wrapper



# # Cache: original function → wrapper
# _wrap_cache: "WeakKeyDictionary[FunctionType, FunctionType]" = WeakKeyDictionary()
# # Primitives we don’t instrument
# PRIMITIVES = (str, int, float, bool, bytes, type(None))


# def wrap_value(val, module_name: str, hook_mgr: HookManager):

#     # primitives & modules stay
#     if isinstance(val, PRIMITIVES) or isinstance(val, ModuleType):
#         return val

#     # 1) If this is a class defined in our target module, rebuild it
#     if inspect.isclass(val) and val.__module__ == module_name:
#         orig_cls = val

#         # 1a) Create a metaclass that intercepts class‐level get/sets
#         class AttrMeta(type(orig_cls)):
#             def __getattribute__(cls, name):
#                 hook_mgr.on_attr_read(orig_cls.__module__, cls, name)
#                 return super().__getattribute__(name)

#             def __setattr__(cls, name, value):
#                 hook_mgr.on_attr_write(orig_cls.__module__, cls, name, value)
#                 return super().__setattr__(name, value)

#         # 1b) Rebuild the class under AttrMeta
#         Wrapped = AttrMeta(
#             orig_cls.__name__,
#             orig_cls.__bases__,
#             dict(orig_cls.__dict__),
#         )

#         # 1c) Inject instance‐level hooks into Wrapped
#         def __getattribute__(self, name):
#             hook_mgr.on_attr_read(orig_cls.__module__, self, name)
#             return super(Wrapped, self).__getattribute__(name)

#         def __setattr__(self, name, value):
#             hook_mgr.on_attr_write(orig_cls.__module__, self, name, value)
#             return super(Wrapped, self).__setattr__(name, value)

#         Wrapped.__getattribute__ = __getattribute__
#         Wrapped.__setattr__      = __setattr__

#         return Wrapped

#     # 2) Functions & bound methods
#     if isinstance(val, (FunctionType, MethodType)) and val.__module__.startswith(module_name):
#         # print(f"🔀 wrap_value called for module_name='{module_name}', val.__module__='{val.__module__}', fn={val.__name__}")
#         cached = _wrap_cache.get(val)
#         if cached is not None:
#             return cached

#         if val.__name__ in ('__repr__', '__str__') or hasattr(val, '__wrapped__'):
#             return val

#         is_async = inspect.iscoroutinefunction(val)
#         wrapper = make_wrapper(val, module_name, hook_mgr, is_async)
#         _wrap_cache[val] = wrapper
#         return wrapper

#     # 3) Everything else
#     return val



# class InstrumentLoader(importlib.abc.Loader):
#     def __init__(self, hook_mgr: HookManager, orig_loader: importlib.abc.Loader):
#         self.hook_mgr = hook_mgr
#         self.orig_loader = orig_loader

#     def create_module(self, spec):
#         return self.orig_loader.create_module(spec)

#     def exec_module(self, module):
#         parent = module.__spec__.parent or module.__name__
#         if parent != module.__name__:  
#             self.hook_mgr.on_import(parent, module.__name__)

#         try:
#             source = self.orig_loader.get_source(module.__name__)
#         except Exception:
#             source = None

#         if source is None:
#             self.orig_loader.exec_module(module)
#         else:
#             code = compile(source, module.__spec__.origin, 'exec')
#             exec(code, module.__dict__, module.__dict__)

#         for attr_name, attr_val in list(module.__dict__.items()):
#             if not attr_name.startswith('__'):
#                 try:
#                     module.__dict__[attr_name] = wrap_value(
#                         attr_val, module.__name__, self.hook_mgr
#                     )
#                 except Exception:
#                     pass


# class InstrumentFinder(importlib.abc.MetaPathFinder):
#     def __init__(self, hook_mgr: HookManager, targets: List[str]):
#         self.hook_mgr = hook_mgr
#         self.targets = set(targets)

#     def _matches(self, fullname: str) -> bool:
#         return any(
#             fullname == t or (t.endswith('*') and fullname.startswith(t[:-1]))
#             for t in self.targets
#         )
    

#     def find_spec(self, fullname, path, target=None):
#         # 1) Always record first-time imports via on_import
#         #    Finder only sees non-cached modules
#         self.hook_mgr.on_import(None, fullname)

#         # 2) Delegate to default PathFinder
#         spec = importlib.machinery.PathFinder.find_spec(fullname, path)
#         if spec and self._matches(fullname):
#             spec.loader = InstrumentLoader(self.hook_mgr, spec.loader)
#         return spec


# def install_import_hook(
#     hook_mgr: HookManager,
#     targets: List[str],
#     replace_import_module: bool = True
# ) -> None:
#     """
#     Install a unified import hook and instrumentation finder/loader.
#     - Uses MetaPathFinder to log and instrument target modules on first load.
#     - Falls back to a __import__ wrapper to catch cached or C-level imports.
#     """
#     # 1) Insert unified finder for logging & instrumentation
#     sys.meta_path.insert(0, InstrumentFinder(hook_mgr, targets))

#     # 2) Fallback for imports not seen by the finder (e.g., cached or C extensions)
#     orig_import = builtins.__import__
#     def fallback_import(name, globals=None, locals=None, fromlist=(), level=0):
#         parent = globals.get('__name__') if globals else None
#         parent_mod = parent or '__main__'

#         # print(f"📦 [__import__ fallback] {parent_mod} → import {name}")
#         # Record import only if finder did not log it
#         if name not in hook_mgr.dep_graph.get(parent_mod, set()):
#             hook_mgr.on_import(parent, name)
#         return orig_import(name, globals, locals, fromlist, level)
#     builtins.__import__ = fallback_import

#     # 3) Preserve optional import_module instrumentation
#     if replace_import_module:
#         real_import_module = importlib.import_module
#         def instrumented_import_module(name, package=None):
#             module = real_import_module(name, package)
#             for attr in dir(module):
#                 if not attr.startswith('__'):
#                     try:
#                         raw = getattr(module, attr)
#                         setattr(
#                             module,
#                             attr,
#                             wrap_value(raw, module.__name__, hook_mgr)
#                         )
#                     except Exception:
#                         pass
#             return module
#         importlib.import_module = instrumented_import_module

# def rewrap_existing_targets(hook_mgr: HookManager, targets: List[str]):
#     """
#     Go through already-loaded target modules in sys.modules and wrap their top-level functions.
#     This ensures instrumentation even for modules that were imported before the hooks were installed.
#     """
#     for name in targets:
#         mod = sys.modules.get(name)
#         if not mod:
#             continue
#         for attr in dir(mod):
#             if not attr.startswith('__'):
#                 try:
#                     raw = getattr(mod, attr)
#                     wrapped = wrap_value(raw, name, hook_mgr)
#                     setattr(mod, attr, wrapped)
#                 except Exception:
#                     pass



# # File: utils.py
# import inspect
# from functools import wraps
# from typing import Any, Callable
# from pylya.hook_manager import HookManager




# def make_wrapper(
#     fn: Callable,
#     module: str,
#     hook_mgr: HookManager,
#     is_async: bool
# ) -> Callable:
#     """
#     Return a wrapper that calls hook_mgr.on_call/on_return
#     around fn, respecting async vs. sync.
#     """
#     _local = hook_mgr._local
#     _on_call = hook_mgr.on_call
#     _on_return = hook_mgr.on_return

#     def ensure_hook_flag():
#         if not hasattr(_local, 'in_hook'):
#             _local.in_hook = False

#     if is_async:
#         @wraps(fn)
#         async def async_wrapper(*args, **kwargs):
#             # Record entry without blocking nested calls
#             ensure_hook_flag()
#             if not _local.in_hook:
#                 _local.in_hook = True
#                 try:
#                     _on_call(module, fn.__name__, args, kwargs)
#                 finally:
#                     _local.in_hook = False

#             # Execute the function body
#             result = await fn(*args, **kwargs)

#             # Record exit without blocking nested calls
#             ensure_hook_flag()
#             if not _local.in_hook:
#                 _local.in_hook = True
#                 try:
#                     _on_return(module, fn.__name__, result)
#                 finally:
#                     _local.in_hook = False

#             return result

#         async_wrapper.__wrapped__ = fn
#         return async_wrapper

#     else:
#         @wraps(fn)
#         def sync_wrapper(*args, **kwargs):
#             # Record entry without blocking nested calls
#             ensure_hook_flag()
#             if not _local.in_hook:
#                 _local.in_hook = True
#                 try:
#                     _on_call(module, fn.__name__, args, kwargs)
#                 finally:
#                     _local.in_hook = False

#             print(f"[DEBUG] entering {module}.{fn.__name__}")   # ← add this
#             result = fn(*args, **kwargs)
#             print(f"[DEBUG] exiting {module}.{fn.__name__} → {type(result).__name__}")

#             # Record exit without blocking nested calls
#             ensure_hook_flag()
#             if not _local.in_hook:
#                 _local.in_hook = True
#                 try:
#                     _on_return(module, fn.__name__, result)
#                 finally:
#                     _local.in_hook = False

#             return result

#         sync_wrapper.__wrapped__ = fn
#         return sync_wrapper


# #cli.py
# import sys
# import runpy
# import argparse
# from pathlib import Path

# from pylya.hook_loader import install_hooks
# from pylya.analysis import PerfAnalyzer, TypeExtractor

# __version__ = "0.1.0"

# ANALYSIS_MAP = {
#     "perf": PerfAnalyzer,
#     "types": TypeExtractor,
# }


# def main():
#     parser = argparse.ArgumentParser(
#         description="Learn or enforce module dependencies and hook enforcement"
#     )
#     parser.add_argument(
#         "-v", "--version",
#         action="version", version=__version__,
#         help="Show the tool version"
#     )
#     parser.add_argument(
#         "-m", "--mode",
#         choices=["learn", "enforce"], required=True,
#         help="Mode: 'learn' to generate events/deps/allowlist; 'enforce' to apply an existing allowlist"
#     )
#     parser.add_argument(
#         "-c", "--config",
#         default="config.json",
#         help="Path to config.json defining hook targets"
#     )
#     parser.add_argument(
#         "-a", "--analyses",
#         nargs="*",
#         choices=ANALYSIS_MAP.keys(),
#         default=[],
#         help="Analyses to run (only in learn mode): perf, types"
#     )
#     parser.add_argument(
#         "-o", "--outdir",
#         default=".",
#         help="Directory to write analysis logs (learn mode)"
#     )
#     parser.add_argument(
#         "--allowlist",
#         default="allowlist.json",
#         help="Path to allowlist.json (only in enforce mode, defaults to cwd/allowlist.json)"
#     )
#     parser.add_argument(
#         "script",
#         help="Target Python script to execute under hooks"
#     )
#     parser.add_argument(
#         "args",
#         nargs=argparse.REMAINDER,
#         help="Arguments to pass to the target script"
#     )

#     args = parser.parse_args()
#     outdir = Path(args.outdir)

#     if args.mode == "learn":
#         # Prepare output directory for analysis logs
#         outdir.mkdir(parents=True, exist_ok=True)
#         analyses = [ANALYSIS_MAP[name](outfile=str(outdir / f"{name}.log"))
#                     for name in args.analyses]

#         # Install hooks in learn mode; JSON reports are auto-written to cwd
#         install_hooks(
#             config_path=args.config,
#             mode="learn",
#             analyses=analyses
#         )

#         # Execute the script under instrumentation
#         sys.argv = [args.script] + (args.args or [])
#         runpy.run_path(args.script, run_name="__main__")
#         print(f"Learn mode complete. Logs in {outdir}, JSON reports (events.json, dependencies.json, allowlist.json) in current directory.")

#     else:
#         # Enforce mode: use existing allowlist to block disallowed calls
#         install_hooks(
#             config_path=args.config,
#             mode="enforce",
#             analyses=[],
#             allowlist_path=args.allowlist
#         )

#         # Execute the script under enforcement
#         sys.argv = [args.script] + (args.args or [])
#         runpy.run_path(args.script, run_name="__main__")

# if __name__ == "__main__":
#     main()