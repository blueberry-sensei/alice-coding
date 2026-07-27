#!/usr/bin/env node
/**
 * cli — lớp vỏ npm cho ALICE CODING.
 *
 * KHÔNG chứa logic nghiệp vụ. Nó chỉ: dò môi trường (Docker Desktop / Docker CE
 * trong WSL / mac / Linux), tìm đúng Python, rồi gọi launcher + script Python thật.
 * Ai không dùng Node vẫn chạy được mọi thứ bằng lệnh gốc — xem `npm run doctor`.
 *
 * Chỉ dùng built-in của Node (>=18). Không dependency.
 */
"use strict";

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const http = require("http");

const ROOT = path.resolve(__dirname, "..");
const STACK = path.join(ROOT, "brain", "stack");
const IS_WIN = process.platform === "win32";

const C = {
  d: (s) => `\x1b[2m${s}\x1b[0m`,
  b: (s) => `\x1b[1m${s}\x1b[0m`,
  g: (s) => `\x1b[32m${s}\x1b[0m`,
  y: (s) => `\x1b[33m${s}\x1b[0m`,
  r: (s) => `\x1b[31m${s}\x1b[0m`,
};
const OK = C.g("  OK  "), WARN = C.y(" CHÚ Ý"), ERR = C.r(" LỖI ");

function tryRun(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { encoding: "utf8", shell: false, ...opts });
  return { ok: r.status === 0, out: ((r.stdout || "") + (r.stderr || "")).trim(), status: r.status };
}

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: "inherit", shell: false, cwd: ROOT, ...opts });
  return r.status === 0 ? 0 : (r.status === null ? 1 : r.status);
}

/* ------------------------------------------------------------ môi trường */

function findPython() {
  const cands = IS_WIN
    ? [["py", ["-3"]], ["python", []], ["python3", []]]
    : [["python3", []], ["python", []]];
  for (const [cmd, pre] of cands) {
    const r = tryRun(cmd, [...pre, "-c", "import sys;print(sys.version.split()[0])"]);
    if (r.ok) return { cmd, pre, version: r.out };
  }
  return null;
}

/** Docker Desktop/native trước; Windows thì thử tiếp Docker CE trong WSL. */
function findDocker() {
  const native = tryRun("docker", ["version", "--format", "{{.Server.Version}}"]);
  if (native.ok) return { kind: "native", cmd: "docker", pre: [], version: native.out };
  if (IS_WIN) {
    const wsl = tryRun("wsl", ["-e", "docker", "version", "--format", "{{.Server.Version}}"]);
    if (wsl.ok) return { kind: "wsl", cmd: "wsl", pre: ["-e", "docker"], version: wsl.out };
  }
  return null;
}

const brainEnv = require(path.join(STACK, "brain-env.js"));

/**
 * Bộ biến môi trường cho `docker compose`, đọc từ file .env của brain — file này nằm NGOÀI
 * repo (thư mục state của người dùng) vì nó chứa SAG_SECRET_KEY.
 *
 * Chỉ ĐỌC, không tạo: `status`/`list`/`mcp` chỉ đang hỏi thăm, không nên đẻ ra state cho một
 * brain chưa từng dựng. Việc tạo là của `npm run brain`.
 */
