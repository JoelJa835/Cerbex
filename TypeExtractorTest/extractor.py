from collections import defaultdict
import re

# === You can modify this list with your target functions ===
TARGET_FUNCTIONS = {"concat", "shout", "count_chars"}

# Path to your log file
log_path = "type.log"

# Data structure: { "module.func": set([types]) }
type_summary = defaultdict(set)

# Regex to match lines like: [Type] string_utils.concat returned str
pattern = re.compile(r'\[Type\] (\S+)\.(\w+) returned (\w+)')

with open(log_path, 'r') as f:
    for line in f:
        match = pattern.match(line.strip())
        if match:
            module = match.group(1)
            func = match.group(2)
            ret_type = match.group(3)
            if func in TARGET_FUNCTIONS:
                key = f"{module}.{func}"
                type_summary[key].add(ret_type)

# Print the result
print("Targeted Function Return Types:")
for func, types in sorted(type_summary.items()):
    print(f"{func}: {', '.join(sorted(types))}")
