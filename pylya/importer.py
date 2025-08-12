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
    # EXCLUDE_PREFIXES = ('fastapi', 'pydantic', 'starlette')
    # if module_name.startswith(EXCLUDE_PREFIXES):
    #     return val

    try:

        if inspect.isclass(val) and val.__module__ == module_name:
            for attr_name, attr_val in list(val.__dict__.items()):
                if should_wrap(attr_name, attr_val):  # filtering logic
                    setattr(val, attr_name, LazyWrapper(attr_name, attr_val, module_name, hook_mgr))
            return val
        # 2) Functions & bound methods
        if isinstance(val, (FunctionType, MethodType)) and val.__module__.startswith(module_name):
            # print(f"🔀 wrap_value called for module_name='{module_name}', val.__module__='{val.__module__}', fn={val.__name__}")
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
        # 1) Always record first-time imports via on_import
        #    Finder only sees non-cached modules
        # self.hook_mgr.on_import(None, fullname)

        # 2) Delegate to default PathFinder
        # spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        # if spec and self._matches(fullname):
        #     spec.loader = InstrumentLoader(self.hook_mgr, spec.loader)
        # return spec
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        # print(f"DEBUG: fullname={fullname}, spec={spec is not None}", file=sys.stderr)
        if spec and self._matches(fullname):
            origin = getattr(spec, "origin", None) or ""
            if origin.endswith(".py"):
                # print(f"PY MODULE: {fullname}", file=sys.stderr)
                spec.loader = InstrumentLoader(self.hook_mgr, spec.loader)
            elif origin.endswith((".so", ".pyd")):
                # print(f"C MODULE: {fullname}", file=sys.stderr)
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
            # print(f"C MODULE: {name}", file=sys.stderr)
            hook_mgr.c_ext_modules.add(name)



# def mark_loaded_c_exts(hook_mgr):
#         for name, mod in sys.modules.items():
#             print(name)
#             spec = getattr(mod, "__spec__", None)
#             if spec and getattr(spec, "origin", None) and spec.origin.endswith((".so", ".pyd")):
#                 print(f"C MODULE: {name}", file=sys.stderr)
#                 hook_mgr.c_ext_modules.add(name)

#     def find_spec(self, fullname, path, target=None):
#         spec = importlib.machinery.PathFinder.find_spec(fullname, path)
#         if spec:
#             if self._matches(fullname):
#                 spec.loader = InstrumentLoader(self.hook_mgr, spec.loader)
#         return spec


# def install_import_hook(
#     hook_mgr: HookManager,
#     targets: List[str],
#     replace_import_module: bool = True
# ) -> None:
#     orig_import = builtins.__import__

#     def hooked_import(name, globals=None, locals=None, fromlist=(), level=0):
#         parent = globals.get('__name__') if globals else None
#         hook_mgr.on_import(parent, name)
#         return orig_import(name, globals, locals, fromlist, level)

#     builtins.__import__ = hooked_import
#     sys.meta_path.insert(0, InstrumentFinder(hook_mgr, targets))

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






















# # Cache: original function → wrapper
# _wrap_cache: "WeakKeyDictionary[FunctionType, FunctionType]" = WeakKeyDictionary()
# # Primitives we don’t instrument
# PRIMITIVES = (str, int, float, bool, bytes, type(None))


# # def wrap_value(val, module_name: str, hook_mgr: HookManager):
# #     try:
# #         # primitives & modules stay
# #         if isinstance(val, PRIMITIVES) or isinstance(val, ModuleType):
# #             return val

# #         if inspect.isclass(val) and val.__module__ == module_name:
# #             orig_cls = val

# #             # 1) Your existing recursive wrap of methods & nested classes
# #             for attr_name, attr_val in list(orig_cls.__dict__.items()):
# #                 wrapped = wrap_value(attr_val, module_name, hook_mgr)
# #                 if wrapped is not attr_val:
# #                     setattr(orig_cls, attr_name, wrapped)

# #             # 2) Inject instance-level attribute-access hooks
# #             module_for_hooks = orig_cls.__module__

# #             def __getattribute__(self, name):
# #                 hook_mgr.on_attr_read(module_for_hooks, self, name)
# #                 return super(orig_cls, self).__getattribute__(name)