function composeEnv() {
  const info = brainEnv.peek();
  if (!info.exists) return null;
  const map = {};
  for (const line of fs.readFileSync(info.BRAIN_ENV_FILE, "utf8").split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith("#") || !t.includes("=")) continue;
    const i = t.indexOf("=");
    map[t.slice(0, i).trim()] = t.slice(i + 1).trim();
  }
  const abs = (v, fallback) => {
    const raw = v || fallback;
    return path.isAbsolute(raw) ? path.normalize(raw) : path.resolve(STACK, raw);
  };
  return {
    ...process.env,
    // Mặc định trỏ tới thư mục launcher tự clone; .env có thể ép sang bản trên máy.
    ALICE_APP_PATH: abs(map.ALICE_APP_PATH, "alice-brain"),
    ALICE_CORE_PATH: abs(map.ALICE_CORE_PATH, "alice-core"),
    BRAIN_LOGS: path.join(ROOT, "brain", ".logs", "api"),
    SAG_SECRET_KEY: map.SAG_SECRET_KEY || "",
    BIND_ADDRESS: map.BIND_ADDRESS || "127.0.0.1",
    WEB_PORT: info.WEB_PORT,
    API_PORT: info.API_PORT,
    CHECKLIST_PORT: info.CHECKLIST_PORT,
    ALICE_APP_PATH: abs(map.ALICE_APP_PATH, "alice-brain"),
    ALICE_CORE_PATH: abs(map.ALICE_CORE_PATH, "alice-core"),
    // compose.dev.yaml nội suy ${BRAIN_ID} vào tag image. Thiếu biến này thì `down`/`uninstall`
    // ở chế độ dev nhìn ra tag rỗng và KHÔNG xoá được image vừa build.
    BRAIN_ID: info.BRAIN_ID,
    _BRAIN_ID: info.BRAIN_ID,
    _ENV_FILE: info.BRAIN_ENV_FILE,
    _MODE: info.BRAIN_MODE,
  };
}

function compose(args) {
  const env = composeEnv();
  if (!env) {
    console.error(C.r("Brain của project này chưa từng được dựng."));
    console.error("Chạy trước: " + C.b("npm run brain"));
    return 1;
  }
  const d = findDocker();
  if (!d) { console.error(C.r("Không tìm thấy Docker.") + " Chạy `npm run doctor`."); return 1; }
  // `-p <BRAIN_ID>` là thứ tách brain của project này khỏi brain của project khác:
  // container, network và named volume đều mang tiền tố đó.
  // Bộ `-f` phải khớp với lúc `up`, nếu không compose nhìn ra một stack khác và
  // `down` sẽ không tắt đúng cái vừa dựng.
  return run(d.cmd,
    [...d.pre, "compose", "-p", env._BRAIN_ID, ...brainEnv.composeFiles(env._MODE),
     "--env-file", env._ENV_FILE, ...args],
    { cwd: STACK, env });
}

/**
 * p có nằm THẬT SỰ trong thư mục project không?
 * CẢNH BÁO Windows: path.relative() giữa hai Ổ ĐĨA khác nhau (E:\ -> C:\) trả về
 * đường dẫn TUYỆT ĐỐI, không bắt đầu bằng ".." — nên chỉ kiểm startsWith("..")
 * là thủng, và lệnh xoá sẽ nuốt cả thư mục ngoài project. Phải chặn cả hai hướng.
 */
function insideRoot(p) {
  const rel = path.relative(ROOT, path.resolve(p));
  return rel !== "" && !rel.startsWith("..") && !path.isAbsolute(rel);
}

/** Mục tiêu sẽ bị xoá khi uninstall — tính TỪ .env (đọc trước khi xoá .env). */
function uninstallTargets() {
  // Dữ liệu não nay ở named volume; thư mục dưới đây chỉ còn là tàn dư của bản bind-mount cũ.
  const dataDir = path.resolve(STACK, "../.sag-data");
  return [
    // Dữ liệu não nay nằm trong NAMED VOLUME của Docker (`down --volumes` ở trên xoá nó).
    // Thư mục dưới đây chỉ còn là tàn dư của bản trước khi chuyển sang volume.
    { p: dataDir, what: "dữ liệu não bản cũ (bind-mount, nếu còn sót)" },
    { p: path.join(STACK, "alice-brain"), what: "source ứng dụng do launcher clone" },
    { p: path.join(STACK, "alice-core"), what: "source engine do launcher clone" },
    { p: path.join(STACK, ".env"), what: "cấu hình stack bản cũ (nếu còn sót)" },
    { p: path.join(STACK, ".env.moved"), what: "ghi chú vị trí .env mới" },
    { p: path.join(ROOT, "brain", "brain.config"), what: "cấu hình sync (chứa token)" },
    { p: path.join(ROOT, "brain", ".sync-state.json"), what: "map file→document của sync" },
  ];
}

