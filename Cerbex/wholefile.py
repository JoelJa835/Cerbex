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
    """
    Extracts return types of each function call with zero I/O overhead during execution.
    Buffers type info in memory and dumps to file at program exit.
    """
    def __init__(self, outfile: str = "types.log") -> None:
        self.outfile = outfile
        self.exclude_prefixes = {
            'builtins', '__builtins__', 'fastapi', 'pydantic', 
            'starlette', '_json'
        }
        
        # Buffer for (module.func, type_name) tuples
        self._buffer: List[Tuple[str, str]] = []
        # Register dump at program exit
        atexit.register(self._dump)

    def on_return(self, module: str, func: str, result: Any) -> None:
        # Skip library internals, only log user code
        if any(module.startswith(prefix) for prefix in self.exclude_prefixes):
            return
        
        # Buffer the type information instead of writing immediately
        self._buffer.append((f"{module}.{func}", type(result).__name__))
    
    def results(self) -> List[Tuple[str, str]]:
        """
        Returns the list of ("module.func", type_name) tuples.
        """
        return list(self._buffer)

    def _dump(self) -> None:
        """
        Writes all buffered type information to the output file in one batch.
        """
        if not self._buffer:
            return
        lines = [f"[Type] {name} returned {type_name}\n" for name, type_name in self._buffer]
        with open(self.outfile, "a") as f:
            f.writelines(lines)



##cli.py
import sys
import runpy
import argparse
from pathlib import Path

from pylya.hook_loader import install_hooks
from pylya.analysis import PerfAnalyzer, TypeExtractor

__version__ = "0.1.0"

ANALYSIS_MAP = {
    "perf": PerfAnalyzer,
    "types": TypeExtractor
}


def main():
    parser = argparse.ArgumentParser(
        description="Learn or enforce module dependencies and hook enforcement"
    )
    parser.add_argument(
        "-v", "--version",
        action="version", version=__version__,
        help="Show the tool version"
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["learn", "enforce"], required=True,
        help="Mode: 'learn' to generate events/deps/allowlist; 'enforce' to apply an existing allowlist"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Path to config.json defining hook targets"
    )
    parser.add_argument(
        "-a", "--analyses",
        nargs="*",
        choices=ANALYSIS_MAP.keys(),
        default=[],
        help="Analyses to run (only in learn mode): perf, types"
    )
    parser.add_argument(
        "-o", "--outdir",
        default=".",
        help="Directory to write analysis logs (learn mode)"
    )
    parser.add_argument(
        "--allowlist",
        default="allowlist.json",
        help="Path to allowlist.json (only in enforce mode, defaults to cwd/allowlist.json)"
    )
    parser.add_argument(
        "script",
        help="Target Python script to execute under hooks"
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to the target script"
    )
    parser.add_argument("--no-log", action="store_true",
                    help="Disable in-memory event recording (imports/calls/returns)")

    args = parser.parse_args()
    outdir = Path(args.outdir)

    if args.mode == "learn":
        # Prepare output directory for analysis logs
        outdir.mkdir(parents=True, exist_ok=True)
        analyses = [ANALYSIS_MAP[name](outfile=str(outdir / f"{name}.log"))
                    for name in args.analyses]

        # Install hooks in learn mode; JSON reports are auto-written to cwd
        install_hooks(
            config_path=args.config,
            mode="learn",
            analyses=analyses,
            log_events=not args.no_log
        )

        # Execute the script under instrumentation
        sys.argv = [args.script] + (args.args or [])
        runpy.run_path(args.script, run_name="__main__")
        print(f"Learn mode complete. Logs in {outdir}, JSON reports (events.json, dependencies.json, allowlist.json) in current directory.")

    else:
        # Enforce mode: use existing allowlist to block disallowed calls
        install_hooks(
            config_path=args.config,
            mode="enforce",
            analyses=[],
            allowlist_path=args.allowlist,
            log_events=not args.no_log
        )

        # Execute the script under enforcement
        sys.argv = [args.script] + (args.args or [])
        runpy.run_path(args.script, run_name="__main__")

if __name__ == "__main__":
    main()



# File: hook_loader.py
"""
Standalone hook loader for your project. Import this at startup to enable Lyapy instrumentation.
"""
import sys
import atexit
import json
from typing import Dict, List, Tuple

from pylya.hook_manager import HookManager, Analysis
from pylya.importer import install_import_hook, rewrap_existing_targets, mark_loaded_c_exts



