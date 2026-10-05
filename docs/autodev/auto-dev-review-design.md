# Thiết kế hệ thống Auto-Dev + Auto-Review với Claude Code

> **Phiên bản:** 1.2. **Ngày:** 2026-10-06 (bản 1.0: 2026-10-05; xem mục 13 về các thay đổi).
> **Vị trí:** `docs/autodev/auto-dev-review-design.md` trong repo SME CI Agent (dự án chạy thử). Phần thiết lập chế độ A nằm ở `.claude/agents/`, `.autodev/`, `plan/`.
> **Trạng thái:** Đã thiết lập chế độ A trên SME CI Agent (mục 9.1, nhánh `autodev/setup`), **chưa chạy thử**.
> **Người sở hữu:** roppyhoangle@gmail.com
> **Nguồn gốc:** tổng hợp từ một phiên thảo luận dài giữa người dùng và Claude. Phát sinh như một nhánh nghiên cứu tách ra từ dự án SME CI Agent, nhưng **không gắn với dự án đó**.

---

## 0. Hướng dẫn cho Claude khi nhận tài liệu này ở phiên mới

Nếu bạn là Claude và người dùng gửi tài liệu này cho bạn:

1. **Đọc hết trước khi trả lời.** Mục 2 (yêu cầu đã xác nhận) và mục 6 (thiết kế chốt) là phần chính. Mục 4 ghi lại các phương án đã loại và **lý do loại**. Đừng đề xuất lại một phương án đã loại mà không giải quyết được đúng lý do loại nó.
2. **Phân biệt 3 loại thông tin** trong tài liệu:
   - `[XÁC NHẬN]`: người dùng đã trả lời rõ. Không cần hỏi lại, trừ khi người dùng nói đã thay đổi.
   - `[KIỂM CHỨNG]`: đã đối chiếu với tài liệu chính thức của Claude Code vào ngày 2026-10-05. **Tính năng có thể đã thay đổi**, nên kiểm tra lại docs trước khi dựa vào.
   - `[GIẢ ĐỊNH]` / `[CHƯA CHỐT]`: chưa được xác nhận. **Phải hỏi người dùng**, không tự suy diễn.
3. **Quy tắc làm việc người dùng yêu cầu:** nếu có gì chưa rõ thì **không suy diễn mà hỏi hoặc xác nhận**, để đạt mức hiểu trên 95% ý tưởng, concept và mục tiêu trước khi phân tích sâu hay triển khai.
4. **Bước đầu tiên nên làm:** tóm tắt lại trong 5–10 dòng cách bạn hiểu mục tiêu. Sau đó hỏi người dùng: (a) từ lần thảo luận trước có gì thay đổi không, (b) họ đang ở bước nào trong lộ trình ở mục 9, (c) những điểm `[CHƯA CHỐT]` ở mục 7 đã có câu trả lời chưa.
5. Người dùng giao tiếp bằng **tiếng Việt**.

---

## 1. Bối cảnh và vấn đề

### 1.1 Quy trình hiện tại (thủ công)

```
[Người dùng] lập plan + task
      │
      ▼
[Claude Code – VS Code extension] code task → xuất BÁO CÁO
      │  (người dùng copy báo cáo)
      ▼
[Claude Chat – claude.ai, trong một Project có tài liệu + plan tổng]
      phân tích báo cáo → FEEDBACK
      │  (người dùng copy feedback)
      ▼
[Claude Code] sửa theo feedback → báo cáo mới → lặp lại
```

### 1.2 Quan sát của người dùng `[XÁC NHẬN]`

- Người dùng gần như **tin tưởng toàn bộ** đầu ra của Claude và **không can thiệp sâu**.
- Họ chỉ review sơ lược kết quả, chủ yếu xem các chức năng của web app có chạy ổn không. Đa số lần đều ổn.
- Vì vậy vai trò của người dùng trong vòng lặp chủ yếu là **chuyển tin nhắn qua lại (copy-paste)**. Đây là phần cần tự động hoá.

### 1.3 Vấn đề cốt lõi

Việc copy-paste qua lại giữa hai giao diện:

- tốn thời gian và đòi hỏi con người phải có mặt liên tục;
- là nút thắt duy nhất ngăn quy trình chạy tự động;
- không lưu lại lịch sử feedback một cách có cấu trúc.

---

## 2. Mục tiêu và yêu cầu đã xác nhận

### 2.1 Mục tiêu

Dùng Claude để **tự code và tự review theo chuẩn đặt ra ban đầu**, với thao tác của con người ở mức tối thiểu hoặc không cần. Cụ thể:

- Con người phân tích bối cảnh, đặt mục tiêu, phác thảo plan.
- Sau đó **hai vai trò Claude (developer và reviewer) tự làm việc với nhau**.
- Con người chỉ review kết quả **sau mỗi mốc lớn** hoặc sau một khoảng thời gian.

### 2.2 Bảng yêu cầu

| # | Chủ đề | Quyết định | Trạng thái |
|---|---|---|---|
| R1 | Phạm vi áp dụng | Bộ công cụ **dùng lại được cho nhiều dự án**, cả dự án đang làm dở lẫn dự án sau này. **Không** gắn với SME CI Agent. | `[XÁC NHẬN]` |
| R2 | Gói Claude | **Pro** (đăng nhập bằng subscription, không dùng API key) | `[XÁC NHẬN]` |
| R3 | Nguồn ngữ cảnh | Tài liệu và plan tổng hiện nằm trong Project của Claude Chat. **Sẽ được chuyển vào repo** để reviewer dùng. | `[XÁC NHẬN]` |
| R4 | Nơi chạy | **Cả hai**: theo dõi được trong VS Code, **và** chạy không người trông trên máy cá nhân. Máy để bật qua đêm được. | `[XÁC NHẬN]` |
| R5 | GitHub Actions | **Chưa có nhu cầu** | `[XÁC NHẬN]` |
| R6 | Kiểm thử | **Muốn tự động hoá**, gồm cả kiểm tra chức năng web (e2e) | `[XÁC NHẬN]` |
| R7 | Plan | Lưu **trong repo**. Ban đầu người dùng duyệt. Sau mỗi task, Claude tự điều chỉnh và ghi chú cho phù hợp với yêu cầu dự án. | `[XÁC NHẬN]` |
| R8 | Quyền điều chỉnh plan | (a) ghi chú, tách nhỏ task: **tự do**. (b) thêm hoặc sửa task trong cùng mốc: **tự do**. (c) sửa tiêu chí chấp nhận hoặc phạm vi mốc: **chỉ được đề xuất**, người dùng duyệt. | `[XÁC NHẬN]` |
| R9 | Cấu trúc plan | Mốc lớn **M1, M2, M3…**, mỗi mốc chia nhỏ thành **dev-01, dev-02…** | `[XÁC NHẬN]` |
| R10 | Git | Repo trên **GitHub**. Agent được **tự commit vào nhánh riêng và mở PR**. | `[XÁC NHẬN]` |
| R11 | Bàn giao theo mốc | **Báo cáo tóm tắt + link chạy thử** để người dùng tự test app | `[XÁC NHẬN]` |
| R12 | Quyền thực thi | Chấp nhận cho agent chạy **không hỏi duyệt từng lệnh** (auto mode / acceptEdits) **khi làm trên nhánh riêng** | `[XÁC NHẬN]` |
| R13 | Hạ tầng deploy | **Chưa có**. Link chạy thử sẽ là app chạy local. | `[XÁC NHẬN]` |

---

