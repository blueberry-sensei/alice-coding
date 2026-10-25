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

/**
 * Distro nội bộ của Docker Desktop. Nó KHÔNG phải nơi chạy launcher: rootfs tối giản
 * (có thể không có bash), và ổ Windows được mount ở `/mnt/host/<drive>` chứ không phải
 * `/mnt/<drive>`. Docker Desktop cũng nói thẳng là không hỗ trợ gọi CLI từ đó.
 */
const WSL_INTERNAL_DISTROS = new Set(["docker-desktop", "docker-desktop-data"]);

function wslDistroName() {
  const r = tryRun("wsl", ["-e", "sh", "-c", "printf %s \"$WSL_DISTRO_NAME\""]);
  return r.ok ? r.out.trim() : "";
}

/** Docker Desktop/native trước; Windows thì thử tiếp Docker CE trong WSL. */
function findDocker() {
  const native = tryRun("docker", ["version", "--format", "{{.Server.Version}}"]);
  if (native.ok) return { kind: "native", cmd: "docker", pre: [], version: native.out };
  if (IS_WIN && !WSL_INTERNAL_DISTROS.has(wslDistroName())) {
    const wsl = tryRun("wsl", ["-e", "docker", "version", "--format", "{{.Server.Version}}"]);
    if (wsl.ok) return { kind: "wsl", cmd: "wsl", pre: ["-e", "docker"], version: wsl.out };
  }
  return null;
}

/**
 * Đường dẫn của project NHÌN TỪ TRONG distro.
 *
 * `wsl.exe` chỉ mang cwd Windows sang distro khi thư mục đó thật sự tồn tại ở đó. Distro
 * tắt `[automount]`, đổi `[automount] root`, hay chỉ mount ổ ở đường dẫn khác đều làm cwd
 * rơi về `/` hoặc `$HOME`. Lúc đó mọi đường dẫn TƯƠNG ĐỐI truyền vào WSL đều trỏ sai và
 * bash chỉ nói `No such file or directory` — không hề nói vì sao, nên người dùng đi tìm
 * file trong repo (nó vẫn ở đó) thay vì đi xem mount của distro.
 *
 * Vì vậy: dịch sang đường dẫn tuyệt đối của distro và kiểm tra nó tồn tại TRƯỚC khi chạy.
 * @returns {string|null} đường dẫn POSIX của ROOT trong distro, null nếu distro không thấy.
 */
let wslRootCache;
function wslRoot() {
  if (wslRootCache !== undefined) return wslRootCache;
  const candidates = [];
  // `wslpath` là câu trả lời chính thức của distro, nhưng không phải lúc nào cũng dùng được:
  // distro nội bộ của Docker Desktop trả một đường dẫn chỉ có nghĩa bên trong engine.
  const probe = tryRun("wsl", ["-e", "wslpath", "-a", ROOT]);
  if (probe.ok && probe.out) candidates.push(probe.out.split(/\r?\n/)[0].trim());
  const drive = /^([A-Za-z]):[\\/](.*)$/.exec(ROOT);
  if (drive) candidates.push(`/mnt/${drive[1].toLowerCase()}/${drive[2].replace(/\\/g, "/")}`);
  for (const candidate of candidates) {
    if (!candidate) continue;
    const seen = tryRun("wsl", ["-e", "sh", "-c", '[ -d "$1" ]', "alice-probe", candidate]);
    if (seen.ok) return (wslRootCache = candidate);
  }
  return (wslRootCache = null);
}

function wslRootMissing() {
  console.error(C.r("This project folder is not visible from inside WSL."));
  console.error(`  Windows path : ${ROOT}`);
  console.error("  Docker runs inside the WSL distro, so the launcher has to run there too -");
  console.error("  and the distro cannot reach this folder.");
  console.error("  Open a WSL terminal and check that the drive is mounted:");
  console.error(C.b("    ls /mnt"));
  console.error("  If the drive is missing, enable automount in /etc/wsl.conf, then `wsl --shutdown`:");
  console.error(C.b("    [automount]\n    enabled = true\n    root = /mnt/"));
  console.error("  Or move the project onto a drive the distro can see.");
  return 1;
}

const brainEnv = require(path.join(STACK, "brain-env.js"));

/**
 * Docker CE nằm trong WSL thì state + BRAIN_ID cũng phải được đọc trong WSL.
 * `up` vốn đã chạy brain-up.sh trong distro; các lệnh quản trị phải đi cùng runtime,
 * nếu không D:\project và /mnt/d/project sinh hai hash + hai state root khác nhau.
 */
const WSL_DELEGATED_COMMANDS = new Set([
  "down", "restart", "logs", "status", "list", "pull", "uninstall",
  "embedding", "embedding-down", "embedding-reclaim", "embedding-purge",
]);

function runSelfInWsl(args) {
  const root = wslRoot();
  if (!root) return wslRootMissing();
  return run("wsl", [
    "-e", "bash", "-c",
    'cd "$1" || exit 1; shift; PATH="$HOME/.local/alice-node/bin:$PATH"; exec node tools/cli.js "$@"',
    "alice-cli", root, ...args,
  ]);
}

