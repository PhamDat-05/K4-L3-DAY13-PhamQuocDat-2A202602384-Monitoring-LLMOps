# Alert và runbook

Ba điều kiện trong [alert_rules.yaml](../config/alert_rules.yaml) được tính từ `data/logs.jsonl` trên cửa sổ trượt 5 phút; chỉ đánh giá khi có ít nhất một `request_received`. `duration: 5m` nghĩa là triệu chứng phải duy trì 5 phút liên tục. Kênh cảnh báo là Slack `#k4-l3b-alerts`, người phụ trách `student-2A202602384`.

## Alert 1

- **HighLatencyP95**, warning: P95 của `response_sent.latency_ms` > 2000 ms trong 5 phút. Đây là cảnh báo sớm trước ngưỡng SLO 3000 ms để nhận ra suy giảm latency khi request vẫn thành công. Người dùng nhận câu trả lời chậm.
- Mở panel Latency, xác định P95/P99, TTFT P95 và khoảng thời gian tăng.
- Lọc `response_sent` trong khoảng đó, lấy `correlation_id` của request chậm; so sánh với `request_received` cùng ID.
- Mở trace Langfuse theo `correlation_id`, so thời gian `retrieval` và `generation` để xác định bước gây chậm.
- **Mitigation:** nếu generation dài do prompt mới, đưa label `production` về version ổn định; nếu retrieval chậm trong challenge, tắt incident bằng `scripts/inject_incident.py --disable` sau khi lưu evidence. Trong vận hành thật, khôi phục dịch vụ retrieval sau khi xác nhận nguyên nhân. Nếu request đồng thời bị xếp hàng vì truy xuất đồng bộ đang chặn event loop, chuyển lời gọi blocking sang threadpool hoặc async client và kiểm thử tải trước khi phát hành.

## Alert 2

- **HighRequestErrorRate**, critical: `request_failed / request_received > 2%` trong 5 phút. Người dùng không nhận câu trả lời; vi phạm phần thành công của SLO.
- Mở panel Errors, xác nhận error rate và breakdown theo `error_type` trong khoảng cảnh báo.
- Lọc log `request_failed`, lấy một `correlation_id`, `error_type` và `tool_name`.
- Mở trace cùng ID, xem observation nào có trạng thái ERROR và đối chiếu với error type trong log.
- **Mitigation:** nếu lỗi ở retrieval, khôi phục vector store hoặc tắt `tool_fail` practice sau khi thu evidence; nếu lỗi ở generation, rollback prompt hoặc cấu hình mới gây lỗi. Gửi cập nhật vào cùng kênh Slack.

## Alert 3

- **LowRetrievalSuccess**, warning: tỷ lệ `tool_success == true` trên các request có `tool_name == retrieval` < 90% trong 5 phút. Người dùng mất context hoặc gặp lỗi khi truy xuất; liên quan guardrail `retrieval_success_rate_pct_min`.
- Mở panel Errors để xác nhận retrieval success giảm cùng thời điểm, kiểm tra breakdown lỗi.
- Lọc log `tool_name == retrieval` và `tool_success == false`, lấy `correlation_id` và thời gian.
- Mở trace cùng ID, xem observation `retrieval` và đối chiếu với generation; kiểm tra health của vector store.
- **Mitigation:** khôi phục backend retrieval hoặc dùng fallback đã được kiểm chứng; trong practice, tắt `tool_fail` sau khi lưu evidence. Xác nhận tỷ lệ phục hồi trên dashboard trước khi đóng alert.
