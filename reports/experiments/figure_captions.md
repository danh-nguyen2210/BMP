# Danh mục hình và chú thích

## 01_dataset

Phân bố số đỉnh và số cạnh của 42 instance; các nhóm kích thước chỉ dựa trên n.

[PNG](figures/01_dataset.png) · [PDF](figures/01_dataset.pdf) · [SVG](figures/01_dataset.svg)

## 02_status_by_configuration

Trạng thái của 42 lượt trên mỗi cấu hình; ERROR được giữ riêng, TIMEOUT không đồng nghĩa không có nghiệm.

[PNG](figures/02_status_by_configuration.png) · [PDF](figures/02_status_by_configuration.pdf) · [SVG](figures/02_status_by_configuration.svg)

## 03_summary_table

BW: số lượt ghi nhận bandwidth; Match: số lượt bằng Paper_Best. Median gap tính trên BW lượt, không tính ô thiếu.

[PNG](figures/03_summary_table.png) · [PDF](figures/03_summary_table.pdf) · [SVG](figures/03_summary_table.svg)

## 04_quality_coverage

Độ phủ nghiệm và quan hệ với Paper_Best; mọi cấu hình dùng cùng mẫu số 42, không loại các lượt thiếu nghiệm khỏi tỷ lệ.

[PNG](figures/04_quality_coverage.png) · [PDF](figures/04_quality_coverage.pdf) · [SVG](figures/04_quality_coverage.svg)

## 05_gap_heatmap

Độ lệch bandwidth so với Paper_Best trên từng instance và cấu hình. Ô xám là thiếu bandwidth, không được tính là gap 0%.

[PNG](figures/05_gap_heatmap.png) · [PDF](figures/05_gap_heatmap.pdf) · [SVG](figures/05_gap_heatmap.svg)

## 06_optimal_cactus

Số instance có trạng thái OPTIMAL theo ngưỡng thời gian ghi nhận; TIMEOUT và ERROR không tạo điểm giải thành công.

[PNG](figures/06_optimal_cactus.png) · [PDF](figures/06_optimal_cactus.pdf) · [SVG](figures/06_optimal_cactus.svg)

## 07_amo_comparison

So sánh ba AMO trong từng solver SAT: số lượt OPTIMAL trên 42 instance và mean gap trên giao k instance có bandwidth ở cả ba AMO.

[PNG](figures/07_amo_comparison.png) · [PDF](figures/07_amo_comparison.pdf) · [SVG](figures/07_amo_comparison.svg)

## 08_encoding_clauses

Số mệnh đề SAT ghi nhận theo n, chỉ tính snapshot dương; k là số snapshot. Không phải phép đo RAM hoặc kích thước encoding tối đa.

[PNG](figures/08_encoding_clauses.png) · [PDF](figures/08_encoding_clauses.pdf) · [SVG](figures/08_encoding_clauses.svg)

## 09_baseline_proof_gap

Phân bố chênh lệch UB_Found − LB_Proven của các baseline; giá trị 0 là cận đã khép, không phải chỉ trùng Paper_Best.

[PNG](figures/09_baseline_proof_gap.png) · [PDF](figures/09_baseline_proof_gap.pdf) · [SVG](figures/09_baseline_proof_gap.svg)

## 10_size_group_outcomes

Tỷ lệ OPTIMAL và tỷ lệ ghi nhận bandwidth theo nhóm n; mẫu số N của từng nhóm được ghi trên trục.

[PNG](figures/10_size_group_outcomes.png) · [PDF](figures/10_size_group_outcomes.pdf) · [SVG](figures/10_size_group_outcomes.svg)
