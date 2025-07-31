import os
import importlib.util
import sys
import json
import csv
from pylya.hook_loader import install_hooks
from pylya.analysis import PerfAnalyzer, TypeExtractor

TEST_DIR = "Tests"
LOG_DIR = "logs"
SUMMARY_CSV = "summary.csv"

os.makedirs(LOG_DIR, exist_ok=True)

# List of test scripts (one per small package)
test_scripts = [f for f in os.listdir(TEST_DIR) if f.startswith("test_") and f.endswith(".py")]

with open("config.json") as f:
    config = json.load(f)
allowed_modules = config.get("targets", [])

# CSV header
summary = [["package", "total_calls", "total_time_s", "unique_return_types"]]

for test_script in test_scripts:
    package = test_script.replace("test_", "").replace(".py", "")
    print(f"\n🧪 Running test for {package}")

    # Set output files unique per test
    perf_log = os.path.join(LOG_DIR, f"{package}_perf.log")
    type_log = os.path.join(LOG_DIR, f"{package}_types.log")

    # Reset logs
    for f in [perf_log, type_log, "events.json", "dependencies.json", "allowlist.json"]:
        try: os.remove(f)
        except FileNotFoundError: pass

    # Install hooks fresh for this run
    install_hooks(
    config_path="config.json",
    analyses=[
        PerfAnalyzer(perf_log, allowed_modules),
        TypeExtractor(type_log, allowed_modules)
    ],
    mode="learn"
)


    # Dynamically run the test module
    script_path = os.path.join(TEST_DIR, test_script)
    spec = importlib.util.spec_from_file_location("test_module", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["test_module"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"❌ Error running {test_script}: {e}")
        continue

    # Analyze logs
    total_time = 0.0
    total_calls = 0
    return_types = set()

    try:
        with open(perf_log) as f:
            for line in f:
                if "[Perf]" in line:
                    total_calls += 1
                    try:
                        time_taken = float(line.split("took ")[-1].replace("s", ""))
                        total_time += time_taken
                    except ValueError:
                        pass
    except FileNotFoundError:
        pass

    try:
        with open(type_log) as f:
            for line in f:
                if "[Type]" in line:
                    t = line.strip().split("returned ")[-1]
                    return_types.add(t)
    except FileNotFoundError:
        pass

    summary.append([package, total_calls, round(total_time, 4), ", ".join(sorted(return_types))])

# Write summary CSV
with open(SUMMARY_CSV, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(summary)

print(f"\n✅ Summary written to {SUMMARY_CSV}")
