# target_script.py
def process_item(x):
    print(f"Processing {x} ({type(x).__name__})")

def main():
    process_item(42)
    process_item("hello")
    process_item([1, 2, 3])
    process_item(99)
    process_item("world")
    process_item("test")
    process_item(3.14)

if __name__ == "__main__":
    main()

