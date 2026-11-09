# Notebook báo cáo thực nghiệm BMP

Notebook: [`BMP_Experimental_Results.ipynb`](../notebooks/BMP_Experimental_Results.ipynb).
Đầu vào duy nhất: [`results/results.csv`](../results/results.csv).
Notebook không chạy lại solver và không sửa dữ liệu đầu vào hay checkpoint.

## Chạy trong VS Code

1. Mở notebook, chọn kernel Python từ `.venv` của project.
2. Chọn **Restart Kernel**, rồi **Run All**.
3. Xem biểu đồ trực tiếp trong notebook hoặc lấy file xuất trong `reports/experiments/`.

Nếu thiếu thư viện, chạy từ thư mục gốc BMP:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements-analysis.txt
```

## Chạy toàn bộ từ Terminal

```powershell
& .\.venv\Scripts\python.exe -X utf8 scripts/run_analysis_notebook.py
```

Script sử dụng chính interpreter được gọi, không cần đăng ký kernel toàn cục.
Chỉ xử lý dữ liệu và xuất hình; không gọi CPLEX, Gurobi hoặc SAT solver.

## Sản phẩm

- `reports/experiments/figures/`: 10 hình, mỗi hình có PNG 300 dpi, PDF và SVG.
- `reports/experiments/tables/`: bảng tổng hợp, metadata instance, so sánh AMO,
  cận baseline, lỗi, thời gian bất thường và các ma trận kết quả để làm phụ lục.
  Mỗi bảng báo cáo có CSV và LaTeX; `analysis_rows.csv` chứa các cột phân tích phát sinh.
- `reports/experiments/experimental_findings.md`: nhận xét tự động theo dữ liệu.
- `reports/experiments/figure_captions.md`: chú thích cho từng hình.
- `reports/experiments/analysis_manifest.json`: hash đầu vào, phiên bản thư viện phân tích,
  quy tắc xử lý giá trị thiếu và trạng thái.

Các hình so sánh theo **cấu hình solver, AMO, instance và nhóm kích thước**,
không có phân nhóm hay nhãn tên máy. Không tự thêm thông số phần cứng chưa xác minh.
Giữ nguyên TIMEOUT kể cả khi bandwidth bằng tham chiếu; không thay bandwidth thiếu bằng 0.
CSV không có hoán vị nghiệm nên kiểm tra trong notebook là kiểm tra nhất quán dữ liệu,
không phải chứng nhận nghiệm độc lập.

Nếu cần sửa nội dung gốc bằng script, chỉnh `scripts/build_results_notebook.py`, rồi chạy:

```powershell
& .\.venv\Scripts\python.exe -X utf8 scripts/build_results_notebook.py
& .\.venv\Scripts\python.exe -X utf8 scripts/run_analysis_notebook.py
```

Lệnh build tạo lại notebook và xóa output cũ bên trong notebook. Không chạy build sau
khi chỉnh notebook thủ công nếu chưa chuyển các chỉnh sửa đó về script nguồn.