# #             def __setattr__(self, name, value):
# #                 hook_mgr.on_attr_write(module_for_hooks, self, name, value)
# #                 return super(orig_cls, self).__setattr__(name, value)

# #             setattr(orig_cls, "__getattribute__", __getattribute__)
# #             setattr(orig_cls, "__setattr__", __setattr__)

# #             return orig_cls

# #         # if inspect.isclass(val) and val.__module__ == module_name:
# #         #     for attr_name, attr_val in list(val.__dict__.items()):
# #         #         wrapped = wrap_value(attr_val, module_name, hook_mgr)
# #         #         if wrapped is not attr_val:
# #         #             setattr(val, attr_name, wrapped)
# #         #     return val
       
    

# #         # 2) Functions & bound methods
# #         if isinstance(val, (FunctionType, MethodType)) and val.__module__.startswith(module_name):
            
# #             cached = _wrap_cache.get(val)
# #             if cached is not None:
# #                 return cached

# #             if val.__name__ in ('__repr__', '__str__') or hasattr(val, '__wrapped__'):
# #                 return val

# #             is_async = inspect.iscoroutinefunction(val)
# #             wrapper = make_wrapper(val, module_name, hook_mgr, is_async)
# #             _wrap_cache[val] = wrapper
# #             return wrapper

# #         # 3) Everything else
# #         return val
# #     except Exception:
# #         return val
# def wrap_value(val, module_name: str, hook_mgr: HookManager):
#     try:
#         # ❗ Skip if this module is excluded
#         for pat in hook_mgr.excludes:
#             if module_name == pat or (pat.endswith("*") and module_name.startswith(pat[:-1])):
#                 return val
#         # 0) Primitives & modules: skip
#         if isinstance(val, PRIMITIVES) or isinstance(val, ModuleType):
#             return val

#         # 1) Wrap classes
#         if inspect.isclass(val) and val.__module__ == module_name:
#             orig_cls = val

#             # Wrap class methods / attributes
#             for attr_name, attr_val in list(orig_cls.__dict__.items()):
#                 wrapped = wrap_value(attr_val, module_name, hook_mgr)
#                 if wrapped is not attr_val:
#                     setattr(orig_cls, attr_name, wrapped)

#             # Inject attribute read/write hooks
#             module_for_hooks = orig_cls.__module__

#             def __getattribute__(self, name):
#                 hook_mgr.on_attr_read(module_for_hooks, self, name)
#                 return super(orig_cls, self).__getattribute__(name)

#             def __setattr__(self, name, value):
#                 hook_mgr.on_attr_write(module_for_hooks, self, name, value)
#                 return super(orig_cls, self).__setattr__(name, value)

#             setattr(orig_cls, "__getattribute__", __getattribute__)
#             setattr(orig_cls, "__setattr__", __setattr__)

#             return orig_cls

#         # 2) Wrap functions & methods (including decorated ones)
#         if isinstance(val, (FunctionType, MethodType)):
#             # Unwrap if decorated (e.g. @app.get)
#             original = getattr(val, "__wrapped__", val)

#             # Only wrap if it's from this module
#             mod = getattr(original, "__module__", None)
#             if not mod or not mod.startswith(module_name):
#                 return val
#             # if module_name not in getattr(original, "__module__", ""):
#             #     return val


#             # Skip dunder repr/str
#             if original.__name__ in ("__repr__", "__str__"):
#                 return val

#             # Avoid double-wrapping
#             cached = _wrap_cache.get(original)
#             if cached is not None:
#                 return cached

#             is_async = inspect.iscoroutinefunction(original)
#             wrapper = make_wrapper(original, module_name, hook_mgr, is_async)
#             _wrap_cache[original] = wrapper
#             # print(f"[WRAP] Wrapped {original.__module__}.{original.__name__} (async={is_async})")

#             # Preserve signature & __wrapped__
#             if hasattr(val, "__signature__"):
#                 wrapper.__signature__ = val.__signature__
#             wrapper.__wrapped__ = original

#             return wrapper

#         # 3) Everything else: return unchanged
#         return val

#     except Exception:
#         return val








