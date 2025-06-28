# File: importer.py
import builtins
import sys
import importlib
import importlib.abc
import importlib.machinery
import inspect
from types import ModuleType, FunctionType
from typing import List
from weakref import WeakKeyDictionary

from hook_manager import HookManager
from utils import make_wrapper



# Cache: original function → wrapper
_wrap_cache: "WeakKeyDictionary[FunctionType, FunctionType]" = WeakKeyDictionary()
# Primitives we don’t instrument
PRIMITIVES = (str, int, float, bool, bytes, type(None))


def wrap_value(val, module_name: str, hook_mgr: HookManager):
    if isinstance(val, PRIMITIVES) or isinstance(val, ModuleType):
        return val

    if isinstance(val, FunctionType) and val.__module__.startswith(module_name):
        # 1) Already wrapped?
        cached = _wrap_cache.get(val)
        if cached is not None:
            return cached

        # 2) Skip repr/str or already-wrapped markers
        if val.__name__ in ('__repr__', '__str__') or hasattr(val, '__wrapped__'):
            return val

        is_async = inspect.iscoroutinefunction(val)
        wrapper = make_wrapper(val, module_name, hook_mgr, is_async)

        # 3) Cache it
        _wrap_cache[val] = wrapper
        return wrapper

    return val



class InstrumentLoader(importlib.abc.Loader):
    def __init__(self, hook_mgr: HookManager, orig_loader: importlib.abc.Loader):
        self.hook_mgr = hook_mgr
        self.orig_loader = orig_loader

    def create_module(self, spec):
        return self.orig_loader.create_module(spec)

    def exec_module(self, module):
        parent = module.__spec__.parent or module.__name__
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
        return any(
            fullname == t or (t.endswith('*') and fullname.startswith(t[:-1]))
            for t in self.targets
        )

    def find_spec(self, fullname, path, target=None):
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and self._matches(fullname):
            spec.loader = InstrumentLoader(self.hook_mgr, spec.loader)
        return spec


def install_import_hook(
    hook_mgr: HookManager,
    targets: List[str],
    replace_import_module: bool = True
) -> None:
    orig_import = builtins.__import__

    def hooked_import(name, globals=None, locals=None, fromlist=(), level=0):
        parent = globals.get('__name__') if globals else None
        hook_mgr.on_import(parent, name)
        return orig_import(name, globals, locals, fromlist, level)

    builtins.__import__ = hooked_import
    sys.meta_path.insert(0, InstrumentFinder(hook_mgr, targets))

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