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
const OK = C.g("  OK  "), WARN = C.y(" NOTE "), ERR = C.r(" FAIL ");

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
    // Chỉ có tác dụng ở chế độ dev; chế độ image thì compose.yaml không dùng tới.
    ALICE_APP_PATH: abs(map.ALICE_APP_PATH, "alice-brain"),
    ALICE_CORE_PATH: abs(map.ALICE_CORE_PATH, "alice-core"),
    BRAIN_LOGS: path.join(ROOT, "brain", ".logs", "api"),
    SAG_SECRET_KEY: map.SAG_SECRET_KEY || "",
    BIND_ADDRESS: map.BIND_ADDRESS || (process.platform === "win32" ? "127.0.0.1" : ""),
    WEB_PORT: info.WEB_PORT,
    API_PORT: info.API_PORT,
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
    console.error(C.r("This project's brain has never been built."));
    console.error("Run this first: " + C.b("npm run brain"));
    return 1;
  }
  const d = findDocker();
  if (!d) { console.error(C.r("Docker not found.") + " Run `npm run doctor`."); return 1; }
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
    { p: dataDir, what: "legacy brain data (bind-mount, if any is left)" },
    { p: path.join(STACK, "alice-brain"), what: "application source cloned by the launcher" },
    { p: path.join(STACK, "alice-core"), what: "engine source cloned by the launcher" },
    { p: path.join(STACK, ".env"), what: "legacy stack config (if any is left)" },
    { p: path.join(STACK, ".env.moved"), what: "pointer to the new .env location" },
    { p: path.join(ROOT, "brain", "brain.config"), what: "sync config (holds a token)" },
    { p: path.join(ROOT, "brain", ".sync-state.json"), what: "sync file-to-document map" },
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

  console.log(C.b("Will remove:"));
  console.log("  - containers, network, volumes and images of brain " + C.b(brain.BRAIN_ID));
  console.log("  - dangling images left behind by earlier brain builds");
  console.log(keepCache
    ? C.d("  - build cache: KEPT (--keep-cache is set)")
    : "  - Docker build cache " + C.y("- shared MACHINE-WIDE, see the note below"));
  if (!targets.length) console.log(C.d("  - (no runtime files left on disk)"));
  for (const t of targets) {
    const outside = !insideRoot(t.p);
    console.log(`  - ${outside ? t.p : path.relative(ROOT, t.p)}  ${C.d("- " + t.what)}`
      + (outside ? C.y("  [OUTSIDE the project directory - WILL BE SKIPPED]") : ""));
  }
  console.log(C.g("\nKept: ") + "wiki/ | mistakes/ | decisions/ | context/ | changelog/ | ALICE.project.md");

  if (!keepCache) {
    console.log(C.d("\nDocker does not label build cache per project, so it cannot filter out just this"));
    console.log(C.d("brain's share - clearing it clears the whole machine. No data is lost; it only makes"));
    console.log(C.d("the next build of EVERY project slower. Keep it: npm run uninstall -- --yes --keep-cache"));
  }

  if (!yes) {
    console.log(C.y("\nThis CANNOT be undone (brain data has to be ingested again from scratch)."));
    console.log("If you are sure, run: " + C.b("npm run uninstall -- --yes"));
    return 2;
  }

  let failed = false;
  const d = findDocker();
  if (!d) {
    console.log(C.y("Docker not found - skipping containers, cleaning files only."));
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
      console.log(C.d(`Removing ${images.length} image(s) of this brain...`));
      run(d.cmd, [...d.pre, "rmi", "-f", ...images]);
    }

    // Image mồ côi: an toàn tuyệt đối — theo định nghĩa là không tag và không container nào dùng.
    run(d.cmd, [...d.pre, "image", "prune", "-f"]);

    // Build cache là phần NẶNG NHẤT (vài chục GB sau ít lần build) và là lý do "gỡ rồi mà đĩa
    // vẫn đầy". Docker không lọc cache theo project được nên đây là thao tác toàn máy — đã
    // cảnh báo ở trên, `--keep-cache` để từ chối.
    if (!keepCache) {
      console.log(C.d("Clearing the Docker build cache..."));
      run(d.cmd, [...d.pre, "builder", "prune", "-af"]);
    }
  }

  for (const t of targets) {
    // An toàn: không bao giờ xoá thứ nằm ngoài thư mục project.
    if (!insideRoot(t.p)) {
      console.log(C.y(`Skipping ${t.p} (outside the project) - delete it by hand if you want.`));
      continue;
    }
    try { fs.rmSync(t.p, { recursive: true, force: true, maxRetries: 3 }); }
    catch (err) {
      failed = true;
      console.error(C.r(`Could not delete ${path.relative(ROOT, t.p)}: ${err.message}`));
      console.error(C.d("  (Docker Desktop still holding the files? Try `npm run brain:down`, then retry.)"));
    }
  }

  console.log(failed ? C.r("\nRemoval incomplete - see the errors above.")
                     : C.g("\nDocker and runtime removed. Your knowledge base is untouched."));
  console.log(C.d("Rebuild: npm run brain   |   Also wipe knowledge: npm run reset -- --yes"));
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

  console.log(C.r(C.b("RESET - this PERMANENTLY DELETES the project knowledge base:\n")));
  if (!files.length) console.log(C.d("  (no knowledge files yet - the base is empty)"));
  for (const f of files) console.log("  - " + path.relative(ROOT, f).replace(/\\/g, "/"));
  console.log(C.d("\nThen `tools/update.py --ref main` pulls the newest template and recreates a blank skeleton."));

  if (!yes) {
    console.log(C.y("\nThere is no backup. If knowledge/ is committed you can still recover it with git;"));
    console.log(C.y("if it is not, the knowledge is gone for good."));
    console.log("If you are sure, run: " + C.b("npm run reset -- --yes"));
    return 2;
  }

  for (const f of files) {
    try { fs.rmSync(f, { force: true }); }
    catch (err) { console.error(C.r(`Could not delete ${path.relative(ROOT, f)}: ${err.message}`)); return 1; }
  }
  console.log(C.d(`Deleted ${files.length} file(s). Pulling the newest template...`));
  const rc = python("tools/update.py", ["--ref", "main"]);
  if (rc !== 0) {
    console.error(C.r("update.py failed - the base is empty. Run `npm run update` again once you are online."));
    return rc;
  }
  console.log(C.g("\nReset done. Run `npm run verify`, then INITIALIZATION to refill the knowledge base."));
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