function peekBrainInWsl() {
  const root = wslRoot();
  if (!root) return null;
  const r = tryRun("wsl", [
    "-e", "bash", "-c",
    'PATH="$HOME/.local/alice-node/bin:$PATH"; exec node "$1/brain/stack/brain-env.js" --peek-json',
    "alice-peek", root,
  ]);
  if (!r.ok) return null;
  try { return JSON.parse(r.out); } catch { return null; }
}

function runtimeBrainInfo(d = findDocker()) {
  if (IS_WIN && d && d.kind === "wsl") {
    const info = peekBrainInWsl();
    if (info) return info;
  }
  return brainEnv.peek();
}

function readWslConfig() {
  const home = process.env.USERPROFILE;
  if (!home) return { file: "", text: "" };
  const file = path.join(home, ".wslconfig");
  try { return { file, text: fs.readFileSync(file, "utf8").replace(/^\uFEFF/, "") }; }
  catch { return { file, text: "" }; }
}

function iniValue(text, section, key) {
  let current = "";
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    const header = line.match(/^\[([^\]]+)\]$/);
    if (header) {
      current = header[1].trim().toLowerCase();
      continue;
    }
    if (current !== section.toLowerCase() || line.startsWith("#") || line.startsWith(";")) continue;
    const eq = line.indexOf("=");
    if (eq < 1 || line.slice(0, eq).trim().toLowerCase() !== key.toLowerCase()) continue;
    return line.slice(eq + 1).trim();
  }
  return "";
}

/** Thêm setting còn thiếu vào đúng section, không ghi đè lựa chọn có chủ đích của người dùng. */
function addIniSetting(text, section, key, value) {
  const lines = text ? text.replace(/\r\n/g, "\n").split("\n") : [];
  let start = -1;
  let end = lines.length;
  for (let i = 0; i < lines.length; i += 1) {
    const header = lines[i].trim().match(/^\[([^\]]+)\]$/);
    if (!header) continue;
    if (start >= 0) {
      end = i;
      break;
    }
    if (header[1].trim().toLowerCase() === section.toLowerCase()) start = i;
  }
  if (start >= 0) {
    while (end > start + 1 && !lines[end - 1].trim()) end -= 1;
    for (let i = start + 1; i < end; i += 1) {
      const line = lines[i].trim();
      if (line.startsWith("#") || line.startsWith(";")) continue;
      const eq = line.indexOf("=");
      if (eq > 0 && line.slice(0, eq).trim().toLowerCase() === key.toLowerCase()) {
        return { text, changed: false };
      }
    }
    lines.splice(end, 0, `${key}=${value}`);
  } else {
    if (lines.length && lines[lines.length - 1].trim()) lines.push("");
    lines.push(`[${section}]`, `${key}=${value}`);
  }
  return { text: `${lines.join("\n").replace(/\n+$/, "")}\n`, changed: true };
}

function wslNetworkMode() {
  const { text } = readWslConfig();
  return (iniValue(text, "wsl2", "networkingMode") || "nat").toLowerCase();
}

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
  // Suy lại mỗi lần chạy từ ALICE_EMBEDDING_MODE, không đọc giá trị đã lưu: hai biến này là
  // HỆ QUẢ của chế độ, lưu chúng lại là mời gọi một .env cũ mâu thuẫn với compose file đang dùng.
  const embedding = brainEnv.embeddingMode(map);
  return {
    ...process.env,
    ...brainEnv.embeddingVars(embedding, map),
    ALICE_EMBEDDING_MODE: embedding,
    // Chỉ có tác dụng ở chế độ dev; chế độ image thì compose.yaml không dùng tới.
    ALICE_APP_PATH: abs(map.ALICE_APP_PATH, "alice-brain"),
    ALICE_CORE_PATH: abs(map.ALICE_CORE_PATH, "alice-core"),
    BRAIN_LOGS: path.join(ROOT, "brain", ".logs", "api"),
    SAG_SECRET_KEY: map.SAG_SECRET_KEY || "",
    BIND_ADDRESS: map.BIND_ADDRESS || (process.platform === "win32" ? "127.0.0.1" : ""),
    WEB_PORT: info.WEB_PORT,
    API_PORT: info.API_PORT,
    BRAIN_HOST: info.BRAIN_HOST,
    // compose.dev.yaml nội suy ${BRAIN_ID} vào tag image. Thiếu biến này thì `down`/`uninstall`
    // ở chế độ dev nhìn ra tag rỗng và KHÔNG xoá được image vừa build.
    BRAIN_ID: info.BRAIN_ID,
    _BRAIN_ID: info.BRAIN_ID,
    _ENV_FILE: info.BRAIN_ENV_FILE,
    _MODE: info.BRAIN_MODE,
    _EMBEDDING: embedding,
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
    [...d.pre, "compose", "-p", env._BRAIN_ID, ...brainEnv.composeFiles(env._MODE, env._EMBEDDING),
     "--env-file", env._ENV_FILE, ...args],
    { cwd: STACK, env });
}

/** Model embedding của brain này (đọc .env thật; mặc định bge-m3). */
function embeddingModel() {
  const info = brainEnv.peek();
  if (!info.exists) return "bge-m3";
  try {
    for (const line of fs.readFileSync(info.BRAIN_ENV_FILE, "utf8").split(/\r?\n/)) {
      const m = /^\s*SAG_EMBEDDING_MODEL\s*=\s*(.+?)\s*$/.exec(line);
      if (m) return m[1];
    }
  } catch { /* .env không đọc được thì dùng mặc định */ }
  return "bge-m3";
}