def _load_config(path: str = 'config.json') -> Tuple[list, None]:
    """
    Load 'targets' from JSON config file.  Allowlist is now handled separately.
    """
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        return data.get('targets', []), None
    except FileNotFoundError:
        return [], None


def _load_allowlist(path: str = 'allowlist.json') -> Dict[str, list]:
    """
    Load generated allowlist for enforce mode.
    """
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        # Expect top-level 'allowlist' key
        return data.get('allowlist', {})
    except FileNotFoundError:
        return {}


def install_hooks(
    config_path: str = 'config.json',
    mode: str       = 'learn',
    analyses        = None,
    allowlist_path: str = 'allowlist.json',
    log_events=True
) -> HookManager:
    # 1) load config & allowlist

    # print(mode)
    # print(allowlist_path)
    targets, _   = _load_config(config_path)
    raw_allowlist = mode == 'enforce' and _load_allowlist(allowlist_path) or {}

    if analyses is None:
        analyses = []

    # 2) always create a HookManager
    hook_mgr = HookManager(targets, analyses, mode=mode, allowlist=raw_allowlist,log_events=log_events)


    # 4) install hooks
    install_import_hook(hook_mgr, targets)

    mark_loaded_c_exts(hook_mgr)
    rewrap_existing_targets(hook_mgr, targets)
    sys.setprofile(hook_mgr.c_profile)

    # 5) register the exit handler
  
    atexit.register(hook_mgr.write_reports)

    return hook_mgr

# File: hook_manager.py
import json
import threading
import builtins
from typing import Any, Dict, List, Optional, Set
from functools import wraps
import logging
logger = logging.getLogger(__name__)


def safe_hook(fn):
    """
    Ultra-defensive decorator that handles ANY exception type, including:
    - TypeError from malformed exception classes
    - SystemExit, KeyboardInterrupt
    - Custom exceptions that don't inherit properly
    """
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception as e:
            # don't crash the program for analysis failures, but keep the signal exceptions
            logger.exception("analysis hook failed: %s", e)
            return None
    return wrapper

class Analysis:
    """
    Base hook interface: override any of these methods.
    """
    def on_import(self, parent: Optional[str], name: str) -> None: ...
    def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None: ...
    def on_return(self, module: str, func: str, result: Any) -> None: ...

