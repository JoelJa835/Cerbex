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