/**
 * Giữ WSL không tự tắt — bằng cơ chế CHÍNH THỨC của WSL, không phải tiến trình canh.
 *
 * Đã thử giữ bằng một `wsl.exe sleep infinity` nền: nó chết ngay khi launcher thoát
 * (`pgrep` không thấy gì), và `uptime` trong distro luôn "up 0 min" → VM tắt/bật liên tục,
 * kéo theo Docker và brain. Vá bằng tiến trình canh là sai hướng.
 *
 * `vmIdleTimeout=-1` trong `%USERPROFILE%\.wslconfig` bảo WSL đừng tắt VM khi rảnh. Đây là
 * file cấu hình của người dùng nên chỉ THÊM khoá còn thiếu, không ghi đè cái đang có.
 * Có hiệu lực sau `wsl --shutdown` một lần.
 *
 * @returns {boolean} true nếu vừa sửa file (người dùng cần `wsl --shutdown`).
 */
function ensureWslNeverIdles() {
  const home = process.env.USERPROFILE;
  if (!home) return false;
  const file = path.join(home, ".wslconfig");
  let text = "";
  try { text = fs.readFileSync(file, "utf8"); } catch { /* chưa có thì tạo mới */ }
  if (/^\s*vmIdleTimeout\s*=/mi.test(text)) return false;

  const line = "vmIdleTimeout=-1";
  const NL = "\n";
  let next;
  if (/^\s*\[wsl2\]/mi.test(text)) {
    next = text.replace(/^[ \t]*\[wsl2\].*$/mi, (m) => m + NL + line);
  } else {
    const head = text.trim() ? text.trimEnd() + NL + NL : "";
    next = head + "[wsl2]" + NL + line + NL;
  }
  try {
    fs.writeFileSync(file, next);
    console.log(C.y(`Đã thêm ${line} vào ${file} — WSL sẽ không tự tắt VM nữa.`));
    return true;
  } catch (err) {
    console.log(C.y(`Không ghi được ${file} (${err.message}). Thêm tay: [wsl2] / ${line}`));
    return false;
  }
}

