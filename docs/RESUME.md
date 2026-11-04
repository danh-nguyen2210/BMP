# Chạy benchmark theo phiên và tiếp tục hôm sau

Runner `run_benchmarks.py` tự lưu sau **từng lượt instance–solver–AMO** vào SQLite.
Chạy lại cùng lệnh sẽ bỏ qua lượt đã hoàn thành. Không cần giữ Python chạy qua đêm.
Đây là resume giữa các lượt, không phải lưu toàn bộ bộ nhớ SAT khi đang giải dở.

## Chạy 23 instance của người 1

Tại thư mục gốc BMP, dùng môi trường Python có `numpy`, `scipy`, `python-sat`.
Nếu dùng `.venv` của dự án trong PowerShell:

```powershell
.\.venv\Scripts\python.exe run_benchmarks.py --instances-file config/instances_person1.txt --amo all --timeout 600 --session-hours 4 --checkpoint results/person1.sqlite3 --output results/person1.csv
```

- File danh sách có đúng 23 instance theo phân công.
- `--amo all`: 4 biến thể SAT × 5 AMO = **20 cấu hình/instance**, 460 lượt.
  Runner này chưa điều phối 4 baseline CP/MIP.
- Đổi thành `--amo sequential` để chỉ chạy 4 cấu hình SAT/instance.
- `--session-hours 4`: không nhận lượt mới khi thời gian còn lại không đủ ngân sách
  `--timeout`. Tiền xử lý và dọn tiến trình có thể gây chênh lệch nhỏ; đây không phải
  lịch tự tắt máy. Không sleep/hibernate giữa một lượt benchmark.
- `--max-jobs 5`: tùy chọn dừng sau 5 lượt mới, tiện kiểm tra trước đợt chạy dài.
- `--solvers order-inc`: chỉ chạy một biến thể; bỏ tùy chọn để chạy cả bốn.
- `--instances pores_1 ibm32`: chọn nhanh vài instance thay cho `--instances-file`.

Hôm sau, chạy lại **đúng lệnh trên**. Có thể thay đổi thời lượng phiên, số lượt tối đa
hoặc mở rộng danh sách instance/solver/AMO; các lượt đã có cùng cấu hình vẫn được bỏ qua.
`--resume` là cờ tùy chọn để dễ đọc: resume vốn luôn bật.

## Dừng để tắt máy

**Nhấn Ctrl+C một lần** trong terminal. Runner thông báo sẽ dừng, đợi lượt hiện tại
hoàn thành hoặc hết timeout, lưu kết quả rồi thoát. Đợi dòng **“Đã dừng an toàn”**
và dấu nhắc terminal trở lại trước khi tắt máy. Ctrl+C lặp lại vẫn yêu cầu dừng mềm.

Nếu không tiện dùng Ctrl+C, mở PowerShell thứ hai tại BMP:

```powershell
New-Item -ItemType File -Path results/person1.sqlite3.stop -Force
```

Runner kiểm tra file này giữa các lượt. Trước phiên tiếp theo, xóa đúng stop-file:

```powershell
Remove-Item -LiteralPath results/person1.sqlite3.stop
```

Có thể đổi vị trí bằng `--stop-file`. Không đóng cưỡng bức terminal để yêu cầu dừng mềm.
Nếu mất điện/kill tiến trình, kết quả đã commit vẫn được giữ; lượt `RUNNING` được
chuyển thành `INTERRUPTED` khi mở checkpoint lần sau và được chạy lại **từ đầu**.
Lịch sử lần chạy gián đoạn được giữ riêng, không cộng vào runtime của lần chạy mới.

## Các file cần giữ

- `results/person1.sqlite3`: checkpoint gốc; có kết quả, phép gán nhãn, cấu hình,
  dấu thời gian UTC, thông tin máy và lịch sử lần chạy. **Không xóa nếu muốn resume.**
- `results/person1.csv`: bản xuất dạng dài, một hàng mỗi lần chạy, không append trùng
  khi resume. Có thể tái tạo từ SQLite bằng cách chạy lại lệnh.
- Nếu Excel đang khóa CSV, SQLite vẫn lưu bình thường. Đóng Excel, chạy lại để xuất lại.
- Sau sự cố, giữ cả các file SQLite phụ đi kèm (nếu có) để SQLite tự phục hồi.
  Sao lưu checkpoint khi runner đã thoát; mỗi máy dùng file checkpoint riêng.

Chỉ một runner được mở cùng một checkpoint tại một thời điểm. CSV mới không dùng
schema cũ của `benchmark_summary.csv`; runner từ chối ghi đè CSV cũ. Công cụ vẽ cũ
vẫn đọc `benchmark_summary.csv`, chưa hỗ trợ CSV resume dạng dài.

Khi tổng hợp báo cáo, lấy lần chạy mới nhất theo `Job_ID`, tách rõ trạng thái;
không coi `LIMIT`, `ERROR`, `INTERRUPTED` là lượt giải thành công. Thông tin `Machine`
và `Platform` được giữ để báo cáo đúng môi trường thực nghiệm.

## Quy tắc bỏ qua và chạy lại

| Trạng thái lần gần nhất | Lần chạy tiếp theo |
| --- | --- |
| `OPTIMAL`, `TIMEOUT`, `LIMIT` | Bỏ qua |
| `ERROR`, `DOWNLOAD_ERROR` | Bỏ qua; thêm `--retry-errors` để thử lại |
| `RUNNING` còn sót sau sự cố | Đánh dấu `INTERRUPTED`, rồi chạy lại |
| `INTERRUPTED` | Chạy lại từ đầu |

`TIMEOUT` là kết quả đã dùng hết ngân sách, không tự chạy lại để kéo dài thời gian giải.
Runner đánh dấu `LIMIT` cho `n >= 400`; instance đã biết vượt ngưỡng không cần tải file.
Quy tắc này thuộc runner benchmark; CLI `solve.py` vẫn có chính sách kích thước cũ.

Khóa checkpoint gồm instance, hash dữ liệu, solver, AMO, chiến lược, timeout,
heuristic/phân rã, ngưỡng kích thước, hash code và phiên bản môi trường liên quan.
**Thay đổi code solver/runner, dữ liệu hoặc cấu hình tạo công việc mới**; không lấy
kết quả cũ làm kết quả của cấu hình mới. Nên chốt code trước khi chạy chính thức.
Các kết quả CSV cũ thiếu thông tin này không được tự nhập thành checkpoint.

## Kiểm tra tính năng

```powershell
python -m unittest discover -s tests -p test_resume.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_watchdog.py -v
```

Bộ test resume dùng thư viện chuẩn. Bộ watchdog dùng SciPy/PySAT và tiến trình thật,
bao gồm giới hạn thời gian cho đồ thị nhỏ, truyền lỗi worker và nhận nghiệm SAT.