## 3. Ràng buộc chính

1. **Hạn mức của gói Pro** là ràng buộc lớn nhất `[KIỂM CHỨNG]`:
   - Hạn mức tính theo **cửa sổ 5 tiếng** và có thêm **hạn mức theo tuần**. Người dùng ước tính chạy liên tục khoảng 1 tiếng là có thể hết, sau đó phải chờ reset.
   - Mọi model và **mọi subagent đều dùng chung** hạn mức này. Subagent không "miễn phí".
   - Khi đổi model với `/model`, hạn mức chung theo phiên hoặc theo tuần **không** được khôi phục. Chỉ thông báo hạn mức riêng của một model (ví dụ "Opus limit") mới tránh được bằng cách đổi sang model khác.
   - ⇒ Thiết kế phải **tiết kiệm token** và **chạy tiếp được sau khi bị ngắt**, ưu tiên hai điều này hơn tốc độ.
2. **Chạy trên máy cá nhân**, không có server và không có CI.
3. **Chưa có chỗ deploy**, nên link chạy thử chỉ có thể là `localhost`.
4. **Cùng một nhà cung cấp và cùng họ model** cho cả dev lẫn reviewer, nên có rủi ro điểm mù chung (xem mục 6.12).

---

## 4. Lịch sử các phương án đã cân nhắc và lý do loại

> Mục này ghi lại để **không lặp lại sai lầm**. Mỗi phương án có: mô tả, luồng, ưu, nhược, lý do loại, và những gì được giữ lại trong thiết kế cuối.

### 4.1 Phương án 0: Orchestrator Python gọi thẳng Messages API

**Mô tả.** Các file `orchestrator.py` (mock) và `orchestrator_with_api.py` (gọi API thật). Script giữ một file state JSON (`task-001-state.json`). Mỗi vòng, script gọi "Developer Agent" rồi "Reviewer Agent" qua `client.messages.create(...)`. Mỗi bên trả về một JSON. Tối đa 5 vòng, quá số vòng thì chuyển trạng thái `ESCALATED` cho người quyết định.

**Luồng:** `Spec → Developer (API) → JSON báo cáo → Reviewer (API) → PASS/FAIL → lặp`.

**Ưu:**
- Khung ý tưởng đúng: vòng lặp có giới hạn, có escalation, state lưu ra file, reviewer có context tách biệt.

**Nhược và lý do loại (lỗi nghiêm trọng):**
- ❌ **Messages API không có tool**, nên "Developer Agent" **không ghi file, không chạy test**. Nó chỉ *trả về JSON tự khai* là đã code xong và test pass. Toàn bộ vòng lặp xoay quanh những báo cáo bịa.
- ❌ Reviewer chỉ đọc báo cáo tự khai, nên không có gì thật để kiểm tra.
- ❌ Dùng API key thì tính phí theo token, trong khi người dùng có gói Pro (R2).
- ❌ Trong code có tên model không tồn tại (ví dụ `claude-3-7-opus`) và các con số chi phí ước lượng không có căn cứ.

**Giữ lại:** giới hạn số vòng, escalation, state file, nguyên tắc tách context của reviewer.

---

### 4.2 Phương án 1: Workflow Bridge (`workflow-bridge.py`)

**Mô tả.** Script CLI quản lý state giữa Claude Code và Claude Chat. Các lệnh: `create` (tạo task), `submit` (nhận báo cáo, sinh file `.claude-workflow/TASK-xxx-report.md` có prompt soạn sẵn cho Chat), `apply` (đọc feedback JSON mà người dùng lưu từ Chat, in ra danh sách việc cần làm), `status`.

**Luồng:**
```
Claude Code → báo cáo → `submit` → file report.md
→ (người dùng copy vào Claude Chat) → Chat trả JSON feedback
→ (người dùng lưu thành feedback.json) → `apply` → action items → Claude Code sửa
```

**Ưu:**
- Format có cấu trúc, lưu lịch sử các vòng lặp.
- Không tốn thêm token (Chat nằm trong gói).
- Review vẫn có ngữ cảnh của Project trong Chat.

**Nhược và lý do loại:**
- ❌ **Không loại bỏ được copy-paste**, chỉ giảm số lần. Con người vẫn là người chuyển tin ở giữa, nên không đạt mục tiêu "không cần con người".
- ❌ Ngữ cảnh vẫn nằm trong Chat, không nằm trong repo.

**Giữ lại:** ý tưởng **báo cáo và feedback có cấu trúc (JSON)**, **nhật ký các vòng lặp**, và việc tách "báo cáo" với "feedback" thành hai artifact riêng.

---

### 4.3 Phương án 2: Git pre-commit hook review code trực tiếp

**Mô tả.** File `.git/hooks/pre-commit` chạy một script Python reviewer khi gõ `git commit`. Script lấy `git diff --cached`, chạy test, đọc spec, gọi Claude API review diff, lưu `.claude-workflow/*-review.json`, rồi `exit 0` (cho commit) hoặc `exit 1` (chặn commit). Có cấu hình chặn khi có lỗi critical/major, ngưỡng chất lượng, loại file cần review, và có thể bỏ qua bằng `--no-verify`.

**Ưu:**
- Tự động, phản hồi ngay ở thời điểm commit, setup đơn giản.

**Nhược và lý do loại:**
- ❌ **Sai điểm kích hoạt.** Trong quy trình này, người viết code và commit là **Claude Code** chứ không phải con người. Khi hook fail, agent chỉ thấy một lỗi bash. Kênh phản hồi gián tiếp, dễ vỡ, và agent có thể dùng `--no-verify` để bỏ qua.
- ❌ Đây là **logic review thứ hai**, trùng với reviewer trong orchestrator, và hai bên có thể không nhất quán.
- ❌ Reviewer chỉ thấy diff, không thấy tiêu chí của task và trạng thái hoàn thành của task.
- ❌ Làm mỗi commit chậm đi vài giây và tốn hạn mức theo từng commit.

**Giữ lại:** pre-commit **chỉ chạy kiểm tra cứng** (lint, format, test) như một chốt cuối, tuỳ chọn và không dùng LLM. Phần "chặn khi có lỗi" được chuyển sang hook của Claude Code (mục 6.6).

---

### 4.4 Phương án 3: Hai session chat trong VS Code (Dual-Session)

**Mô tả (ý tưởng của người dùng).** Trong khung chat của VS Code có hai session: session 1 làm task và tạo báo cáo, session 2 review và phản hồi cho session 1. Một script orchestrator bên ngoài điều khiển cả hai, tối đa 5 vòng, kết quả hiện trong chat.

**Ưu:**
- **Ý tưởng đúng hướng**: hai vai trò với context tách biệt, vòng lặp tự động, tích hợp vào VS Code.

**Nhược và lý do loại (về cách hiện thực, không phải về ý tưởng):**
- ❌ **Chưa kiểm chứng và gần như không làm được** việc một script bên ngoài điều khiển các session chat trong panel của VS Code extension. Nhận định trước đó rằng "extension hỗ trợ multi-session API" là sai và chưa được kiểm tra.
- ❌ Bản phác thảo khi đó cần viết riêng một VS Code extension (TypeScript), tốn công và khó bảo trì.

**Giữ lại (phần cốt lõi của thiết kế cuối):** ý tưởng hai vai trò được hiện thực bằng **subagents của Claude Code** (`.claude/agents/developer.md` và `reviewer.md`). Đây là cơ chế chính thức để có hai "session" với context riêng, và nó chạy được cả trong VS Code lẫn ở chế độ headless.

