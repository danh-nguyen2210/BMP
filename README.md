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

## 3. Các Phương pháp Mã hóa ALO và AMO Nâng cao (Cardinality Encodings)

BƯỚC 1: Ràng buộc Song ánh cho biến $X$ (Bijective Assignment):
- **(1.1) At-Least-Once (ALO) trên đỉnh:** Mỗi đỉnh nhận ít nhất 1 nhãn: $\bigvee_{i=1}^n X_{u, i}$ ($n$ mệnh đề độ dài $n$).
- **(1.2) At-Most-Once (AMO) trên đỉnh:** Mỗi đỉnh nhận nhiều nhất 1 nhãn: $\text{AMO}(X_{u, 1}, \dots, X_{u, n})$.
- **(1.3) Đơn ánh (Injective AMO):** Không có 2 đỉnh khác nhau nhận cùng một nhãn: $\text{AMO}(X_{1, i}, \dots, X_{n, i})$.

Hệ thống hỗ trợ 5 kỹ thuật mã hóa AMO:
1. **`pairwise`**: Ghép cặp trực tiếp $\binom{n}{2}$ mệnh đề nhị phân, 0 biến phụ.
2. **`sequential`**: **Sequential Counter Encoding** (Sinz, 2005) qua thư viện PySAT (`EncType.seqcounter`), sinh $O(n)$ mệnh đề tuyến tính và hỗ trợ lan truyền đơn vị (Unit Propagation) mạnh mẽ.
3. **`binary` / `bitwise`**: **Bitwise/Binary Encoding** qua thư viện PySAT (`EncType.bitwise`), dùng $\lceil \log_2 n \rceil$ biến boolean biểu diễn nhị phân, sinh $O(n \log n)$ mệnh đề.
4. **`commander`**: **Commander Encoding** (Klieber & Kwon, 2007) chia tập biến thành các nhóm nhỏ kích thước 3, sinh $O(n)$ mệnh đề với các biến chỉ huy (commanders).
5. **`product`**: **2-Product Encoding** (Chen, 2010) ánh xạ biến lên lưới ma trận 2 chiều kích thước $p \times q$, chỉ sinh $O(n)$ mệnh đề với $O(\sqrt{n})$ biến phụ.

---

## 4. Các Cải tiến Tối ưu hóa Nâng cao

- **Quy tắc Giới hạn Kích thước (Memory Limit):**
  - Mọi ma trận có số đỉnh $n > 400$ đều được giữ link tải chính thức từ NIST Matrix Market và tải về bình thường, nhưng khi chạy thực nghiệm sẽ tự động bỏ qua và ghi nhận trạng thái **`MEM_EXCEED`** (Memory Exceeded) mà không làm tràn RAM hệ thống.
- **Giới hạn Thời gian (Timeout):**
  - Mỗi bài toán có thời gian giải tối đa là **10 phút (600 giây)**. Quá thời gian này sẽ tự động ngắt và trả về kết quả `TIMEOUT`.
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

## 5. Cấu trúc Dự án

```text
.
├── data/                      # Chứa các ma trận benchmark Harwell-Boeing (.mtx)
├── docs/                      # Tài liệu hướng dẫn và báo cáo khoa học (Elsevier cas-sc)
│   └── Huong_Dan_BTL2_BMP.md  # Tài liệu đặc tả chuẩn BTL 2
├── results/                   # Kết quả thực nghiệm và biểu đồ cnsplots
│   ├── benchmark_summary.csv  # Bảng tổng kết số liệu chi tiết
│   ├── runtime_comparison.png # Biểu đồ so sánh thời gian chạy
│   └── clauses_comparison.png # Biểu đồ so sánh số lượng mệnh đề
├── src/
│   ├── cardinality.py         # Triển khai các phương pháp ALO/AMO (pairwise, sequential, binary, commander, product)
│   ├── graph.py               # Lớp GraphData, tính LB/UB, Connected Components
│   ├── solvers.py             # Triển khai 4 bộ giải SAT kế thừa BaseBMPSolver
│   ├── downloader.py          # Tải tự động 72 ma trận Harwell-Boeing từ NIST
│   ├── baselines.py           # 4 bộ giải đối chuẩn: CP-SAT, CPLEX-CP, Gurobi, CPLEX-MIP
│   └── visualizer.py          # Vẽ biểu đồ khoa học bằng cnsplots
├── tests/
│   └── test_unit.py           # Bộ kiểm thử tự động (Unit Tests)
├── run_benchmarks.py          # Chạy thực nghiệm tự động trên Harwell-Boeing (Table 6 & 7)
├── solve.py                   # Giao diện dòng lệnh chính (CLI Entrypoint)
├── requirements.txt           # Danh mục thư viện phụ thuộc
└── README.md                  # Hướng dẫn sử dụng
```

---

## 6. Hướng dẫn Cài đặt & Chạy Thực nghiệm

### 6.1. Cài đặt môi trường
Yêu cầu Python 3.10 trở lên.
```bash
pip install -r requirements.txt
```

