// 目录完整性检查(spec 2026-09-18 §5.2): 遍历 dist/news/*/index.html(排除列表页),
// 校验目录锚点与正文标题完全一致 —— 目录缺失/悬空链接/文字或顺序或层级不符/重复 id 均 fail。
// 零依赖;退出码非 0 = CI 失败。用法: npm run build && npm run checktoc
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const distNews = join(fileURLToPath(new URL("../dist/news/", import.meta.url)));

const norm = (s) =>
  s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
   .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
   .replace(/\s+/g, " ").trim();

function navLinks(html) {
  const nav = html.match(/<nav class="toc-col"[^>]*>([\s\S]*?)<\/nav>/);
  if (!nav) return null;
  const out = [];
  const re = /<a\b([^>]*)>([^<]*)<\/a>/g;
  let m;
  while ((m = re.exec(nav[1]))) {
    const href = m[1].match(/href="#([^"]+)"/);
    const depth = m[1].match(/data-depth="(\d)"/);
    if (href && depth) out.push({ id: href[1], text: norm(m[2]), depth: Number(depth[1]) });
  }
  return { links: out, block: nav[1] };
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
  const errs = [];
  const nav = navLinks(html);
  if (!nav || nav.links.length === 0) errs.push('缺少 <nav class="toc-col"> 目录');
  // D5 决策(目录不用 ul/ol 列表元素,GEO 结构计数稳定): nav 块内出现 ul/ol 即 FAIL,
  // 防未来重构回列表结构后本检查仍绿而 GEO ul_count 漂移。
  if (nav && /<(ul|ol)\b/.test(nav.block)) {
    errs.push('目录使用了 ul/ol —— 违反 D5(GEO 结构计数)');
  }
  const hs = headings(html);
  // fail-closed: 原始 h2/h3 出现次数必须与纯文本正则的匹配数一致,
  // 不一致说明有标题含内联标记而漏配 —— 显式报错,不得静默缩小检查范围。
  const rawH = (html.match(/<h[23]\b/g) ?? []).length;
  if (rawH !== hs.length) {
    errs.push(`正文标题计数不匹配: raw=${rawH} matched=${hs.length}（含内联标记的标题不被支持）`);
  }
  const noId = hs.filter((h) => !h.id);
  if (noId.length) errs.push(`正文标题缺 id: ${noId.map((h) => h.text).join(" / ")}`);
  const counts = {};
  for (const h of hs) if (h.id) counts[h.id] = (counts[h.id] ?? 0) + 1;
  const dup = Object.entries(counts).filter(([, n]) => n > 1);
  if (dup.length) errs.push(`正文标题 id 重复: ${dup.map(([k]) => k).join(", ")}`);
  if (nav) {
    const seen = new Set();
    for (const l of nav.links) {
      if (seen.has(l.id)) errs.push(`目录重复链接 #${l.id}`);
      seen.add(l.id);
    }
    const want = hs.filter((h) => h.id)
      .map((h) => ({ id: h.id, text: h.text, depth: Number(h.tag[1]) }));
    if (JSON.stringify(nav.links) !== JSON.stringify(want)) {
      errs.push(`目录与正文标题不一致(逐条比对 id/text/depth/顺序):\n    toc : ${JSON.stringify(nav.links)}\n    body: ${JSON.stringify(want)}`);
    }
  }
  if (errs.length) {
    failures++;
    console.error(`FAIL ${p}\n  ${errs.join("\n  ")}`);
  } else {
    console.log(`ok   ${p} (${nav.links.length} 条目录)`);
  }
}
process.exit(failures ? 1 : 0);
