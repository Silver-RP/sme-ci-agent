# Bắt đầu làm việc với dự án và Claude Code

Dành cho thành viên mới (vai A dữ liệu, D giao diện, Q kiểm chứng). Đọc xong khoảng 10 phút, cài đặt khoảng 30 phút.

## 1. Vai nào cần cài gì

| Vai | Cần chạy hệ thống? | Cần API key (`.env`)? |
|---|---|---|
| A: dữ liệu, kịch bản | Không bắt buộc. Chỉ cần `uv` để chạy `gen_data.py` xem dữ liệu | Không |
| D: giao diện | Có: cả backend + dashboard | Không. Dùng LLM giả hoặc fixture |
| Q: kiểm chứng | Có: cả backend + dashboard | Có, chỉ khi chạy LLM thật (`--llm real`). Hỏi leader trước mỗi lần chạy |

**LLM giả** (`scripts/demo.sh` mặc định) chạy trọn vòng mà không cần key và không tốn credit. Đa số việc chỉ cần chế độ này.

## 2. Cài công cụ

| Công cụ | Phiên bản | Cài (macOS; Windows dùng WSL2) |
|---|---|---|
| Git | bất kỳ | có sẵn, hoặc `xcode-select --install` |
| Docker Desktop | bất kỳ | https://www.docker.com/products/docker-desktop/ (chạy Postgres) |
| uv | mới nhất | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (tự cài Python ≥ 3.12) |
| Node | ≥ 22.13 | `brew install node`, hoặc nvm |
| yarn | 1.22 | `corepack enable` |
| Claude Code | mới nhất | https://docs.claude.com/en/docs/claude-code (cần tài khoản Claude Pro trở lên) |

## 3. Lấy code và kiểm tra cài đặt

```bash
git clone https://github.com/Silver-RP/sme-ci-agent.git
cd sme-ci-agent
uv sync                              # thư viện Python
(cd dashboard && yarn install)       # thư viện dashboard
scripts/demo.sh --check              # bật DB + backend + dashboard, thử từng phần, tự tắt; cuối cùng in CHECK PASSED
```

Sau khi `--check` báo ổn:
- `scripts/demo.sh` rồi mở http://localhost:3000/?source=live để bấm thử trọn vòng (Ctrl+C để dừng).
- Hoặc http://localhost:3000/?source=fixture: chỉ cần dashboard, dữ liệu mẫu trong `docs/schema/examples/`.

Cổng 5432, 8000 hay 3000 bị chiếm: đặt `DB_PORT`, `API_PORT`, `DASH_PORT` (xem README).

**Chỉ vai Q, khi leader cho chạy LLM thật:** chép `.env.example` thành `.env`, tự điền `ANTHROPIC_API_KEY` và `MODEL_REASONING`. Không commit `.env`, không dán key vào chat hay issue, không nhờ Claude đọc file này (dự án đã chặn).

## 4. Lệnh mở đầu cho Claude Code

Mở terminal trong thư mục dự án, chạy `claude`, rồi dán lệnh của vai mình:

**Vai A (dữ liệu):**
> Đọc CLAUDE.md, docs/briefs/data-research.md và issue #63, #66 (dùng `gh issue view`). Tôi là vai A. Lập kế hoạch cho D1 trong phạm vi vai của tôi, chỉ sửa các thư mục được phép ở mục 5 của docs/onboarding-claude.md. Hỏi tôi trước khi sửa file.

**Vai D (giao diện):**
> Đọc CLAUDE.md, docs/briefs/frontend.md, docs/demo-storyboard.md và issue #64, #67 (dùng `gh issue view`). Tôi là vai D. Lập kế hoạch cho FR-01 trong phạm vi vai của tôi, chỉ sửa trong dashboard/. Hỏi tôi trước khi sửa file.

**Vai Q (kiểm chứng):**
> Đọc CLAUDE.md, docs/briefs/qa.md, hai brief data-research.md và frontend.md, và issue #65 (dùng `gh issue view`). Tôi là vai Q. Lập kế hoạch cho Q1 (ca kiểm thử FR-01..05 và D1), chỉ ghi vào docs/qa/ và docs/token-cost.md. Không chạy `--llm real` khi tôi chưa xác nhận.

Muốn Claude đọc được issue: cài GitHub CLI (`brew install gh`) và `gh auth login`.

## 5. Được và không được

**Mỗi vai chỉ sửa trong vùng của mình:**

| Vai | Được sửa |
|---|---|
| A | `docs/schema/data_contract.md`, `docs/research/`, `data/templates/`, `data/scenarios/draft/` |
| D | `dashboard/` |
| Q | `docs/qa/`, `docs/token-cost.md`; còn lại chỉ mở issue và comment PR |

**Cả đội:**
- Làm trên nhánh riêng (`feat/data-*`, `feat/ui-*`, `docs/qa-*`), mở PR vào `main`. `main` không nhận đẩy thẳng và không nhận force-push.
- **Không sửa** `.claude/`, `.autodev/`, `docs/autodev/`, `.github/`. Đây là file của plugin auto-dev và CI. PR đụng các thư mục này sẽ bị kiểm tra `plugin-guard` chặn. Muốn đổi thì mở issue cho leader.
- **Không chạy** `/run-milestone`, `/supervise`, `/audit`. Chỉ leader chạy auto-dev, để các mốc không chồng lên nhau.
- Đổi `docs/schema/events.json` (hợp đồng backend ↔ dashboard): PR riêng, báo trong sync.
- Chỉ dùng dữ liệu synthetic. Không dùng dữ liệu thật hay dữ liệu cá nhân.
- Cần backend thêm API: mở issue nhãn `api`. Gặp lỗi: issue nhãn `bug` + `sev:1–3`; `sev:1` báo ngay trong chat.

Claude Code trên máy bạn đã được dự án cài sẵn hàng rào (`.claude/settings.json`): không đọc `.env`, không xoá file hay nhánh, không sửa baseline test. Bị chặn là đúng thiết kế; đừng tìm cách vượt, hãy hỏi leader.