---

### 4.5 Phương án 4: Pre-commit kích hoạt orchestrator (Dev và Reviewer qua API)

**Mô tả.** Khi `git commit`, hook gọi orchestrator. Orchestrator chạy Developer Agent (API) để sinh báo cáo, rồi Reviewer Agent (API) review báo cáo. APPROVED thì cho commit, REJECTED thì chặn. Có thể commit luôn file báo cáo.

**Lý do loại:**
- ❌ Gặp cả lỗi của 4.1 (dev agent không code thật) lẫn lỗi của 4.3 (sai điểm kích hoạt).
- ❌ Hai lần gọi API cho mỗi commit.

---

### 4.6 Phương án 5: Báo cáo sinh bằng script local + 1 lần gọi API để review

**Mô tả (ý tưởng của người dùng).** Pre-commit chỉ xử lý **file báo cáo**: một script local (không dùng LLM) sinh báo cáo từ git diff, kết quả test và coverage, sau đó chỉ gọi **một lần** reviewer để review báo cáo. Mục đích là tiết kiệm chi phí.

**Ưu:**
- Hướng đúng ở chỗ **đưa phần tất định (test, diff, lint) ra ngoài LLM** để tiết kiệm token.

**Nhược và lý do loại:**
- ❌ Nếu reviewer **chỉ đọc báo cáo**, nó đang tin vào số liệu tự khai mà không xem code thật. Nó không bắt được trường hợp code sai spec nhưng test vẫn xanh, hoặc test quá hời hợt.
- ❌ Vẫn dùng pre-commit làm điểm kích hoạt, nên giữ nguyên nhược điểm của 4.3.
- ⚠️ Lúc đó Claude đã **đồng tình quá nhanh** và gọi đây là "tối ưu". Nhận định đó đã được đính chính.

**Giữ lại:** nguyên tắc **"kiểm tra cứng trước, LLM review sau"** (mục 6.1, nguyên tắc 1).

---

### 4.7 Đính chính tổng hợp (các khẳng định sai ở phiên trước)

| Khẳng định trước đó | Đính chính |
|---|---|
| "Developer Agent" gọi qua Messages API code được | Sai. Không có tool thì không code, không chạy test được. |
| Chi phí khoảng $0.05 / $0.10–0.15 mỗi commit | Con số tự ước lượng, không có căn cứ. Với gói Pro, đơn vị đúng là **% hạn mức**, không phải $. |
| Model `claude-3-7-opus`… | Không tồn tại. |
| "Script điều khiển được nhiều session chat trong VS Code" | Chưa kiểm chứng và gần như không làm được. |
| Dùng `CronCreate` để chạy nền | Không phù hợp. Đó là công cụ lập lịch trong một phiên, không phải cơ chế chạy nền lâu dài. |
| "Review báo cáo là tối ưu" | Thiếu. Reviewer phải đọc **diff thật** và **tự chạy lại test**. |

---

## 5. Các cơ chế của Claude Code đã kiểm chứng `[KIỂM CHỨNG 2026-10-05]`

> Đã đối chiếu với tài liệu chính thức tại code.claude.com/docs. **Phiên sau nên kiểm tra lại**, vì tính năng thay đổi nhanh.

### 5.1 Subagents

- Là file Markdown có YAML frontmatter, đặt tại `.claude/agents/` (theo dự án, có thể commit), `~/.claude/agents/` (theo người dùng), hoặc trong **plugin**.
- **Context riêng**: system prompt riêng cùng task được giao, `CLAUDE.md`, và snapshot git status. **Không thừa hưởng lịch sử hội thoại** của session chính (trừ chế độ fork).
- Giới hạn tool bằng `tools:` (allowlist) hoặc `disallowedTools:`.
- Chọn model riêng bằng `model:` (`sonnet`, `opus`, `haiku`, `inherit`…).
- Gọi bằng cách để Claude tự giao việc, @-mention, hoặc chạy cả phiên với `claude --agent <tên>`.
- Subagent trả về **bản tóm tắt** cho session chính và tiếp tục được (resume) theo agent ID.
- Mặc định cho phép lồng tối đa 3 tầng và chạy đồng thời tối đa 20 subagent (có biến môi trường để chỉnh).

### 5.2 Hooks

- Cấu hình trong `.claude/settings.json` (theo dự án), `~/.claude/settings.json`, hoặc `hooks/hooks.json` của plugin.
- Các sự kiện liên quan:
  - **`Stop`** và **`SubagentStop`**: chạy khi agent định dừng. Hook trả **exit 2** hoặc `{"decision":"block","reason":...}` thì agent **bị chặn dừng**, và lý do được đưa vào context để agent làm tiếp.
  - **`TaskCompleted`**: chặn được việc đánh dấu task là xong.
  - **`PreToolUse`**: chặn hoặc sửa một lệnh trước khi nó chạy, dùng để bảo vệ an toàn.
  - **`PostToolUse`**: không chặn được, nhưng đưa thêm thông tin vào context được.
- **`stop_hook_active`**: cờ dùng để tránh vòng lặp vô hạn khi chính hook Stop gây ra một lần Stop khác.
- Có hook kiểu **`prompt`** (nhờ model đánh giá) và **`agent`** (spawn subagent có tool). Kiểu `agent` vẫn đang **experimental**.

### 5.3 Headless: `claude -p`

- Chạy không cần giao diện và script hoá được. Exit code 0 khi thành công, khác 0 khi lỗi.
- Các cờ quan trọng: `--output-format json` (có `session_id` và kết quả), `--json-schema` (ép output theo schema, nằm ở trường `structured_output`), `--resume <session_id>` / `--continue`, `--allowedTools`, `--permission-mode` (`auto` / `acceptEdits` / `dontAsk`), `--permission-prompts none` (cho lần chạy không người trông), `--append-system-prompt`, `--agents`.
- `--bare` bỏ qua hooks, agents, CLAUDE.md, và **bắt buộc dùng API key**, không dùng được đăng nhập subscription. ⇒ Với gói Pro thì **không dùng `--bare`**.
- Không có `--bare`, `-p` nạp hooks, agents và CLAUDE.md của dự án như một phiên interactive.

### 5.4 Khi hết hạn mức

- **Interactive:** thông báo có giờ reset (ví dụ "You've hit your session limit · resets 3:45pm"). Có tuỳ chọn **"Continue automatically at usage limit"** trong `/config` để tự chờ rồi chạy tiếp task đang dở.
- **Headless (`-p`):** tài liệu **không nói rõ** có tự chờ hay không `[GIẢ ĐỊNH: không]`. ⇒ Script điều phối phải tự nhận diện lỗi, tính giờ reset, chờ, rồi `--resume`. **Cần kiểm tra thực tế khi chạy thử.**
- `/usage` có bảng phân bổ hạn mức **theo subagent**, dùng được để đo chi phí mỗi task.

### 5.5 Agent teams

