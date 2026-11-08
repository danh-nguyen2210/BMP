# Chạy CPLEX CP, CPLEX MIP và Gurobi có resume

`run_baselines.py` là runner riêng, không dùng các lớp baseline cũ trong
`src/baselines.py`, không sửa fingerprint hoặc checkpoint SAT.
Chạy tại thư mục BMP, dùng Python trong `.venv` đã cài `gurobipy`, `cplex`,
`docplex` và cấu hình engine/license hợp lệ. Gurobi của máy hiện tại cần mạng
để xác thực license; việc tối ưu vẫn diễn ra local.

## Người 1: 14 instance, ba baseline, timeout 600 giây

```powershell
.\.venv\Scripts\python.exe run_baselines.py `
  --instances-file config/split42_person1.txt `
  --solvers cplex-cp cplex-mip gurobi `
  --timeout 600 `
  --threads 1 `
  --retry-errors `
  --checkpoint results/baselines_person1_600.sqlite3 `
  --output results/baselines_person1_600.csv
```

42 lượt chạy tuần tự; ngân sách timeout cộng dồn 7 giờ, cộng thời gian đọc dữ liệu,
dọn tiến trình và xuất kết quả. `--max-jobs 3` chỉ nhận ba lượt mới.
`--session-hours 2` không nhận lượt mới nếu ngân sách phiên còn ít hơn timeout.
Đổi `person1` thành `person2` hoặc `person3` ở cả ba đường dẫn khi giao cho bạn khác.

## Dừng và resume

Ctrl+C một lần: chờ lượt hiện tại kết thúc hoặc hết giờ rồi lưu và dừng.
Không có vòng PowerShell gọi tiếp một AMO khác. Chạy lại đúng lệnh để tiếp tục.
Nếu muốn dùng file báo dừng, mở terminal thứ hai tại BMP:

```powershell
New-Item -ItemType File -Path results/baselines_person1_600.sqlite3.stop -Force
```

Xóa file này trước phiên tiếp theo:

```powershell
Remove-Item -LiteralPath results/baselines_person1_600.sqlite3.stop
```

Giữ SQLite (bao gồm nghiệm), CSV chỉ là bản xuất. OPTIMAL/TIMEOUT/FEASIBLE đã lưu
được bỏ qua. `--retry-errors` chạy lại ERROR; INTERRUPTED và RUNNING còn sót sau
sự cố được chạy lại từ đầu. Không lưu trạng thái tìm kiếm bên trong một lượt.
Runner dừng phiên khi gặp ERROR để tránh lặp lỗi cài đặt/license trên mọi mẫu.

## Mô hình và cách đọc kết quả

- CPLEX MIP và Gurobi dùng biến nhị phân gán nhãn X[u,i], tổng hàng/cột bằng 1,
  và hai bất đẳng thức khoảng cách cho mỗi cạnh.
- CP Optimizer dùng biến nguyên nhãn, AllDifferent và khoảng cách tuyệt đối.
- Mỗi baseline chạy một lần/instance; không nhân thêm theo AMO hay linear/binary.
- Tất cả dùng RCM làm nghiệm ban đầu; không dùng Paper_LB để kết luận tối ưu.
- Giải toàn đồ thị, `Use_Components=False`, cận dưới tính riêng từng thành phần
  rồi lấy max để đúng cho đồ thị không liên thông. SAT trước đó có phân rã;
  cần ghi rõ khác biệt này khi báo cáo so sánh trên mẫu không liên thông.
- `--threads 1` giữ một luồng tìm kiếm/solver; solver dùng cùng số luồng đã chọn.
- Native time limit tính phần ngân sách còn lại sau thiết lập mô hình, chừa tối đa
  2 giây để lấy và gửi kết quả trước watchdog. Thời gian đo bắt đầu từ tính cận,
  bao gồm khởi động worker và dựng mô hình, không gồm đọc/download dữ liệu.
- Mọi nghiệm trả về đều được kiểm tra là hoán vị và tính lại bandwidth trên cạnh.
- `Bandwidth`/`UB_Found`: bandwidth của nghiệm hợp lệ đã giữ được.
- `LB_Proven`: cận tự tính, kết hợp cận engine khi có. `Gap_Absolute = UB - LB`.
- `OPTIMAL`: engine chứng minh tối ưu hoặc cận đã xác lập bằng bandwidth nghiệm.
- `TIMEOUT`: hết ngân sách, chưa chứng minh tối ưu; vẫn lưu nghiệm khả thi.
- `FEASIBLE`: có nghiệm hợp lệ, engine dừng chưa tối ưu và không do time limit.
- `Solution_Source=RCM`: dùng nghiệm RCM dự phòng, không khẳng định engine tìm ra nó.
- `Engine_Status` ghi lý do gốc. Nếu watchdog phải giết worker, nghiệm/bound mới
  trong engine có thể chưa gửi về; runner giữ RCM và cận ban đầu, không bịa tiến độ.
- `LIMIT`: n >= 400. `ERROR`: lỗi engine/license/code, không phải TIMEOUT.

OR-Tools CP-SAT là baseline thứ tư, dùng runner riêng `run_cpsat.py` để giữ nguyên
fingerprint của các lượt CPLEX/Gurobi đã chạy. Cài `ortools` trong `.venv` trước.

```powershell
.\.venv\Scripts\python.exe run_cpsat.py `
  --instances-file config/split42_person1.txt `
  --timeout 600 `
  --threads 1 `
  --retry-errors `
  --checkpoint results/cpsat_person1_600.sqlite3 `
  --output results/cpsat_person1_600.csv
```

14 lượt, ngân sách timeout cộng dồn 2 giờ 20 phút. CP-SAT dùng biến nhãn nguyên,
AllDifferent, khoảng cách tuyệt đối, RCM hint và giải toàn đồ thị như các baseline
khác. Tự kiểm tra nghiệm, lưu cận/UB, native time limit và watchdog. Ctrl+C một lần
đợi lưu lượt hiện tại rồi dừng; chạy lại cùng lệnh để resume. Stop-file tùy chọn
là `results/cpsat_person1_600.sqlite3.stop`; xóa nó trước phiên tiếp theo nếu đã tạo.

Không dùng `solve.py` hoặc runner SAT để thay cho lệnh baseline bên trên.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_baseline_runner.py -v
```

Các test engine CPLEX cần cài đặt/license tương ứng; các test còn lại kiểm tra
chứng chỉ, cận cho đồ thị không liên thông, timeout và resume/retry.
