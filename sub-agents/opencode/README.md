# Agent: opencode

Sub-agent chính hiện dùng. CLI docs: https://opencode.ai/docs/cli/ (dưới đây là phần chắt lọc cho workflow delegate).

## Environment — điền theo máy

> Bản generic. Chạy các lệnh dò rồi cập nhật cho máy thực tế.

| Mục | Cách kiểm / giá trị mặc định (máy chủ repo) |
|---|---|
| CLI | `opencode --version` — cài qua `npm i -g opencode-ai` |
| Gọi từ Git Bash (Windows) | npm global bin đôi khi chưa trên PATH → `export PATH="$PATH:$(cygpath "$APPDATA")/npm"` (hoặc path npm global thật) |
| Config | `~/.config/opencode/opencode.json` |
| Auth | `~/.local/share/opencode/auth.json` (CLI dùng chung — không cần login lại nếu Desktop đã auth) |
| Providers | `opencode auth list` — mặc định máy này: **OpenCode Go + Google (+ ZEN free)** |
| Desktop GUI | Có thể cài kèm (`@opencode-aidesktop`), Electron, **KHÔNG có headless** — tách biệt CLI |

**Model** lấy từ slot OpenCode GO/ZEN đang bật ở Brain → Settings → Sub Agents, rồi đối chiếu
`opencode models` trên máy hiện tại trước khi chạy.

## Lệnh cốt lõi: `opencode run` (non-interactive)

```bash
opencode run --model <provider/model> --agent build --auto \
  --dir "<đường dẫn project>" "$(cat spec.md)" > run.log 2>&1
```

| Flag | Tác dụng |
|---|---|
| `-m, --model` | `provider/model` (theo model policy) |
| `--agent` | agent dùng (vd `build`); có thể tạo agent custom |
| `--auto` | **auto-approve permission** — bắt buộc khi headless, kẻo treo chờ xác nhận |
| `--dir` | thư mục làm việc |
| `--format` | `default` hoặc `json` (raw event, dễ parse, đỡ tràn context) |
| `-c/--continue`, `-s/--session`, `--fork` | tiếp/chỉ định/fork session |
| `-f, --file` | đính kèm file vào prompt |
| `--title` | đặt tên session |
| `--attach <url>` | gắn vào `opencode serve` đang chạy (tránh cold-boot MCP mỗi lần) |

### Giảm cold-start: `serve` + `--attach`
```bash
opencode serve --port 4096                       # terminal nền
opencode run --attach http://localhost:4096 -m <model> --auto "..."
```

### Agent custom (scope quyền, giới hạn blast radius)
```bash
opencode agent create --path .opencode/agent --description "impl từ spec, không push" \
  --mode subagent --permissions read,edit,bash,grep,glob
```
Quyền cấp được: `bash, read, edit, glob, grep, webfetch, task, todowrite, websearch, lsp, skill`. **Bỏ cái nào = deny.**

### Xem lại
```bash
opencode session list --format json -n 5
opencode export <sessionID> --sanitize > session.json
opencode stats --days 7
```

## Gotchas (đã verify)

1. **Model free CHẬM** — task nhỏ có thể >2 phút → **chạy nền** hoặc set timeout cao; luôn `> run.log 2>&1` để không mất kết quả nếu bị cắt (file thường đã ghi xong trước khi model "nói xong").
2. **`--auto` bắt buộc** khi headless.
3. **Windows**: có thể cần `OPENCODE_GIT_BASH_PATH` trỏ tới `bash.exe` nếu tool `bash` lỗi.
4. **opencode mặc định ĐỌC `~/.claude/CLAUDE.md` + `.claude/skills`** → tự tuân ràng buộc project. Tắt bằng `OPENCODE_DISABLE_CLAUDE_CODE=true` nếu muốn cô lập.
5. **Quyền sửa file thật** → branch riêng + commit mốc trước khi giao.
6. `OPENCODE_PERMISSION` / `OPENCODE_CONFIG_CONTENT` (inline JSON) để override theo từng lần chạy.

## Recipe đầy đủ
```bash
# branch sạch + mốc
git checkout -b feat/<slug> && git commit -m "wip: baseline" --allow-empty
# giao (chạy nền nếu model chậm), log ra file
opencode run -m opencode/deepseek-v4-flash-free --agent build --auto \
  --dir "<path>" "$(cat spec.md)" > run.log 2>&1
# review gate (đọc phần này, KHÔNG đọc full log)
git --no-pager diff
<lệnh verify của project>
cat SUBAGENT_SUMMARY.md
```
