
# File: hook_loader.py
"""
Standalone hook loader for your project. Import this at startup to enable Lyapy instrumentation.
"""
import sys
import atexit
import json
from typing import Dict, List, Tuple

from pylya.hook_manager import HookManager ,Analysis
from pylya.importer import install_import_hook, rewrap_existing_targets



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
    allowlist_path: str = 'allowlist.json'
) -> HookManager:
    # 1) load config & allowlist

    # print(mode)
    # print(allowlist_path)
    targets, _   = _load_config(config_path)
    raw_allowlist = mode == 'enforce' and _load_allowlist(allowlist_path) or {}

    if analyses is None:
        analyses = []

    # 2) always create a HookManager
    hook_mgr = HookManager(targets, analyses, mode=mode, allowlist=raw_allowlist,)


    # 4) install hooks
    install_import_hook(hook_mgr, targets)
    rewrap_existing_targets(hook_mgr, targets)
    sys.setprofile(hook_mgr.c_profile)

    # 5) register the exit handler
  
    atexit.register(hook_mgr.write_reports)

    return hook_mgr



# def install_analysis(
#     events_path: str = 'events.json',
#     analyses: List[Analysis] = None,
#     include_kinds: List[str] = ['import','call','return','read','write']
# ) -> None:
#     """
#     New API: read recorded events and dispatch them to your analyses.
#     Mirrors install_hooks signature style.
#     """
#     analyses = analyses or []
#     with open(events_path, 'r') as f:
#         events = json.load(f)

#     for module, tags in events.items():
#         is_main = (module == '__main__')
#         parent = None if is_main else module

#         for tag in tags:
#             kind, name = tag.split(':', 1)
#             if kind not in include_kinds:
#                 continue

#             for a in analyses:
#                 if kind == 'import':
#                     a.on_import(parent, name)
#                 elif kind == 'call':
#                     a.on_call(module, name, (), {})
#                 elif kind == 'return':
#                     a.on_return(module, name, None)
#                 elif kind == 'read':
#                     a.on_attr_read(module, None, name)
#                 elif kind == 'write':
#                     a.on_attr_write(module, None, name, None)



