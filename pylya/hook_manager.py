# File: hook_manager.py
import json
import threading
import builtins
from typing import Any, Dict, List, Optional, Set

from functools import wraps

# File: hook_manager.py
import json
import threading
from typing import Any, Dict, List, Optional, Set

def safe_hook(fn):
    """Decorator: run hook method, but catch+ignore all exceptions."""
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception:
            # swallow everything
            return None
    return wrapper

class Analysis:
    """
    Base hook interface: override any of these methods.
    """
    def on_import(self, parent: Optional[str], name: str) -> None: ...
    def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None: ...
    def on_return(self, module: str, func: str, result: Any) -> None: ...
    def on_attr_read(self, module: str, obj: Any, attr: str) -> None: ...
    def on_attr_write(self, module: str, obj: Any, attr: str, value: Any) -> None: ...

class HookManager:
    def __init__(
        self,
        targets: List[str],
        analyses: List[Analysis],
        mode: str = 'learn',
        allowlist: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self.analyses = analyses
        self.mode = mode
        self.allowlist = allowlist or {}
        self.targets  = targets
        self.dep_graph: Dict[str, Set[str]] = {}
        self.events: Dict[str, Set[str]] = {}
        self._local = threading.local()

    def _record_event(self, module: str, tag: str) -> None:
        mod = module or '__main__'
        self.events.setdefault(mod, builtins.set()).add(tag)
    
    def on_import(self, parent: Optional[str], name: str) -> None:
        parent_mod = parent or '__main__'
        self.dep_graph.setdefault(parent_mod, builtins.set()).add(name)

        if self.mode == 'learn':
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
        if self.mode == 'learn':
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
        if self.mode == 'learn':
            self._record_event(module, f"return:{func}")

        # safe analysis callbacks
        self._safe_on_return(module, func, result)

    @safe_hook
    def _safe_on_return(self, module: str, func: str, result: Any) -> None:
        for a in self.analyses:
            a.on_return(module, func, result)


    # -------------------------------
    # Attribute-read hook + safe wrapper
    # -------------------------------
    def on_attr_read(self, module: str, obj: Any, attr: str) -> None:
        if self.mode == 'learn':
            self._record_event(module, f"read:{attr}")

        # safe analysis callbacks
        self._safe_on_attr_read(module, obj, attr)

    @safe_hook
    def _safe_on_attr_read(self, module: str, obj: Any, attr: str) -> None:
        for a in self.analyses:
            a.on_attr_read(module, obj, attr)


    # -------------------------------
    # Attribute-write hook + safe wrapper
    # -------------------------------
    def on_attr_write(self, module: str, obj: Any, attr: str, value: Any) -> None:
        if self.mode == 'learn':
            self._record_event(module, f"write:{attr}")

        # safe analysis callbacks
        self._safe_on_attr_write(module, obj, attr, value)

    @safe_hook
    def _safe_on_attr_write(self, module: str, obj: Any, attr: str, value: Any) -> None:
        for a in self.analyses:
            a.on_attr_write(module, obj, attr, value)

    def on_import(self, parent: Optional[str], name: str) -> None:
        # print(f"🧭 [on_import] {parent} imports {name}")
        parent_mod = parent or '__main__'
        self.dep_graph.setdefault(parent_mod, set()).add(name)
        if self.mode == 'learn':
            self._record_event(parent_mod, f"import:{name}")
        if self.mode == 'enforce' and parent and name not in self.allowlist.get(parent, []):
            raise ImportError(f"Import of {name} not allowed in module {parent}")
        for a in self.analyses:
            a.on_import(parent, name)

    def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None:
        if self.mode == 'learn':
            self._record_event(module, f"call:{func}")
        for a in self.analyses:
            a.on_call(module, func, args, kwargs)
    def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None:
        if self.mode == 'learn':
            self._record_event(module, f"call:{func}")

        # ❗ ENFORCE FUNCTION CALLS
        elif self.mode == 'enforce':
            allowed = self.allowlist.get(module, [])
            if func not in allowed:
                raise RuntimeError(f"[SECURITY] Blocked unauthorized call: {module}.{func}()")

        for a in self.analyses:
            a.on_call(module, func, args, kwargs)

    def on_return(self, module: str, func: str, result: Any) -> None:
        if self.mode == 'learn':
            self._record_event(module, f"return:{func}")
        for a in self.analyses:
            a.on_return(module, func, result)

    def on_attr_read(self, module: str, obj: Any, attr: str) -> None:
        if self.mode == 'learn':
            self._record_event(module, f"read:{attr}")
        for a in self.analyses:
            a.on_attr_read(module, obj, attr)

    def on_attr_write(self, module: str, obj: Any, attr: str, value: Any) -> None:
        if self.mode == 'learn':
            self._record_event(module, f"write:{attr}")
        for a in self.analyses:
            a.on_attr_write(module, obj, attr, value)


    def c_profile(self, frame, event, arg):
        # 1) Reentrancy guard first
        if getattr(self._local, 'in_hook', False):
            return

        # 2) Now mark that we’re in the hook
        self._local.in_hook = True
        try:
            # 3) Filter events immediately
            if event not in ("c_call", "c_return"):
                return

            fn = arg
            mod = getattr(fn, '__module__', '__builtins__') or '__builtins__'
            name = getattr(fn, '__name__', '<c_func>')
            if event == 'c_call':
                self.on_call(mod, name, (), {})
            else:
                # pass the real return value through!
                real_result = arg
                self.on_return(mod, name, real_result)
        finally:
            self._local.in_hook = False





    def record_allowlist(self) -> Dict[str, List[str]]:
        return {m: sorted(list(deps)) for m, deps in self.dep_graph.items()}


    def write_reports(
        self,
        deps_path: str = 'dependencies.json',
        events_path: str = 'events.json',
        allowlist_path: str = 'allowlist.json'
    ) -> None:

        if self.mode == 'enforce':
            return
        # Inline original write_reports behavior from BaseHookManager
        # 1) Write dependencies.json
        deps = self.record_allowlist()
        with open(deps_path, 'w') as f:
            json.dump({'dependencies': deps}, f, indent=2)

        # 2) Write events.json
        events_out = {module: {event: True for event in tags}
                      for module, tags in getattr(self, 'events', {}).items()}
        with open(events_path, 'w') as f:
            json.dump(events_out, f, indent=2)

        # 3) Build allowlist.json for enforce mode
        try:
            with open(events_path, 'r') as f:
                events = json.load(f)
        except FileNotFoundError:
            return

        # Start with import allowlist from dep_graph
        allow = {m: sorted(deps) for m, deps in self.dep_graph.items()}

        # Augment with call-based allowlist from events.json
        for module, tags in events.items():
            calls = [tag.split(':', 1)[1]
                    for tag, seen in tags.items()
                    if seen and tag.startswith('call:')]
            if calls:
                allow.setdefault(module, []).extend(calls)
                allow[module] = sorted(set(allow[module]))  # remove duplicates

        with open(allowlist_path, 'w') as f:
            json.dump({'allowlist': allow}, f, indent=2)













