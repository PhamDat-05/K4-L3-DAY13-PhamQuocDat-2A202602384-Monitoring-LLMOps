# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

## 1. Thông tin học viên

- **Họ và tên:** Phạm Quốc Đạt
- **MSSV:** 2A202602384
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/PhamDat-05/K4-L3-DAY13-PhamQuocDat-2A202602384-Monitoring-LLMOps
- **Commit SHA cuối:** chưa chốt; cần điền sau khi commit toàn bộ source và evidence.
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (file riêng của Lab Coach được giữ trong `.gitignore`, không nộp file).
- **Project Langfuse cá nhân:** `day13-k4-l3b-2A202602384`, xác nhận bằng API của project trong evidence CP2.

## 2. Evidence index

| Nội dung | Evidence thực tế |
|---|---|
| Baseline log validator | [00-baseline-log-validator.txt](evidence/00-baseline-log-validator.txt) |
| Pytest cuối | [01-pytest.txt](evidence/01-pytest.txt) |
| Log validator cuối | [02-log-validator.txt](evidence/02-log-validator.txt) |
| Dashboard validator | [03-dashboard-validator.txt](evidence/03-dashboard-validator.txt) |
| Hai log JSON cùng correlation ID | [04-structured-log.png](evidence/04-structured-log.png), [JSON](evidence/04-structured-log.json) |
| Email, điện thoại, thẻ giả đã redacted | [05-pii-redaction.png](evidence/05-pii-redaction.png), [JSON](evidence/05-pii-redaction.json) |
| 13 trace thật, cây observations và metadata được đọc lại qua Langfuse API | [06-08-langfuse-verification.txt](evidence/06-08-langfuse-verification.txt) |
| Prompt v1/v2, promote/rollback và trace ID của từng trạng thái | [09-10-prompt-workflow.txt](evidence/09-10-prompt-workflow.txt) |
| Dashboard runtime 6 panel | [11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| Incident: baseline, injection, workload và recovery | [12a-baseline](evidence/12a-challenge-baseline.txt), [12b-injection](evidence/12b-challenge-injection.txt), [12c-load](evidence/12c-challenge-load.txt), [12d-disabled](evidence/12d-challenge-disabled.txt), [12e-recovery](evidence/12e-challenge-recovery.txt) |
| Incident metrics | [12-incident-metric.png](evidence/12-incident-metric.png), [số đo theo ba giai đoạn](evidence/12-incident-metrics.txt) |
| Incident log cùng correlation ID | [13-incident-log.png](evidence/13-incident-log.png), [JSON đã lọc](evidence/13-incident-log.json) |
| Incident trace Langfuse được API xác minh | [14-incident-trace-verification.txt](evidence/14-incident-trace-verification.txt); ảnh UI `14-incident-trace.png` chờ chụp. |
| Rà soát file chuẩn bị nộp | [15-submission-scan.txt](evidence/15-submission-scan.txt): kiểm tra đường dẫn cấm, key Langfuse và nội dung query riêng của challenge. |

Evidence `06–10` và `14` hiện là output API đọc trực tiếp từ project cá nhân, chưa phải ảnh giao diện Langfuse. Danh sách ảnh `.png` cần chụp từ UI, nội dung bắt buộc và đúng tên file nằm tại [CAPTURE_LANGFUSE.md](evidence/CAPTURE_LANGFUSE.md).

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | CP1/CP2 hiện tại | Cách kiểm chứng |
|---|---:|---:|---|
| `validate_logs.py` | 30/100; 28 records cũ | 100/100; số record cuối xem evidence 02, 0 leak | Evidence 00 và 02 |
| `validate_dashboard.py` | 6/6 contract; chưa có dashboard runtime | 6/6 contract và trang `/dashboard` có dữ liệu thật | Evidence 03 và 11 |
| `pytest` | 18 pass, 4 lỗi môi trường do thư mục temp bị chặn | 26 pass với `-p no:cacheprovider --basetemp=.test-tmp` | Evidence 01 |
| Trace được đọc lại từ Langfuse | Chưa xác minh | 13 trace CP2 và 10 trace đối chứng/sự cố CP3; mỗi trace có AGENT → RETRIEVER + GENERATION | Evidence 06–08 và 14 |
| PII leak theo validator | 0 trong log baseline | 0 trong log cuối | Evidence 02 và 05 |
| Latency P95 / TTFT P95 | 1271 / 51 ms trên 10 response | 1240 / 50 ms trên 13 response | `data/logs.jsonl`, dashboard |
| Error rate / retrieval success | Chưa xác minh | 0% / 100% | Dashboard 60 phút |
| Cost / token / quality proxy | Chưa xác minh | 0.028404 USD / 468 input + 1800 output / 0.885 | Dashboard 60 phút |

Các số latency/cost/token trong bảng là lượt CP2 trước khi chạy challenge, đối chiếu được với ảnh 11. CP3 có bảng đối chứng riêng ở mục 7. `cost_usd` là ước tính theo giá cấu hình trong fake LLM, không phải hóa đơn nhà cung cấp. Log local được giữ ngoài Git theo `.gitignore`; evidence đã trích các trường an toàn cần chấm.

## 4. CP1 — Logging và PII

`CorrelationIdMiddleware` xóa contextvars đầu mỗi request, chấp nhận `x-request-id` đúng `req-<8 hex>` hoặc sinh ID mới, bind vào context và trả `x-request-id` cùng `x-response-time-ms` trong header. Endpoint `/chat` bind `user_id_hash`, `session_id`, `feature`, `model`, `env` trước event `request_received`. Cùng ID xuất hiện ở `request_received`, `response_sent`, trace metadata và `response_sent.trace_id`.

Processor `scrub_event` xử lý đệ quy mọi chuỗi trong event trước `JsonlFileProcessor` và JSON renderer. Các mẫu email, số điện thoại Việt Nam, CCCD, thẻ và một số dấu hiệu hộ chiếu/địa chỉ được che. Regex điện thoại yêu cầu ranh giới ký tự chữ/số để không cắt nhầm trace ID hex. Raw prompt/output không được đưa vào log; chỉ có preview đã scrub. Evidence 05 là dữ liệu test giả của repo; validator cuối báo 0 PII leak. Test bổ sung kiểm tra header, metadata, CCCD/thẻ và tính toàn vẹn trace ID.

## 5. CP2 — Tracing và prompt versioning

`LabAgent.run` là AGENT observation. Bên dưới là `retrieval` loại RETRIEVER và `generation` loại GENERATION. Generation ghi model, preview đã scrub, TTFT, input/output token, cost và liên kết trực tiếp tới managed prompt. Root và các child đều có `correlation_id` trong metadata. Tracing không capture raw input/output của agent.

Workflow dùng prompt `day13-chat`: v1 mang `baseline` và `production`, v2 mang `candidate`. Cùng query đầu của sample workload được chạy với `baseline` và `candidate`, sau đó `production` được chuyển sang v2 và rollback về v1. `scripts/cp2_prompt_demo.py` tạo workload; `scripts/verify_cp2.py` đọc lại 13 trace qua Langfuse Observations API v2 và xác minh quan hệ cha-con, project, correlation ID, label/version, token và cost. API xác nhận project `day13-k4-l3b-2A202602384`.

[Mở trace baseline trong Langfuse](https://cloud.langfuse.com/project/cmunixfu607wfad0clkugh1wb/traces/91d763ab8ef05b5315e2ccce2802c59a) (cần đăng nhập project cá nhân).

| Trạng thái | Correlation ID | Trace ID | Version thực tế |
|---|---|---|---:|
| `baseline` | `req-93fdd186` | `91d763ab8ef05b5315e2ccce2802c59a` | v1 |
| `candidate` | `req-72868a58` | `e401adb14ea0a97c0ce66e76eb82d361` | v2 |
| `production` sau promote | `req-88ba7174` | `f4b6afcd285c4ff7e322f7646a5823f6` | v2 |
| `production` sau rollback | `req-e3978701` | `77780130a307b2407d6c408f8a1ed358` | v1 |

Sau workflow, nhãn `production` trỏ lại v1. `LANGFUSE_PROMPT_CACHE_TTL_SECONDS=0` chỉ được đặt trong script demo để thấy chuyển nhãn ngay; app mặc định cache 60 giây. Khi Langfuse không truy cập được, app ghi `prompt_source=local-fallback` thay vì giả version từ Cloud.

## 6. CP2 — Dashboard, SLO và alerts

Dashboard chạy tại `http://127.0.0.1:8765/dashboard` trong lần kiểm tra này; khi chạy app ở cổng 8000 thì đường dẫn là `/dashboard`. Endpoint `/dashboard-data` tính trực tiếp từ `data/logs.jsonl` trong cửa sổ trượt 60 phút, refresh mỗi 30 giây. Sáu panel gồm Latency P50/P95/P99 và TTFT P95; Traffic count/rate; Error rate, breakdown và retrieval success; Cost theo phút/tổng; input/output Tokens; Quality proxy mean. Tên, đơn vị và threshold lấy từ [dashboard.yaml](../config/dashboard.yaml). Ảnh runtime ở evidence 11 cho thấy 13 request trong 60 phút; rate 0.22 request/phút phản ánh workload lab ngắn, không phải sự cố traffic.

[SLO](../config/slo.yaml) là 99.5% request có `response_sent` và `latency_ms <= 3000` trong 28 ngày. Error budget = `100% - 99.5% = 0.5%`: với 10,000 request, tối đa 50 request được phép lỗi hoặc quá chậm. Ngưỡng 3000 ms cao hơn P95 baseline 1271 ms, chừa chỗ cho biến động mạng khi lấy managed prompt. Workload hiện tại đạt 13/13 good request; cỡ mẫu nhỏ nên không suy ra độ tin cậy 28 ngày.

Ba alert symptom based trong [alert_rules.yaml](../config/alert_rules.yaml): P95 latency > 2000 ms (cảnh báo sớm sau bài học CP3), request error rate > 2%, retrieval success < 90%; đều có `duration: 5m`, severity, owner và Slack `#k4-l3b-alerts`. [Runbook](../docs/alerts.md) yêu cầu kiểm tra panel, lọc log theo `correlation_id`, mở trace và chọn mitigation theo span thực tế. Ngưỡng SLO vẫn là 3000 ms; alert 2000 ms phát hiện suy giảm trước khi vi phạm SLO. Đây là cấu hình/ngưỡng lab; repo chưa tích hợp dịch vụ gửi thông báo Slack tự động.

## 7. CP3 — Điều tra challenge chính thức

- **Challenge ID/cohort:** `day13-k4-l3b-monitoring-llmops-v1` / K4. File Coach không bị sửa hoặc commit; SHA-256 tại thời điểm nhận: `F8A1B15BFB62F5C91160CB27665D4EFBB9EC89B2F8B6D5EC69E9E874443E0D4F`.
- **Khoảng điều tra:** 2026-09-30 03:55:21.892–03:55:35.170 UTC (10:55:21–10:55:35 giờ Việt Nam); lượt đối chứng ở 03:55:05–03:55:06 UTC. Dùng cùng 5 query của challenge qua `load_test.py --challenge --concurrency 5` ở cả hai lượt; không công bố seed hoặc nội dung query.
- **Metrics → triệu chứng:** P95 latency từ **975 ms** (đối chứng) lên **2652 ms** (challenge), tăng 1677 ms = 2.72 lần. Số request vượt ngưỡng 2000 ms của Coach tăng từ 0/5 lên 5/5. TTFT P95 giữ 50 ms, lỗi 0/5 và retrieval `tool_success=true`, nên đây là suy giảm thời gian chứ không phải lỗi request hay tăng TTFT. Dashboard cửa sổ 60 phút trong ảnh 12 cho thấy P95 2652 ms. SLO 3000 ms vẫn đạt 28/28 request trong cửa sổ đó; việc này giải thích vì sao cần cảnh báo sớm ở 2000 ms.
- **Logs → request đại diện:** `response_sent` lúc `2026-09-30T03:55:24.545965Z`, `correlation_id=req-cf6b725c`, `latency_ms=2652`, `ttft_ms=50`, `trace_id=f2436bd213a6d402947c31faf387cbe5`, `tool_name=retrieval`, `tool_success=true`. Cặp `request_received`/`response_sent` đã lọc an toàn nằm trong evidence 13; các request còn lại nằm trong evidence 12 text.
- **Traces → span gây ảnh hưởng:** [trace Langfuse của request đó](https://cloud.langfuse.com/project/cmunixfu607wfad0clkugh1wb/traces/f2436bd213a6d402947c31faf387cbe5) có root AGENT **2652 ms**, child RETRIEVER **2501 ms** và child GENERATION **151 ms**. Cả ba observation có `correlation_id=req-cf6b725c`; prompt vẫn là `day13-chat` v1. P95 retrieval của 5 trace đối chứng là 1 ms, của 5 trace challenge là 2502 ms. Evidence 14 là kết quả đọc lại trực tiếp từ Langfuse API.
- **Root cause:** incident chính thức bật `rag_slow`; hàm `retrieve()` trong `app/mock_rag.py` chờ 2.5 giây khi cờ này bật. Thời gian tăng nằm trọn ở retrieval, không nằm ở generation/prompt. Lệnh `agent.run()` đồng bộ trong `/chat` async làm các request concurrent bị xếp hàng thêm; load test phía client tăng từ khoảng 1.77 giây lên 10.63–13.29 giây. Đây là suy luận từ trace, log và code, không phải đo trực tiếp của một queue span riêng.
- **Fix action đã thực hiện:** chạy `scripts/inject_incident.py --disable`, xác nhận `rag_slow=false`, rồi chạy lại đúng 5 query. Lượt phục hồi có P95 **914 ms**, 0/5 request vượt 2000 ms; chi tiết ở evidence 12d/12e/12 text.
- **Preventive measure:** đặt cảnh báo P95 > 2000 ms duy trì 5 phút, giữ SLO 3000 ms, cập nhật [runbook](../docs/alerts.md) để khoanh vùng retrieval span. Với hệ thống thật, chuyển lời gọi retrieval blocking ra threadpool hoặc async client và kiểm thử concurrency trước khi phát hành. Cảnh báo `duration: 5m` là quy tắc cho sự cố kéo dài; lượt challenge 13 giây này không đủ thời lượng để khẳng định alert đã phát ra.

## 8. Giải thích và tự đánh giá

- **Quyết định kỹ thuật:** scrub toàn bộ giá trị chuỗi trước khi ghi JSON, đồng thời chỉ gửi preview đã scrub lên Langfuse; việc scrub ở cả hai ranh giới ngăn payload lồng nhau hoặc exception text lọt ra ngoài.
- **Lỗi đã gặp:** khi promote prompt, Langfuse từ chối cập nhật label `latest` vì đây là nhãn tự quản lý. Script demo đã loại `latest` khỏi `new_labels`, sau đó chạy thành công promote và rollback. Một regex điện thoại ban đầu còn cắt nhầm chuỗi hex của trace ID; đã sửa và bổ sung regression test.
- **Metrics → Logs → Traces:** P95 2652 ms trong cửa sổ challenge → log `req-cf6b725c` có latency 2652 ms và trace ID → trace đó chỉ ra retrieval 2501 ms, generation 151 ms → kết luận retrieval chậm là nguyên nhân.
- **Vai trò LLMOps:** prompt version giúp truy vết và rollback; token/cost cho biết tác động của prompt đến tài nguyên; SLO và error budget định lượng mức dịch vụ chấp nhận được.
- **Điều học được:** P95 của request và độ dài retrieval span cần được xem cùng nhau; ở đây request vượt ngưỡng cảnh báo 2000 ms dù TTFT, lỗi và SLO 3000 ms vẫn bình thường. So sánh cùng workload trước và sau khi tắt incident giúp xác nhận biện pháp xử lý.
- **Giới hạn hiện tại:** ảnh UI Langfuse 06–10 và 14 cùng commit SHA cuối cần bổ sung trước khi nộp chính thức. Dữ liệu challenge gốc luôn giữ ngoài Git.

## 9. Checklist trước khi nộp

- [x] CP1–CP3 có source, tests, validators, dashboard và chuỗi metric → log → trace từ challenge chính thức.
- [x] 13 trace thuộc project Langfuse cá nhân, liên kết log bằng correlation ID; prompt v1/v2 và rollback được API xác minh.
- [x] Evidence hiện có dùng đường dẫn tương đối, không chứa key/secret hoặc PII thô.
- [ ] Chụp ảnh UI Langfuse cho trace list, waterfall, metadata, prompt versions, rollback và incident trace theo [CAPTURE_LANGFUSE.md](evidence/CAPTURE_LANGFUSE.md).
- [ ] Chốt commit SHA, chạy lại validators trên commit cuối và nộp URL/SHA qua LMS/Codelabs.
