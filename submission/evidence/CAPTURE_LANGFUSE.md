# Ảnh Langfuse cần chụp trước khi nộp

Lưu toàn bộ ảnh `.png` dưới `submission/evidence/` của repo này. Mở đúng project **`day13-k4-l3b-2A202602384`** trên Langfuse Cloud. Ảnh cần thấy tên project và dữ liệu đọc được; tránh trang API Keys, public/secret key, PII thô và nội dung query riêng của challenge. Ở trace incident, chỉ mở waterfall và metadata cần đối chiếu, không mở rộng input/output chứa query. Không sửa ảnh để thay đổi kết quả. Các trace ID và quan hệ span đã được xác minh bằng API trong `06-08-langfuse-verification.txt` và `14-incident-trace-verification.txt`.

| Tên file `.png` cần lưu | Chụp màn hình gì | Dữ liệu cần đọc được |
|---|---|---|
| `06-trace-list.png` | **Tracing → Traces** của project cá nhân, chọn khoảng thời gian gồm workload CP2 ngày 30/09/2026 khoảng 10:26 giờ Việt Nam. | Tên project, time range và ít nhất 10 trace do workload tạo. Nếu một trang chỉ hiện ít hơn 10 dòng, tăng page size trước khi chụp. |
| `07-trace-waterfall.png` | Mở [trace CP2 baseline](https://cloud.langfuse.com/project/cmunixfu607wfad0clkugh1wb/traces/91d763ab8ef05b5315e2ccce2802c59a), chọn waterfall/tree. | `lab-agent-run` là root AGENT; `retrieval` RETRIEVER và `generation` GENERATION là hai child; cùng trace ID và tên project. |
| `08-trace-metadata.png` | Trong cùng trace baseline, mở chi tiết **generation** và metadata. | `correlation_id=req-93fdd186`, model `claude-sonnet-4-5`, prompt `day13-chat` label `baseline` version `1`, input/output tokens và cost. Nếu cần hai ảnh để đọc đủ, thêm `08b-trace-usage.png` và dẫn cả hai trong report. |
| `09-prompt-versions.png` | **Prompts → day13-chat → Versions**. | Project cá nhân, v1 mang `baseline` + `production`, v2 mang `candidate`, tên prompt và số version. Đây là trạng thái cuối sau rollback. |
| `10a-prompt-promoted.png` | Trạng thái **sau khi chuyển** label `production` sang v2 trong Langfuse UI. | Project, `day13-chat`, version 2 và label `production`. Có thể dùng lịch sử thay đổi nếu UI hiển thị rõ lần promote đã thực hiện; nếu không, chuyển label trong UI rồi chụp. |
| `10b-prompt-rollback.png` | **Rollback** label `production` về v1 trong UI rồi chụp trạng thái cuối. | Project, `day13-chat`, version 1 mang `baseline` + `production`, v2 còn `candidate`. Giữ `production` ở v1 sau khi chụp. |
| `14-incident-trace.png` | Mở [trace challenge chính thức](https://cloud.langfuse.com/project/cmunixfu607wfad0clkugh1wb/traces/f2436bd213a6d402947c31faf387cbe5), xem waterfall và metadata. | Project, trace ID, `correlation_id=req-cf6b725c`, root khoảng 2652 ms, `retrieval` khoảng 2501 ms, `generation` khoảng 151 ms. Nếu waterfall và metadata không vừa một ảnh, lưu thêm `14b-incident-metadata.png` và dẫn cả hai trong report. |

Đối với bằng chứng prompt rollback, báo cáo đã có trace v1 `91d763ab8ef05b5315e2ccce2802c59a` và trace v2 `e401adb14ea0a97c0ce66e76eb82d361`. Ảnh `10a`/`10b` cần thể hiện thay đổi label trên Langfuse UI; không chụp trang chứa key.

Các ảnh **không cần chụp từ Langfuse** đã có sẵn: `04-structured-log.png`, `05-pii-redaction.png`, `11-dashboard-overview.png`, `12-incident-metric.png` và `13-incident-log.png`. Kết quả test/validator là các file `.txt` 01–03.
