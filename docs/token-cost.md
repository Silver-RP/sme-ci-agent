# Sổ chi phí LLM thật (T-044)

Mỗi lần chạy `--llm real` hoặc `SME_LLM=real` ghi một dòng: ngày, lệnh, DB, kết quả, token, USD ước tính, cộng dồn. Chỉ chạy khi leader cho phép từng lần, ≤ 3 USD/lần (`docs/eval/criteria.md` mục 5). USD ước từ token khi không có hoá đơn; ghi "ước".

Từ 2026-10-14 sổ này do leader/Claude giữ (ADR-011; trước là vai Q).

| Ngày | Lệnh | DB | Kết quả | Token | USD | Cộng dồn USD |
|---|---|---|---|---|---|---|
| 2026-10-10 | `eval_rootcause.py --llm real --seeds 2` | `sme_ci` dùng chung | accuracy 50% (chấm theo chuỗi, H-28), ask_rate 0% | ~12,5k | ~0,1 (ước) | ~0,1 |
| 2026-10-12 | `eval_rootcause.py --llm real --seeds 3` | `sme_ci` dùng chung | 67% (chấm theo chữ + 185 bài học lộ đáp án) | ~41k (gộp 2 dòng) | ~0,4 (ước, gộp 2 dòng) | ~0,5 |
| 2026-10-12 | `eval_rootcause.py --llm real --seeds 3` | `sme_ci_demo` sạch | 3/3 `wrong_setpoint`, hỏi 0% (bài dễ ~10σ) | (gộp trên) | (gộp trên) | ~0,5 |
| 2026-10-12 | dashboard `SME_LLM=real` (leader tự thử) | `sme_ci_demo` | vài run demo | chưa ghi | ~0,1–0,2/run (ước) | ~0,7–1,1 |

Nguồn số cũ: `docs/autodev/PROJECT_STATE.md` (12/10), `docs/decisions.md` (T-030 lần 4), `.autodev/runs/usage-log.md`.
