import re
from collections import defaultdict

# Match “[Perf] module.func took X.XXXXXXs”
pattern = re.compile(r"\[Perf\]\s+([\w\.]+)\s+took\s+([\d.]+)s")

# Only keep these fully qualified names
keys = {
    "PIL.Image.open",
    "PIL.Image.thumbnail",
    "PIL.Image.save",
}

times = defaultdict(list)

with open("perf.log") as f:
    for line in f:
        m = pattern.search(line)
        if not m:
            continue
        fn, t = m.group(1), float(m.group(2))
        if fn in keys:
            times[fn].append(t)

# Print per‑call and totals
for fn in keys:
    print(f"\n=== {fn} ===")
    #for t in times[fn]:
        #print(f"  {t:.6f}s")
    print(f"TOTAL {fn}: {sum(times[fn]):.6f}s")
