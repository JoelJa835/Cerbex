# Cerbex ⚡️

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Cerbex** is a Python dynamic analysis framework for monitoring and enforcing module dependencies.
It can measure **performance** and extract **function return types**, and can be used via CLI or programmatically in Python scripts.

---

## Table of Contents

* [Features](#features)
* [Getting Started](#getting-started)

  * [Prerequisites](#prerequisites)
  * [Installation](#installation)
  * [Usage](#usage)
* [Programmatic API](#programmatic-api)
* [License](#license)
* [Acknowledgements](#acknowledgements)

---

## Features

* 🕒 **Performance Analysis**: Track function execution times without slowing the program.
* 🔍 **Type Extraction**: Automatically logs return types of all functions.
* ⚡ **Zero I/O Overhead**: Buffers all data in memory and writes logs at program exit.
* 🔧 **Learn and Enforce Modes**:

  * `learn`: collect data and generate allowlists
  * `enforce`: block disallowed imports or calls

---

## Getting Started

### Prerequisites

* Python 3.11+
* `pip`

### Installation

Clone the repository and install in **editable mode** in the directory that contains setup.py:

```bash
git clone https://github.com/JoelJa835/Cerbex.git
cd Cerbex
pip install -e .
```

> Optional: Use a virtual environment to avoid conflicts with system packages.

---

## Usage

Cerbex runs via the `cli.py` script.

### Learn Mode

Collect function calls, imports, types and generate allowlists:

```bash
Cerbex --mode learn --config config.json --analyses perf types --output logs -- path/to/target_script.py
```


* `-mode learn` → runs in learn mode
* `-analyses perf types` → analyses to run (`perf` = performance, `types` = type extraction)
* `-output logs` → output directory for log files
* `--` → separates Cerbex options from target script arguments

**Output:**

* Logs: `logs/perf.log`, `logs/types.log`
* JSON reports: `events.json`, `dependencies.json`, `allowlist.json`

### Enforce Mode

Block unauthorized calls using a previously generated allowlist:

```bash
Cerbex --mode enforce --allowlist allowlist.json -- path/to/target_script.py 
```
* `-mode enforce` → runs in enforce mode
* `--allowlist` → path to allowlist JSON
* Cerbex enforces restrictions while running the target script

---

## Programmatic API

Integrate Cerbex directly into a Python program without using CLI:

```python
# runner.py
from Cerbex.hook_loader import install_hooks
from Cerbex.analysis import PerfAnalyzer, TypeExtractor

hook_mgr = install_hooks(
    config_path="config.json",
    mode="learn",  # learn or enforce
    analyses=[PerfAnalyzer(), TypeExtractor()],
    allowlist_path="allowlist.json",  # Only used in enforce mode
    log_events=True  # or False
)

import app
app.main()
```

* `install_hooks(...)` sets up imports, wrappers, profiling hooks, loads analyses, and registers `write_reports` at exit.
* `config.json` defines target modules to instrument (e.g., `"targets": ["app", "requests", "json"]`).
* `analyses` specifies which analyses to run.
* `allowlist` is used in enforce mode to control allowed imports and function calls.
* `log_events` enables or disables in-memory event recording.Not needed, its for evaluation purposes.
* `import app; app.main()` runs the main function of the application, preserving the top-level execution behavior.

All imports and function calls go through Cerbex's `HookManager` and analyses. Generated files `dependencies.json`, `events.json`, and `allowlist.json` can be reused in enforce mode.

---

## License

Distributed under the MIT License. See `LICENSE` for details.

---

## Acknowledgements

* [Best README Template](https://github.com/othneildrew/Best-README-Template)
* Python standard library documentation
* Inspiration from [Lya](https://github.com/andromeda/lya) dynamic analysis framework




