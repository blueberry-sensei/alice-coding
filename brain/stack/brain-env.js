#!/usr/bin/env node
/**
 * brain-env.js — danh tính + cấu hình của MỘT brain, tính ở đúng MỘT chỗ.
 *
 * Trước đây compose ghim cứng `name: alice-brain` và `.env` nằm ngay trong repo. Hệ quả:
 * hai project trên cùng máy đụng nhau (cùng container name, cùng port, cùng thư mục dữ liệu),
 * và `SAG_SECRET_KEY` — khoá ký JWT kiêm gốc mã hoá mọi API key — nằm plaintext trong cây repo.
 *
 * File này giải quyết cả hai:
 *
 *  - `BRAIN_ID` suy từ đường dẫn TUYỆT ĐỐI của kho tri thức → mỗi project một compose project
 *    → container, network và named volume đều được Docker gắn tiền tố riêng. Không có đường nào
 *    để brain của project này nhìn thấy dữ liệu của project kia.
 *  - `.env` (chứa SAG_SECRET_KEY + port đã cấp) chuyển ra thư mục state của người dùng, NGOÀI
 *    cây repo. Repo chỉ còn `.env.example` làm tài liệu.
 *
 * Tính ở một chỗ bằng Node vì cả hai launcher đều cần con số giống hệt nhau; viết lại logic
 * hash/cấp port trong bash và PowerShell là mời gọi hai bên lệch nhau. Node cũng cho sẵn CSPRNG
 * (`crypto.randomBytes`) nên không phải nhờ `Get-Random` hay `openssl`.
 *
 * Dùng:
 *   node brain-env.js --shell        # in `export K='V'` cho bash
 *   node brain-env.js --powershell   # in `$env:K='V'` cho PowerShell
 *   node brain-env.js --json         # in JSON
 *   require("./brain-env.js").resolve()
 */

"use strict";

const fs = require("fs");
const os = require("os");
const net = require("net");
const path = require("path");
const crypto = require("crypto");

const STACK = __dirname;
// brain/stack -> brain -> gốc kho tri thức (thư mục `knowledge/` khi đã cài vào project).
const ROOT = path.resolve(STACK, "..", "..");

/** Thư mục chứa state của MỌI brain trên máy này (ngoài mọi repo). */
function stateRoot() {
  if (process.platform === "win32") {
    const base = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    return path.join(base, "alice-brain");
  }
  const base = process.env.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state");
  return path.join(base, "alice-brain");
}

/**
 * Danh tính brain: `<tên project>-<6 hex của đường dẫn>`.
 *
 * Phần chữ để người đọc `docker ps` biết ngay là brain của project nào; phần hash để hai
 * project trùng tên ở hai nơi khác nhau vẫn tách bạch. Chuẩn hoá lowercase + `/` trước khi
 * băm để `E:\Proj` và `e:/proj` ra cùng một brain thay vì đẻ ra hai cái.
 */
function brainId(root = ROOT) {
  const abs = path.resolve(root);
  const normalized = abs.replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
  const hash = crypto.createHash("sha256").update(normalized).digest("hex").slice(0, 6);

  // Kho tri thức thường nằm ở <project>/knowledge → lấy tên project cho dễ nhận.
  let label = path.basename(abs);
  if (/^knowledge$/i.test(label)) label = path.basename(path.dirname(abs)) || label;

  let slug = label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  if (!slug) slug = "brain";
  // Compose project name phải bắt đầu bằng chữ/số thường. Project vốn đã tên "alice-*" thì
  // không dán thêm tiền tố nữa, kẻo ra "alice-alice-coding-…".
  const prefixed = /^alice(-|$)/.test(slug) ? slug : `alice-${slug}`;
  return `${prefixed}-${hash}`.slice(0, 54);
}

/* ------------------------------------------------------------------ .env IO */

function parseEnv(text) {
  const out = {};
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq < 1) continue;
    out[line.slice(0, eq).trim()] = line.slice(eq + 1).trim();
  }
  return out;
}

function readEnvFile(file) {
  try {
    return parseEnv(fs.readFileSync(file, "utf8"));
  } catch {
    return null;
  }
}

