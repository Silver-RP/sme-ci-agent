# Nhật ký auto-dev

Mỗi task một mục: thời gian, số vòng, commit, kết quả review, % hạn mức (đo bằng `/usage` trước và sau task), ghi chú.

## Chỉ số chạy thử (mục 9.1 của thiết kế)

| Task | Vòng dev↔review | Verify bị chặn | Kết quả | % hạn mức | Thời gian | Lỗi người dùng phát hiện sau |
|---|---|---|---|---|---|---|
| M1/dev-01 (T-015) | 1 | 0 | PASS | (người dùng điền) | dev ~61s + review ~33s | |
| M1/dev-02 (T-017 p1) | 1 | 0 | PASS | (người dùng điền) | dev ~81s + review ~24s | |

## Nhật ký

### M1/dev-01 (T-015): DONE
- Ngày: 2026-10-06. Vòng: 1. Commit: 3cc91ce. Review: .autodev/reviews/M1-dev-01-r1.json (PASS).
- Loader: `backend/domain_config.py` (`load_domain_config`). YAML có thêm KPI `rework_rate`, SOP synthetic SOP-INJ-001 và SOP-CAL-002.
- Non-blocking: test quét hard-code mới chỉ quét `backend/domain_config.py`.
- Ghi chú: hook Stop của developer không ghi `verify.last_status` vào state.json (vẫn là null). Session điều phối tự chạy verify và kết quả sạch.

### M1/dev-02 (T-017 phần 1): DONE
- Ngày: 2026-10-06. Vòng: 1. Commit: bc5d995. Review: .autodev/reviews/M1-dev-02-r1.json (PASS).
- `AgentState` (TypedDict, `events` có reducer cộng dồn), `Hypothesis` (Pydantic), `validate_hypothesis_groups(hypotheses, config)`.
- Non-blocking: việc khớp group với YAML nằm ở hàm riêng; dev-03 cần gọi hàm này.
- Hook Stop vẫn không ghi `verify.last_status`.

## Đề xuất chờ duyệt (c)

(chưa có)
