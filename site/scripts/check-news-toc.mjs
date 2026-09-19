// 目录完整性检查(spec 2026-09-18 §5.2 + 2026-09-19 质检加固): 遍历 dist/news/*/index.html(排除列表页),
// 校验桌面 <nav> 与移动端 <details> 两套目录锚点均与正文标题完全一致 —— 任一目录缺失/悬空链接/
// 文字或顺序或层级不符/整页重复 id(含非标题元素)/目录内 ul/ol 均 fail。
// 零依赖;退出码非 0 = CI 失败。用法: npm run build && npm run checktoc
// 自测(反例注入,2026-09-19 质检要求): npm run test:toc
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const norm = (s) =>
  s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
   .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
   .replace(/\s+/g, " ").trim();

function extractLinks(block) {
  const out = [];
  const re = /<a\b([^>]*)>([^<]*)<\/a>/g;
  let m;
  while ((m = re.exec(block))) {
    const href = m[1].match(/href="#([^"]+)"/);
    const depth = m[1].match(/data-depth="(\d)"/);
    if (href && depth) out.push({ id: href[1], text: norm(m[2]), depth: Number(depth[1]) });
  }
  return out;
}

function headings(html) {
  // 注: 标题文本按纯文本捕获([^<]*) —— 语料假设 h2/h3 无内联标记(<strong>/<code>/链接等);
  // 含内联标记的标题不会被该正则捕获,由调用方的计数守卫 fail-closed 兜底(见下方 raw!==matched 检查)。
  const out = [];
  const re = /<(h[23])\b([^>]*)>([^<]*)<\/\1>/g;
  let m;
  while ((m = re.exec(html))) {
    const id = m[2].match(/\bid="([^"]+)"/);
    out.push({ tag: m[1], id: id ? id[1] : null, text: norm(m[3]) });
  }
  return out;
}

function pageIds(html) {
  // 整页 id 收集: 只扫真实标签的属性 —— script/style/pre/code 内容与注释先剔除
  // (防正文示例代码里的 id="..." 文本误报);属性以空白分隔匹配,不会命中 data-id 等。
  const stripped = html
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<pre[\s\S]*?<\/pre>/gi, "")
    .replace(/<code[\s\S]*?<\/code>/gi, "");
  const out = [];
  const re = /<([a-zA-Z][^\s>]*)\b[^>]*>/g;
  let m;
  while ((m = re.exec(stripped))) {
    const id = m[0].match(/\sid="([^"]+)"/);
    if (id) out.push(id[1]);
  }
  return out;
}

// 单页检查: 返回错误列表(空 = 通过)。CLI 与反例自测共用同一实现。
export function checkPageHtml(html) {
  const errs = [];
  const nav = html.match(/<nav class="toc-col"[^>]*>([\s\S]*?)<\/nav>/);
  const mob = html.match(/<details class="toc-mobile"[^>]*>([\s\S]*?)<\/details>/);
  // 2026-09-19 质检: 此前只查桌面目录 —— 整块删除移动端 <details> 仍通过(手机无目录)。
  if (!nav) errs.push('缺少 <nav class="toc-col"> 桌面目录');
  if (!mob) errs.push('缺少 <details class="toc-mobile"> 移动端目录');

  const hs = headings(html);
  // fail-closed: 原始 h2/h3 出现次数必须与纯文本正则的匹配数一致,
  // 不一致说明有标题含内联标记而漏配 —— 显式报错,不得静默缩小检查范围。
  const rawH = (html.match(/<h[23]\b/g) ?? []).length;
  if (rawH !== hs.length) {
    errs.push(`正文标题计数不匹配: raw=${rawH} matched=${hs.length}（含内联标记的标题不被支持）`);
  }
  const noId = hs.filter((h) => !h.id);
  if (noId.length) errs.push(`正文标题缺 id: ${noId.map((h) => h.text).join(" / ")}`);
  const want = hs
    .filter((h) => h.id)
    .map((h) => ({ id: h.id, text: h.text, depth: Number(h.tag[1]) }));

  for (const [name, block] of [["桌面目录", nav], ["移动端目录", mob]]) {
    if (!block) continue;
    const links = extractLinks(block[1]);
    if (links.length === 0) errs.push(`${name}: 无任何目录链接`);
    // D5 决策(目录不用 ul/ol 列表元素,GEO 结构计数稳定): 目录块内出现 ul/ol 即 FAIL,
    // 防未来重构回列表结构后本检查仍绿而 GEO ul_count 漂移。两套目录各自检查。
    if (/<(ul|ol)\b/.test(block[1])) {
      errs.push(`${name}: 使用了 ul/ol —— 违反 D5(GEO 结构计数)`);
    }
    const seen = new Set();
    for (const l of links) {
      if (seen.has(l.id)) errs.push(`${name}: 重复链接 #${l.id}`);
      seen.add(l.id);
    }
    if (JSON.stringify(links) !== JSON.stringify(want)) {
      errs.push(`${name}: 与正文标题不一致(逐条比对 id/text/depth/顺序):\n    toc : ${JSON.stringify(links)}\n    body: ${JSON.stringify(want)}`);
    }
  }

  // 2026-09-19 质检: 整页 id 唯一性 —— 目录锚点靠 getElementById/原生跳转解析,
  // 标题前插入同 id 的非标题元素会让跳转与高亮命中错误元素(此前只查标题间重复,漏检此型)。
  const ids = pageIds(html);
  const counts = {};
  for (const id of ids) counts[id] = (counts[id] ?? 0) + 1;
  const dup = Object.entries(counts).filter(([, n]) => n > 1);
  if (dup.length) errs.push(`整页 id 重复: ${dup.map(([k]) => `#${k}×${counts[k]}`).join(", ")}`);

  return errs;
}

function main() {
  const distNews = join(fileURLToPath(new URL("../dist/news/", import.meta.url)));
  let pages;
  try {
    pages = readdirSync(distNews, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => join(distNews, d.name, "index.html"));
  } catch {
    console.error("FAIL dist/news/ 不存在 —— 先 npm run build");
    process.exit(1);
  }
  if (pages.length === 0) {
    console.error("FAIL 未发现任何 dist/news/*/index.html");
    process.exit(1);
  }

  let failures = 0;
  for (const p of pages) {
    const html = readFileSync(p, "utf8");
    const errs = checkPageHtml(html);
    if (errs.length) {
      failures++;
      console.error(`FAIL ${p}\n  ${errs.join("\n  ")}`);
    } else {
      const nav = html.match(/<nav class="toc-col"[^>]*>([\s\S]*?)<\/nav>/);
      console.log(`ok   ${p} (${extractLinks(nav[1]).length} 条目录)`);
    }
  }
  process.exit(failures ? 1 : 0);
}

// 直接执行时跑 CLI;被 test 文件 import 时不跑(路径含空格,用 pathToFileURL 比较)
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
