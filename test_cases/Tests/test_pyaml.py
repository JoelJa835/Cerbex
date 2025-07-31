import yaml

data = yaml.safe_load("""
name: Alice
age: 30
""")
print(data["name"])
