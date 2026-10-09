# Báo cáo mốc R9h: LLM thật chạy được (sửa nhanh, T-030)

## Tóm tắt so với tiêu chí cấp mốc
1. `verify.py` sạch; `verify.py --smoke` sạch (dev-02 chạy, reviewer chạy lại). ✅
2. Test chữ ký SDK thật (`test_every_request_key_exists_in_installed_sdk_signature`): mọi khoá gửi vào `messages.create` đều có trong chữ ký SDK đã cài. Đỏ với code cũ vì `temperature`. ✅
3. `eval_rootcause.py --llm real --seeds 1` thiếu key: một dòng "Missing ANTHROPIC_API_KEY, MODEL_REASONING", exit 2, không traceback; có test dùng thư mục tạm. ✅

## Task
| Task | Trạng thái | Vòng | Commit |
|---|---|---|---|
| dev-01 bỏ `temperature`, dùng `output_config.effort` (`LLM_EFFORT`, mặc định medium; Haiku 4.5 không gửi) | DONE | 1 | 109293a |
| dev-02 script nạp `.env` khi `--llm real`, lỗi cấu hình rõ, checkpointer cho phép `Hypothesis` | DONE | 1 | 11df454 |

## BLOCKED
Không có.

## Điều chỉnh (a)/(b)
Không có.

## Đề xuất chờ duyệt (c)
Không có từ developer. Non-blocking từ reviewer (để mốc sau):
- `postgres_checkpointer` chưa dùng allowlist msgpack (`ALLOWED_MSGPACK_MODULES`).
- Tiền tố Haiku chỉ khớp `claude-haiku-4-5`; `LLM_EFFORT` rỗng chưa có test; test dọn environ thủ công thay vì monkeypatch.
- Test deserializing vẫn xanh khi allowlist là danh sách rỗng (vẫn bắt được trường hợp thiếu hẳn).

## Verify so với baseline
`python3 .autodev/verify.py`: sạch, không lỗi mới. pytest 421 xanh (baseline trước mốc 412).

## Ghi chú vận hành
- Hook SubagentStop chạy cả hai task (hook_runs 33 → 35).
- Một lần lệnh Bash của supervisor-worker bị `guard.py` chặn vì chuỗi lệnh có nhắc tới tên file env; đã chuyển sang công cụ Edit. Không phải lỗi plugin.
- Thời gian: bắt đầu 13:01Z, xong task 13:18Z (~17 phút).

## Cách chạy thử
`python3 .autodev/verify.py --smoke`. Để kiểm LLM thật (T-030): người dùng đặt key và tên model trong `.env`, rồi `SME_LLM=real scripts/demo.sh`.