/** Ghi .env với quyền chỉ chủ sở hữu đọc được (POSIX; Windows dựa vào ACL của LOCALAPPDATA). */
function writeEnvFile(file, values, header) {
  const body = Object.entries(values)
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${header}\n${body}\n`, { mode: 0o600 });
  if (process.platform !== "win32") {
    try {
      fs.chmodSync(file, 0o600);
    } catch {
      /* filesystem không hỗ trợ chmod — không phải lý do để dừng */
    }
  }
}

/* ------------------------------------------------------------------- ports */

function portFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => server.close(() => resolve(true)));
    server.listen(port, "127.0.0.1");
  });
}

/** Port mà brain KHÁC đã giữ chỗ (kể cả khi nó đang tắt) — không được cướp. */
function reservedByOtherBrains(selfId) {
  const reserved = new Set();
  let entries = [];
  try {
    entries = fs.readdirSync(stateRoot(), { withFileTypes: true });
  } catch {
    return reserved;
  }
  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name === selfId) continue;
    const values = readEnvFile(path.join(stateRoot(), entry.name, ".env"));
    if (!values) continue;
    for (const key of ["WEB_PORT", "API_PORT", "CHECKLIST_PORT"]) {
      const port = Number(values[key]);
      if (Number.isInteger(port)) reserved.add(port);
    }
  }
  return reserved;
}

async function pickPort(preferred, taken, reserved) {
  for (let port = preferred; port < preferred + 400; port += 1) {
    if (taken.has(port) || reserved.has(port)) continue;
    if (await portFree(port)) {
      taken.add(port);
      return port;
    }
  }
  throw new Error(`Không tìm được cổng trống quanh ${preferred}.`);
}

/* ----------------------------------------------------------------- resolve */

const HEADER = `# Cấu hình brain của MỘT project. File này nằm NGOÀI repo có chủ đích:
# SAG_SECRET_KEY vừa ký JWT vừa là gốc dẫn xuất khoá mã hoá mọi API key trong DB.
# Không commit, không chép vào repo, không dán vào chat.
# Sinh/cập nhật tự động bởi brain/stack/brain-env.js.`;

/**
 * Trả về toàn bộ biến cần cho compose, tạo/sửa state khi thiếu.
 *
 * Có sẵn thì DÙNG LẠI: port và SAG_SECRET_KEY phải ổn định giữa các lần chạy, đổi khoá là
 * mất sạch API key đã lưu (chúng được mã hoá bằng khoá dẫn xuất từ nó).
 */
async function resolve({ root = ROOT } = {}) {
  const id = brainId(root);
  const dir = path.join(stateRoot(), id);
  const envFile = path.join(dir, ".env");

  const migrated = [];

  // Bản cũ để .env ngay trong repo. Gộp vào state rồi XOÁ bản trong repo. Giá trị của bản cũ
  // được giữ nguyên — đặc biệt SAG_SECRET_KEY (đổi là mất sạch API key đã lưu, chúng được mã
  // hoá bằng khoá dẫn xuất từ nó) và ALICE_*_PATH (mất là launcher quay về clone bản GitHub,
  // nuốt mất source đang phát triển trên máy). State có sẵn thì state thắng.
  const legacyFile = path.join(STACK, ".env");
  const legacy = readEnvFile(legacyFile);
  let values = readEnvFile(envFile);
  if (legacy) {
    values = { ...legacy, ...(values || {}) };
    migrated.push("env");
  } else if (!values) {
    values = {};
  }

  if (!values.SAG_SECRET_KEY) {
    values.SAG_SECRET_KEY = crypto.randomBytes(32).toString("hex");
    migrated.push("secret");
  }

  const reserved = reservedByOtherBrains(id);
  const taken = new Set();
  const wanted = { WEB_PORT: 3000, API_PORT: 8000, CHECKLIST_PORT: 8090 };
  for (const [key, preferred] of Object.entries(wanted)) {
    const existing = Number(values[key]);
    if (Number.isInteger(existing) && existing > 0 && !reserved.has(existing)) {
      taken.add(existing);
      values[key] = String(existing);
      continue;
    }
    values[key] = String(await pickPort(preferred, taken, reserved));
    migrated.push(`port:${key}`);
  }

  // Log vẫn để trong repo (gitignore) để đọc bằng editor thường — log không chứa credential.
  const logs = path.join(ROOT, "brain", ".logs", "api");
  fs.mkdirSync(logs, { recursive: true });

  writeEnvFile(envFile, values, HEADER);

  // State đã an toàn ngoài repo → XOÁ bản trong repo. Để lại thì mục tiêu "không có secret
  // trong cây repo" thành lời nói suông, và tệ hơn là hai nguồn sự thật lệch nhau về sau.
  if (legacy && fs.existsSync(legacyFile)) {
    fs.writeFileSync(
      path.join(STACK, ".env.moved"),
      `# .env cua brain da chuyen ra ngoai repo (khong con secret nao trong cay repo).\n`
        + `# Vi tri moi: ${envFile}\n`
        + `# Sua cau hinh thi sua file do, hoac chay: npm run brain\n`,
    );
    fs.rmSync(legacyFile);
  }

  return {
    BRAIN_ID: id,
    BRAIN_STATE_DIR: dir,
    BRAIN_ENV_FILE: envFile,
    BRAIN_LOGS: logs,
    BRAIN_ROOT: path.resolve(root),
    // "image" = kéo image dựng sẵn (đường của mọi người dùng, không cần git/source).
    // "dev"   = build từ source trên máy; chỉ bật khi CẢ HAI đường dẫn được khai báo.
    BRAIN_MODE: values.ALICE_APP_PATH && values.ALICE_CORE_PATH ? "dev" : "image",
    WEB_PORT: values.WEB_PORT,
    API_PORT: values.API_PORT,
    CHECKLIST_PORT: values.CHECKLIST_PORT,
    BIND_ADDRESS: values.BIND_ADDRESS || "127.0.0.1",
    SAG_SECRET_KEY: values.SAG_SECRET_KEY,
    ALICE_APP_PATH: values.ALICE_APP_PATH || "",
    ALICE_CORE_PATH: values.ALICE_CORE_PATH || "",
    _migrated: migrated,
  };
}

/** Đọc state đã có, KHÔNG tạo mới — dùng cho status/list/mcp (không nên đẻ state khi chỉ hỏi). */
function peek({ root = ROOT } = {}) {
  const id = brainId(root);
  const envFile = path.join(stateRoot(), id, ".env");
  const values = readEnvFile(envFile) || {};
  return {
    BRAIN_ID: id,
    BRAIN_ENV_FILE: envFile,
    exists: fs.existsSync(envFile),
    WEB_PORT: values.WEB_PORT || "3000",
    API_PORT: values.API_PORT || "8000",
    CHECKLIST_PORT: values.CHECKLIST_PORT || "8090",
    BRAIN_MODE: values.ALICE_APP_PATH && values.ALICE_CORE_PATH ? "dev" : "image",
    ALICE_APP_PATH: values.ALICE_APP_PATH || "",
    ALICE_CORE_PATH: values.ALICE_CORE_PATH || "",
  };
}

/**
 * Danh sách `-f` cho docker compose.
 *
 * Mặc định chỉ `compose.yaml` (kéo image). Có source trên máy thì chồng thêm `compose.dev.yaml`
 * để build từ đó — đây là đường của người phát triển chính alice-brain/alice-core, không phải
 * đường của người dùng.
 */
function composeFiles(mode) {
  const files = ["-f", path.join(STACK, "compose.yaml")];
  if (mode === "dev") files.push("-f", path.join(STACK, "compose.dev.yaml"));
  return files;
}

/** Mọi brain đã từng dựng trên máy này (đọc từ state dir, không cần Docker). */
function listBrains() {
  let entries = [];
  try {
    entries = fs.readdirSync(stateRoot(), { withFileTypes: true });
  } catch {
    return [];
  }
  return entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      const values = readEnvFile(path.join(stateRoot(), entry.name, ".env")) || {};
      return {
        id: entry.name,
        web: values.WEB_PORT || "?",
        api: values.API_PORT || "?",
        checklist: values.CHECKLIST_PORT || "?",
      };
    })
    .sort((a, b) => a.id.localeCompare(b.id));
}

/* --------------------------------------------------------------------- CLI */

function quoteSh(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function quotePs(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

async function main() {
  const mode = process.argv[2] || "--json";
  const env = await resolve();
  delete env._migrated;

  if (mode === "--json") {
    process.stdout.write(`${JSON.stringify(env, null, 2)}\n`);
    return;
  }
  for (const [key, value] of Object.entries(env)) {
    if (mode === "--shell") process.stdout.write(`export ${key}=${quoteSh(value)}\n`);
    else if (mode === "--powershell") process.stdout.write(`$env:${key}=${quotePs(value)}\n`);
    else throw new Error(`Chế độ không hiểu: ${mode}`);
  }
}

module.exports = { resolve, peek, listBrains, brainId, composeFiles, stateRoot, ROOT, STACK };

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`brain-env: ${error.message}\n`);
    process.exit(1);
  });
}
