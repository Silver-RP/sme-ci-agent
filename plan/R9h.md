# R9h (auto-dev run 9, sửa nhanh): LLM thật chạy được

**Phục vụ plugin: P5.** Mốc nhỏ chen giữa, chạy bằng chế độ B. Mục đích: T-030 không bị chặn, đồng thời kiểm chứng runner với một mốc 2 task.

**Mục tiêu dự án:** T-030 (chạy một vòng với LLM thật) đang bị chặn.

Lần chạy thật ngày 2026-10-09 (`SME_LLM=real scripts/demo.sh`, `POST /runs`) dừng ngay ở lần gọi LLM đầu tiên: `run_finished` báo `TypeError: Messages.create() got an unexpected keyword argument 'temperature'`.

Nguyên nhân:
- SDK `anthropic` 1.11 đã bỏ `temperature`. Sonnet 5.5 cũng không nhận tham số lấy mẫu khác mặc định (trả 400).
- H-23 (R9/dev-05) chỉ được kiểm bằng client giả, nên test không bắt được lỗi.

Thêm một vấn đề: `scripts/eval_rootcause.py --llm real` và `scripts/run_scenario.py --llm real` không tự nạp `.env`; chỉ `demo.sh` nạp.

Quy tắc CLAUDE.md giữ nguyên. Tên model chỉ lấy từ env. Agent không đọc hay in `.env`: code được nạp file này khi chạy, nhưng test không được đọc file `.env` thật.

## Phạm vi
- **Trong:** `backend/agent/llm.py`, `scripts/eval_rootcause.py`, `scripts/run_scenario.py`, `.env.example`, test tương ứng; `backend/agent/graph.py` hoặc `checkpoint.py` nếu cần cho dev-02.
- **Ngoài:** mọi thứ khác (R10).

## Quy ước chung
- Test không gọi LLM thật, không cần API key, không mạng.
- Task đụng `scripts/` phải qua `python3 .autodev/verify.py --smoke`.

## Tiêu chí chấp nhận cấp mốc
1. `python3 .autodev/verify.py` sạch; `python3 .autodev/verify.py --smoke` sạch.
2. Có test kiểm mọi khoá mà `AnthropicLLM.complete` gửi vào `messages.create` đều là tham số có thật trong chữ ký của SDK **đã cài**: lấy chữ ký bằng `inspect.signature(anthropic.Anthropic(api_key="test").messages.create)`, không cần mạng. Test này đỏ trên main hiện tại.
3. `uv run python scripts/eval_rootcause.py --llm real --seeds 1` khi thiếu key báo lỗi rõ ràng (thiếu `ANTHROPIC_API_KEY` / `MODEL_REASONING`), không traceback. Có test, dùng env tạm, không đọc `.env` thật.

## Task

### dev-01: Bỏ `temperature`, dùng `output_config.effort`; kiểm theo chữ ký SDK thật
- **Mô tả:**
  - Bỏ `temperature` khỏi request gửi tới API.
  - Thay bằng `output_config={"effort": ...}`. Mức effort đọc từ env `LLM_EFFORT` (mặc định `medium`; giá trị hợp lệ: `low`, `medium`, `high`, `xhigh`, `max`; giá trị khác thì lỗi cấu hình rõ ràng).
  - Model `claude-haiku-4-5*` không hỗ trợ effort: không gửi `output_config` cho model này.
  - Không gửi `thinking` (Sonnet 5.5 mặc định adaptive), không ép `tool_choice`.
  - Giữ `temperature_from_env` nếu nơi khác còn dùng; nếu không thì bỏ, và cập nhật `.env.example` (thay `LLM_TEMPERATURE` bằng `LLM_EFFORT`).
  - Sửa test cũ của H-23 (`test_temperature_sent_from_config_env_and_arg`) theo hành vi mới.
- **Tiêu chí chấp nhận:**
  1. Test chữ ký SDK thật (tiêu chí cấp mốc 2): đỏ trước khi sửa, xanh sau.
  2. Test: `output_config.effort` lấy từ `LLM_EFFORT`, mặc định `medium`; Haiku không có `output_config`; giá trị lạ thì `LLMConfigError`.
- **Phụ thuộc:** không
- **Trạng thái:** DONE · **Số vòng:** 1 (commit 109293a)

### dev-02: Script tự nạp `.env` khi `--llm real`; lỗi cấu hình rõ ràng; checkpoint không cảnh báo kiểu lạ
- **Mô tả:**
  - Với `--llm real`, `scripts/eval_rootcause.py` và `scripts/run_scenario.py` nạp `.env` ở gốc repo bằng `python-dotenv` (đã có trong dependency), không ghi đè biến đã có trong môi trường. Không in giá trị nào.
  - Thiếu `ANTHROPIC_API_KEY` hoặc `MODEL_REASONING` thì in một dòng hướng dẫn và thoát mã khác 0, không traceback.
  - Chạy eval có cảnh báo LangGraph "Deserializing unregistered type backend.agent.state.Hypothesis": cho phép kiểu này một cách tường minh (`allowed_msgpack_modules` hoặc tương đương), hoặc lưu dạng dict.
- **Tiêu chí chấp nhận:**
  1. Test (env tạm, thư mục tạm có file `.env` giả): script nạp được biến; biến đã có trong môi trường không bị ghi đè; thiếu key thì exit khác 0 kèm thông báo rõ.
  2. `uv run python scripts/eval_rootcause.py` (LLM giả) không còn cảnh báo deserializing. Có test bắt warning.
- **Phụ thuộc:** dev-01
- **Trạng thái:** DONE · **Số vòng:** 1 (commit 11df454)

## Ghi chú điều chỉnh (Claude ghi khi làm (a)/(b))

## Đề xuất chờ duyệt