class HookManager:
    def __init__(
        self,
        targets: List[str],
        analyses: List[Analysis],
        mode: str = 'learn',
        log_events=True,
        allowlist: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.analyses = analyses
        self.mode = mode
        self.log_events = log_events
        self.allowlist = allowlist or {}
        self.targets  = targets
        self.dep_graph: Dict[str, Set[str]] = {}
        self.events: Dict[str, Set[str]] = {}
        self._local = threading.local()
        # Track C extension modules we care about
        self.c_ext_modules: Set[str] = set()

    def _record_event(self, module: str, tag: str) -> None:
        mod = module or '__main__'
        self.events.setdefault(mod, builtins.set()).add(tag)
    
    def on_import(self, parent: Optional[str], name: str) -> None:
        parent_mod = parent or '__main__'
        self.dep_graph.setdefault(parent_mod, builtins.set()).add(name)

        if self.mode == "learn" and self.log_events:
            self._record_event(parent_mod, f"import:{name}")
        elif self.mode == 'enforce' and parent and name not in self.allowlist.get(parent, []):
            # enforcement must escape
            raise ImportError(f"Import of {name} not allowed in module {parent}")

        # safe analysis callbacks
        self._safe_on_import(parent, name)

    @safe_hook
    def _safe_on_import(self, parent: Optional[str], name: str) -> None:
        for a in self.analyses:
            a.on_import(parent, name)

    def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None:
        if self.mode == "learn" and self.log_events:
            self._record_event(module, f"call:{func}")
        elif self.mode == 'enforce':
            allowed = self.allowlist.get(module, [])
            if func not in allowed:
                # enforcement must escape
                raise RuntimeError(f"[SECURITY] Blocked unauthorized call: {module}.{func}()")

        # safe analysis callbacks
        self._safe_on_call(module, func, args, kwargs)

    @safe_hook
    def _safe_on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None:
        for a in self.analyses:
            a.on_call(module, func, args, kwargs)


    # -------------------------------
    # Return hook + safe wrapper
    # -------------------------------
    def on_return(self, module: str, func: str, result: Any) -> None:
        if self.mode == "learn" and self.log_events:
            self._record_event(module, f"return:{func}")

        # safe analysis callbacks
        self._safe_on_return(module, func, result)

    @safe_hook
    def _safe_on_return(self, module: str, func: str, result: Any) -> None:
        for a in self.analyses:
            a.on_return(module, func, result)

    # This is a sys.setprofile() callback function that monitors C function calls
    def c_profile(self, frame, event, arg):
        """
        Profile callback that tracks calls to C extension modules.
        
        This gets called by Python's profiling system for every function call/return.
        It's designed to monitor and log calls to C extensions specifically.
        """

        # STEP 1: Prevent infinite recursion
        # reentrancy guard - if we're already inside this hook, don't run again
        if getattr(self._local, 'in_hook', False):
            return  # Exit early to prevent infinite loops
        
        # STEP 2: Filter for C function events only
        if event not in ("c_call", "c_return"):
            return  # Only care about C function calls/returns, ignore Python calls
        
        # STEP 3: Get the C function being called
        fn = arg  # For c_call/c_return events, 'arg' is the C function object
        
        # STEP 4: Determine which module the function belongs to
        mod = getattr(fn, '__module__', '__builtins__') or '__builtins__'
        # STEP 5: Optional filtering - only track specific C modules
        # If c_ext_modules is populated, only log calls to those modules
        if mod not in self.c_ext_modules:
            return  # Skip if this module isn't in our tracking list
        
        # STEP 6: Get function name
        name = getattr(fn, '__name__', '<c_func>')  # Function name or default
        
        # STEP 7: Set reentrancy guard
        self._local.in_hook = True  # Mark that we're inside the hook
        
        try:
            # STEP 8: Handle the specific event type
            if event == 'c_call':
                # C function is being called
                self.on_call(mod, name, (), {})  # Log the call (no args/kwargs available)
            else:  # event == 'c_return'
                # C function is returning
                # Note: Python's profiler can't see C function return values
                self.on_return(mod, name, None)  # Log return with None value
        finally:
            # STEP 9: Always clear the reentrancy guard
            self._local.in_hook = False



    def record_allowlist(self) -> Dict[str, List[str]]:
        return {m: sorted(list(deps)) for m, deps in self.dep_graph.items()}


    def write_reports(self, deps_path='dependencies.json', events_path='events.json', allowlist_path='allowlist.json'):
        if self.mode == 'enforce':
            return

        deps = self.record_allowlist()
        with open(deps_path, 'w') as f:
            json.dump({'dependencies': deps}, f, indent=2)

        # events already in memory
        events_out = {module: {event: True for event in tags} for module, tags in self.events.items()}
        with open(events_path, 'w') as f:
            json.dump(events_out, f, indent=2)

        # build allowlist from dep_graph + events in memory
        allow = {m: sorted(list(deps)) for m, deps in self.dep_graph.items()}
        for module, tags in self.events.items():
            calls = [tag.split(':', 1)[1] for tag in tags if tag.startswith('call:')]
            if calls:
                allow.setdefault(module, []).extend(calls)
                allow[module] = sorted(set(allow[module]))

        with open(allowlist_path, 'w') as f:
            json.dump({'allowlist': allow}, f, indent=2)




# File: importer.py
import builtins
import sys
import importlib
import importlib.abc
import importlib.machinery
import inspect
import functools
from types import ModuleType, FunctionType, MethodType
from typing import List, Any
from weakref import WeakKeyDictionary

from pylya.hook_manager import HookManager
from pylya.utils import make_wrapper

# Cache: original function → wrapper
_wrap_cache: "WeakKeyDictionary[FunctionType, FunctionType]" = WeakKeyDictionary()
# Primitives we don’t instrument
PRIMITIVES = (str, int, float, bool, bytes, type(None))

class LazyWrapper:
    def __init__(self, name, orig_val, module_name, hook_mgr):
        self.name = name
        self.orig_val = orig_val
        self.module_name = module_name
        self.hook_mgr = hook_mgr
        self._wrapped = None

    def __get__(self, instance, owner):
        if self._wrapped is None:
            self._wrapped = wrap_value(self.orig_val, self.module_name, self.hook_mgr)
        return self._wrapped if instance is None else self._wrapped.__get__(instance, owner)

def should_wrap(attr_name: str, attr_val: Any) -> bool:
    """
    Determine if an attribute should be wrapped with instrumentation.
    Returns True for functions/methods that should be monitored.
    """
    # Skip dunder methods and private attributes
    if attr_name.startswith('__'):
        return False
    
    # Skip class attributes, descriptors, and other non-callable items
    if not callable(attr_val):
        return False
    
    # Skip already wrapped functions
    if hasattr(attr_val, '__wrapped__'):
        return False
    
    # Skip built-in functions (they'll be caught by sys.setprofile anyway)
    if isinstance(attr_val, type(len)):  # built-in function type
        return False
    
    # Only wrap actual functions and methods
    return isinstance(attr_val, (FunctionType, MethodType))

def wrap_value(val, module_name: str, hook_mgr: HookManager):

    # primitives & modules stay
    if isinstance(val, PRIMITIVES) or isinstance(val, ModuleType):
        return val

    try:

        if inspect.isclass(val) and val.__module__ == module_name:
            for attr_name, attr_val in list(val.__dict__.items()):
                if should_wrap(attr_name, attr_val):  # filtering logic
                    setattr(val, attr_name, LazyWrapper(attr_name, attr_val, module_name, hook_mgr))
            return val
        # 2) Functions & bound methods
        if isinstance(val, (FunctionType, MethodType)) and val.__module__.startswith(module_name):
           
            cached = _wrap_cache.get(val)
            if cached is not None:
                return cached

            if val.__name__ in ('__repr__', '__str__') or hasattr(val, '__wrapped__'):
                return val

            is_async = inspect.iscoroutinefunction(val) or inspect.isasyncgenfunction(val)
            wrapper = make_wrapper(val, module_name, hook_mgr, is_async)
             # ✅ Preserve __name__, __qualname__, __doc__, __annotations__, __signature__, etc.
            wrapper = functools.update_wrapper(wrapper, val)
             # ✅ Explicitly preserve __signature__
            try:
                wrapper.__signature__ = inspect.signature(val)
            except Exception:
                pass
            _wrap_cache[val] = wrapper
            return wrapper

    except:
        # If wrapping fails for any reason, return original
        pass

    return val



class InstrumentLoader(importlib.abc.Loader):
    def __init__(self, hook_mgr: HookManager, orig_loader: importlib.abc.Loader):
        self.hook_mgr = hook_mgr
        self.orig_loader = orig_loader

    def create_module(self, spec):
        return self.orig_loader.create_module(spec)

    def exec_module(self, module):
        parent = module.__spec__.parent or module.__name__
        if parent != module.__name__:  
            self.hook_mgr.on_import(parent, module.__name__)

        try:
            source = self.orig_loader.get_source(module.__name__)
        except Exception:
            source = None

        if source is None:
            self.orig_loader.exec_module(module)
        else:
            code = compile(source, module.__spec__.origin, 'exec')
            exec(code, module.__dict__, module.__dict__)

        for attr_name, attr_val in list(module.__dict__.items()):
            if not attr_name.startswith('__'):
                try:
                    module.__dict__[attr_name] = wrap_value(
                        attr_val, module.__name__, self.hook_mgr
                    )
                except Exception:
                    pass


class InstrumentFinder(importlib.abc.MetaPathFinder):
    def __init__(self, hook_mgr: HookManager, targets: List[str]):
        self.hook_mgr = hook_mgr
        self.targets = set(targets)

    def _matches(self, fullname: str) -> bool:
        matches = any(
            fullname == t or (t.endswith('*') and fullname.startswith(t[:-1]))
            for t in self.targets
        )
        
        return matches
    

    def find_spec(self, fullname, path, target=None):
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and self._matches(fullname):
            origin = getattr(spec, "origin", None) or ""
            if origin.endswith(".py"):
                spec.loader = InstrumentLoader(self.hook_mgr, spec.loader)
            elif origin.endswith((".so", ".pyd")):
                self.hook_mgr.c_ext_modules.add(fullname)
        return spec


def install_import_hook(
    hook_mgr: HookManager,
    targets: List[str],
    replace_import_module: bool = True
) -> None:
    """
    Install a unified import hook and instrumentation finder/loader.
    - Uses MetaPathFinder to log and instrument target modules on first load.
    - Falls back to a __import__ wrapper to catch cached or C-level imports.
    """
    # 1) Insert unified finder for logging & instrumentation
    sys.meta_path.insert(0, InstrumentFinder(hook_mgr, targets))

    # 2) Fallback for imports not seen by the finder (e.g., cached or C extensions)
    orig_import = builtins.__import__
    def fallback_import(name, globals=None, locals=None, fromlist=(), level=0):
        parent = globals.get('__name__') if globals else None
        parent_mod = parent or '__main__'

        # print(f"📦 [__import__ fallback] {parent_mod} → import {name}")
        # Record import only if finder did not log it
        if name not in hook_mgr.dep_graph.get(parent_mod, set()):
            hook_mgr.on_import(parent, name)
        return orig_import(name, globals, locals, fromlist, level)
    builtins.__import__ = fallback_import

    # 3) Preserve optional import_module instrumentation
    if replace_import_module:
        real_import_module = importlib.import_module
        def instrumented_import_module(name, package=None):
            module = real_import_module(name, package)
            for attr in dir(module):
                if not attr.startswith('__'):
                    try:
                        raw = getattr(module, attr)
                        setattr(
                            module,
                            attr,
                            wrap_value(raw, module.__name__, hook_mgr)
                        )
                    except Exception:
                        pass
            return module
        importlib.import_module = instrumented_import_module

def rewrap_existing_targets(hook_mgr: HookManager, targets: List[str]):
    """
    Go through already-loaded target modules in sys.modules and wrap their top-level functions.
    This ensures instrumentation even for modules that were imported before the hooks were installed.
    """
    for name in targets:
        mod = sys.modules.get(name)
        if not mod:
            continue
        for attr in dir(mod):
            if not attr.startswith('__'):
                try:
                    raw = getattr(mod, attr)
                    wrapped = wrap_value(raw, name, hook_mgr)
                    setattr(mod, attr, wrapped)
                except Exception:
                    pass
# Most robust version
def mark_loaded_c_exts(hook_mgr):
    """Most robust version with additional checks"""
    for name, mod in sys.modules.items():
        spec = getattr(mod, "__spec__", None)
        
        # Skip if no module object
        if mod is None:
            continue
            
        # Extension modules (.so/.pyd files)
        is_extension = (spec and 
                       getattr(spec, "origin", None) and 
                       spec.origin.endswith((".so", ".pyd")))
        
        # Built-in modules
        is_builtin = name in sys.builtin_module_names
        
        # Additional check for frozen modules (like zipimport)
        is_frozen = (spec and 
                    spec.origin == "frozen" or
                    getattr(mod, "__file__", None) is None and 
                    hasattr(mod, "__loader__") and
                    type(mod.__loader__).__name__ in ["FrozenImporter", "BuiltinImporter"])
        
        if is_extension or is_builtin or is_frozen:
            hook_mgr.c_ext_modules.add(name)


# File: utils.py
import inspect
from functools import wraps
from typing import Any, Callable
from pylya.hook_manager import HookManager


def make_wrapper(
    fn: Callable,
    module: str,
    hook_mgr: HookManager,
    is_async: bool
) -> Callable:
    """
    Return a wrapper that calls hook_mgr.on_call/on_return
    around fn, respecting async vs. sync.
    """
    _local = hook_mgr._local
    _on_call = hook_mgr.on_call
    _on_return = hook_mgr.on_return

    def ensure_hook_flag():
        if not hasattr(_local, 'in_hook'):
            _local.in_hook = False

    if is_async:
        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            # Record entry without blocking nested calls
            ensure_hook_flag()
            if not _local.in_hook:
                _local.in_hook = True
                try:
                    _on_call(module, fn.__name__, args, kwargs)
                finally:
                    _local.in_hook = False

            # Execute the function body
            result = await fn(*args, **kwargs)

            # Record exit without blocking nested calls
            ensure_hook_flag()
            if not _local.in_hook:
                _local.in_hook = True
                try:
                    _on_return(module, fn.__name__, result)
                finally:
                    _local.in_hook = False

            return result

        async_wrapper.__wrapped__ = fn
        return async_wrapper

    else:
        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            # Record entry without blocking nested calls
            ensure_hook_flag()
            if not _local.in_hook:
                _local.in_hook = True
                try:
                    _on_call(module, fn.__name__, args, kwargs)
                finally:
                    _local.in_hook = False

            result = fn(*args, **kwargs)

            # Record exit without blocking nested calls
            ensure_hook_flag()
            if not _local.in_hook:
                _local.in_hook = True
                try:
                    _on_return(module, fn.__name__, result)
                finally:
                    _local.in_hook = False

            return result

        sync_wrapper.__wrapped__ = fn
        return sync_wrapper