import json
import threading
from typing import Any, Dict, List, Optional, Set

class Analysis:
    """
    Base hook interface: override any of these methods.
    """
    def on_import(self, parent: Optional[str], name: str) -> None: ...
    def on_call(self, module: str, func: str, args: tuple, kwargs: dict) -> None: ...
    def on_return(self, module: str, func: str, result: Any) -> None: ...
    def on_attr_read(self, module: str, obj: Any, attr: str) -> None: ...
    def on_attr_write(self, module: str, obj: Any, attr: str, value: Any) -> None: ...


# class Analysis:
#     """
#     Base class for instrumentation plugins.
#     Override any of the following hooks as needed:
#       - on_import(parent_module, imported_name)
#       - on_call(module_name, func_name, args, kwargs)
#       - on_return(module_name, func_name, result)
#       - on_attr_read(module_name, obj, attr)
#       - on_attr_write(module_name, obj, attr, value)
#     """
#     def on_import(self, parent, name): pass
#     def on_call(self, module, func, args, kwargs): pass
#     def on_return(self, module, func, result): pass
#     def on_attr_read(self, module, obj, attr): pass
#     def on_attr_write(self, module, obj, attr, value): pass

class HookManager:
    def __init__(
        self,
        analyses: List[Analysis],
        mode: str = 'learn',
        allowlist: Optional[Dict[str, List[str]]] = None
    ) -> None:
        self.analyses = analyses
        self.mode = mode
        self.allowlist = allowlist or {}
        self.dep_graph: Dict[str, Set[str]] = {}
        self.events: Dict[str, Set[str]] = {}
        self._local = threading.local()

    def _record_event(self, module: str, tag: str) -> None:
        mod = module or '__main__'
        self.events.setdefault(mod, set()).add(tag)

    def on_import(self, parent: Optional[str], name: str) -> None:
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
                self.on_return(mod, name, None)
        finally:
            self._local.in_hook = False


    def record_allowlist(self) -> Dict[str, List[str]]:
        return {m: sorted(list(deps)) for m, deps in self.dep_graph.items()}

    def write_reports(
        self,
        deps_path: str = 'dependencies.json',
        events_path: str = 'events.json'
    ) -> None:
        deps = self.record_allowlist()
        with open(deps_path, 'w') as f:
            json.dump({'dependencies': deps}, f, indent=2)
        events_out = {m: {e: True for e in tags} for m, tags in self.events.items()}
        with open(events_path, 'w') as f:
            json.dump(events_out, f, indent=2)