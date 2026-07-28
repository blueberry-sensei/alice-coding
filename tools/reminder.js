#!/usr/bin/env node
/**
 * reminder — in lại entry point ALICE.md vào context của agent.
 *
 * Dùng làm hook `SessionStart` của Claude Code (matcher gồm `compact`): stdout của hook
 * được nạp thẳng vào context. Đây là lớp phòng thủ duy nhất sống NGOÀI model, nên là thứ
 * duy nhất auto-compact không xoá được — mọi luật nằm trong context đều có thể bị tóm tắt
 * mất, kể cả luật "sau compact phải đọc lại".
 *
 * Chỉ đọc lại file đã sinh, không tự dựng nội dung: nhờ vậy không có bản luật thứ hai
 * trôi khác `ALICE.md`.
 *
 * Chuỗi hướng dẫn dành cho AGENT viết tiếng Việt (cùng loại với ALICE.md); chuỗi báo lỗi
 * dành cho người đọc terminal viết tiếng Anh, theo luật của repo.
 */
"use strict";

const fs = require("fs");
const path = require("path");

const KNOWLEDGE_DIR = path.basename(path.resolve(__dirname, ".."));
const ENTRY_POINT = path.resolve(__dirname, "..", "..", "ALICE.md");

if (!fs.existsSync(ENTRY_POINT)) {
  console.error(`ALICE reminder: ALICE.md was not found. Run \`npm run wire\` inside ${KNOWLEDGE_DIR}/.`);
  process.exit(0);
}

const entryPoint = fs.readFileSync(ENTRY_POINT, "utf8").trim();
if (!entryPoint) {
  console.error(`ALICE reminder: ALICE.md is empty. Run \`npm run wire\` inside ${KNOWLEDGE_DIR}/.`);
  process.exit(0);
}

process.stdout.write(
  [
    "<alice-entry-point>",
    "Đây là luật đang có hiệu lực của project, được nạp lại tự động vì phiên vừa khởi động",
    "hoặc vừa bị auto-compact. Ký ức trong context sau compaction KHÔNG đáng tin.",
    "",
    "Trước khi làm tiếp: nạp lại ký ức theo mục [A] bên dưới (re-query brain nếu brain bật),",
    `đọc lại \`${KNOWLEDGE_DIR}/decisions/LOG.md\` (toàn bộ ACTIVE) và \`${KNOWLEDGE_DIR}/mistakes/LOG.md\``,
    "khớp vùng đang đụng, rồi mới suy luận tiếp.",
    "",
    entryPoint,
    "</alice-entry-point>",
    "",
  ].join("\n"),
);