- **Experimental**, mặc định tắt (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`).
- Gồm lead và các teammate, có task list chung và hộp thư nhắn tin trực tiếp giữa các agent.
- **Chỉ chạy trong phiên interactive**, không chạy với `-p`.
- Tốn token **nhiều hơn đáng kể**. Tài liệu nêu khoảng 7 lần khi teammate chạy ở plan mode.
- Tài liệu khuyên: với việc tuần tự, sửa cùng file, hoặc có nhiều phụ thuộc thì dùng **subagents**.
- ⇒ **Chưa dùng** cho thiết kế này, vì vòng dev → review là tuần tự và gói Pro có hạn mức thấp.

### 5.6 GitHub Actions (để tham khảo, R5 chưa cần)

- `anthropics/claude-code-action@v1` hỗ trợ `@claude` trên issue/PR, chạy prompt theo sự kiện hoặc theo cron, và review PR.
- **Chạy được bằng gói Pro**: `claude setup-token` tạo secret `CLAUDE_CODE_OAUTH_TOKEN`, dùng hạn mức subscription thay vì tính phí API. Số phút chạy GitHub Actions vẫn bị tính riêng.

### 5.7 Mẹo tiết kiệm token (từ tài liệu chi phí)

- Sonnet đủ cho phần lớn việc code. Opus để dành cho quyết định kiến trúc.
- `/clear` giữa các task không liên quan.
- Giữ `CLAUDE.md` dưới khoảng 200 dòng. Chuyển các hướng dẫn chuyên biệt sang skills, vì skill chỉ nạp khi được gọi.
- Dùng hook để lọc output dài (ví dụ chỉ giữ dòng FAIL của test).
- Các thao tác sinh nhiều output (chạy test, đọc log) nên giao cho subagent.

---

## 6. Thiết kế đề xuất (bản chốt)

### 6.1 Nguyên tắc thiết kế

1. **Kiểm tra cứng trước, LLM review sau.** Lint, typecheck, test, build và e2e là bằng chứng khách quan và không tốn token. LLM reviewer chỉ chạy khi các kiểm tra này đã xanh.
2. **Reviewer phải tự kiểm chứng**: đọc spec, tiêu chí và **git diff thật**, và **tự chạy lại test**. Không tin báo cáo tự khai.
3. **"Chuẩn ban đầu" phải tồn tại dưới dạng file trong repo** (`docs/`, `plan/`, `CLAUDE.md`), để dev và reviewer cùng đọc một nguồn.
4. **Vòng lặp chạy bên trong Claude Code** (subagents + hooks), không nối thêm từ bên ngoài bằng git hook hay Messages API.
5. **Cấu hình agent chỉ viết một lần** và dùng chung cho cả chế độ VS Code lẫn chế độ chạy qua đêm.
6. **Mọi trạng thái nằm trong file và được commit theo task**, để chạy tiếp được sau khi hết hạn mức, tắt máy hay crash.
7. **Tiết kiệm hạn mức là ưu tiên số 1** (gói Pro).
8. **Con người chốt ở mỗi mốc**: hệ thống không tự sang mốc tiếp theo.

### 6.2 Cấu trúc: bộ công cụ chung + cấu hình theo dự án

```
BỘ CÔNG CỤ CHUNG  (đóng gói thành Claude Code plugin; cài 1 lần, dùng cho mọi repo)
├─ agents/developer.md
├─ agents/reviewer.md
├─ hooks/hooks.json            SubagentStop(developer) → chạy verify; PreToolUse → chặn lệnh nguy hiểm
├─ commands|skills/onboard     chuẩn hoá một dự án (mới hoặc đang dở)
├─ commands|skills/run-milestone   chạy một mốc trong VS Code
└─ orchestrator (script)       chạy headless qua đêm, gọi `claude -p`

CẤU HÌNH TỪNG DỰ ÁN  (nằm trong repo dự án)
├─ CLAUDE.md                   chuẩn code + quy ước (ngắn)
├─ docs/                       plan tổng, spec, tài liệu chuyển từ Claude Chat Project
├─ plan/M1.md, M2.md …         mỗi mốc: mục tiêu, danh sách dev-xx, tiêu chí chấp nhận
├─ PROGRESS.md                 nhật ký theo task + mục "Đề xuất chờ duyệt"
├─ .autodev/config             lệnh verify, lệnh chạy app, cổng, số vòng tối đa…
├─ .autodev/state.json         trạng thái máy (task hiện tại, số vòng, session_id…)
└─ .autodev/baseline           lỗi có sẵn (test fail, lint) lúc onboarding
```

`[CHƯA CHỐT]`: đóng gói thành **plugin** hay chỉ là một **thư mục template** để copy vào từng repo. Plugin là cơ chế chính thức để dùng lại agents, hooks và skills giữa các dự án, nhưng cần kiểm tra cách cài và cập nhật.

### 6.3 Đặc tả các agent

| | **developer** | **reviewer** |
|---|---|---|
| Nhiệm vụ | Hiện thực một task dev-xx theo spec và tiêu chí, viết hoặc cập nhật test, commit | Đánh giá task có đạt tiêu chí và đúng spec không, chất lượng và rủi ro |
| Tools | Đủ: Read, Edit, Write, Bash, Grep, Glob | **Chỉ đọc**: Read, Grep, Glob, Bash (để chạy test hoặc chạy lại verify). **Không có** Edit/Write. |
| Model | Sonnet | Sonnet (cân nhắc Opus cho mốc quan trọng; trên Pro thì tốn hạn mức) |
| Đầu vào | File task + tiêu chí, `docs/` liên quan, feedback vòng trước (nếu có) | File task + tiêu chí, spec liên quan, **git diff của task**, kết quả verify |
| Đầu ra | Code + test + commit + ghi chú ngắn | **JSON theo schema** (mục 6.9) |
| Không được | Sửa tiêu chí chấp nhận, thay đổi phạm vi mốc, push lên main | Sửa code, PASS khi chưa tự chạy test |

### 6.4 Chuẩn hoá dự án (onboarding, mỗi dự án làm 1 lần, có người dùng tham gia)

1. Chuyển tài liệu và plan từ Claude Chat Project vào `docs/` và `plan/`.
2. Chạy `onboard`. Claude đọc repo rồi đề xuất:
   - `CLAUDE.md` (chuẩn code, cấu trúc thư mục, cách chạy);
   - lệnh **verify** (lint, typecheck, unit test, build, e2e);
   - lệnh **chạy app** và cổng;
   - **test e2e (Playwright) cho các luồng chính đang có**.
3. Chụp **baseline**: danh sách test đang fail sẵn và số lỗi lint hiện có.
   - Lý do: với dự án đang dở, nếu không có baseline thì gate sẽ chặn ngay từ task đầu tiên vì những lỗi có từ trước.
   - Quy tắc: gate chỉ chặn **lỗi mới phát sinh so với baseline**.
4. **Người dùng duyệt** cấu hình onboarding. Đây là "chuẩn ban đầu" của mọi bước tự động.

### 6.5 Định dạng plan (đề xuất)

```
plan/M1.md
  - Mục tiêu mốc, phạm vi (in/out of scope)
  - Tiêu chí chấp nhận cấp mốc            ← chỉ người dùng được sửa (R8-c)
  - Danh sách task:
      dev-01: tiêu đề | mô tả | tiêu chí chấp nhận | phụ thuộc | trạng thái | số vòng
      dev-02: …
  - Ghi chú điều chỉnh (Claude tự ghi khi làm (a)/(b))
```

### 6.6 Kiểm tra cứng (gates)

- Lệnh verify được khai báo trong `.autodev/config` và chạy theo thứ tự: lint → typecheck → unit test → build → e2e.
- **Gắn vào hook `SubagentStop` của developer**: khi developer định kết thúc, hook chạy verify và so với baseline.
  - Có lỗi mới → **exit 2** kèm tóm tắt lỗi (đã lọc ngắn), developer phải sửa tiếp.
  - Sạch → cho phép kết thúc, chuyển sang reviewer.
  - Dùng `stop_hook_active` cùng một bộ đếm để tránh vòng lặp vô hạn.
- Test e2e chập chờn (flaky): chạy lại 1 lần trước khi tính là fail.
- Pre-commit (tuỳ chọn): chỉ chạy lint/format nhanh, không dùng LLM.

### 6.7 Điều phối: hai chế độ dùng chung các lớp trên

| | **A. Interactive (VS Code)** | **B. Headless (qua đêm)** |
|---|---|---|
| Kích hoạt | Lệnh `run-milestone M1` trong chat | `orchestrator run M1` trong terminal |
| Ai điều phối | Session chính của Claude Code (theo hướng dẫn của skill hoặc command) | Script, vòng lặp tất định, gọi `claude -p` |
| Context | Dùng chung một phiên, có `/clear` hoặc compact giữa các task | **Mỗi task một session mới**; dùng `--resume` khi cần |
| Hết hạn mức | Bật "Continue automatically at usage limit" | Script nhận diện lỗi, chờ đến giờ reset rồi tiếp tục `[cần kiểm thử]` |
| Theo dõi | Xem trực tiếp | Log, `PROGRESS.md`, PR |
| Khi nào dùng | Chạy thử, quan sát, task cần theo dõi | Khi quy trình đã ổn định, chạy khi ngủ |

**Worktree:** chế độ B (và nên dùng cả cho A) chạy trong một **git worktree riêng**, tức một thư mục làm việc tách biệt của cùng repo. Như vậy agent không đụng vào những gì người dùng đang mở trong VS Code.

### 6.8 Luồng chi tiết của một mốc

```
GIAI ĐOẠN 1: CHẠY MỐC (tự động)
  Tạo/checkout nhánh milestone/M1 trong worktree riêng
  Lặp qua task chưa xong, theo thứ tự phụ thuộc:
    ① developer: code + test → commit "M1/dev-01: …"
         └ hook SubagentStop: verify so với baseline
              lỗi mới → developer sửa tiếp (không tốn lượt review)
    ② reviewer (context sạch): task + tiêu chí + diff + tự chạy test → JSON
    ③ FAIL → feedback (blocking issues) quay lại ① ; số vòng += 1
         số vòng > MAX (đề xuất 3)          → BLOCKED
         cùng một blocking issue lặp lại 2 lần → BLOCKED (phát hiện bị kẹt)
    ④ PASS → task DONE; cập nhật plan/M1.md + PROGRESS.md
         điều chỉnh plan (a)/(b): làm luôn, ghi lý do
         điều chỉnh (c): CHỈ ghi vào "Đề xuất chờ duyệt"
  Hết task → verify toàn mốc + e2e toàn bộ

GIAI ĐOẠN 2: BÀN GIAO MỐC
  push nhánh → mở PR "M1: …" với báo cáo (mục 6.10)
  khởi động app local → ghi link + ảnh chụp màn hình (Playwright)
  DỪNG. Không tự sang M2.

GIAI ĐOẠN 3: NGƯỜI DÙNG DUYỆT
  mở link để test, đọc báo cáo, duyệt hoặc từ chối đề xuất (c), merge PR
  nếu cần sửa: ghi feedback vào file → feedback trở thành task đầu tiên của lượt chạy sau
  ra lệnh chạy M2
```

### 6.9 Đầu ra của reviewer (schema đề xuất)

Các trường (ép bằng `--json-schema` ở chế độ headless):

- `task_id`: ví dụ `"M1/dev-01"`
- `status`: `"PASS"` | `"FAIL"`
- `criteria`: mảng `{criterion, met: true|false, evidence}`. **Bằng chứng** phải trỏ tới file, dòng code, hoặc test cụ thể.
- `blocking_issues`: mảng `{id, file, description, required_action}`
- `non_blocking`: mảng góp ý (không chặn)
- `tests_rerun`: `{command, passed, failed}`, do **reviewer tự chạy**
- `plan_suggestions`: đề xuất loại (c), nếu có
- `summary`: 1–2 câu

### 6.10 Báo cáo mốc (nội dung PR)

1. Tóm tắt mốc: đã đạt những gì so với tiêu chí cấp mốc.
2. Bảng task: trạng thái, số vòng, commit, ghi chú.
3. **Task BLOCKED** và lý do, kèm việc cần người dùng quyết định.
4. Các điều chỉnh plan (a)/(b) đã tự làm, kèm lý do.
5. **Đề xuất chờ duyệt (c).**
6. Kết quả verify và e2e toàn mốc, kèm so sánh với baseline.
7. **Link chạy thử** (`http://localhost:PORT`), cách khởi động lại app, và ảnh chụp các màn hình chính.
8. Hạn mức đã dùng (nếu đo được) và thời gian chạy.

### 6.11 Máy trạng thái của task

```
TODO → IN_PROGRESS → VERIFYING → IN_REVIEW → DONE
            ▲             │            │
            └── REWORK ◄──┴────────────┘   (đếm số vòng)
                  │
                  └──► BLOCKED (vượt số vòng / lỗi lặp lại / cần quyết định của người)
```

Trạng thái lưu ở `.autodev/state.json` và trong `plan/Mx.md`, được commit theo task. Nhờ đó luôn **chạy tiếp được đúng chỗ**.

### 6.12 Rủi ro và cách chặn

| Rủi ro | Cách xử lý |
|---|---|
| Hết hạn mức giữa chừng | State nằm trong file, commit theo task. A: auto-continue. B: script chờ đến giờ reset rồi tiếp tục. |
| Cùng một họ model tự chấm bài (điểm mù chung) | Gate cứng và e2e làm bằng chứng khách quan. Reviewer có prompt riêng và chỉ có quyền đọc. Người dùng duyệt mỗi mốc. Tuỳ chọn: reviewer dùng model khác. |
| Reviewer quá dễ dãi hoặc quá khắt khe | Đo trong giai đoạn chạy thử, tinh chỉnh prompt và tiêu chí. Bắt buộc có trường `evidence`. |
| Plan bị trôi | Quyền điều chỉnh theo R8. Mọi thay đổi ghi lý do vào PROGRESS.md. Mục (c) chỉ được đề xuất. |
| Vòng lặp dev ↔ reviewer không dứt | Tối đa N vòng và phát hiện cùng một lỗi lặp lại, dẫn tới BLOCKED. |
| Lệnh nguy hiểm khi chạy không hỏi | Chỉ làm việc trên nhánh riêng, trong worktree riêng. Permission rules và hook `PreToolUse` chặn push lên main, `rm -rf`, sửa `.env`/secrets, và các lệnh phá huỷ database. |
| Test e2e chập chờn | Chạy lại 1 lần. Ghi nhận test flaky vào báo cáo. |
| Context hoặc token phình | Mỗi task một session (B). Reviewer chỉ đọc diff. CLAUDE.md ngắn. Hook lọc output test. |
| Dự án đang dở có sẵn lỗi | Baseline. Gate chỉ chặn lỗi mới phát sinh. |
| Agent và người dùng cùng sửa một repo | Agent chạy trong git worktree riêng. |
| Lộ token bot Telegram / topic ntfy | Lưu token trong `.env` (đã thêm vào `.gitignore`) hoặc biến môi trường. Đặt tên topic ntfy ngẫu nhiên. Không gửi nội dung nhạy cảm qua thông báo. |
| Người khác điều khiển phiên qua kênh chat | Bật allowlist và chỉ ghép cặp tài khoản của chính người dùng (mục 6.13). |

### 6.13 Thông báo và điều khiển từ xa (bổ sung ở bản 1.1)

**Mục đích:** khi chạy qua đêm hoặc khi người dùng không ngồi ở máy, họ vẫn biết được lúc mốc xong, lúc có task bị BLOCKED, hay lúc Claude đang chờ trả lời. Nếu muốn, họ có thể trả lời hoặc ra lệnh từ điện thoại.

**Nguyên lý chung:** cần một "người đưa thư" trung gian (dịch vụ thông báo hoặc bot chat). Máy tính gửi tin lên dịch vụ đó, dịch vụ đẩy tin xuống điện thoại. Lệnh gửi tin được gắn vào **hook** của Claude Code hoặc vào **orchestrator**.

**Các điểm gắn thông báo:**
- Hook **`Notification`** `[KIỂM CHỨNG]`: kích hoạt khi Claude đang chờ người dùng trả lời hoặc duyệt quyền. Các loại thông báo có `permission_prompt`, `idle_prompt`, `agent_completed`, `quota_auto_resume_fired`… Tài liệu chính thức có ví dụ hook gửi thông báo desktop (`osascript` trên macOS, `notify-send` trên Linux). Chỉ cần thay lệnh trong ví dụ bằng lệnh gửi lên điện thoại.
- Hook **`Stop`**: kích hoạt khi Claude làm xong một lượt.
- **Orchestrator (chế độ B)**: gửi tin ở cuối mỗi mốc, khi có task BLOCKED, khi hết hạn mức (kèm giờ dự kiến chạy tiếp), và khi gặp lỗi bất thường.

**Ba lựa chọn, từ đơn giản đến mạnh:**

| | **ntfy** | **Bot Telegram một chiều** | **Telegram channel của Claude Code (hai chiều)** |
|---|---|---|---|
| Chiều | Máy → điện thoại | Máy → điện thoại | Điện thoại ⇄ phiên Claude Code đang chạy |
| Thời gian setup | ~15 phút | ~10–15 phút | ~20–30 phút |
| Riêng tư | Thấp: topic công khai, ai đoán được tên thì đọc được | Cao: cần token để gửi, chỉ chat_id của người dùng nhận | Cao: ghép cặp và allowlist |
| Chạy được với `claude -p` (B) | ✅ (orchestrator gọi lệnh) | ✅ (orchestrator gọi lệnh) | Có `--channels` ở chế độ `-p`, nhưng các tool cần nhập liệu bị tắt. Phù hợp nhất với phiên interactive (A). |
| Trạng thái | Dịch vụ bên thứ ba | API Telegram ổn định | **Research preview** `[KIỂM CHỨNG]`, có thể thay đổi |

**(1) ntfy:**
1. Cài app ntfy trên điện thoại, theo dõi một topic có tên ngẫu nhiên (ví dụ `autodev-<chuỗi-ngẫu-nhiên>`).
2. Gửi tin: `curl -d "M1 xong, PR đã mở" ntfy.sh/<topic>`.

**(2) Bot Telegram một chiều:**
1. Trong Telegram, nhắn **@BotFather** lệnh `/newbot`, đặt tên và username (kết thúc bằng `bot`), nhận về **token**.
2. Lấy **chat_id**: nhắn bot một tin bất kỳ, rồi mở `https://api.telegram.org/bot<TOKEN>/getUpdates` và tìm `"chat":{"id": …}`.
3. Gửi tin: `curl -s https://api.telegram.org/bot<TOKEN>/sendMessage -d chat_id=<CHAT_ID> -d text="…"`.
4. Gói lệnh vào một script `notify.sh` đọc token và chat_id từ biến môi trường. Gọi script từ hook hoặc orchestrator.

**(3) Telegram channel chính thức của Claude Code** `[KIỂM CHỨNG 2026-10-06]`:
- **Bản chất:** Channels là một MCP server, được cài dưới dạng plugin, có nhiệm vụ **đẩy tin nhắn vào phiên Claude Code đang mở**. Claude đọc tin, làm việc trên file thật của máy, rồi trả lời lại trong Telegram. Có bản cho Telegram, Discord và iMessage.
- **Yêu cầu:** cài **Bun**. Người dùng gói Pro/Max không thuộc tổ chức thì không cần admin bật gì thêm.
- **Các bước:**
  1. Tạo bot với @BotFather, lấy token.
  2. `/plugin install telegram@claude-plugins-official` (chọn phạm vi user). Nếu báo thiếu marketplace thì chạy `/plugin marketplace add anthropics/claude-plugins-official` trước.
  3. `/telegram:configure <token>` (lưu vào `~/.claude/channels/telegram/.env`).
  4. Khởi động lại Claude Code với `claude --channels plugin:telegram@claude-plugins-official`.
  5. Nhắn bot một tin để nhận mã ghép cặp, rồi chạy `/telegram:access pair <mã>` và `/telegram:access policy allowlist`.
- **Làm được gì:** hỏi tiến độ, ra lệnh ("bỏ qua dev-03"), trả lời câu hỏi của Claude, và **duyệt quyền từ xa** (permission relay, khi channel hỗ trợ).
- **Lưu ý:**
  - Tin chỉ đến được khi **phiên đang mở**.
  - **Ai nằm trong allowlist cũng duyệt được quyền thay người dùng**.
  - Mỗi tin nhắn là một lượt làm việc của Claude, nên **tốn hạn mức gói Pro**.
  - Đây là research preview, cờ `--channels` có thể đổi cú pháp.

**Phương án thay thế: Remote Control.** Theo bảng so sánh trong tài liệu Channels, tính năng này cho phép điều khiển phiên Claude Code trên máy từ claude.ai hoặc app Claude trên điện thoại, không cần tạo bot. `[CHƯA ĐỌC CHI TIẾT]`, nên nghiên cứu thêm.

**Khuyến nghị:**
- Bắt đầu bằng **(2) bot Telegram một chiều**, gọi từ hook `Notification`/`Stop` và từ orchestrator.
- Khi quy trình đã ổn định, thử **(3) Telegram channel** cho chế độ A.

### 6.14 "Framework" và "plugin": giải thích và cách triển khai (bổ sung ở bản 1.1)

> Mục đích: làm rõ hai khái niệm thường nghe thấy, để thấy chúng **không đòi hỏi kỹ năng lập trình lớn**. Trong bối cảnh này, cả hai về bản chất là **thư mục và file văn bản đặt đúng chỗ, theo đúng quy ước**.

**Framework = bộ quy ước + file mẫu.**
- Không phải một thư viện code như React hay Django. Ở đây "framework" chỉ có nghĩa là: *mọi dự án đều được tổ chức giống nhau*, để cùng một bộ agent làm việc được với tất cả.
- Hình dung như mẫu hồ sơ chuẩn của một công ty: giá trị nằm ở sự **nhất quán**, không nằm ở kỹ thuật.
- Trong thiết kế này, framework gồm các quy ước đã nêu ở mục 6:
  - plan ở `plan/Mx.md` theo mẫu ở mục 6.5;
  - nhật ký ở `PROGRESS.md`;
  - trạng thái task theo mục 6.11;
  - lệnh kiểm tra khai báo ở `.autodev/config`;
  - schema của reviewer theo mục 6.9;
  - báo cáo mốc theo mục 6.10.
- **Cách xây dựng:** viết các file mẫu một lần, copy vào dự án mới, điền nội dung. Phần khó là **chọn quy ước cho hợp lý**, và điều này chỉ rõ dần qua các lần chạy thử.

**Plugin = gói chứa bộ công cụ, cài một lần, dùng cho mọi dự án** `[KIỂM CHỨNG]`.
- **Vấn đề nó giải quyết:** agents, hooks và skills nằm trong `.claude/` của **một** dự án. Sang dự án khác phải copy lại, và sửa prompt reviewer thì phải sửa ở mọi nơi. Plugin gom tất cả về một chỗ: sửa một lần, mọi dự án được cập nhật.
- **Cấu trúc:** chỉ là một thư mục:
  ```
  autodev-plugin/
  ├─ .claude-plugin/plugin.json      "nhãn hộp": tên, phiên bản, mô tả
  ├─ agents/developer.md, reviewer.md
  ├─ skills/run-milestone/SKILL.md   chạy như lệnh /autodev-plugin:run-milestone
  ├─ skills/onboard/SKILL.md
  └─ hooks/hooks.json                verify, chặn lệnh nguy hiểm, gửi thông báo
  ```
  Nội dung bên trong **giống hệt** những gì đặt trong `.claude/` của dự án. Đóng gói chỉ thêm `plugin.json` và sắp xếp lại thư mục, **không viết thêm logic**.
- **Cách dùng:**
  1. Thử tại chỗ: `claude --plugin-dir ./autodev-plugin`.
  2. Dùng cho mọi dự án: đẩy lên một repo GitHub có `.claude-plugin/marketplace.json` (danh mục plugin), rồi `/plugin marketplace add <repo>` và `/plugin install <tên>@<marketplace>`.
  3. **Phạm vi cài:** user (mọi dự án trên máy, dùng được cả trong terminal, app desktop và VS Code extension), project (qua `.claude/settings.json` được commit), hoặc local.
- **Chi phí:** khi plugin đang bật, tên và mô tả của các agent và skill trong nó luôn nằm trong context ở mọi lượt, nên **tốn một ít hạn mức** kể cả khi không dùng. Hãy giữ plugin gọn và tắt nó ở dự án không cần (`/plugin` hoặc `claude plugin disable`).
- **Bảo mật:** plugin chạy với quyền của người dùng. Chỉ cài plugin từ nguồn tin cậy.

**Lộ trình cho người ít kinh nghiệm:**

| Bước | Việc | Độ khó |
|---|---|---|
| 1 | Đặt agents và hooks thẳng vào `.claude/` của **một** dự án, chạy thử | Thấp (viết Markdown) |
| 2 | Thêm thông báo Telegram một chiều vào hook | Thấp (một lệnh `curl`) |
| 3 | Viết file mẫu cho plan, PROGRESS và config ("framework") | Thấp, làm dần |
| 4 | Sang dự án thứ hai: chuyển các file từ bước 1 vào thư mục plugin, thêm `plugin.json`, thử bằng `--plugin-dir` | Trung bình thấp |
| 5 | Đẩy plugin lên GitHub làm marketplace riêng | Trung bình |

**Nguyên tắc:** **không đóng gói plugin trước khi bộ agent chạy ổn trên một dự án.** Claude Code tự viết được các file này. Có sẵn skill hướng dẫn tạo plugin và tạo skill để hỗ trợ.

---

## 7. Điểm chưa chốt `[CHƯA CHỐT]`

| # | Câu hỏi | Ghi chú / gợi ý |
|---|---|---|
| Q1 | Khi chạy qua đêm mà xong mốc (hoặc bị BLOCKED), có cần **thông báo** (desktop, điện thoại) không, hay sáng ra mở PR là đủ? Nếu có thì dùng kênh nào: ntfy, bot Telegram một chiều, hay Telegram channel hai chiều? | Người dùng đã hỏi kỹ về Telegram (mục 6.13). Khuyến nghị: bắt đầu bằng bot Telegram một chiều. **Chưa chốt.** |
| Q2 | Khi một task **BLOCKED**: tiếp tục các task không phụ thuộc vào nó, hay **dừng cả mốc**? | **Đã chốt:** chạy tiếp các task không phụ thuộc. |
| Q3 | Đóng gói bộ công cụ thành **plugin** hay thành **thư mục template** để copy? | Khuyến nghị (mục 6.14): giai đoạn đầu đặt thẳng vào `.claude/` của một dự án, đến dự án thứ hai mới chuyển thành plugin. |
| Q9 | Dự án SME CI Agent có **hạn chót** gần (demo, nộp MVP) không? | **Đã chốt 2026-10-06:** các hạn trong TASKS.md/PLAN.md **chỉ để tham khảo**, người dùng (leader) tự điều chỉnh. Không dùng hạn làm lý do hoãn chạy thử hay cắt việc. Chạy thử ngay. |
| Q4 | Có cần mở link chạy thử **từ điện thoại hoặc máy khác** không (cần tunnel), hay chỉ cần trên máy cá nhân? | Mặc định: chỉ localhost |
| Q5 | Số vòng tối đa cho mỗi task: 3 (đề xuất mới) hay 5 (ý ban đầu)? | **Đã chốt:** 3 |
| Q6 | Reviewer dùng Sonnet hay Opus? | **Đã chốt:** Sonnet (xem lại sau khi đo hạn mức) |
| Q7 | Các dự án hiện có **test tự động** chưa, và dùng **stack** gì? | **SME CI Agent:** Python 3.12 + uv, pytest + ruff; chưa có typecheck, build, e2e (dashboard chưa khởi tạo). Verify = ruff → pytest. |
| Q8 | PR theo mốc: merge vào `main` trực tiếp hay qua nhánh trung gian (`develop`)? | Chưa thảo luận |

---

## 8. Giả định và điểm chưa kiểm chứng

- `[GIẢ ĐỊNH]` `claude -p` **không** tự chờ khi hết hạn mức của subscription. Cần kiểm tra thực tế xem lỗi trả về trông thế nào và có kèm giờ reset không.
- `[KIỂM CHỨNG 2026-10-06]` Matcher của `SubagentStop` lọc theo tên agent (`agent_type`). Hook cũng khai báo được trong frontmatter của agent; ở đó `Stop` được tự chuyển thành `SubagentStop` và chỉ sống khi agent đó chạy. Lưu ý: `stop_hook_active` chỉ cho biết có hook Stop đang chạy ở phiên cha, nên vẫn cần bộ đếm riêng để chống lặp. `[GIẢ ĐỊNH]` còn lại: hoạt động như nhau ở chế độ B (`-p`).
- `[CHƯA BIẾT]` Một task tiêu tốn bao nhiêu % hạn mức 5 tiếng của gói Pro. **Không ước lượng**, phải đo bằng `/usage` khi chạy thử.
- `[CHƯA BIẾT]` Chất lượng thực tế của reviewer: tỷ lệ bắt được lỗi thật so với lỗi vụn hay báo sai.
- `[RỦI RO]` Các tính năng Claude Code thay đổi nhanh. Mọi mục `[KIỂM CHỨNG]` đều phải kiểm tra lại docs trước khi triển khai.

---

## 9. Lộ trình đề xuất

| Bước | Nội dung | Tiêu chí xong |
|---|---|---|
| 0 | Chốt các mục Q1–Q8 | Có câu trả lời |
| 1 | Viết thiết kế chi tiết: nội dung từng file agent, hook, config, verify, logic orchestrator | Người dùng duyệt |
| 2 | Chọn **1 dự án đang dở**, onboarding, tạo baseline | Verify chạy được, có e2e cho luồng chính |
| 3 | **Chạy thử ở chế độ A** trên 1 mốc nhỏ (3–4 task) | Đo được: % hạn mức mỗi task, số vòng trung bình, chất lượng review |
| 4 | Tinh chỉnh prompt reviewer, tiêu chí, gate | Tỷ lệ báo sai chấp nhận được |
| 5 | Viết orchestrator chế độ B, kiểm thử trường hợp hết hạn mức | Chạy qua đêm 1 mốc không cần can thiệp |
| 6 | Đóng gói thành plugin hoặc template, áp dụng cho dự án thứ 2 | Onboarding dự án mới chỉ mất < 1 buổi |
| 7 (tuỳ chọn) | GitHub Actions (OAuth token gói Pro), deploy preview, thông báo | Khi có nhu cầu |

### 9.1 Khuyến nghị bước tiếp theo (bổ sung ở bản 1.1)

Thay vì chọn giữa "quay lại SME CI Agent" và "nghiên cứu tiếp", **dùng SME CI Agent làm dự án chạy thử** (bước 2–3 ở bảng trên):

- **Lý do:** thiết kế vốn đề xuất chạy thử trên một dự án đang dở. Các câu hỏi mở quan trọng nhất (hạn mức tiêu hao, chất lượng reviewer) chỉ trả lời được bằng code thật. Dự án vẫn tiến, còn thiết kế được kiểm chứng.
- **Giới hạn thời gian:** phần thiết lập chỉ nên mất khoảng **một buổi tối**, và chỉ làm chế độ A:
  - 2 file agent;
  - 1 script verify;
  - đưa plan của SME CI Agent về dạng M1 / dev-01 có tiêu chí chấp nhận;
  - chụp baseline;
  - (tuỳ chọn) bot Telegram một chiều.
- **Chưa làm:** orchestrator chế độ B, đóng gói plugin.
- **Nếu chạy thử không ổn:** quay về cách làm cũ cho SME CI Agent, không mất nhiều.
- **Về hạn chót (Q9, đã chốt):** hạn của dự án chỉ để tham khảo, không phải điều kiện để dời việc chạy thử.

**Chỉ số cần theo dõi khi chạy thử:** % hạn mức mỗi task, số vòng dev ↔ reviewer, tỷ lệ task bị BLOCKED, số lỗi người dùng phát hiện khi duyệt mốc mà hệ thống đã bỏ sót, và thời gian đến khi có PR.

---

## 10. Hướng nghiên cứu mở rộng

- **Agent teams** của Claude Code (khi bớt experimental, hoặc khi chuyển lên gói cao hơn): dùng cho các task song song độc lập, ví dụ frontend và backend cùng lúc.
- **Claude Agent SDK** (Python/TypeScript): viết orchestrator kiểm soát chặt hơn so với gọi `claude -p` qua shell.
- **GitHub Actions + `@claude`**: chuyển vòng lặp lên cloud để không phụ thuộc vào việc máy cá nhân bật.
- **Code Review của Claude trên PR**: thêm một lớp review ở cấp mốc.
- Các mô hình "AI dev team" khác (planner → dev → QA → reviewer): cân nhắc thêm vai trò **planner** để tự tách mốc thành task, hoặc **QA** chuyên viết e2e.
- Reviewer dùng **model hoặc nhà cung cấp khác** để giảm điểm mù chung.

---

## 11. Thuật ngữ

| Thuật ngữ | Nghĩa trong tài liệu này |
|---|---|
| Mốc (milestone) | M1, M2…: đơn vị công việc lớn, mỗi mốc kết thúc bằng một PR và một lần người dùng duyệt |
| Task | dev-01, dev-02…: đơn vị nhỏ trong mốc, mỗi task một commit |
| Gate / kiểm tra cứng | Lint, typecheck, test, build, e2e: kiểm tra tất định, không dùng LLM |
| Baseline | Ảnh chụp các lỗi có sẵn lúc onboarding; gate chỉ chặn lỗi mới so với ảnh chụp này |
| Subagent | Agent con của Claude Code với context, tool và model riêng |
| Hook | Script hoặc prompt chạy tự động tại các sự kiện của Claude Code (Stop, SubagentStop, PreToolUse…) |
| Headless | Chạy Claude Code không cần giao diện bằng `claude -p` |
| Worktree | Thư mục làm việc tách biệt của cùng một git repo |
| BLOCKED | Task không tự hoàn thành được, cần người dùng quyết định |
| (a)/(b)/(c) | Ba mức quyền điều chỉnh plan (xem R8) |
| Framework | Trong tài liệu này: bộ quy ước và file mẫu chung cho mọi dự án (mục 6.14), không phải thư viện code |
| Plugin | Thư mục đóng gói agents, skills, hooks (và MCP server), cài một lần dùng cho nhiều dự án (mục 6.14) |
| Marketplace | Repo hoặc thư mục có `.claude-plugin/marketplace.json`, đóng vai trò danh mục để cài plugin |
| Channel | MCP server (cài dạng plugin) đẩy tin nhắn từ Telegram/Discord/iMessage vào phiên Claude Code đang chạy; research preview |
| ntfy | Dịch vụ thông báo đẩy đơn giản: gửi bằng `curl`, nhận bằng app điện thoại |

---

## 12. Nguồn tham khảo (đã đọc ngày 2026-10-05)

- Subagents: https://code.claude.com/docs/en/sub-agents
- Hooks reference: https://code.claude.com/docs/en/hooks
- Headless / chạy bằng chương trình: https://code.claude.com/docs/en/headless.md
- Agent teams: https://code.claude.com/docs/en/agent-teams.md
- Quản lý chi phí và hạn mức: https://code.claude.com/docs/en/costs.md
- Lỗi và hạn mức sử dụng: https://code.claude.com/docs/en/errors.md
- GitHub Actions: https://code.claude.com/docs/en/github-actions.md
- Bản đồ tài liệu Claude Code: https://code.claude.com/docs/en/claude_code_docs_map.md
- Hooks guide (hook Notification): https://code.claude.com/docs/en/hooks-guide.md *(đọc ngày 2026-10-06)*
- Plugins overview: https://code.claude.com/docs/en/plugins.md *(đọc ngày 2026-10-06)*
- Channels (Telegram, Discord, iMessage): https://code.claude.com/docs/en/channels.md *(đọc ngày 2026-10-06)*

---

## 13. Nhật ký thay đổi

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| 1.0 | 2026-10-05 | Bản đầu: yêu cầu đã xác nhận, các phương án đã loại, thiết kế chốt, các điểm còn mở, lộ trình |
| 1.2 | 2026-10-06 | Chuyển vào `docs/autodev/`. Chốt Q2 (chạy tiếp task không phụ thuộc), Q5 (3 vòng), Q6 (Sonnet), Q7 (Python/uv; verify = ruff + pytest, chưa có typecheck/e2e), Q9 (hạn chỉ tham khảo); Q1 hoãn. Kiểm chứng lại matcher `SubagentStop` và frontmatter agent (`hooks`, `maxTurns`, `isolation`). Thiết lập chế độ A. |
| 1.1 | 2026-10-06 | Thêm mục 6.13 (thông báo và điều khiển từ xa: ntfy, bot Telegram, Telegram channel, Remote Control), mục 6.14 (giải thích framework và plugin, lộ trình triển khai), mục 9.1 (khuyến nghị dùng SME CI Agent làm dự án chạy thử, có giới hạn thời gian), Q9; cập nhật Q1, Q3, thuật ngữ, nguồn, và 2 rủi ro về bảo mật thông báo |