function up() {
  const d = findDocker();
  if (!d) {
    console.error(C.r("No running Docker daemon found."));
    console.error("  - Docker Desktop: open the app, wait for the green icon, then retry.");
    if (IS_WIN) console.error("  - Docker CE inside WSL: open a WSL terminal, `sudo service docker start`.");
    return 1;
  }
  console.log(C.d(`Docker: ${d.kind} (server ${d.version})`));
  if (IS_WIN && d.kind === "native") {
    console.log(C.d("→ brain-up.ps1 (Windows + Docker Desktop)"));
    return run("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass",
                              "-File", path.join(STACK, "brain-up.ps1")]);
  }
  if (IS_WIN && d.kind === "wsl") {
    // Docker nằm TRONG distro, nên launcher chạy trong đó luôn — và mọi thứ nó cần
    // (Node, đường dẫn) phải là của Linux, không phải của Windows. Node trên Windows
    // KHÔNG dùng được ở đây; đó là lý do phải dò riêng thay vì để script tự chết.
    // Không chặn ở đây: `brain-up.sh` tự cài Node vào $HOME của distro khi thiếu. Chỉ báo
    // trước để người dùng biết vì sao lần chạy đầu lâu hơn.
    // Node do launcher cài nằm ở $HOME/.local/alice-node/bin — shell không-login của
    // `wsl -e` không có nó trong PATH, nên phải hỏi qua đúng PATH đó, kẻo lần nào cũng báo
    // "chưa có" dù đã cài.
    const nodeProbe = tryRun("wsl", ["-e", "bash", "-c",
      'PATH="$HOME/.local/alice-node/bin:$PATH" node --version']);
    if (!nodeProbe.ok) {
      console.log(C.y("Node chưa có trong WSL — launcher sẽ tự cài (không cần sudo)."));
    }
    console.log(C.d("→ brain-up.sh inside WSL (Docker CE)"));
    const needsShutdown = ensureWslNeverIdles();
    const code = run("wsl", ["-e", "bash", "brain/stack/brain-up.sh"]);
    if (code === 0 && needsShutdown) {
      console.log(C.y("\nCấu hình WSL vừa đổi. Chạy MỘT lần rồi dựng lại thì brain mới thôi tự chết:"));
      console.log(C.b("  wsl --shutdown"));
      console.log(C.b("  npm run brain"));
    }
    return code;
  }
  console.log(C.d("→ brain-up.sh"));
  return run("bash", [path.join(STACK, "brain-up.sh")]);
}

function python(scriptRel, args) {
  const py = findPython();
  if (!py) {
    console.error(C.r("Python not found.") + " Python 3.9+ is required (https://python.org).");
    return 1;
  }
  return run(py.cmd, [...py.pre, path.join(ROOT, scriptRel), ...args]);
}

async function status() {
  const d = findDocker();
  const info = brainEnv.peek();
  console.log(C.b("Brain for this project:"));
  console.log(`  ${info.BRAIN_ID}` + (info.exists ? "" : C.y("  [never built]")));
  console.log(C.d(`  mode: ${info.BRAIN_MODE === "dev" ? "dev - built from local sources" : "published image"}`));
  console.log(C.b("\nContainer:"));
  if (d) run(d.cmd, [...d.pre, "ps", "--filter",
                     `label=com.docker.compose.project=${info.BRAIN_ID}`,
                     "--format", "  {{.Names}}\t{{.Status}}"]);
  else console.log(C.r("  Docker not found."));
  console.log(C.b("\nServices:"));
  const probes = [
    ["API", `http://localhost:${info.API_PORT}`, "/api/v1/system/ready"],
    ["Web", `http://localhost:${info.WEB_PORT}`, ""],
  ];
  for (const [label, base, probe] of probes) {
    const res = await get(base + probe);
    const up = probe ? res && res.status === 200 : Boolean(res);
    console.log(`  ${label} ${base}  ${up ? C.g("ready") : C.r("down")}`);
  }
  return 0;
}

/** Mọi brain trên máy này — để biết project nào đang chiếm cổng nào, và cái nào còn chạy. */
async function list() {
  const brains = brainEnv.listBrains();
  if (!brains.length) {
    console.log(C.y("No brain on this machine yet.") + " Build one: " + C.b("npm run brain"));
    return 0;
  }
  const d = findDocker();
  const running = new Set();
  if (d) {
    const out = tryRun(d.cmd, [...d.pre, "ps", "--format", "{{.Label \"com.docker.compose.project\"}}"]).out;
    for (const name of out.split(/\r?\n/)) if (name.trim()) running.add(name.trim());
  }
  const here = brainEnv.brainId();
  console.log(C.b("Brains on this machine:"));
  for (const brain of brains) {
    const mark = brain.id === here ? C.g(" <- current project") : "";
    const state = running.has(brain.id) ? C.g("running") : C.d("stopped");
    console.log(`  ${state}  ${brain.id.padEnd(34)} web ${brain.web} | api ${brain.api}${mark}`);
  }
  console.log(C.d("\nEach brain is its own compose project: containers, network and volumes are all separate."));
  return 0;
}

