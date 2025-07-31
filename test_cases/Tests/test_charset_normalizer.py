from charset_normalizer import from_bytes

data = b'This is a test.'
result = from_bytes(data)
print(result.best().encoding)