/**
 * Gỡ Docker + toàn bộ runtime của brain. KHÔNG đụng tri thức (wiki/mistakes/
 * decisions/context/changelog) — muốn xoá tri thức thì dùng lệnh `reset`.
 */
function uninstall(argv) {
  const yes = argv.includes("--yes") || argv.includes("-y");
  const targets = uninstallTargets().filter((t) => fs.existsSync(t.p));

  const brain = brainEnv.peek();
  const keepCache = argv.includes("--keep-cache");

  console.log(C.b("Sẽ gỡ:"));
  console.log("  • container + network + volume + image của brain " + C.b(brain.BRAIN_ID));
  console.log("  • image mồ côi (dangling) do các lần build brain để lại");
  console.log(keepCache
    ? C.d("  • build cache: GIỮ (đang bật --keep-cache)")
    : "  • build cache của Docker " + C.y("— dùng chung CẢ MÁY, xem ghi chú bên dưới"));
  if (!targets.length) console.log(C.d("  • (không còn file runtime nào trên đĩa)"));
  for (const t of targets) {
    const outside = !insideRoot(t.p);
    console.log(`  • ${outside ? t.p : path.relative(ROOT, t.p)}  ${C.d("— " + t.what)}`
      + (outside ? C.y("  [NGOÀI thư mục project — sẽ BỎ QUA]") : ""));
  }
  console.log(C.g("\nGiữ nguyên: ") + "wiki/ · mistakes/ · decisions/ · context/ · changelog/ · ALICE.project.md");

  if (!keepCache) {
    console.log(C.d("\nBuild cache không gắn nhãn theo project nên Docker không lọc được phần"));
    console.log(C.d("riêng của brain — dọn là dọn cả máy. Không mất dữ liệu, chỉ khiến lần build"));
    console.log(C.d("kế tiếp của MỌI project chậm hơn. Giữ lại: npm run uninstall -- --yes --keep-cache"));
  }

  if (!yes) {
    console.log(C.y("\nĐây là thao tác KHÔNG hoàn tác được (dữ liệu não phải ingest lại từ đầu)."));
    console.log("Chắc chắn thì chạy: " + C.b("npm run uninstall -- --yes"));
    return 2;
  }

  let failed = false;
  const d = findDocker();
  if (!d) {
    console.log(C.y("Không thấy Docker — bỏ qua phần container, chỉ dọn file."));
  } else {
    const env = composeEnv();
    const viaCompose = env && run(d.cmd,
      [...d.pre, "compose", "-p", env._BRAIN_ID, ...brainEnv.composeFiles(env._MODE),
       "--env-file", env._ENV_FILE, "down",
       "--volumes", "--remove-orphans", "--rmi", "local"], { cwd: STACK, env }) === 0;
    if (!viaCompose) {
      // Lưới an toàn khi state mất hoặc compose lỗi: dọn theo label. Không có nhánh này thì
      // brain bị xoá state sẽ để lại container và volume mồ côi mà không lệnh nào nhặt được.
      const ids = tryRun(d.cmd, [...d.pre, "ps", "-aq", "--filter",
        `label=com.docker.compose.project=${brain.BRAIN_ID}`]).out.split(/\s+/).filter(Boolean);
      if (ids.length && run(d.cmd, [...d.pre, "rm", "-f", ...ids]) !== 0) failed = true;
      const vols = tryRun(d.cmd, [...d.pre, "volume", "ls", "-q", "--filter",
        `label=com.docker.compose.project=${brain.BRAIN_ID}`]).out.split(/\s+/).filter(Boolean);
      if (vols.length) run(d.cmd, [...d.pre, "volume", "rm", "-f", ...vols]);
    }

    // `compose down --rmi local` chỉ xoá image mà compose CÒN nhận ra. Image do các lần build
    // trước để lại (đổi chế độ, đổi tag, project đã xoá state) thì nó không thấy → quét theo tên.
    const images = tryRun(d.cmd, [...d.pre, "images", "--format", "{{.Repository}}:{{.Tag}}"])
      .out.split(/\r?\n/)
      .map((line) => line.trim())
      .filter((name) => name && !name.endsWith(":<none>")
        && (name.includes(brain.BRAIN_ID)
          || name.startsWith("alice-brain-api:") || name.startsWith("alice-brain-web:")));
    if (images.length) {
      console.log(C.d(`Xoá ${images.length} image của brain này...`));
      run(d.cmd, [...d.pre, "rmi", "-f", ...images]);
    }

    // Image mồ côi: an toàn tuyệt đối — theo định nghĩa là không tag và không container nào dùng.
    run(d.cmd, [...d.pre, "image", "prune", "-f"]);

    // Build cache là phần NẶNG NHẤT (vài chục GB sau ít lần build) và là lý do "gỡ rồi mà đĩa
    // vẫn đầy". Docker không lọc cache theo project được nên đây là thao tác toàn máy — đã
    // cảnh báo ở trên, `--keep-cache` để từ chối.
    if (!keepCache) {
      console.log(C.d("Dọn build cache của Docker..."));
      run(d.cmd, [...d.pre, "builder", "prune", "-af"]);
    }
  }

  for (const t of targets) {
    // An toàn: không bao giờ xoá thứ nằm ngoài thư mục project.
    if (!insideRoot(t.p)) {
      console.log(C.y(`Bỏ qua ${t.p} (ngoài project) — xoá tay nếu muốn.`));
      continue;
    }
    try { fs.rmSync(t.p, { recursive: true, force: true, maxRetries: 3 }); }
    catch (err) {
      failed = true;
      console.error(C.r(`Không xoá được ${path.relative(ROOT, t.p)}: ${err.message}`));
      console.error(C.d("  (Docker Desktop còn giữ file? Thử `npm run brain:down` rồi chạy lại.)"));
    }
  }

  console.log(failed ? C.r("\nGỡ chưa hoàn tất — xem lỗi phía trên.")
                     : C.g("\nĐã gỡ Docker + runtime. Tri thức còn nguyên."));
  console.log(C.d("Dựng lại: npm run brain   ·   Xoá luôn tri thức: npm run reset -- --yes"));
  return failed ? 1 : 0;
}

