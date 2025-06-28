# File: cli.py
import sys
import atexit
import argparse
import json
import importlib.util

from hook_manager import HookManager
from importer import install_import_hook


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="lyapy", description="Dynamic instrumentation tool")
    p.add_argument('script', help='Path to Python script to run')
    p.add_argument('--mode', choices=['learn','enforce'], default='learn')
    p.add_argument('--config', help='JSON config (targets & allowlist)')
    return p.parse_args()


def load_config(path: str):
    data = json.load(open(path))
    return data.get('targets', []), data.get('allowlist', {})


def main() -> None:
    args = parse_args()
    targets, allowlist = ([], {}) if not args.config else load_config(args.config)

    analyses = []
    try:
        from lyapy.plugins import CallLogger
        analyses.append(CallLogger())
    except ImportError:
        pass

    hook_mgr = HookManager(analyses, mode=args.mode, allowlist=allowlist)
    install_import_hook(hook_mgr, targets)
    sys.setprofile(hook_mgr.c_profile)

    for mod in list(sys.modules):
        if any(mod == t or mod.startswith(f"{t}.") for t in targets):
            del sys.modules[mod]

    atexit.register(hook_mgr.write_reports)

    spec = importlib.util.spec_from_file_location("__main__", args.script)
    module = importlib.util.module_from_spec(spec)
    sys.modules["__main__"] = module
    spec.loader.exec_module(module)

if __name__ == '__main__':
    main()
