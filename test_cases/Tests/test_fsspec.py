import fsspec
fs = fsspec.filesystem("file")
print(fs.cat(__file__)[:30])  # Read this test script itself