/** File tri thức thuộc PROJECT (update.py không bao giờ đụng) — reset sẽ xoá đúng nhóm này. */
function instanceKnowledge() {
  const keep = new Set(["README.md", "_TEMPLATE.md"]);
  const out = [];
  const sweep = (dir, extraKeep = []) => {
    const abs = path.join(ROOT, dir);
    if (!fs.existsSync(abs)) return;
    for (const f of fs.readdirSync(abs)) {
      if (!f.endsWith(".md") || keep.has(f) || extraKeep.includes(f)) continue;
      out.push(path.join(abs, f));
    }
  };
  sweep("wiki");                 // <module>.md + ROUTER.md
  sweep("mistakes");             // LOG.md
  sweep("decisions");            // LOG.md
  sweep("context");              // INDEX.md + digest
  sweep("changelog");            // <module>.md
  const ap = path.join(ROOT, "ALICE.project.md");
  if (fs.existsSync(ap)) out.push(ap);
  return out;
}

/**
 * Xoá sạch tri thức project rồi dựng lại khung trắng từ template mới nhất.
 * PHÁ HUỶ DỮ LIỆU — luôn cần --yes.
 */
function reset(argv) {
  const yes = argv.includes("--yes") || argv.includes("-y");
  const files = instanceKnowledge();

  console.log(C.r(C.b("RESET — sẽ XOÁ VĨNH VIỄN tri thức của project:\n")));
  if (!files.length) console.log(C.d("  (chưa có file tri thức nào — kho đang trắng)"));
  for (const f of files) console.log("  • " + path.relative(ROOT, f).replace(/\\/g, "/"));
  console.log(C.d("\nSau đó chạy `tools/update.py --ref main` để kéo template mới nhất và tạo lại khung trắng."));

  if (!yes) {
    console.log(C.y("\nKhông có bản sao lưu nào. Nếu knowledge/ đã commit thì còn cứu được bằng git;"));
    console.log(C.y("nếu chưa, tri thức mất là mất hẳn."));
    console.log("Chắc chắn thì chạy: " + C.b("npm run reset -- --yes"));
    return 2;
  }

  for (const f of files) {
    try { fs.rmSync(f, { force: true }); }
    catch (err) { console.error(C.r(`Không xoá được ${path.relative(ROOT, f)}: ${err.message}`)); return 1; }
  }
  console.log(C.d(`Đã xoá ${files.length} file. Đang kéo template mới nhất...`));
  const rc = python("tools/update.py", ["--ref", "main"]);
  if (rc !== 0) {
    console.error(C.r("update.py lỗi — kho đang trống. Chạy lại `npm run update` khi có mạng."));
    return rc;
  }
  console.log(C.g("\nĐã reset. Chạy `npm run verify` rồi INITIALIZATION để nạp lại tri thức."));
  return 0;
}

