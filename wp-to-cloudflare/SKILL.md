---
name: wp-to-cloudflare
description: Migrate a WordPress site (any host) to a free static site on Cloudflare Pages using Simply Static. Fully automated — only requires WP admin credentials. Use when asked to migrate, export, or move a WordPress site off expensive hosting (10web, WP Engine, Kinsta, SiteGround, etc.) to Cloudflare Pages. Also use for phrases like "get off 10web", "static site deploy", "migrate wordpress", or "reduce hosting costs". NOT for sites that require dynamic WordPress features (WooCommerce checkout, logged-in user content, etc.) unless those are handled by external embeds.
---

# wp-to-cloudflare

Migrates a WordPress/Elementor site to a free static site on Cloudflare Pages.

- **Cost:** $0/month hosting (vs $50–200/mo on managed WP hosts)
- **Speed:** 65–90+ mobile PageSpeed depending on optimization level (see Step 3)
- **Time:** ~30–45 min per site, fully automated
- **Embeds preserved:** GHL forms, Google Maps, review widgets, iframes, tel: links

## Prerequisites

Store credentials before running:

```
~/.config/cloudflare/credentials.json  → {"api_token": "...", "account_id": "..."}
~/.config/github/credentials.json      → {"token": "..."}
~/.config/namecheap/credentials.json   → {"api_user": "...", "api_key": "...", "username": "...", "client_ip": "..."}
```

- Cloudflare token needs **Cloudflare Pages: Edit** permission
- Namecheap API key must have machine IP whitelisted: Profile → Tools → API Access
- Install Pillow for image optimization: `brew install pillow`

## ⚠️ Critical: 10web Booster Cache

If the site uses **10web / 10Web Booster** (common on 10web-hosted sites), the speed
optimizer aggregates all CSS/JS into a single cached bundle at `wp-content/cache/tw_optimize/`.

**Simply Static must run WHILE this cache is warm**, otherwise the exported HTML will
reference 20+ individual plugin JS/CSS files instead of the aggregated bundle — resulting
in a PageSpeed score ~30 points lower than the live site.

**Before running Simply Static:**
1. Navigate to `https://{domain}/wp-admin/admin.php?page=two_settings_page`
2. Confirm "10Web Booster is Active — The plugin is now optimizing your website"
3. Visit the homepage of the live site in a browser (warms the cache)
4. Then immediately run Simply Static

If the cache directory is missing from the export, see `references/performance-gotchas.md`.

---

## Workflow

### Step 1 — Generate static export via Simply Static

1. Log in: `https://{domain}/wp-admin/`
2. Install Simply Static if not present: `/wp-admin/plugin-install.php?s=simply+static&tab=search`
3. Configure: `/wp-admin/admin.php?page=simply-static-settings` → **Replacing URLs: Relative Path**
4. Generate: `/wp-admin/admin.php?page=simply-static-generate` → **Generate Static Files**
   - Wait for completion (2–10 min, 5k–15k URLs typical)
   - Copy the ZIP download URL from the results

If a ZIP URL is already visible on the generate page (previously ran), skip to Step 2.

### Step 2 — Download and extract

```bash
mkdir -p ~/migrations/{site-slug}/static-site
cd ~/migrations/{site-slug}
curl -L -o export.zip "{zip_url}"
unzip -q export.zip -d static-site
```

**Do NOT delete:**
- `wp-content/uploads/` — active images used on pages
- `wp-content/cache/` — 10web Booster aggregated CSS/JS (critical for PageSpeed)
- `wp-content/plugins/` — Elementor/builder JS/CSS assets

Check for 10web cache:
```bash
ls static-site/wp-content/cache/tw_optimize/ 2>/dev/null && echo "Cache present ✅" || echo "Cache MISSING ⚠️"
```

If missing, see `references/performance-gotchas.md`.

### Step 3 — Optimize (run all three scripts in order)

```bash
# 3a. Compress images — biggest single PageSpeed win
#     Requires: brew install pillow
python3 scripts/optimize_images.py static-site/wp-content/uploads/ --confirm

# 3b. Post-process HTML — defer JS, lazy-load images, preload hero
python3 scripts/postprocess_html.py static-site/

# 3c. Add browser caching headers
python3 scripts/add_headers.py static-site/
```

Expected results after all three:
- Image directory: 70–85% smaller (e.g. 300MB → 60MB)
- Mobile PageSpeed: +20–35 points vs raw export
- TTI: typically drops from 20s+ to under 10s

### Step 4 — Deploy to GitHub + Cloudflare Pages

```bash
python3 scripts/deploy.py {site-slug} {domain.com} {github-org}
```

This handles: GitHub repo creation → git push → Cloudflare Pages project → deployment → custom domains.

### Step 5 — Switch DNS (Namecheap)

```bash
python3 scripts/switch_dns.py {domain.com} {site-slug}
```

Handles: detect current NS → switch to Namecheap BasicDNS if on custom NS → set CNAME + URL redirect.

### Step 6 — Verify

```bash
# DNS propagated
dig www.{domain.com} CNAME +short  # → {site-slug}.pages.dev.

# SSL + 200 OK
curl -sI https://www.{domain.com} | head -3
```

Then visually verify the site:
- All images loading (run `optimize_images.py --dry-run` first to catch srcset variants)
- GHL forms / Google Maps / review widgets present
- Mobile layout intact
- No console errors

Run Lighthouse to confirm score:
```bash
npx lighthouse https://www.{domain.com} --form-factor=mobile --only-categories=performance \
  --chrome-flags="--headless --no-sandbox" --output=json --output-path=/tmp/lh.json --quiet
python3 -c "import json; d=json.load(open('/tmp/lh.json')); print('Score:', int(d['categories']['performance']['score']*100))"
```

---

## Common Issues

| Issue | Fix |
|---|---|
| Login fails | Each WP site has a unique password — ask the user |
| Domain on AWS Route 53 NS | `switch_dns.py` handles this automatically |
| Images broken after deploy | `optimize_images.py` missed srcset references — run the fix in `references/performance-gotchas.md` |
| Cache dir missing from export | See performance-gotchas.md — 10web Booster wasn't warm |
| PageSpeed lower than live site | Usually missing `wp-content/cache/` — see performance-gotchas.md |
| SSL pending >10 min | Verify CNAME resolves; Cloudflare needs DNS propagation first |
| `_headers` file not taking effect | Must be at static site root (next to `index.html`), not in a subdirectory |
| 10web Booster admin page says "not allowed" | Booster requires active 10web connection — if already migrated DNS, use postprocess_html.py instead |

---

## PageSpeed Expectations

| Optimization level | Score | What's done |
|---|---|---|
| Raw export, no optimization | 30–40 | Nothing |
| Images optimized only | 55–65 | `optimize_images.py` |
| Images + HTML post-process | 60–70 | + `postprocess_html.py` |
| All scripts + cache present | 75–85 | + `add_headers.py` + 10web cache |
| Full optimization | 85–95 | + PurgeCSS on unused styles |

---

## References

- `references/image-optimization.md` — image compression strategy and thresholds
- `references/embed-compatibility.md` — which WP embeds survive static export
- `references/performance-gotchas.md` — 10web cache, srcset bugs, GTM removal
