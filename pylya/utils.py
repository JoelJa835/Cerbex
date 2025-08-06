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

            print(f"[DEBUG] entering {module}.{fn.__name__}")   # ← add this
            result = fn(*args, **kwargs)
            print(f"[DEBUG] exiting {module}.{fn.__name__} → {type(result).__name__}")

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

# def make_wrapper(
#     fn: Callable,
#     module: str,
#     hook_mgr: HookManager,
#     is_async: bool
# ) -> Callable:
#     _local     = hook_mgr._local
#     _on_call   = hook_mgr.on_call
#     _on_return = hook_mgr.on_return

#     def ensure_hook_flag():
#         if not hasattr(_local, 'in_hook'):
#             _local.in_hook = False

#     if is_async:
#         @wraps(fn)
#         async def async_wrapper(*args, **kwargs):
#             ensure_hook_flag()
#             if not _local.in_hook:
#                 _local.in_hook = True
#                 try:
#                     _on_call(module, fn.__name__, args, kwargs)
#                 finally:
#                     _local.in_hook = False

#             # print(f"[DEBUG] entering (async) {module}.{fn.__name__}")
#             result = await fn(*args, **kwargs)
#             # print(f"[DEBUG] exiting  (async) {module}.{fn.__name__} → {type(result).__name__}")

#             ensure_hook_flag()
#             if not _local.in_hook:
#                 _local.in_hook = True
#                 try:
#                     _on_return(module, fn.__name__, result)
#                 finally:
#                     _local.in_hook = False

#             return result

#         # ← Must set __wrapped__ and return the wrapper
#         async_wrapper.__wrapped__ = fn
#         return async_wrapper

#     else:
#         @wraps(fn)
#         def sync_wrapper(*args, **kwargs):
#             ensure_hook_flag()
#             if not _local.in_hook:
#                 _local.in_hook = True
#                 try:
#                     _on_call(module, fn.__name__, args, kwargs)
#                 finally:
#                     _local.in_hook = False

#             # print(f"[DEBUG] entering {module}.{fn.__name__}")
#             result = fn(*args, **kwargs)
#             # print(f"[DEBUG] exiting {module}.{fn.__name__} → {type(result).__name__}")

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




# from hook_manager import HookManager


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
#             ensure_hook_flag()
#             if _local.in_hook:
#                 return await fn(*args, **kwargs)
#             _local.in_hook = True
#             try:
#                 _on_call(module, fn.__name__, args, kwargs)
#                 result = await fn(*args, **kwargs)
#                 _on_return(module, fn.__name__, result)
#                 return result
#             finally:
#                 _local.in_hook = False

#         async_wrapper.__wrapped__ = fn
#         return async_wrapper

#     else:
#         @wraps(fn)
#         def sync_wrapper(*args, **kwargs):
#             ensure_hook_flag()
#             if _local.in_hook:
#                 return fn(*args, **kwargs)
#             _local.in_hook = True
#             try:
#                 _on_call(module, fn.__name__, args, kwargs)
#                 result = fn(*args, **kwargs)
#                 _on_return(module, fn.__name__, result)
#                 return result
#             finally:
#                 _local.in_hook = False

#         sync_wrapper.__wrapped__ = fn
#         return sync_wrapper