function get(url, ms = 2500) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: ms }, (res) => {
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () => resolve({ status: res.statusCode, body }));
    });
    req.on("timeout", () => { req.destroy(); resolve(null); });
    req.on("error", () => resolve(null));
  });
}

/* -------------------------------------------------------------- commands */

function up() {
  const d = findDocker();
  if (!d) {
    console.error(C.r("Không tìm thấy Docker đang chạy."));
    console.error("  • Docker Desktop: mở app, đợi icon xanh, chạy lại.");
    if (IS_WIN) console.error("  • Docker CE trong WSL: mở terminal WSL, `sudo service docker start`.");
    return 1;
  }
  console.log(C.d(`Docker: ${d.kind} (server ${d.version})`));
  if (IS_WIN && d.kind === "native") {
    console.log(C.d("→ brain-up.ps1 (Windows + Docker Desktop)"));
    return run("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass",
                              "-File", path.join(STACK, "brain-up.ps1")]);
  }
  if (IS_WIN && d.kind === "wsl") {
    console.log(C.d("→ brain-up.sh qua WSL (Docker CE trong WSL)"));
    console.log(C.y("Giữ cửa sổ này MỞ — đóng đi thì WSL tắt, brain tắt theo."));
    return run("wsl", ["-e", "bash", "brain/stack/brain-up.sh"]);
  }
  console.log(C.d("→ brain-up.sh"));
  return run("bash", [path.join(STACK, "brain-up.sh")]);
}

function python(scriptRel, args) {
  const py = findPython();
  if (!py) {
    console.error(C.r("Không tìm thấy Python.") + " Cần Python 3.9+ (https://python.org).");
    return 1;
  }
  return run(py.cmd, [...py.pre, path.join(ROOT, scriptRel), ...args]);
}

async function status() {
  const d = findDocker();
  const info = brainEnv.peek();
  console.log(C.b("Brain của project này:"));
  console.log(`  ${info.BRAIN_ID}` + (info.exists ? "" : C.y("  [chưa dựng bao giờ]")));
  console.log(C.d(`  chế độ: ${info.BRAIN_MODE === "dev" ? "dev — build từ source trên máy" : "image dựng sẵn"}`));
  console.log(C.b("\nContainer:"));
  if (d) run(d.cmd, [...d.pre, "ps", "--filter",
                     `label=com.docker.compose.project=${info.BRAIN_ID}`,
                     "--format", "  {{.Names}}\t{{.Status}}"]);
  else console.log(C.r("  Không tìm thấy Docker."));
  console.log(C.b("\nDịch vụ:"));
  const probes = [
    ["API      ", `http://localhost:${info.API_PORT}`, "/api/v1/system/ready"],
    ["Web      ", `http://localhost:${info.WEB_PORT}`, ""],
    ["Checklist", `http://localhost:${info.CHECKLIST_PORT}`, ""],
  ];
  for (const [label, base, probe] of probes) {
    const res = await get(base + probe);
    const up = probe ? res && res.status === 200 : Boolean(res);
    console.log(`  ${label} ${base}  ${up ? C.g("sẵn sàng") : C.r("chưa lên")}`);
  }
  return 0;
}

