---
name: site-clone
description: Scrape, analyze, and rebuild a prospect's existing website as a fast static site. Use when asked to clone a competitor or prospect's site, rebuild someone's website for a sales demo, scrape and recreate a local business website, or create a "before vs after" demo site. Phrases like "clone their site", "rebuild their website", "scrape and rebuild", "create a demo for [prospect]", "tank track style", or "rebuild a prospect's site" should trigger this skill.
---

# site-clone

Clones a prospect's live website, analyzes what's broken, and produces a rebuild brief + clean static version for use as a sales demo or replacement site.

**Typical use case:** Find a contractor with a slow/ugly site → clone it → show them a fast version → close the sale.

## Workflow

### Step 1 — Scrape

```bash
python3 scripts/scrape_site.py https://www.prospect.com
# Output: ~/prospects/{slug}/raw/ + audit.json + screenshots/
```

Requires `wget` (`brew install wget`). Screenshots require Playwright (`pip install playwright && playwright install chromium`).

### Step 2 — Analyze

```bash
python3 scripts/analyze_site.py ~/prospects/{slug}
# Output: ~/prospects/{slug}/rebuild_brief.md
```

This generates a rebuild brief with:
- Mobile PageSpeed score (via Lighthouse)
- Detected services and contact info
- Issues list
- Page inventory
- Rebuild checklist

### Step 3 — Rebuild

Read `rebuild_brief.md` then build the new site in `~/prospects/{slug}/rebuild/`.

For simple contractor sites (1–5 pages): build raw HTML/CSS — fastest path.
For Elementor/WP sites: use the `wp-to-cloudflare` skill to export and optimize the existing WP build instead of rebuilding from scratch.

Key decisions:
- **Keep:** phone, services, service area, logo, testimonials, license numbers
- **Add:** hero CTA, trust bar, `tel:` links, contact form (Formspree), LocalBusiness schema
- **Remove:** all tracking scripts, plugin bloat, chat widgets, cookie banners
- **Replace:** images → WebP at 1600px max, fonts → Google Fonts

See `references/rebuild-patterns.md` for full keep/replace/add/remove guide and target performance numbers.

### Step 4 — Deploy demo

Push rebuilt site to GitHub (private) + deploy on Cloudflare Pages:
```bash
# Use deploy.py from wp-to-cloudflare skill, or manually:
git init && git add -A && git commit -m "Prospect demo: {slug}"
git push  # → triggers CF Pages deploy at {slug}.pages.dev
```

No custom domain needed until the prospect pays. Send them the `{slug}.pages.dev` URL as the demo.

## Sales Pitch Flow

1. Scrape quietly — no login, no contact needed
2. Build demo (even 60% done is enough)
3. Message: *"I already rebuilt your site — here's the live preview [link]. Loads in under 2s on mobile, your current site takes 12s."*
4. Close on one-time rebuild fee or ongoing hosting + management

## Common Issues

| Issue | Fix |
|---|---|
| wget blocked (403/429) | Add `--wait=2 --random-wait`, try different user-agent |
| Site requires JS to render | Use Playwright: `playwright open {url}` to capture rendered HTML |
| Images load from CDN | Check audit.json for external image URLs; download manually |
| WP site with login wall | Switch to wp-to-cloudflare skill (needs admin access) |
| Site is already fast (70+) | Still rebuild — design and CTA are usually the real pitch |

## References

- `references/rebuild-patterns.md` — What to keep, replace, remove, add; target metrics; sales pitch context
