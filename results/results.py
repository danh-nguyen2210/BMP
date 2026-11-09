from pathlib import Path
import sys
import pandas as pd

# Tranh loi font chu tieng Viet tren Windows PowerShell (cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RESULTS_DIR = Path(__file__).resolve().parent

# Quet tat ca cac file ket qua cua person 3 (pairwise, sequential, product)
csv_files = sorted(RESULTS_DIR.glob("split42_person3_*_600.csv"))

if not csv_files:
    print("Chua tim thay file ket qua split42 nao trong thu muc results.")
else:
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)

    key_cols = [
        "Instance", "Solver", "AMO_Method", "Status",
        "Bandwidth", "Runtime_s", "Paper_LB", "Paper_Best", "n"
    ]

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        view_cols = [col for col in key_cols if col in df.columns]

        print("\n" + "=" * 75)
        print(f" FILE: {csv_file.name} (Tien do: {len(df)}/56 luot)")
        print("=" * 75)
        print(df[view_cols].to_string(index=False))

        print("\n Thong ke trang thai:")
        print(df["Status"].value_counts().to_string())
        print()
