# make_benign.py
import pickle
from types import SimpleNamespace

class Benign:
    def __reduce__(self):
        # Reconstruct a harmless SimpleNamespace at load time
        state = {
            "user": "alice",
            "id": 42,
            "items": ["apple", "banana", "cherry"]
        }
        # On unpickle, Python will call SimpleNamespace(**state)
        return (SimpleNamespace, (), state)

# Build the benign pickle file using the same __reduce__ pattern
with open('data.pkl', 'wb') as f:
    pickle.dump(Benign(), f)

print("Benign payload written to data.pkl")
