from packaging import version

v1 = version.parse("1.0.0")
v2 = version.parse("2.0.0")
print(v1 < v2)
