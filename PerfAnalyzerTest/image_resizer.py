# image_resizer.py
from pathlib import Path
from PIL import Image

INPUT_DIR  = Path("photos/")
OUTPUT_DIR = Path("thumbnails/")
SIZE       = (200, 200)

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    for img_path in INPUT_DIR.glob("*.jpg"):
        img = Image.open(img_path)
        img.thumbnail(SIZE)
        img.save(OUTPUT_DIR / img_path.name)

if __name__ == "__main__":
    main()



# class MyClass:
#     def __init__(self):
#         self.value = 42  # WRITE

#     def show(self):
#         return self.value  # READ

# def run():
#     obj = MyClass()
#     obj.value = 100  # WRITE
#     print(obj.show())  # READ




# pylya --mode learn --config config.json -- unsafe_deserialize.py
#  2000  pylya --mode enforce --allowlist allowlist.json -- unsafe_deserialize.py