/** Mọi brain trên máy này — để biết project nào đang chiếm cổng nào, và cái nào còn chạy. */
async function list() {
  const brains = brainEnv.listBrains();
  if (!brains.length) {
    console.log(C.y("Chưa có brain nào trên máy này.") + " Dựng: " + C.b("npm run brain"));
    return 0;
  }
  const d = findDocker();
  const running = new Set();
  if (d) {
    const out = tryRun(d.cmd, [...d.pre, "ps", "--format", "{{.Label \"com.docker.compose.project\"}}"]).out;
    for (const name of out.split(/\r?\n/)) if (name.trim()) running.add(name.trim());
  }
  const here = brainEnv.brainId();
  console.log(C.b("Brain trên máy này:"));
  for (const brain of brains) {
    const mark = brain.id === here ? C.g(" ← project hiện tại") : "";
    const state = running.has(brain.id) ? C.g("đang chạy") : C.d("đã tắt  ");
    console.log(`  ${state}  ${brain.id.padEnd(34)} web ${brain.web} · api ${brain.api} · checklist ${brain.checklist}${mark}`);
  }
  console.log(C.d("\nMỗi brain là một compose project riêng: container, network và volume đều tách."));
  return 0;
}

function mcp() {
  const d = findDocker();
  const wsl = d && d.kind === "wsl";
  const cmd = wsl ? "wsl" : "docker";
  const args = wsl
    ? ["-e", "docker", "exec", "-i", `${brainEnv.brainId()}-api-1`, "python", "-m", "sag_api.mcp.server"]
    : ["exec", "-i", `${brainEnv.brainId()}-api-1`, "python", "-m", "sag_api.mcp.server"];
  console.log(C.b("Cấu hình MCP cho agent (stdio bridge)\n"));
  console.log(C.d("Claude Code:"));
  console.log(`  claude mcp add brain -- ${cmd} ${args.join(" ")}\n`);
  console.log(C.d("Codex (~/.codex/config.toml):"));
  console.log(`  [mcp_servers.brain]\n  command = "${cmd}"\n  args = ${JSON.stringify(args)}\n`);
  console.log(C.d(".mcp.json của project:"));
  console.log(JSON.stringify({ mcpServers: { brain: { command: cmd, args } } }, null, 2));
  console.log(C.y("\nGhi xong phải RESTART agent — agent không hot-reload MCP."));
  return 0;
}