### 6.2. Chạy kiểm thử đơn vị tự động (Unit Tests)
```bash
python -m unittest tests/test_unit.py
```
*(Toàn bộ 13 bài test về đồ thị, phân rã liên thông, 4 bộ giải SAT, 5 kỹ thuật AMO và cơ chế MEM_EXCEED chạy thành công trong < 0.05 giây).*

### 6.3. Tải dữ liệu benchmark từ NIST Matrix Market
```bash
# Tải toàn bộ 72 ma trận Bảng 6 & Bảng 7:
python src/downloader.py --all

# Hoặc tải các ma trận cụ thể:
python src/downloader.py bcspwr01 can_144 pores_1
```

### 6.4. Chạy giải một đồ thị đơn lẻ bằng `solve.py`
```bash
# Chạy Order + Incremental SAT với các tùy chọn AMO khác nhau:
python solve.py -i data/pores_1.mtx -s order-inc --amo pairwise
python solve.py -i data/pores_1.mtx -s order-inc --amo sequential
python solve.py -i data/pores_1.mtx -s order-inc --amo binary
python solve.py -i data/pores_1.mtx -s order-inc --amo commander
python solve.py -i data/pores_1.mtx -s order-inc --amo product

# Giới hạn thời gian (mặc định 600s = 10 phút):
python solve.py -i data/pores_1.mtx -s order-inc --timeout 600

# Chạy với 4 bộ giải đối chuẩn (Exact Baselines):
python solve.py -i data/pores_1.mtx -s cp-sat
python solve.py -i data/pores_1.mtx -s cplex-cp
python solve.py -i data/pores_1.mtx -s gurobi
python solve.py -i data/pores_1.mtx -s cplex-mip
```

### 6.5. Chạy thực nghiệm đối chuẩn tự động (`run_benchmarks.py`)
```bash
# Chạy toàn bộ Bảng 6 (31 ma trận nhỏ):
python run_benchmarks.py --table 6 --amo sequential

# Chạy Bảng 7 (41 ma trận lớn, tự động đánh dấu MEM_EXCEED cho n > 400):
python run_benchmarks.py --table 7 --amo sequential

# Chạy tất cả với thuật toán AMO tùy chọn:
python run_benchmarks.py --table all --amo product --timeout 600
```

### 6.6. Kết xuất biểu đồ trực quan hóa bằng `cnsplots`
```bash
python solve.py --plot
# hoặc
python src/visualizer.py
```

---

## 7. Danh mục Toàn bộ 72 Dataset từ Bảng 6 & Bảng 7 (Torres-Jimenez et al., 2015)

