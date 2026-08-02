import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// site URL is the target domain; update if TLD changes.
const SITE = 'https://sunhestia.com';
const root = fileURLToPath(new URL('.', import.meta.url));

// Files whose changes affect every page. A page's <lastmod> is the latest mtime
// of its own source file OR any of these shared-chrome files, so a Layout-level
// change (e.g. adding site-wide JSON-LD) correctly marks every page as updated.
const sharedChromeMs = [
  'src/layouts/Layout.astro',
  'src/components/Header.astro',
  'src/components/Footer.astro',
  'src/styles/global.css',
]
  .map((f) => mtimeMs(`${root}${f}`))
  .filter((ms) => ms > 0);

function mtimeMs(file) {
  try {
    return statSync(file).mtimeMs;
  } catch {
    return 0;
  }
}

// path like "/", "/about/", "/news/lifepo4-home-batteries/", "/legal/imprint/"
function lastmodFor(path) {
  const seg = path.replace(/^\/+|\/+$/g, '');
  const candidates =
    seg === ''
      ? [`${root}src/pages/index.astro`]
      : [`${root}src/pages/${seg}.astro`, `${root}src/pages/${seg}/index.astro`];
  const pageMs = candidates.map(mtimeMs).find((ms) => ms > 0) || 0;
  const latest = Math.max(pageMs, ...sharedChromeMs);
  return latest > 0 ? new Date(latest).toISOString() : undefined;
}

export default defineConfig({
  site: SITE,
  trailingSlash: 'ignore',
  build: {
    format: 'directory',
  },
  integrations: [
    sitemap({
      filter: (page) => !page.includes('/draft/'),
      serialize(item) {
        const path = item.url.startsWith(SITE) ? item.url.slice(SITE.length) : item.url;
        const lm = lastmodFor(path);
        if (lm) item.lastmod = lm;
        return item;
      },
    }),
  ],
});