async function doctor() {
  console.log(C.b("ALICE CODING — kiểm tra môi trường\n"));
  let blocking = 0;

  console.log(`[${OK}] Node ${process.version}`);

  const py = findPython();
  if (py) console.log(`[${OK}] Python ${py.version} (${[py.cmd, ...py.pre].join(" ")})`);
  else { console.log(`[${ERR}] Python — KHÔNG thấy. Cần 3.9+; verify/sync/update đều cần.`); blocking++; }

  const d = findDocker();
  if (d) console.log(`[${OK}] Docker ${d.version} — ${d.kind === "wsl" ? "Docker CE trong WSL" : "Desktop/native"}`);
  else {
    console.log(`[${ERR}] Docker — không thấy daemon nào đang chạy. Brain sẽ không dựng được.`);
    console.log(C.d("       (không có Docker vẫn dùng được chế độ file: brain = disabled)"));
    blocking++;
  }

  const cfg = fs.existsSync(path.join(ROOT, "brain", "brain.config"));
  console.log(`[${cfg ? OK : WARN}] brain.config ${cfg ? "đã có" : "chưa có — copy từ brain/brain.config.example khi cần sync"}`);

  const ready = await get("http://localhost:8000/api/v1/system/ready");
  if (ready && ready.status === 200) {
    console.log(`[${OK}] ALICE API sẵn sàng (localhost:8000)`);
    const cap = await get("http://localhost:8000/api/v1/system/capabilities");
    let llm = null;
    try { llm = JSON.parse(cap.body).llm_configured; } catch (_) {}
    if (llm === true) console.log(`[${OK}] LLM đã cấu hình — sẵn sàng ingest`);
    else if (llm === false) console.log(`[${WARN}] LLM CHƯA cấu hình → mở http://localhost:3000 → Settings → Models`);
    else console.log(`[${WARN}] Không đọc được /system/capabilities (API khác version?)`);
  } else {
    console.log(`[${WARN}] ALICE API chưa lên — chạy ${C.b("npm run brain")}`);
  }

  console.log(C.b("\nKho tri thức:"));
  const rc = python("tools/verify.py", []);
  if (rc !== 0) blocking++;

  console.log(C.b("\nLệnh gốc (nếu không muốn dùng npm):"));
  console.log(C.d(IS_WIN
    ? "  powershell -File brain\\stack\\brain-up.ps1\n  python tools\\verify.py\n  python brain\\sync\\sync.py"
    : "  bash brain/stack/brain-up.sh\n  python3 tools/verify.py\n  python3 brain/sync/sync.py"));

  console.log(blocking ? C.r(`\n${blocking} vấn đề chặn đường. Xử lý rồi chạy lại.`)
                       : C.g("\nMọi thứ ổn."));
  return blocking ? 1 : 0;
}

/* ------------------------------------------------------------------ main */

const [cmd, ...rest] = process.argv.slice(2);
(async () => {
  switch (cmd) {
    case "up":       process.exit(up());
    case "down":     process.exit(compose(["down"]));
    case "restart":  process.exit(compose(["restart"]));
    case "logs":     process.exit(compose(["logs", "-f", "--tail", "100", ...rest]));
    case "uninstall":process.exit(uninstall(rest));
    case "reset":    process.exit(reset(rest));
    case "status":   process.exit(await status());
    case "list":     process.exit(await list());
    case "pull":     process.exit(compose(["exec", "-T", "embedding", "ollama", "pull", "bge-m3"]));
    case "verify":   process.exit(python("tools/verify.py", rest));
    case "sync":     process.exit(python("brain/sync/sync.py", rest));
    case "update":   process.exit(python("tools/update.py", rest));
    case "mcp":      process.exit(mcp());
    case "doctor":   process.exit(await doctor());
    default:
      console.log(`Dùng: node tools/cli.js <lệnh>

  doctor    kiểm môi trường (Docker/Python/API/LLM/kho tri thức)
  up        dựng brain stack (tự chọn launcher đúng môi trường)
  down      tắt stack          restart   khởi động lại
  status    trạng thái brain của project này
  list      MỌI brain trên máy (id, cổng, đang chạy hay không)
  logs      xem log (-f)       pull      kéo lại model embedding
  uninstall gỡ Docker + runtime brain (GIỮ tri thức)      cần --yes
  reset     XOÁ tri thức project + kéo lại template mới   cần --yes
  verify    kiểm kho tri thức  sync      đồng bộ file -> não
  update    nâng cấp template  mcp       in cấu hình MCP cho agent

Qua npm: npm run doctor · npm run brain · npm run verify · npm run sync
Lệnh phá huỷ: npm run uninstall -- --yes   ·   npm run reset -- --yes`);
      process.exit(cmd ? 2 : 0);
  }
})();
