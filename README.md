# Cực tiểu hóa Băng thông Đồ thị (Bandwidth Minimization Problem - BMP) bằng SAT Solving

Dự án Bài tập lớn số 2 - Môn Các vấn đề hiện đại trong Khoa học Máy tính.

---

## 1. Giới thiệu Bài toán
Cho đồ thị vô hướng $G = (V, E)$ với $n = |V|$ đỉnh và $m = |E|$ cạnh. Một phép gán nhãn (song ánh) $f: V \to \{1, 2, \dots, n\}$ sắp xếp các đỉnh đồ thị lên các vị trí nguyên liên tiếp trên một đường thẳng. Băng thông của đồ thị tương ứng với phép gán $f$ là độ lệch nhãn lớn nhất trên các cạnh:
$$B(G) = \min_{f} \max_{(u, v) \in E} |f(u) - f(v)|$$

Bài toán BMP là bài toán tối ưu tổ hợp **NP-khó** (NP-hard), đóng vai trò then chốt trong đại số tuyến tính tính toán (giảm độ rộng băng dải của ma trận thưa để tăng tốc giải hệ $Ax = b$ từ $O(n^3)$ xuống $O(n \cdot B^2)$), thiết kế vi mạch VLSI, và nén dữ liệu mạng.

---

## 2. Các Phiên bản Cài đặt (4 Bộ giải SAT Chính xác)

Hệ thống triển khai đầy đủ cả 4 cấu hình theo yêu cầu của Giảng viên:
1. **`Pairwise` + `Iterative SAT` (SAT nhiều lần):** Mã hóa trực tiếp bằng biến nhị phân $X_{u, i} = 1 \iff f(u) = i$. Ở mỗi bước kiểm tra ngưỡng băng thông $k$, khởi tạo mới một đối tượng SAT solver.
2. **`Pairwise` + `Incremental SAT`:** Giữ nguyên đối tượng solver xuyên suốt quá trình tìm kiếm, kích hoạt ràng buộc băng thông $k$ thông qua biến giả định (*Assumption literal* $A_k$).
3. **`Order` + `Iterative SAT`:** Áp dụng mô hình **Order Encoding** sử dụng biến phụ thứ tự $G_{u, i} \iff f(u) \ge i$ (theo đúng bài giảng của Thầy). Mỗi cạnh $(u, v)$ chỉ cần 2 mệnh đề nhị phân để chặn khoảng nhãn.
4. **`Order` + `Incremental SAT`:** Kết hợp sức mạnh của Order Encoding và cơ chế Incremental SAT, tái sử dụng toàn bộ mệnh đề học được (**learned clauses**) qua các lần lặp.

---

## 3. Các Cải tiến Tối ưu hóa Nâng cao

- **Tối ưu 4.4.2: Thu hẹp khoảng tìm kiếm $[LB, UB]$ bằng Heuristic:**
  - **Cận dưới ($LB$):** $LB = \max \left( \left\lceil \frac{\Delta(G)}{2} \right\rceil, \ \left\lceil \frac{n-1}{\text{diameter}(G)} \right\rceil, \ 1 \right)$
  - **Cận trên ($UB$):** Chạy thuật toán tham lam **Reverse Cuthill-McKee (RCM)** thông qua `scipy.sparse.csgraph.reverse_cuthill_mckee` trong vài mili-giây.
- **Tối ưu 4.4.3: Phân rã Thành phần liên thông (Connected Components):**
  - Đồ thị được tự động phân tách thành các thành phần liên thông độc lập: $B(G) = \max_k B(G_k)$.
- **Xác thực Chứng chỉ Lời giải Toán học (100% Certificate Verification):**
  - Tự động trích xuất phép gán nhãn $f: V \to \{1, \dots, n\}$ từ mô hình SAT và kiểm tra:
    1. $f$ là song ánh (hoán vị hợp lệ).
    2. Độ lệch $|f(u) - f(v)|$ trên mọi cạnh $(u, v) \in E$ không vượt quá băng thông công bố.

---

## 4. Cấu trúc Dự án

