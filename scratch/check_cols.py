import pandas as pd
from pathlib import Path
import json

root = Path("D:/projects/MetaMind/data")

def check_columns():
    print("--- Family A (vct_2021) ---")
    f_a = root / "vct_2021"
    if f_a.exists():
        for csv in f_a.glob("**/*.csv"):
            df = pd.read_csv(csv, nrows=0)
            print(f"{csv.name}: {list(df.columns)}")
            
    print("\n--- Family C (CT2024 Americas Kickoff) ---")
    f_c = root / "Champions Tour 2024 Americas Kickoff_csvs"
    if f_c.exists():
        for csv in f_c.glob("*.csv"):
            df = pd.read_csv(csv, nrows=0)
            print(f"{csv.name}: {list(df.columns)}")

if __name__ == "__main__":
    check_columns()
