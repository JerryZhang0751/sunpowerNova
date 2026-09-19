// check-news-toc 门禁自测(2026-09-19 质检修复): 反例注入必须被检出 ——
// 此前两个漏检反例(删除移动端目录 / 标题前同 id 非标题元素)在旧版检查下均返回成功。
// 用法: npm run test:toc (node --test,零依赖,不需要 dist)
import test from "node:test";
import assert from "node:assert/strict";
import { checkPageHtml } from "./check-news-toc.mjs";

// 最小合法页: 桌面+移动两套目录与正文标题逐条一致,整页 id 唯一。
function page({
  mobile = true,
  desktop = true,
  injectBeforeHeading = "",
  desktopExtra = "",
  mobileUl = false,
} = {}) {
  const links = `<a class="toc-link" href="#s1" data-depth="2">Section one</a><a class="toc-link" href="#s2" data-depth="3">Sub two</a>`;
  const headings = `<h2 id="s1">Section one</h2><p>x</p><h3 id="s2">Sub two</h3>`;
  const nav = desktop
    ? `<nav class="toc-col"><div class="toc-list">${links}${desktopExtra}</div></nav>`
    : "";
  const mobInner = mobileUl
    ? `<ul><li>${links}</li></ul>`
    : `<div class="toc-list">${links}</div>`;
  const mob = mobile
    ? `<details class="toc-mobile"><summary>On this page</summary>${mobInner}</details>`
    : "";
  return `<html><body>${mob}${nav}<main>${injectBeforeHeading}${headings}</main></body></html>`;
}

test("合法页面: 零错误", () => {
  assert.deepEqual(checkPageHtml(page()), []);
});

test("反例①(此前漏检): 整块删除移动端目录必须 FAIL", () => {
  const errs = checkPageHtml(page({ mobile: false }));
  assert.ok(errs.some((e) => e.includes("移动端目录")), `应有移动端目录缺失错误,实际: ${errs.join(" | ")}`);
});

test("反例②(此前漏检): 标题前插入同 id 非标题元素必须 FAIL", () => {
  const errs = checkPageHtml(page({ injectBeforeHeading: `<div id="s1">fake</div>` }));
  assert.ok(errs.some((e) => e.includes("整页 id 重复")), `应有整页 id 重复错误,实际: ${errs.join(" | ")}`);
});

test("反例: 缺桌面目录必须 FAIL", () => {
  const errs = checkPageHtml(page({ desktop: false }));
  assert.ok(errs.some((e) => e.includes("桌面目录")), `应有桌面目录缺失错误,实际: ${errs.join(" | ")}`);
});

test("反例: 移动端目录用 ul 必须 FAIL(两套目录各自查 D5)", () => {
  const errs = checkPageHtml(page({ mobileUl: true }));
  assert.ok(errs.some((e) => e.includes("移动端目录") && e.includes("ul/ol")), `应有移动端 ul/ol 错误,实际: ${errs.join(" | ")}`);
});

test("反例: 目录链接与正文不一致必须 FAIL", () => {
  const errs = checkPageHtml(page({ desktopExtra: `<a class="toc-link" href="#ghost" data-depth="2">Ghost</a>` }));
  assert.ok(
    errs.filter((e) => e.includes("桌面目录") && e.includes("不一致")).length > 0,
    `应有桌面目录不一致错误,实际: ${errs.join(" | ")}`,
  );
});
