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
