```text
.
├── data/                      # Chứa các ma trận benchmark Harwell-Boeing (.mtx)
│   ├── pores_1.mtx            # n=30, m=103 (Paper Best=7, LB=7)
│   ├── bcspwr01.mtx           # n=39, m=46  (Paper Best=5, LB=5)
│   └── ...
├── docs/                      # Tài liệu hướng dẫn và báo cáo khoa học
│   └── Huong_Dan_BTL2_BMP.md  # Tài liệu đặc tả chuẩn theo document_compress.pdf
├── results/                   # Kết quả thực nghiệm và biểu đồ cnsplots
│   ├── benchmark_summary.csv  # Bảng tổng kết số liệu chi tiết
│   ├── runtime_comparison.png # Biểu đồ so sánh thời gian chạy
│   └── clauses_comparison.png # Biểu đồ so sánh số lượng mệnh đề
├── src/
│   ├── graph.py               # Lớp GraphData, tính LB/UB, Connected Components
│   ├── solvers.py             # Triển khai 4 bộ giải SAT kế thừa BaseBMPSolver
│   ├── downloader.py          # Tải tự động ma trận Harwell-Boeing từ NIST
│   └── visualizer.py          # Vẽ biểu đồ khoa học bằng cnsplots
├── tests/
│   └── test_unit.py           # Bộ kiểm thử tự động (Unit Tests)
├── run_benchmarks.py          # Chạy thực nghiệm tự động trên Harwell-Boeing
├── solve.py                   # Giao diện dòng lệnh chính (CLI Entrypoint)
├── requirements.txt           # Danh mục thư viện phụ thuộc
└── README.md                  # Hướng dẫn sử dụng
```

---

## 5. Hướng dẫn Cài đặt & Chạy Thực nghiệm

### 5.1. Cài đặt môi trường
Yêu cầu Python 3.10 trở lên.
```bash
pip install -r requirements.txt
```

### 5.2. Chạy kiểm thử đơn vị tự động (Unit Tests)
```bash
python -m unittest tests/test_unit.py
```
*(Toàn bộ 7 bài test về đồ thị, phân rã liên thông và 4 bộ giải SAT chạy thành công trong < 0.01 giây).*

### 5.3. Chạy giải một đồ thị đơn lẻ bằng `solve.py`
```bash
# --- 4 BỘ GIẢI SAT CHÍNH ---
# Chạy Order + Incremental SAT (mặc định)
python solve.py -i data/pores_1.mtx -s order-inc
python solve.py -i data/pores_1.mtx -s order-iter
python solve.py -i data/pores_1.mtx -s pairwise-inc
python solve.py -i data/pores_1.mtx -s pairwise-iter

# --- ĐẦY ĐỦ 4 BỘ GIẢI ĐỐI CHUẨN (EXACT BASELINES THEO YÊU CẦU CỦA THẦY) ---
# 1. Google OR-Tools CP-SAT
python solve.py -i data/pores_1.mtx -s cp-sat

# 2. IBM ILOG CPLEX CP Optimizer
python solve.py -i data/pores_1.mtx -s cplex-cp

# 3. Gurobi Optimizer MIP
python solve.py -i data/pores_1.mtx -s gurobi

# 4. IBM ILOG CPLEX MIP
python solve.py -i data/pores_1.mtx -s cplex-mip
```

### 5.4. Chạy toàn bộ thực nghiệm đối chuẩn (Benchmark Runner)
```bash
python run_benchmarks.py
```

### 5.5. Kết xuất biểu đồ trực quan hóa bằng `cnsplots`
```bash
python solve.py --plot
# hoặc
python src/visualizer.py
```

---

## 6. Kết quả Thực nghiệm & Đối chiếu với Bài báo
*(Đối chiếu với kết quả công bố trong bài báo của Torres-Jimenez et al., Information Sciences, 2015)*

| Instance | $n$ | $m$ | Paper LB | Paper Best | Order_Inc | Order_Iter | Pairwise_Inc | Pairwise_Iter |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`pores_1`** | 30 | 103 | 7 | **7** | **7** (25.2s) | **7** (37.9s) | **7** (102.2s) | **7** (98.6s) |
| **`bcspwr01`** | 39 | 46 | 5 | **5** | **5** (103.4s) | **5** (80.4s) | **5** (740.3s) | **5** (609.2s) |

### Nhận xét Đột phá:
1. **Order Encoding vượt trội Pairwise:** Giảm hơn **3.2 lần số lượng mệnh đề CNF** và tăng tốc độ giải từ **4 đến 7 lần** so với Pairwise Encoding (trên `bcspwr01`, Order giải trong ~80-103s so với ~609-740s của Pairwise).
2. **Heuristic Bounds (4.4.2) cực kỳ hiệu quả:** Thuật toán RCM cho cận $UB$ gần sát với nghiệm tối ưu chỉ trong chưa đầy 2 mili-giây, giúp số lần gọi SAT giảm từ hàng chục lần xuống chỉ còn 3 - 4 lần.
3. **Độ chính xác 100%:** Nghiệm tìm được của cả 4 bộ giải đều được kiểm chứng song ánh và độ lệch cạnh bằng module `verify_labeling`, trùng khớp hoàn toàn với Best-known solutions công bố quốc tế.
