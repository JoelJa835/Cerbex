# pipeline.py
import pandas as pd
import builtins
import sys

def run_pipeline():
    print("HELLO WORLD")
    result = eval("2 + 3 * 4")
    print("Eval returned:", result)
    exec("""
def greet(name):
    print(f"Hello, {name}!")

greet("Alice")
""")
    df = pd.read_csv("data.csv")
    df["z"] = df.x + df.y
    grouped = df.groupby("z").agg({"x": "mean", "y": "sum"})
    filtered = grouped[grouped.x > 0]
    result = filtered.reset_index()
    result.to_json("out.json")