/** Chế độ embedding của brain này: "external" | "shared" (mặc định) | "project". */
function embeddingModeHere() {
  const env = composeEnv();
  return env ? env._EMBEDDING : "shared";
}

/** Endpoint embedding người dùng tự khai trong .env của brain (chế độ external). */
function externalEmbeddingUrl() {
  const info = brainEnv.peek();
  if (!info.exists) return "";
  try {
    for (const line of fs.readFileSync(info.BRAIN_ENV_FILE, "utf8").split(/\r?\n/)) {
      const m = /^\s*SAG_EMBEDDING_BASE_URL\s*=\s*(.+?)\s*$/.exec(line);
      if (m) return m[1];
    }
  } catch { /* .env không đọc được thì thôi */ }
  return "";
}

/** `docker compose` trên stack embedding dùng chung toàn máy. */
function hub(args) {
  const d = findDocker();
  if (!d) { console.error(C.r("Docker not found.") + " Run `npm run doctor`."); return 1; }
  return run(d.cmd, [...d.pre, ...brainEnv.hubComposeArgs(), ...args], { cwd: STACK });
}

/** Tải model về đúng nơi đang phục vụ brain này. */
function pull() {
  const model = embeddingModel();
  const mode = embeddingModeHere();
  if (mode === "external") {
    console.log(C.y("Nothing to pull: this brain uses your own embedding endpoint."));
    console.log(C.d("  ALICE does not run or download any model in this mode - that is the point."));
    console.log(C.d("  Endpoint: " + (externalEmbeddingUrl() || "SAG_EMBEDDING_BASE_URL in the brain .env")));
    return 0;
  }
  if (mode === "shared") {
    console.log(C.d(`Pulling ${model} into the shared embedding container (once per machine)...`));
    return hub(["exec", "-T", "embedding", "ollama", "pull", model]);
  }
  console.log(C.d(`Pulling ${model} into this project's embedding container...`));
  return compose(["exec", "-T", "embedding", "ollama", "pull", model]);
}

/**
 * Trạng thái embedding dùng chung + brain nào đang gắn vào nó.
 *
 * Cần một lệnh riêng vì stack này KHÔNG thuộc brain nào: `brain:status` của một project không
 * nói được gì về một container mà mọi project cùng dùng.
 */
async function embedding() {
  const d = findDocker();
  const mode = embeddingModeHere();
  console.log(C.b("Embedding for this project:"));
  const label = {
    external: C.g("external") + C.d(" - your own endpoint; ALICE runs and downloads nothing"),
    shared: C.g("shared") + C.d(" - one Ollama container for the whole machine"),
    project: C.y("project") + C.d(" - a private Ollama container for this brain"),
  };
  console.log(`  mode: ${label[mode] || label.shared}`);
  if (mode === "external") {
    console.log(`  endpoint: ${externalEmbeddingUrl() || C.y("SAG_EMBEDDING_BASE_URL (unreadable)")}`);
    console.log(C.d("\n  No Ollama container is started and no model is downloaded in this mode."));
    console.log(C.d("  Want ALICE to run one instead? Remove SAG_EMBEDDING_BASE_URL from"));
    console.log(C.d(`    ${brainEnv.peek().BRAIN_ENV_FILE}`));
    console.log(C.d("  then: npm run brain"));
    console.log(C.y("\n  Note: an embedding endpoint saved in Settings -> Models overrides the .env value"));
    console.log(C.y("  for the API, but the launcher only reads .env. Keep the two in agreement."));
    return 0;
  }
  if (mode !== "shared") {
    console.log(C.d("\n  Switch to the shared container (frees ~1.2 GB per extra project):"));
    console.log(C.d(`    remove ALICE_EMBEDDING_MODE=project from ${brainEnv.peek().BRAIN_ENV_FILE}`));
    console.log(C.d("    then: npm run brain"));
    return 0;
  }
  // Chế độ ở trên đọc từ `.env`; cái đang THỰC SỰ chạy có thể khác vì cấu hình lưu trong app
  // ghi đè. Nói ra chênh lệch đó, đừng để người dùng tự đoán.
  const info = brainEnv.peek();
  if (info.exists && (await usesBundledEmbedding(info.API_PORT)) === false && mode !== "external") {
    console.log(C.y("\n  In effect: this brain uses an endpoint saved in the app, NOT this container."));
    console.log(C.d("  The container is running for nothing. Reclaim it: ") + C.b("npm run embedding:reclaim"));
  }
  if (!d) { console.log(C.r("\n  Docker not found.")); return 1; }
  console.log(C.b("\nShared container:"));
  const ps = tryRun(d.cmd, [...d.pre, "ps", "-a", "--filter",
    `label=com.docker.compose.project=${brainEnv.EMBEDDING_HUB_PROJECT}`,
    "--format", "  {{.Names}}\t{{.Status}}"]).out;
  if (!ps.trim()) {
    console.log(C.y("  not built yet") + C.d(" - it comes up with `npm run brain`"));
    return 0;
  }
  console.log(ps);
  // `docker exec` KHÔNG có cờ `-T` (đó là cờ của `docker compose exec`) — thêm vào là exec
  // hỏng và cột model luôn rỗng.
  const models = tryRun(d.cmd, [...d.pre, "exec", brainEnv.EMBEDDING_HUB_CONTAINER,
    "ollama", "list"]);
  console.log(C.b("\nModels (shared by every project on this machine):"));
  console.log(models.ok ? models.out.split(/\r?\n/).map((l) => "  " + l).join("\n")
                        : C.y("  could not read the model list (container still starting?)"));
  console.log(C.b("\nBrains attached:"));
  const attached = tryRun(d.cmd, [...d.pre, "network", "inspect", brainEnv.EMBEDDING_HUB_PROJECT,
    "--format", "{{range .Containers}}{{println .Name}}{{end}}"]).out
    .split(/\r?\n/)
    .map((name) => name.trim())
    // Bỏ chính container embedding: nó luôn ở đó, liệt kê nó ra chỉ làm nhiễu câu hỏi thật
    // ("còn brain nào đang dùng cái này không, tắt có ai chết không").
    .filter((name) => name && name !== brainEnv.EMBEDDING_HUB_CONTAINER);
  console.log(attached.length ? attached.map((name) => "  " + name).join("\n")
                              : C.d("  (no brain is running right now)"));
  return 0;
}