function mcp() {
  const d = findDocker();
  const wsl = d && d.kind === "wsl";
  const cmd = wsl ? "wsl" : "docker";
  const args = wsl
    ? ["-e", "docker", "exec", "-i", `${brainEnv.brainId()}-api-1`, "python", "-m", "sag_api.mcp.server"]
    : ["exec", "-i", `${brainEnv.brainId()}-api-1`, "python", "-m", "sag_api.mcp.server"];
  console.log(C.b("MCP configuration for your agent (stdio bridge)\n"));
  console.log(C.d("Claude Code:"));
  console.log(`  claude mcp add brain -- ${cmd} ${args.join(" ")}\n`);
  console.log(C.d("Codex (~/.codex/config.toml):"));
  console.log(`  [mcp_servers.brain]\n  command = "${cmd}"\n  args = ${JSON.stringify(args)}\n`);
  console.log(C.d("Project .mcp.json:"));
  console.log(JSON.stringify({ mcpServers: { brain: { command: cmd, args } } }, null, 2));
  console.log(C.y("\nRESTART the agent after saving - agents do not hot-reload MCP."));
  return 0;
}

async function doctor() {
  console.log(C.b("ALICE CODING - environment check\n"));
  let blocking = 0;

  console.log(`[${OK}] Node ${process.version}`);

  const py = findPython();
  if (py) console.log(`[${OK}] Python ${py.version} (${[py.cmd, ...py.pre].join(" ")})`);
  else { console.log(`[${ERR}] Python - NOT found. 3.9+ is required by verify/sync/update.`); blocking++; }

  const d = findDocker();
  if (d) console.log(`[${OK}] Docker ${d.version} - ${d.kind === "wsl" ? "Docker CE inside WSL" : "Desktop/native"}`);
  else {
    console.log(`[${ERR}] Docker - no running daemon. The brain cannot be built.`);
    console.log(C.d("       (without Docker you can still work in file mode: brain = disabled)"));
    blocking++;
  }

  const cfg = fs.existsSync(path.join(ROOT, "brain", "brain.config"));
  console.log(`[${cfg ? OK : WARN}] brain.config ${cfg ? "present" : "missing - copy brain/brain.config.example when you need sync"}`);

  const ready = await get("http://localhost:8000/api/v1/system/ready");
  if (ready && ready.status === 200) {
    console.log(`[${OK}] ALICE API ready (localhost:8000)`);
    const cap = await get("http://localhost:8000/api/v1/system/capabilities");
    let llm = null;
    try { llm = JSON.parse(cap.body).llm_configured; } catch (_) {}
    if (llm === true) console.log(`[${OK}] LLM configured - ready to ingest`);
    else if (llm === false) console.log(`[${WARN}] LLM NOT configured - open http://localhost:3000 -> Settings -> Models`);
    else console.log(`[${WARN}] Could not read /system/capabilities (API version mismatch?)`);
  } else {
    console.log(`[${WARN}] ALICE API is down - run ${C.b("npm run brain")}`);
  }

  console.log(C.b("\nKnowledge base:"));
  const rc = python("tools/verify.py", []);
  if (rc !== 0) blocking++;

  // Khối "lệnh gốc" của bản cũ đã bỏ: từ 2.3.0 Node là bắt buộc (cả hai launcher gọi
  // brain-env.js), nên nhánh "không dùng npm" không còn tồn tại trên thực tế. In nó ra chỉ
  // mời người dùng đi đường đã hỏng.
  console.log(C.d("\nEverything runs through npm: npm run brain | verify | sync | update"));

  console.log(blocking ? C.r(`\n${blocking} blocking issue(s). Fix them and run again.`)
                       : C.g("\nAll good."));
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
      console.log(`Usage: node tools/cli.js <command>

  doctor    check the environment (Docker/Python/API/LLM/knowledge base)
  up        build and start the brain stack (picks the right launcher)
  down      stop the stack     restart   restart it
  status    status of this project's brain
  list      EVERY brain on this machine (id, ports, running or not)
  logs      tail the log (-f)  pull      re-pull the embedding model
  uninstall remove Docker + brain runtime (KEEPS knowledge)   needs --yes
  reset     DELETE project knowledge + pull a fresh template  needs --yes
  verify    check the knowledge base   sync    push files into the brain
  update    upgrade the template       mcp     print the MCP config for your agent

Via npm: npm run doctor | npm run brain | npm run verify | npm run sync
Destructive: npm run uninstall -- --yes   |   npm run reset -- --yes`);
      process.exit(cmd ? 2 : 0);
  }
})();
