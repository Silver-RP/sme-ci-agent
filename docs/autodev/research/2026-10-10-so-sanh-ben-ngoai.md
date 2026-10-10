# So sánh plugin auto-dev với cách làm bên ngoài (2026-10-10)

Người đọc: leader. Mục đích: tìm cách giải sẵn có cho các vấn đề plugin đang gặp, nhất là **B1 = 0,71** (reviewer lỏng: 18/18 task PASS vòng 1, audit 3 vẫn tìm 12 lỗ hổng mới mức cao + vừa). Chỉ giữ ý gắn được với một vấn đề đã gặp (LESSONS hoặc chỉ số B). Mỗi đề xuất cần leader duyệt trước khi vào ROADMAP.

## 1. Nguồn đã đọc

| Nguồn | Nội dung chính dùng ở đây |
|---|---|
| OpenHands, [The Verification Stack](https://www.openhands.dev/blog/20260506-the-verification-stack) (05/2026) | 2 tầng kiểm: critic (model nhỏ) chấm quá trình làm của agent trước khi đẩy code; reviewer PR theo danh sách 10 tình huống + agent QA chạy phần mềm thật. Reviewer đạt độ chính xác ~85%, bắt > 50% góp ý được dùng. Danh sách ưu tiên: cấu trúc dữ liệu; bảo mật và đúng đắn (race condition); **thiếu test (loại test chỉ dùng mock)**; phụ thuộc |
| SWR-Bench, [Benchmarking and Studying the LLM-based Code Review](https://arxiv.org/html/2509.01494v2) | LLM review bắt lỗi kém (F1 ~12–19%). Chạy review **nhiều lần** rồi gộp: tỷ lệ bắt lỗi (recall) tăng 119% (n = 10); **n = 5 là điểm cân bằng** giữa chi phí và lợi ích. Các lần chạy độc lập cho kết quả khác nhau nhiều ("ngẫu nhiên đáng kể") |
| Augment, [Deep Code Review: Recall vs. Precision](https://www.augmentcode.com/guides/deep-code-review-recall-vs-precision) | Độ chính xác (precision) dễ đo và dễ làm đẹp; recall mới khó và cần bộ lỗi có sẵn đáp án. Reviewer chỉ đọc diff bỏ sót lỗi xuyên file (luồng trạng thái, hợp đồng API); đọc cả repo thì bắt được nhiều hơn |
| Anthropic, [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices) | Cho agent một phép kiểm chạy được; cổng cứng bằng Stop hook; **phiên mới** để review (không thiên vị code vừa viết); bước review đối kháng; cảnh báo: reviewer được bảo "tìm lỗi" sẽ luôn tìm ra, nên chỉ chặn lỗi ảnh hưởng đúng đắn |
| Anthropic, [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | File tiến độ + danh sách tính năng có trường `passes`; **cấm sửa hay xoá test**; nếu không bắt kiểm đầu-cuối thì agent tuyên bố xong sớm |
| Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Mẫu evaluator-optimizer (cần tiêu chí rõ); song song kiểu **bỏ phiếu** cho review; giữ đơn giản, chỉ thêm phức tạp khi đo thấy cần; công cụ "poka-yoke" (khó dùng sai) |
| SWE-agent, [Agent-Computer Interfaces](https://hyper.ai/en/papers/2405.15793) (NeurIPS 2024) | Ít lệnh, phản hồi rõ sau mỗi lệnh; lint ngay sau khi sửa giúp agent sửa sai sớm; lỗi chủ yếu do cài sai và lỗi sửa dây chuyền |
| Meta, [Mutation-Guided LLM Test Generation (ACH)](https://arxiv.org/html/2501.12862v1) | Tạo đột biến (cố ý gây lỗi) rồi sinh test giết đột biến; kỹ sư nhận 73% test. Dùng đột biến để đo độ mạnh của test |
| Cursor, [Reward hacking in coding benchmarks](https://cursor.com/blog/reward-hacking-coding-benchmarks); [EvilGenie](https://arxiv.org/pdf/2511.21654) | Agent "ăn gian" để qua kiểm: sửa file test, hard-code kết quả, lấy bản sửa có sẵn. Cách phát hiện: test giữ kín, LLM chấm, **phát hiện sửa file test** |
| [Agent harness evolution](https://arxiv.org/abs/2607.03691) (07/2026) | Chất lượng agent thay đổi theo từng bản harness, không chỉ theo model. Phải đo lại mỗi khi đổi prompt hay luồng |

## 2. Đối chiếu với plugin

| Chủ đề | Bên ngoài | Plugin hiện tại | Đánh giá |
|---|---|---|---|
| Tách người làm / người kiểm | Phiên mới, không thấy suy luận của người làm (Anthropic); nhiều tầng (OpenHands) | 4 tầng: reviewer (từng task), supervisor Opus (từng mốc), audit (định kỳ), người duyệt | **Ngang hoặc hơn** về số tầng |
| Model của reviewer | Gộp nhiều model cho recall cao hơn (SWR-Bench Multi-Agg) | Reviewer **Sonnet, cùng model với developer**; một lần chạy | **Thiếu**: cùng model thì cùng điểm mù |
| Số lần review | 5 lần rồi gộp: recall gấp khoảng 2 | 1 lần | **Thiếu**: bộ lỗi lọt cho thấy recall thấp |
| Phạm vi đọc | Đọc cả repo, không chỉ diff (Augment) | Reviewer đọc diff `base..HEAD` + plan + PROJECT_STATE | Lỗi lọt ở audit 3 (H-45, H-47, H-50, H-51) đều là lỗi **luồng trạng thái xuyên file**: đúng loại mà reviewer chỉ đọc diff bỏ sót |
| Kiểm chạy thật | Agent QA chạy phần mềm thật (OpenHands); kiểm đầu-cuối (Anthropic) | `verify.py --smoke`, `demo.sh --check` qua HTTP thật; bảng tiêu chí của supervisor | **Ngang** (bài học 6 đã xử lý) |
| Chống sửa/xoá test | Cấm sửa test; phát hiện sửa file test (EvilGenie) | `verify.py` chỉ so lỗi **mới** với baseline; **không** kiểm test bị xoá, bị skip hay bị nới | **Thiếu**, rẻ để thêm |
| Test chỉ dùng mock | Danh sách review chặn test chỉ dùng mock (OpenHands) | Reviewer probe trường hợp biên; không có luật riêng | Một phần. H-54 ("đạt theo cấu tạo") và H-57/H-58 (TestClient khác HTTP thật) là cùng họ lỗi |
| Độ mạnh của test | Đo bằng đột biến (Meta ACH) | Không đo | **Thiếu**; hướng 1 dùng cách này |
| Đo chất lượng reviewer | Đo recall trên bộ lỗi có đáp án (Augment, SWR-Bench) | Đo gián tiếp bằng B1 sau audit (trễ một mốc, cỡ mẫu nhỏ) | **Thiếu** cách đo trực tiếp; hướng 1 bổ sung |
| Bàn giao giữa phiên | File tiến độ + git log + danh sách tính năng (Anthropic) | HANDOFF, PROJECT_STATE + `state.json`, PROGRESS, `/session-start` | **Ngang** |
| Quy tắc thành cổng cứng | Hook chạy chắc chắn, không như lời dặn (Anthropic) | `guard.py` (PreToolUse), `plugin-guard` trên GitHub, verify | **Ngang** (bài học 5) |
| Reviewer báo lỗi quá tay | Cảnh báo reviewer "tìm lỗi" sẽ luôn có lỗi, dẫn tới làm thừa | Chưa gặp: vấn đề của plugin là ngược lại (quá dễ dãi) | Cần nhớ khi siết: chỉ chặn lỗi ảnh hưởng đúng đắn hay tiêu chí |
| Đo lại khi đổi harness | Chất lượng đổi theo bản harness | Bảng B đo theo mốc; không có bộ thử cố định khi đổi prompt | **Thiếu**; bộ lỗi lọt của hướng 1 dùng làm bộ thử hồi quy |

## 3. Đề xuất (xếp theo lợi ích / công sức)

| # | Đề xuất | Vấn đề nó giải | Công sức | Chi phí chạy thêm |
|---|---|---|---|---|
| 1 | **Cổng "không nới test"** trong `verify.py`: so với baseline, chặn khi số test giảm, test mới bị `skip`/`xfail`, hay assert bị xoá trong diff mà không có lý do ghi ở plan | Agent làm xanh bằng cách nới test (EvilGenie); hiện không ai kiểm | ~1 giờ, có test | 0 |
| 2 | **Reviewer khác model với developer**: reviewer Opus (hoặc chạy cả Sonnet và Opus rồi gộp) | Cùng model, cùng điểm mù; B1 = 0,71 | Đổi `model:` + đo | +0,3–0,6 USD/task |
| 3 | **Câu hỏi bắt buộc theo họ lỗi đã lọt** trong `reviewer.md`: (a) kill/restart giữa hai bước; (b) chỉ số đạt sẵn nhờ cách dựng dữ liệu; (c) test chỉ chạy TestClient hay mock; (d) luồng trạng thái xuyên file: đọc cả hàm gọi và hàm được gọi ngoài diff | Đúng 4 họ lỗi audit 3 tìm ra | ~30 phút | ~0 |
| 4 | **Bộ thử reviewer từ lỗi đã lọt** (= hướng 1): đo recall trước và sau đề xuất 2, 3, 5 | Hiện không biết reviewer bắt được bao nhiêu %; mọi thay đổi prompt đều đoán | 1–2 ngày | 15–20 USD |
| 5 | **Review nhiều lần có chọn lọc**: task chạm trạng thái bền hay chỉ số A thì chạy reviewer 3 lần, FAIL nếu một lần tìm ra lỗi chặn có bằng chứng tái hiện | Recall tăng khoảng 2 lần theo SWR-Bench; tốn nên chỉ dùng cho task rủi ro | ~2 giờ | +0,5–1 USD/task rủi ro |
| 6 | **Đột biến nhẹ** trong review task rủi ro: reviewer đảo một điều kiện hay bỏ một lần commit (trên bản tạm), xem test có đỏ không | Test yếu nhưng xanh (H-54) | ~3 giờ, cần guard cho bản tạm | +0,3 USD/task |
| 7 | Critic theo quá trình (OpenHands) | Agent lạc hướng giữa chừng | Lớn (cần dữ liệu huấn luyện) | Không làm: `max_rounds` + supervisor đã đủ ở quy mô này |

**Thứ tự khuyến nghị:** 1 và 3 trước (rẻ, không tốn thêm khi chạy). Sau đó làm 4 để có số đo, rồi dùng số đo đó quyết 2 và 5 (đáng tiền hay không). 6 để sau v0.1. 7 không làm.

**Đã làm (2026-10-10):** 1 và 3. Cổng `test_guard` trong `verify.py`: chạy thử trên 12 PR mốc cũ thì 5 PR bị gắn cờ, cả 5 đều là đổi hành vi hợp lệ theo plan. Vì vậy developer được giải trình bằng dòng `allow-test-change:` trong commit; khi đó cổng không chặn nhưng reviewer phải xét lý do. Dòng giải trình trong `plan/` trên main thì miễn hẳn. Câu hỏi (a)–(d) nằm trong `.claude/agents/reviewer.md` bước 8, trả lời ở trường `risk_checks`.

## 4. Điều plugin đang làm tốt (dùng được cho pitch)
- Nhiều tầng kiểm độc lập, mỗi tầng nhìn một góc: task, mốc, toàn dự án. Kết quả nghiên cứu cho thấy reviewer đơn lẻ chỉ bắt khoảng 20–50% lỗi, nên cần nhiều tầng.
- Quy tắc quan trọng thành cổng cứng (guard, `plugin-guard`, verify, smoke), không chỉ là lời dặn; khớp khuyến nghị của Anthropic.
- Bàn giao giữa phiên bằng file ngắn đọc được từ đầu; khớp mẫu "long-running harness" của Anthropic.
- Có chỉ số đo được cho chính plugin (B1–B6). Ít hệ thống mã nguồn mở công bố recall của reviewer; plugin đã đo được B1 qua audit.

## 5. Giới hạn của báo cáo
- Số liệu bên ngoài đo trên benchmark khác dự án này (ngôn ngữ, cỡ PR, cách chấm); chỉ dùng để chọn hướng, không để dự đoán con số.
- Chưa đọc toàn văn bài "agent harness evolution" (bản PDF không đọc được); chỉ dùng phần tóm tắt.
- Các đề xuất 2, 5, 6 cần đo bằng bộ thử (đề xuất 4) trước khi bật mặc định.
