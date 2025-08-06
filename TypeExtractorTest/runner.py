# runner_debug.py

import os
import sys
import json
import asyncio
import importlib
import inspect

# 1) Make sure your project root is on the path
sys.path.insert(0, os.getcwd())

# 2) (Re)write config.json to point at test_module
with open("config.json", "w") as f:
    json.dump({"targets": ["test_module", "test_module.*"]}, f)

# 3) Install your hooks before importing anything else
from pylya.hook_loader import install_hooks
from pylya.analysis import TypeExtractor

install_hooks(
    config_path="config.json",
    mode="learn",
    analyses=[TypeExtractor(outfile="type.log")],
)

# 4) Now import your module
import test_module

# 5) Inspect what actually got bound to those names:
print("test_module.read_items =", test_module.read_items)
print("  callable?             ", callable(test_module.read_items))
print("  is coroutinefunction? ", inspect.iscoroutinefunction(test_module.read_items))
print("  __wrapped__ attr?     ", getattr(test_module.read_items, "__wrapped__", None))
print()
print("test_module.get_data   =", test_module.get_data)
print("  callable?             ", callable(test_module.get_data))
print("  __wrapped__ attr?     ", getattr(test_module.get_data, "__wrapped__", None))
print()

# 6) If everything looks sane, invoke them:
if __name__ == "__main__":
    try:
        print("→ Calling async read_items…")
        result = asyncio.run(test_module.read_items("testtoken"))
        print("  result:", result)
    except Exception as e:
        print("  [ERROR] async call failed:", repr(e))

    try:
        print("→ Calling sync get_data…")
        val = test_module.get_data(2, 3)
        print("  result:", val)
    except Exception as e:
        print("  [ERROR] sync call failed:", repr(e))
