# Deploying SunHestia to Cloudflare Pages

The site is a static Astro build. Two deploy paths — pick **A** for speed
(live on a `*.pages.dev` URL within minutes, ideal for the W1 baseline), or **B**
for auto-deploy from Git.

## Build spec (same for both paths)

| | |
|---|---|
| Framework | Astro (static / SSG) |
| Root directory | `site/` (if repo root is the project) |
| Build command | `npm run build` |
| Build output | `dist/` |
| Node version | 20+ (uses Astro 5) |

---

## Path A — Direct upload via Wrangler (fastest, no Git needed)

Gets a live `https://sunhestia.pages.dev` URL immediately. Use this for the W1
control so the site is crawlable while the custom domain is being registered.

```bash
cd site

# one-time auth (opens a browser to log into Cloudflare)
npx wrangler login

# create the Pages project
npx wrangler pages project create sunhestia --production-branch main

# deploy the already-built output (run `npm run build` first)
npm run build
npx wrangler pages deploy dist --project-name sunhestia
```

Wrangler prints the live URL (e.g. `https://sunhestia.pages.dev`). That URL is
the W1 baseline measurement target.

### Add the custom domain later

Once `sunhestia.com` is registered and DNS is on Cloudflare:
Cloudflare dashboard → Pages → `sunhestia` → Custom domains → Add `sunhestia.com`.
Cloudflare provisions the certificate and points it at the project.

---

## Path B — Git integration (auto-deploy on every push)

```bash
# from project root
git init && git add -A && git commit -m "SunHestia W1 baseline site"
# create an empty GitHub repo, then push:
git remote add origin git@github.com:USER/sunhestia.git
git branch -M main
git push -u origin main
```

Then in Cloudflare: Pages → Create a project → Connect the GitHub repo.
Set **Root directory** = `site`, **Build command** = `npm run build`,
**Build output directory** = `dist`. Save — it builds and deploys, and rebuilds
on every push.

---

## Post-deploy (W1 infrastructure)

After the site is live on any URL:

1. **Google Search Console** → Add property → verify (DNS TXT or HTML file) →
   submit `https://sunhestia.com/sitemap-index.xml`.
2. **Bing Webmaster Tools** → Add site → submit the same sitemap (Bing feeds
   Copilot / AI search).
3. Spot-check the live robots.txt (`/robots.txt`) and sitemap (`/sitemap-index.xml`).
4. Confirm pages render as static HTML (view source — the H1 and copy should be
   present without JavaScript). The Astro build already guarantees this.