/**
 * Đánh dấu "chế độ external là do ALICE tự đặt, không phải người dùng chọn".
 *
 * Cần phân biệt vì chỉ thứ ALICE tự đặt mới được ALICE tự gỡ. Người dùng khai
 * `ALICE_EMBEDDING_MODE=project`/`external` bằng tay thì đó là quyết định của họ.
 */
const AUTO_EXTERNAL_KEY = "ALICE_EMBEDDING_MODE_SET_BY_ALICE";

function autoExternal() {
  const info = brainEnv.peek();
  if (!info.exists) return false;
  try {
    return fs.readFileSync(info.BRAIN_ENV_FILE, "utf8")
      .split(/\r?\n/)
      .some((line) => new RegExp(`^\\s*${AUTO_EXTERNAL_KEY}\\s*=\\s*1\\s*$`).test(line));
  } catch {
    return false;
  }
}

/** Ghi/xoá một khoá trong .env của brain, giữ nguyên mọi dòng khác. */
function setBrainEnvValue(key, value) {
  const info = brainEnv.peek();
  if (!info.exists) return false;
  let lines;
  try {
    lines = fs.readFileSync(info.BRAIN_ENV_FILE, "utf8").split(/\r?\n/);
  } catch {
    return false;
  }
  const re = new RegExp(`^\\s*${key}\\s*=`);
  const next = lines.filter((line) => !re.test(line));
  // Bỏ dòng trống ở cuối trước khi ghi thêm, kẻo mỗi lần chạy lại nhét thêm một dòng trắng.
  while (next.length && !next[next.length - 1].trim()) next.pop();
  if (value !== null) next.push(`${key}=${value}`);
  try {
    fs.writeFileSync(info.BRAIN_ENV_FILE, `${next.join("\n")}\n`, { mode: 0o600 });
    return true;
  } catch {
    return false;
  }
}

/** Cờ `embedding_uses_bundled_container` của một brain đang chạy; null nếu không hỏi được. */
async function usesBundledEmbedding(apiPort) {
  const res = await get(`http://localhost:${apiPort}/api/v1/system/capabilities`, 3000);
  if (!res || res.status !== 200) return null;
  try {
    const body = JSON.parse(res.body);
    // Field chỉ có từ 2.4.16. Brain cũ trả undefined -> coi như "không biết" và KHÔNG đụng gì.
    const flag = body.embedding_uses_bundled_container;
    return typeof flag === "boolean" ? flag : null;
  } catch {
    return null;
  }
}

/**
 * Thu hồi container embedding không còn ai dùng.
 *
 * Vì sao cần: endpoint embedding có thể được đổi trong app (Settings → Models, hoặc import config),
 * mà launcher chỉ đọc `.env`. Không có bước này thì đổi sang API riêng xong, container Ollama vẫn
 * chạy và model 1,2 GB vẫn nằm đó — chạy không công, đúng thứ phải tránh.
 *
 * Hai ràng buộc an toàn:
 * - chỉ tắt embedding DÙNG CHUNG khi **không brain nào khác** còn dùng nó;
 * - chỉ `stop`, không `down -v`: network vẫn còn cho brain đang gắn, model đã tải không bị xoá.
 */
