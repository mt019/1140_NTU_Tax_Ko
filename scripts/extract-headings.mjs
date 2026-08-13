// 從校對版正文抽出所有標題，帶來源檔、行號與 MkDocs 錨點。
//
// 用途：主題重編的第一步。按課時編排的 186 個檔裡，標題本身就是老師講課的
// 顆粒；把它們全部抽出來排在一起，才看得出同一個主題散落在哪幾門課、講過幾次。
//
// 唯讀，不改動任何正文。輸出 _work/headings.json（已 gitignore，隨時可重跑）。
//
//   node scripts/extract-headings.mjs
//
// 排除：逐字稿初稿（未上線的原始稿）、_原稿、不用的廢稿、各層 index.md、404.md。
// 注意「不用的廢稿」是真的廢稿：1141 租稅法總論與所得稅法四各有一份，內容與
// 正式的 W03／W04 高度重疊，線上是 404。混進來會讓同一段講課被數兩次。

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative } from 'node:path';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..');
const DOCS = join(REPO, 'mkdocs/My_Notes');
const OUT = join(REPO, '_work/headings.json');

const files = execSync(
  `find "${DOCS}" -name "*.md"` +
  ` -not -path "*逐字稿初稿*" -not -path "*_原稿*" -not -path "*不用的廢稿*"` +
  ` -not -name "index.md" -not -name "404.md"`,
  { encoding: 'utf8' },
).trim().split('\n').filter(Boolean).sort();

// MkDocs Material 的錨點規則：小寫、空白轉連字號、去掉標點，中文原樣保留。
const slugify = (s) =>
  s.trim().toLowerCase()
    .replace(/[`*_~]/g, '')
    .replace(/[^\p{L}\p{N}\s-]/gu, '')
    .trim().replace(/\s+/g, '-');

const rows = [];
for (const file of files) {
  const rel = relative(DOCS, file);
  const [semester, second] = rel.split('/');
  const course = second && second.endsWith('.md') ? '' : second || '';
  const page = rel.replace(/\.md$/, '');
  let inFence = false;
  // 檔尾的 <!-- --> 有時整段藏著原始逐字稿，裡頭的 ## 不是頁面上的標題。
  const body = readFileSync(file, 'utf8').replace(/<!--[\s\S]*?-->/g, (m) =>
    m.replace(/[^\n]/g, ''));   // 用等量空行換掉，行號才不會跑掉
  body.split('\n').forEach((line, i) => {
    if (/^\s*(```|~~~)/.test(line)) { inFence = !inFence; return; }
    if (inFence) return;
    const m = /^(#{1,4})\s+(.+?)\s*$/.exec(line);
    if (!m) return;
    const text = m[2].replace(/\s*\{[^}]*\}\s*$/, '');   // 去掉 {#custom-id}
    rows.push({
      level: m[1].length,
      text,
      semester,
      course,
      page,
      line: i + 1,
      anchor: `${page}/#${slugify(text)}`,
    });
  });
}

mkdirSync(join(REPO, '_work'), { recursive: true });
writeFileSync(OUT, JSON.stringify(rows, null, 1));

const byLevel = rows.reduce((a, r) => ((a[r.level] = (a[r.level] || 0) + 1), a), {});
console.log(`檔案 ${files.length}｜標題 ${rows.length}｜` +
  Object.entries(byLevel).map(([k, v]) => `H${k}=${v}`).join(' '));
console.log(`輸出 ${relative(REPO, OUT)}`);