| Bảng | Tên Ma trận | $n$ | $m$ | Paper LB | Paper Best | Phân loại |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 6 | `pores_1` | 30 | 103 | 7 | 7 | $n \le 400$ (Chạy nghiệm) |
| 6 | `ibm32` | 32 | 90 | 11 | 11 | $n \le 400$ (Chạy nghiệm) |
| 6 | `bcspwr01` | 39 | 46 | 5 | 5 | $n \le 400$ (Chạy nghiệm) |
| 6 | `bcsstk01` | 48 | 176 | 16 | 16 | $n \le 400$ (Chạy nghiệm) |
| 6 | `bcspwr02` | 49 | 59 | 7 | 7 | $n \le 400$ (Chạy nghiệm) |
| 6 | `curtis54` | 54 | 291 | 10 | 10 | $n \le 400$ (Chạy nghiệm) |
| 6 | `will57` | 57 | 127 | 6 | 6 | $n \le 400$ (Chạy nghiệm) |
| 6 | `impcol_b` | 59 | 281 | 19 | 20 | $n \le 400$ (Chạy nghiệm) |
| 6 | `steam3` | 80 | 211 | 7 | 7 | $n \le 400$ (Chạy nghiệm) |
| 6 | `ash85` | 85 | 219 | 9 | 9 | $n \le 400$ (Chạy nghiệm) |
| 6 | `nos4` | 100 | 247 | 10 | 10 | $n \le 400$ (Chạy nghiệm) |
| 6 | `gent113` | 113 | 650 | 25 | 27 | $n \le 400$ (Chạy nghiệm) |
| 6 | `gre_115` | 115 | 286 | 20 | 23 | $n \le 400$ (Chạy nghiệm) |
| 6 | `bcspwr03` | 118 | 179 | 9 | 10 | $n \le 400$ (Chạy nghiệm) |
| 6 | `arc130` | 130 | 1037 | 63 | 63 | $n \le 400$ (Chạy nghiệm) |
| 6 | `lns_131` | 131 | 536 | 18 | 20 | $n \le 400$ (Chạy nghiệm) |
| 6 | `bcsstk04` | 132 | 1758 | 36 | 37 | $n \le 400$ (Chạy nghiệm) |
| 6 | `west0132` | 132 | 414 | 23 | 32 | $n \le 400$ (Chạy nghiệm) |
| 6 | `impcol_c` | 137 | 411 | 23 | 30 | $n \le 400$ (Chạy nghiệm) |
| 6 | `bcsstk22` | 138 | 496 | 9 | 10 | $n \le 400$ (Chạy nghiệm) |
| 6 | `can_144` | 144 | 720 | 13 | 13 | $n \le 400$ (Chạy nghiệm) |
| 6 | `lund_a` | 147 | 1141 | 19 | 23 | $n \le 400$ (Chạy nghiệm) |
| 6 | `lund_b` | 147 | 1141 | 19 | 23 | $n \le 400$ (Chạy nghiệm) |
| 6 | `bcsstk05` | 153 | 1288 | 19 | 20 | $n \le 400$ (Chạy nghiệm) |
| 6 | `west0156` | 156 | 362 | 33 | 36 | $n \le 400$ (Chạy nghiệm) |
| 6 | `can_161` | 161 | 608 | 18 | 18 | $n \le 400$ (Chạy nghiệm) |
| 6 | `west0167` | 167 | 506 | 31 | 34 | $n \le 400$ (Chạy nghiệm) |
| 6 | `mcca` | 180 | 1459 | 32 | 37 | $n \le 400$ (Chạy nghiệm) |
| 6 | `fs_183_1` | 183 | 1069 | 52 | 60 | $n \le 400$ (Chạy nghiệm) |
| 6 | `gre_185` | 185 | 975 | 17 | 21 | $n \le 400$ (Chạy nghiệm) |
| 6 | `will199` | 199 | 701 | 55 | 64 | $n \le 400$ (Chạy nghiệm) |
| 7 | `dwt_209` | 209 | 767 | 21 | 23 | $n \le 400$ (Chạy nghiệm) |
| 7 | `gre_216a` | 216 | 363 | 17 | 21 | $n \le 400$ (Chạy nghiệm) |
| 7 | `dwt_221` | 221 | 704 | 12 | 13 | $n \le 400$ (Chạy nghiệm) |
| 7 | `dwt_234` | 234 | 834 | 11 | 11 | $n \le 400$ (Chạy nghiệm) |
| 7 | `dwt_245` | 245 | 1228 | 21 | 21 | $n \le 400$ (Chạy nghiệm) |
| 7 | `bcspwr04` | 274 | 669 | 23 | 24 | $n \le 400$ (Chạy nghiệm) |
| 7 | `ash292` | 292 | 868 | 16 | 19 | $n \le 400$ (Chạy nghiệm) |
| 7 | `can_292` | 292 | 1124 | 34 | 38 | $n \le 400$ (Chạy nghiệm) |
| 7 | `dwt_310` | 310 | 1079 | 11 | 12 | $n \le 400$ (Chạy nghiệm) |
| 7 | `gre_343` | 343 | 1078 | 23 | 28 | $n \le 400$ (Chạy nghiệm) |
| 7 | `dwt_361` | 361 | 1156 | 14 | 14 | $n \le 400$ (Chạy nghiệm) |
| 7 | `dwt_419` | 419 | 1572 | 23 | 25 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bcsstk06` | 420 | 3724 | 38 | 45 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bcsstm07` | 420 | 3724 | 37 | 45 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bcspwr05` | 443 | 590 | 25 | 27 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `can_445` | 445 | 1682 | 46 | 52 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bcsstk20` | 485 | 1810 | 8 | 13 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `494_bus` | 494 | 586 | 25 | 28 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `dwt_503` | 503 | 2603 | 29 | 41 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `fs_541_1` | 541 | 4285 | 270 | 270 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `dwt_592` | 592 | 2256 | 22 | 29 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `662_bus` | 662 | 912 | 36 | 39 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `fs_680_1` | 680 | 2110 | 17 | 17 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `685_bus` | 685 | 1282 | 30 | 32 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `can_715` | 715 | 3163 | 54 | 71 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `fs_760_1` | 760 | 5836 | 36 | 37 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bcsstk19` | 817 | 3835 | 13 | 14 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bp_0` | 822 | 3276 | 174 | 234 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bp_200` | 822 | 3802 | 186 | 257 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bp_400` | 822 | 4028 | 188 | 267 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bp_600` | 822 | 4172 | 190 | 272 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bp_800` | 822 | 4216 | 197 | 278 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bp_1000` | 822 | 4616 | 197 | 283 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bp_1200` | 822 | 4726 | 197 | 287 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bp_1400` | 822 | 4790 | 199 | 291 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `bp_1600` | 822 | 4841 | 199 | 292 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `can_838` | 838 | 4510 | 75 | 86 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `dwt_878` | 878 | 3155 | 23 | 25 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `gr_30_30` | 900 | 4322 | 31 | 33 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `dwt_918` | 918 | 3233 | 27 | 32 | **$n > 400 \to$ MEM_EXCEED** |
| 7 | `dwt_992` | 992 | 7515 | 35 | 35 | **$n > 400 \to$ MEM_EXCEED** |
