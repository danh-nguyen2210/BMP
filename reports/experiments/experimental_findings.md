# Bản nháp nhận xét thực nghiệm

Tập đánh giá gồm 42 instance có n < 400 trong Table 6 và Table 7, với 16 cấu hình
(12 SAT và 4 baseline), tổng cộng 672 lượt. Giới hạn đặt cho mỗi lượt là 600 giây.

Kết quả ghi nhận 63 lượt OPTIMAL, 603 lượt TIMEOUT
và 6 lượt ERROR. Có 430/672 lượt ghi nhận
bandwidth; 242 lượt còn lại không được gán bandwidth bằng 0.
Trong các lỗi, 6 mô tả lỗi có chứa MemoryError/OOM; đây là phân loại từ log,
không phải phép đo độc lập về bộ nhớ.

Cấu hình có nhiều lượt chứng minh tối ưu nhất là cp-sat, với
11/42 instance. Cấu hình có nhiều lượt trùng Paper_Best nhất
là cplex-cp, với 21/42 instance.
Hai tiêu chí này đo hai khía cạnh khác nhau; không mặc định cấu hình tốt nhất theo một
tiêu chí sẽ tốt nhất theo mọi tiêu chí.

Nếu lấy bandwidth tốt nhất trong 16 cấu hình cho mỗi instance, có 22/42
instance bằng Paper_Best. Đây là kết quả tổng hợp của cả tập cấu hình, không phải kết quả
của một thuật toán trong một lượt 600 giây. Có 11/42 instance được ít nhất
một cấu hình ghi nhận OPTIMAL.

Có 47 lượt TIMEOUT đạt bandwidth bằng cả Paper_LB và Paper_Best.
Notebook giữ nguyên trạng thái TIMEOUT: trùng giá trị tối ưu tham chiếu không đồng nghĩa
runner đã hoàn tất chứng minh tối ưu. Việc dùng các cận tham chiếu còn phụ thuộc cùng
định nghĩa và dữ liệu đồ thị.

Có 4 lượt có Runtime_s > 605 giây; các thời gian gốc được giữ trong bảng
01_runtime_anomalies. Biểu đồ cactus chỉ đếm OPTIMAL; không tính TIMEOUT như giải xong ở 600 giây.

## Giới hạn

- Mỗi cặp instance–cấu hình chỉ có một kết quả trong CSV, chưa có các lần lặp độc lập
  để ước lượng biến thiên giữa các lần chạy. Không báo độ lệch chuẩn của lần lặp hoặc
  kết luận ý nghĩa thống kê từ dữ liệu này.
- CSV không chứa hoán vị nghiệm, chứng chỉ UNSAT, RAM đỉnh hoặc thời điểm tìm nghiệm
  tốt nhất. Không thể kiểm chứng lại tất cả nghiệm hay kết luận về RAM chỉ từ bảng này.
- Chỉ đánh giá 42 instance đã chọn; không ngoại suy độ phủ tới toàn bộ Harwell–Boeing.
- SAT bật Use_Components, các baseline không bật; so sánh phản ánh cấu hình triển khai
  hoàn chỉnh. Nghiệm baseline có thể là RCM dự phòng, không nhất thiết do engine tìm mới.
- Thời gian chỉ mô tả lượt chạy đã ghi nhận. CSV không đủ metadata để xác nhận điều kiện
  phần cứng thống nhất; không suy ra speedup được kiểm soát hoặc so thời gian trực tiếp
  với DRSA có điều kiện dừng khác.
- Median/mean gap trên lượt có bandwidth chịu ảnh hưởng của độ phủ nghiệm. Phân tích
  AMO trên giao instance làm rõ mẫu so sánh, nhưng không loại bỏ thiên lệch do chỉ lấy
  các instance có nghiệm ở cả ba AMO.
