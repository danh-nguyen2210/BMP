import csv
import sys
from pathlib import Path

def print_table(csv_path):
    path = Path(csv_path)
    if not path.exists():
        print(f"Khong tim thay file: {csv_path}")
        return
    with open(path, "r", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))
    
    # Giữ lần chạy mới nhất của mỗi (Instance, Solver)
    latest_runs = {}
    for r in all_rows:
        key = (r.get("Instance", ""), r.get("Solver", ""))
        latest_runs[key] = r
    
    rows = list(latest_runs.values())
    total = len(rows)
    print("=" * 82)
    print(f"FILE: {path.name} (Tien do: {total} luot)")
    print("=" * 82)
    print(f"{'Instance':<12} {'Solver':<14} {'AMO_Method':<11} {'Status':<8} {'Bandwidth':>9} {'Runtime_s':>10} {'Paper_LB':>9} {'Paper_Best':>10} {'n':>4}")
    print("-" * 82)
    for r in rows:
        inst = r.get("Instance", "")
        solver = r.get("Solver", "")
        amo = r.get("AMO_Method", "")
        status = r.get("Status", "")
        bw = r.get("Bandwidth", "")
        rt = f"{float(r.get('Runtime_s', 0)):.3f}" if r.get("Runtime_s") else ""
        lb = r.get("Paper_LB", "")
        best = r.get("Paper_Best", "")
        n = r.get("n", "")
        print(f"{inst:<12} {solver:<14} {amo:<11} {status:<8} {bw:>9} {rt:>10} {lb:>9} {best:>10} {n:>4}")
    print()

def print_summary(person=2):
    groups = [
        ("SAT — pairwise", f"results/split42_person{person}_pairwise_600.csv", 56),
        ("SAT — sequential", f"results/split42_person{person}_sequential_600.csv", 56),
        ("SAT — product", f"results/split42_person{person}_product_600.csv", 56),
        ("CPLEX CP + CPLEX MIP + Gurobi", f"results/baselines_person{person}_600.csv", 42),
        ("CP-SAT", f"results/cpsat_person{person}_600.csv", 14),
    ]
    
    print("=" * 65)
    print(f"BẢNG TỔNG KẾT THỰC NGHIỆM (PERSON {person} - BẢO)")
    print("=" * 65)
    print(f"{'Nhóm':<30} {'Hoàn thành':<15} {'OPTIMAL':<10} {'TIMEOUT':<10}")
    print("-" * 65)
    
    tot_done = tot_req = tot_opt = tot_to = 0
    for name, filepath, req in groups:
        p = Path(filepath)
        if not p.exists():
            print(f"{name:<30} {'0/' + str(req):<15} {'0':<10} {'0':<10}")
            continue
        with open(p, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        latest = {}
        for r in rows:
            latest[(r["Instance"], r["Solver"])] = r
        done = len(latest)
        opt = sum(1 for r in latest.values() if r["Status"] == "OPTIMAL")
        to = sum(1 for r in latest.values() if r["Status"] == "TIMEOUT")
        tot_done += done
        tot_req += req
        tot_opt += opt
        tot_to += to
        print(f"{name:<30} {f'{done}/{req}':<15} {str(opt):<10} {str(to):<10}")
        
    print("=" * 65)
    print(f"{'Tổng':<30} {f'{tot_done}/{tot_req}':<15} {str(tot_opt):<10} {str(tot_to):<10}")
    print("=" * 65)

def main():
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "summary"
    person = 2
    
    if arg in ("summary", "tongket", "sum"):
        print_summary(person)
        return
        
    targets = []
    if arg in ("pairwise", "seq", "sequential", "product"):
        full_amo = "sequential" if arg == "seq" else arg
        targets.append(f"results/split42_person{person}_{full_amo}_600.csv")
    elif arg in ("baselines", "baseline"):
        targets.append(f"results/baselines_person{person}_600.csv")
    elif arg in ("cpsat", "cp"):
        targets.append(f"results/cpsat_person{person}_600.csv")
    elif arg == "all":
        print_summary(person)
        for amo in ["pairwise", "sequential", "product"]:
            targets.append(f"results/split42_person{person}_{amo}_600.csv")
        targets.append(f"results/cpsat_person{person}_600.csv")
        targets.append(f"results/baselines_person{person}_600.csv")
    else:
        targets.append(arg)
        
    for target in targets:
        print_table(target)

if __name__ == "__main__":
    main()
