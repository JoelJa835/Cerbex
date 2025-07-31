from typing_extensions import TypedDict

class User(TypedDict):
    id: int
    name: str

u = User(id=1, name="Alice")
print(u)