async function reconcileEmbedding(info) {
  const mode = embeddingModeHere();
  const usesBundled = await usesBundledEmbedding(info.API_PORT);
  if (usesBundled === null) {
    // Không kết luận được. Trước đây return im lặng — và đó chính là cách một brain đã trỏ
    // embedding ra ngoài vẫn bị dựng Ollama + tải 1,2 GB ở MỌI lần chạy mà không ai biết vì sao.
    // Im lặng ở đây là bỏ mất tín hiệu duy nhất người dùng có.
    if (mode !== "external") {
      console.log(C.y("\nCould not tell which embedding endpoint this brain actually uses"));
      console.log(C.d("  (/system/capabilities did not answer, or this image predates 2.4.16)."));
      console.log(C.d("  If it points somewhere else, the container ALICE just started is idle."));
      console.log(C.d("  Check: ") + C.b("npm run embedding"));
    }
    return;
  }

  // ── Chiều 2: brain CẦN container nhưng ta đang ở external do tự ghi trước đó ──
  // Xảy ra khi người dùng bỏ endpoint riêng trong app. Không có nhánh này thì brain kẹt ở
  // external mà không còn embedding nào, và lỗi chỉ lộ ra lúc ingest.
  if (usesBundled === true) {
    if (mode === "external" && autoExternal()) {
      setBrainEnvValue("ALICE_EMBEDDING_MODE", null);
      setBrainEnvValue(AUTO_EXTERNAL_KEY, null);
      console.log(C.y("\nThis brain needs the bundled embedding container again"));
      console.log(C.y("(the endpoint saved in the app is gone). Run `npm run brain` once more."));
    }
    return;
  }

  // ── Chiều 1: container đang chạy không công ──
  if (mode === "external") return;   // đã ở external, không có gì để thu hồi
  console.log(C.y("\nThis brain's saved configuration points embedding somewhere else,"));
  console.log(C.y("so the embedding container ALICE started for it is doing nothing."));

  // Ghi lại vào .env để lần chạy sau KHÔNG dựng lên nữa, thay vì bật rồi tắt mỗi lượt.
  // Đánh dấu là do ALICE tự đặt, để còn tự gỡ được; lựa chọn của người dùng thì không đụng.
  if (setBrainEnvValue("ALICE_EMBEDDING_MODE", "external")) {
    setBrainEnvValue(AUTO_EXTERNAL_KEY, "1");
    console.log(C.d("  It will not be started again while the app points somewhere else."));
  }

  const d = findDocker();
  if (!d) return;

  if (mode === "project") {
    compose(["rm", "-sf", "embedding"]);
    console.log(C.g("  Stopped and removed this project's embedding container."));
    return;
  }

  // Chế độ shared: container là của CẢ MÁY. Hỏi từng brain khác trước khi đụng vào.
  const others = brainEnv.listBrains().filter((brain) => brain.id !== info.BRAIN_ID);
  for (const brain of others) {
    if (await usesBundledEmbedding(brain.api) === true) {
      console.log(C.d(`  Keeping the shared container: ${brain.id} still uses it.`));
      return;
    }
  }
  const running = tryRun(d.cmd, [...d.pre, "ps", "-q", "--filter",
    `label=com.docker.compose.project=${brainEnv.EMBEDDING_HUB_PROJECT}`]).out.trim();
  if (!running) return;
  if (hub(["stop"]) === 0) {
    console.log(C.g("  Stopped the shared embedding container - no brain on this machine needs it."));
    console.log(C.d("  Downloaded models were kept; it starts again by itself when a brain needs one."));
    console.log(C.d("  Reclaim that disk space too: npm run embedding:purge:yes"));
  }
}

/** Tắt embedding dùng chung — ảnh hưởng MỌI project trên máy, nên phải nói rõ. */
function embeddingDown(argv) {
  const yes = argv.includes("--yes") || argv.includes("-y");
  console.log(C.y("This stops the embedding container shared by EVERY project on this machine."));
  console.log(C.d("Any brain that is still running loses its ability to create vectors:"));
  console.log(C.d("ingest and search will fail (loudly) until it is back."));
  if (!yes) {
    console.log("If you are sure, run: " + C.b("npm run embedding:down:yes"));
    return 2;
  }
  // Chỉ `down`, KHÔNG `--volumes`: xoá volume là xoá model đã tải cho cả máy, lần bật lại phải
  // kéo về từ đầu. Xoá model là một quyết định riêng, không phải hệ quả phụ của việc tắt.
  const rc = hub(["down"]);
  if (rc === 0) console.log(C.g("Shared embedding stopped. Downloaded models were kept."));
  return rc;
}

/**
 * Xoá model embedding đã tải để lấy lại dung lượng đĩa.
 *
 * Gồm cả volume dùng chung `alice-embedding-models` lẫn volume `<BRAIN_ID>_ollama` còn sót lại
 * từ thời mỗi project một Ollama — mỗi cái ~1,2 GB và không còn ai dùng sau khi chuyển sang
 * embedding dùng chung.
 *
 * Docker tự từ chối xoá volume đang được container dùng, nên volume của brain đang chạy không
 * thể bị xoá nhầm; ở đây chỉ báo lại và bỏ qua.
 */
