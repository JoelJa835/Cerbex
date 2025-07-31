from PIL import Image
from pathlib import Path
import random

Path("photos").mkdir(exist_ok=True)

for i in range(100):
    color = tuple(random.randint(0, 255) for _ in range(3))
    img = Image.new("RGB", (4000, 3000), color)
    img.save(f"photos/img{i:03}.jpg", "JPEG", quality=95)
