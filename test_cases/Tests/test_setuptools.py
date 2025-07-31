from setuptools.config import read_configuration
# Try reading a sample config file
try:
    config = read_configuration("setup.cfg")
    print(config.get("metadata", {}).get("name"))
except Exception:
    print("No setup.cfg found (OK)")