function embeddingPurge(argv) {
  const yes = argv.includes("--yes") || argv.includes("-y");
  const d = findDocker();
  if (!d) { console.error(C.r("Docker not found.") + " Run `npm run doctor`."); return 1; }

  const volumes = tryRun(d.cmd, [...d.pre, "volume", "ls", "-q"]).out
    .split(/\r?\n/)
    .map((name) => name.trim())
    .filter((name) => name === "alice-embedding-models" || /_ollama$/.test(name));

  if (!volumes.length) {
    console.log(C.g("No downloaded embedding model is taking up space."));
    return 0;
  }

  console.log(C.b("Will delete these downloaded embedding models:"));
  for (const name of volumes) console.log(`  - ${name}  ${C.d("~1.2 GB")}`);
  console.log(C.d("\nOnly the downloaded model files. No knowledge, no brain data is touched."));
  console.log(C.y("Any brain that still needs one downloads it again on the next `npm run brain`."));

  if (!yes) {
    console.log("If you are sure, run: " + C.b("npm run embedding:purge:yes"));
    return 2;
  }

  let removed = 0;
  let inUse = 0;
  for (const name of volumes) {
    const r = tryRun(d.cmd, [...d.pre, "volume", "rm", name]);
    if (r.ok) {
      removed += 1;
      continue;
    }
    // Đang có container dùng -> Docker từ chối. Đó là lưới an toàn, không phải lỗi.
    inUse += 1;
    console.log(C.y(`  kept ${name}`) + C.d(" - a running container still uses it"));
  }
  console.log(C.g(`\nDeleted ${removed} model volume(s).`)
    + (inUse ? C.d(` ${inUse} kept because they are in use.`) : ""));
  if (inUse) console.log(C.d("Stop those brains (npm run brain:down) and run this again to reclaim them."));
  return 0;
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
  if (embeddingModeHere() === "shared") {
    console.log(C.g("Kept: ") + "the machine-wide embedding container and its downloaded models"
      + C.d(" - other projects use it (npm run embedding:down:yes to stop it)"));
  }

  if (!keepCache) {
    console.log(C.d("\nDocker does not label build cache per project, so it cannot filter out just this"));
    console.log(C.d("brain's share - clearing it clears the whole machine. No data is lost; it only makes"));
    console.log(C.d("the next build of EVERY project slower. Keep it: npm run uninstall:keep-cache"));
  }

  if (!yes) {
    console.log(C.y("\nThis CANNOT be undone (brain data has to be ingested again from scratch)."));
    console.log("If you are sure, run: " + C.b("npm run uninstall:yes"));
    return 2;
  }

  let failed = false;
  const d = findDocker();
  if (!d) {
    console.log(C.y("Docker not found - skipping containers, cleaning files only."));
  } else {
    const env = composeEnv();
    const viaCompose = env && run(d.cmd,
      [...d.pre, "compose", "-p", env._BRAIN_ID, ...brainEnv.composeFiles(env._MODE, env._EMBEDDING),
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
  console.log(C.d("Rebuild: npm run brain   |   Also wipe knowledge: npm run reset:yes"));
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
    console.log("If you are sure, run: " + C.b("npm run reset:yes"));
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
 * `instanceIdleTimeout=-1` giữ distro; `vmIdleTimeout=-1` giữ VM chung. Thiếu một trong hai thì
 * systemd + Docker vẫn có thể dừng ngay khi lệnh `wsl.exe` cuối cùng thoát. File cấu hình của người
 * dùng nên chỉ THÊM khoá còn thiếu, không ghi đè cái đang có.
 * Có hiệu lực sau `wsl --shutdown` một lần.
 *
 * @returns {boolean} true nếu vừa sửa file (người dùng cần `wsl --shutdown`).
 */
function ensureWslNeverIdles() {
  const { file, text } = readWslConfig();
  if (!file) return false;
  let next = text;
  const added = [];
  for (const [section, key] of [
    ["general", "instanceIdleTimeout"],
    ["wsl2", "vmIdleTimeout"],
  ]) {
    const result = addIniSetting(next, section, key, "-1");
    next = result.text;
    if (result.changed) added.push(`[${section}] ${key}=-1`);
  }
  if (!added.length) return false;
  try {
    fs.writeFileSync(file, next, "utf8");
    console.log(C.y(`Đã thêm ${added.join(" + ")} vào ${file}.`));
    return true;
  } catch (err) {
    console.log(C.y(`Không ghi được ${file} (${err.message}). Xem GUIDE WSL trong README.md.`));
    return false;
  }
}

async function up() {
  const d = findDocker();
  if (!d) {
    console.error(C.r("No running Docker daemon found."));
    console.error("  - Docker Desktop: open the app, wait for the green icon, then retry.");
    if (IS_WIN) console.error("  - Docker CE inside WSL: open a WSL terminal, `sudo service docker start`.");
    return 1;
  }
  console.log(C.d(`Docker: ${d.kind} (server ${d.version})`));
  let launcherCode = 0;
  if (IS_WIN && d.kind === "native") {
    console.log(C.d("→ brain-up.ps1 (Windows + Docker Desktop)"));
    launcherCode = run("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass",
                              "-File", path.join(STACK, "brain-up.ps1")]);
  } else if (IS_WIN && d.kind === "wsl") {
    const root = wslRoot();
    if (!root) return wslRootMissing();
    const nodeProbe = tryRun("wsl", ["-e", "bash", "-c",
      'PATH="$HOME/.local/alice-node/bin:$PATH" node --version']);
    if (!nodeProbe.ok) {
      console.log(C.y("Node is missing inside WSL - the launcher installs it (no sudo needed)."));
    }
    console.log(C.d("→ brain-up.sh inside WSL (Docker CE)"));
    const needsShutdown = ensureWslNeverIdles();
    const networkMode = wslNetworkMode();
    launcherCode = run("wsl", [
      "-e", "env", `ALICE_WSL_NETWORK_MODE=${networkMode}`,
      "bash", `${root}/brain/stack/brain-up.sh`,
    ]);
    if (launcherCode === 0 && needsShutdown) {
      console.log(C.y("\nWSL settings changed. Run this ONCE, then start again - the brain will stop dying:"));
      console.log(C.b("  wsl --shutdown"));
      console.log(C.b("  npm run brain"));
    }
  } else {
    console.log(C.d("→ brain-up.sh"));
    launcherCode = run("bash", [path.join(STACK, "brain-up.sh")]);
  }
  if (launcherCode !== 0) return launcherCode;

  // Wait for the brain to become ready — the launcher exits once containers are up,
  // but the API may still be pulling models or extracting entities.
  const info = brainEnv.peek();
  const readyUrl = `http://localhost:${info.API_PORT}/api/v1/system/ready`;
  console.log(C.d("\nWaiting for the brain to become ready..."));
  const deadline = Date.now() + 120_000; // 2 minutes — covers model pulls (bge-m3 ~1.2 GB)
  let lastStatus = "";
  while (Date.now() < deadline) {
    const res = await get(readyUrl, 3000);
    if (res && res.status === 200) {
      try {
        const body = JSON.parse(res.body);
        if (body.status === "ready") {
          console.log(C.g(`  Brain is ready (${info.BRAIN_HOST}:${info.API_PORT})`));
          // Brain đã trả lời được thì mới biết endpoint embedding NÀO đang thực sự có hiệu lực —
          // giá trị đó nằm trong DB, launcher không đọc được từ `.env`.
          await reconcileEmbedding(info);
          return 0;
        }
        if (body.status !== lastStatus) {
          console.log(C.d(`  ${body.status}...`));
          lastStatus = body.status;
        }
      } catch (_) {
        console.log(C.d("  ..."));
      }
    } else {
      console.log(C.d("  ..."));
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  console.log(C.y("\nBrain did not become ready within 2 minutes — it may still be pulling models."));
  console.log(C.d("Check: docker compose ps   |   Wait and run: npm run brain:status"));
  return 0;
}

function python(scriptRel, args, opts = {}) {
  const py = findPython();
  if (!py) {
    console.error(C.r("Python not found.") + " Python 3.9+ is required (https://python.org).");
    return 1;
  }
  return run(py.cmd, [...py.pre, path.join(ROOT, scriptRel), ...args], opts);
}

async function status() {
  const d = findDocker();
  const info = runtimeBrainInfo(d);
  console.log(C.b("Brain for this project:"));
  console.log(`  ${info.BRAIN_ID}` + (info.exists ? "" : C.y("  [never built]")));
  console.log(C.d(`  mode: ${info.BRAIN_MODE === "dev" ? "dev - built from local sources" : "published image"}`));
  console.log(C.d(`  embedding: ${{
    external: "external - your own endpoint; ALICE runs and downloads nothing",
    project: "project - a private Ollama container for this brain",
  }[info.ALICE_EMBEDDING_MODE] || "shared - one Ollama container for the whole machine (npm run embedding)"}`));
  console.log(C.b("\nContainer:"));
  if (!info.exists) {
    console.log(C.d("  (not built)"));
    console.log(C.b("\nServices:"));
    console.log(C.d("  (not available - run npm run brain)"));
    return 0;
  }
  let containerNames = [];
  if (d) {
    const ps = tryRun(d.cmd, [...d.pre, "ps", "--filter",
      `label=com.docker.compose.project=${info.BRAIN_ID}`,
      "--format", "{{.Names}}"]).out;
    containerNames = ps.split(/\r?\n/).map((name) => name.trim()).filter(Boolean);
    if (containerNames.length) {
      run(d.cmd, [...d.pre, "ps", "--filter",
        `label=com.docker.compose.project=${info.BRAIN_ID}`,
        "--format", "  {{.Names}}\t{{.Status}}"]);
      console.log(C.b("\nResources:"));
      run(d.cmd, [...d.pre, "stats", "--no-stream",
        "--format", "  {{.Name}}\tRAM {{.MemUsage}}\tPIDs {{.PIDs}}\tI/O {{.BlockIO}}",
        ...containerNames]);
      console.log(C.d("  RAM above is separate from Docker disk images, volumes, and build cache."));
    } else {
      console.log(C.y("  No running containers."));
    }
  } else console.log(C.r("  Docker not found."));
  console.log(C.b("\nServices:"));
  const probes = [
    ["API", `http://${info.BRAIN_HOST}:${info.API_PORT}`, `http://localhost:${info.API_PORT}`, "/api/v1/system/ready"],
    ["Web", `http://${info.BRAIN_HOST}:${info.WEB_PORT}`, `http://localhost:${info.WEB_PORT}`, ""],
  ];
  for (const [label, displayBase, probeBase, probe] of probes) {
    // Node trên một số bản Windows không tự phân giải `*.localhost`; probe qua loopback
    // thuần nhưng luôn in URL project-specific mà trình duyệt dùng.
    const res = await get(probeBase + probe);
    const up = probe ? res && res.status === 200 : Boolean(res);
    console.log(`  ${label} ${displayBase}  ${up ? C.g("ready") : C.r("down")}`);
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
    console.log(`  ${state}  ${brain.id}${mark}`);
    console.log(C.d(`           web http://${brain.host}:${brain.web} | api http://${brain.host}:${brain.api}`));
  }
  console.log(C.d("\nEach brain is its own compose project: containers, network and volumes are all separate."));
  return 0;
}

function mcp() {
  const d = findDocker();
  const wsl = d && d.kind === "wsl";
  const info = runtimeBrainInfo(d);
  const cmd = wsl ? "wsl" : "docker";
  // `-e SAG_MCP_ACTOR=<agent>` only labels the telemetry rows (Settings -> Telemetry) so the
  // brain can tell which agent asked for what. It grants nothing; auth is still the JWT/scope.
  const argsFor = (actor) => {
    const base = ["exec", "-i", "-e", `SAG_MCP_ACTOR=${actor}`, `${info.BRAIN_ID}-api-1`, "python", "-m", "sag_api.mcp.server"];
    return wsl ? ["-e", "docker", ...base] : base;
  };
  console.log(C.b("MCP configuration for your agent (stdio bridge)\n"));
  console.log(C.d("Claude Code:"));
  console.log(`  claude mcp add brain -- ${cmd} ${argsFor("claude-code").join(" ")}\n`);
  console.log(C.d("Codex (~/.codex/config.toml):"));
  console.log(`  [mcp_servers.brain]\n  command = "${cmd}"\n  args = ${JSON.stringify(argsFor("codex"))}\n`);
  console.log(C.d("Project .mcp.json:"));
  console.log(JSON.stringify({ mcpServers: { brain: { command: cmd, args: argsFor("mcp-client") } } }, null, 2));
  console.log(C.d("\nSAG_MCP_ACTOR only labels telemetry rows - change it to whatever names the agent."));
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

  const info = runtimeBrainInfo(d);
  const ready = info.exists
    ? await get(`http://localhost:${info.API_PORT}/api/v1/system/ready`)
    : null;
  if (ready && ready.status === 200) {
    console.log(`[${OK}] ALICE API ready (http://${info.BRAIN_HOST}:${info.API_PORT})`);
    const cap = await get(`http://localhost:${info.API_PORT}/api/v1/system/capabilities`);
    let llm = null;
    try { llm = JSON.parse(cap.body).llm_configured; } catch (_) {}
    if (llm === true) console.log(`[${OK}] LLM configured - ready to ingest`);
    else if (llm === false) {
      console.log(`[${WARN}] LLM NOT configured - open http://${info.BRAIN_HOST}:${info.WEB_PORT} -> Settings -> Models`);
    }
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

function sync(args) {
  const info = runtimeBrainInfo();
  if (!info.exists) {
    console.error(C.r("This project's brain has never been built."));
    console.error("Run this first: " + C.b("npm run brain"));
    return 1;
  }
  return python("brain/sync/sync.py", args, {
    env: {
      ...process.env,
      // Đây là default runtime, không phải override cấu hình người dùng. sync.py chỉ dùng
      // chúng khi brain.config còn giữ giá trị mặc định cũ hoặc không khai báo.
      ALICE_BRAIN_ID: info.BRAIN_ID,
      ALICE_BRAIN_API_PORT: info.API_PORT,
    },
  });
}

/* ------------------------------------------------------------------ main */

const [cmd, ...rest] = process.argv.slice(2);
(async () => {
  if (IS_WIN && WSL_DELEGATED_COMMANDS.has(cmd)) {
    const d = findDocker();
    if (d && d.kind === "wsl") process.exit(runSelfInWsl([cmd, ...rest]));
  }
  switch (cmd) {
    case "up":       process.exit(await up());
    case "down":     process.exit(compose(["down"]));
    case "restart":  process.exit(compose(["restart"]));
    case "logs":     process.exit(compose(["logs", "-f", "--tail", "100", ...rest]));
    case "uninstall":process.exit(uninstall(rest));
    case "reset":    process.exit(reset(rest));
    case "status":   process.exit(await status());
    case "list":     process.exit(await list());
    case "pull":     process.exit(pull());
    case "embedding":     process.exit(await embedding());
    case "embedding-reclaim": {
      const info = runtimeBrainInfo();
      if (!info.exists) { console.error(C.r("This project's brain has never been built.")); process.exit(1); }
      await reconcileEmbedding(info);
      process.exit(0);
    }
    case "embedding-down": process.exit(embeddingDown(rest));
    case "embedding-purge": process.exit(embeddingPurge(rest));
    case "verify":   process.exit(python("tools/verify.py", rest));
    case "sync":     process.exit(sync(rest));
    case "test-sync": process.exit(python("brain/sync/test_sync.py", rest));
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
  embedding status of the embedding container (shared machine-wide by default)
  embedding-reclaim  stop the embedding container when the saved config no longer uses it
  embedding-down  stop the SHARED embedding container (affects every project)  needs --yes
  embedding-purge delete downloaded embedding models to reclaim disk space  needs --yes
  uninstall remove Docker + brain runtime (KEEPS knowledge)   needs --yes
  reset     DELETE project knowledge + pull a fresh template  needs --yes
  verify    check the knowledge base   sync    push files into the brain
  update    upgrade the template       mcp     print the MCP config (INITIALIZATION runs this itself)

Via npm: npm run doctor | npm run brain | npm run verify | npm run sync
Destructive: npm run uninstall:yes   |   npm run reset:yes

Note: on Windows PowerShell the npm.ps1 shim drops "--", so "npm run x -- --flag"
never reaches the script. Every flag has its own npm script for that reason.`);
      process.exit(cmd ? 2 : 0);
  }
})();
