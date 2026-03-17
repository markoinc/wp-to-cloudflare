# Performance Gotchas

Lessons learned from real-world Elementor/10web migrations.

---

## 1. 10web Booster Cache Must Be Warm Before Simply Static

**Symptom:** PageSpeed score 30–40 points lower than the live site. HTML references 15–25 individual JS/CSS files instead of 1–2 aggregated bundles.

**Root cause:** 10web Booster (`tenweb-speed-optimizer` plugin) aggregates all plugin CSS/JS into:
```
wp-content/cache/tw_optimize/css/two_front_page_aggregated*.min.css
wp-content/cache/tw_optimize/js/...
```
Simply Static crawls the page HTML as served. If the cache is cold when Simply Static runs, WordPress serves the un-optimized HTML with 20+ individual script tags. The export captures those — and `wp-content/cache/` is empty or absent.

**Detection:**
```bash
ls static-site/wp-content/cache/tw_optimize/ 2>/dev/null || echo "MISSING"
grep -c '<script.*src=' static-site/index.html   # >10 = probably missing cache
```

**Fix option A (preferred) — re-export with warm cache:**
1. Log into WP admin → confirm 10Web Booster active
2. Visit the live homepage in a browser (warms cache)
3. Re-run Simply Static immediately after

**Fix option B — postprocess instead:**
If re-export isn't possible (DNS already migrated, no WP access), run:
```bash
python3 scripts/postprocess_html.py static-site/
```
This defers JS, adds lazy-load/fetchpriority, strips query strings. Gets ~15–20 point
improvement without the cache. Not as good as the aggregated bundle but acceptable.

---

## 2. optimize_images.py Removes srcset Variants — Verify Before Push

**Symptom:** Images load fine on desktop, broken on mobile. Browser console shows 404s for `*-300x200.webp`, `*-768x512.webp` variants.

**Root cause:** WordPress generates multiple scaled variants for responsive `srcset` attributes.
The optimizer removes variants it believes are unreferenced — but earlier versions only scanned
`src=`, `href=`, `url()` and missed `srcset=` attributes.

**Detection (after optimize, before push):**
```bash
python3 - << 'EOF'
import re
from pathlib import Path

site = Path("static-site")
srcset_re = re.compile(r'srcset=["\']([^"\']+)["\']', re.IGNORECASE)
url_re = re.compile(r'([^\s,]+\.(?:webp|jpe?g|png|gif))', re.IGNORECASE)

missing = set()
for html in site.rglob("*.html"):
    for m in srcset_re.finditer(html.read_text(errors="ignore")):
        for u in url_re.findall(m.group(1)):
            p = site / u.lstrip("/").split("?")[0]
            if not p.exists():
                missing.add(u.lstrip("/"))

print(f"Missing srcset files: {len(missing)}")
for f in sorted(missing)[:20]:
    print(f"  {f}")
EOF
```

**Fix:** Restore from the original export ZIP:
```bash
python3 - << 'EOF'
import re, zipfile
from pathlib import Path
# ... (see scripts/optimize_images.py for the full restore logic)
EOF
```

Current version of `optimize_images.py` (v1.2+) already scans srcset — this only affects
exports processed with older versions.

---

## 3. Google Tag Manager / Analytics JS — Major Performance Drag

**Symptom:** Unused JavaScript audit shows 300–400KB wasted, mostly from Google Tag Manager.

**Root cause:** GTM and Google Analytics load large JS bundles even for pages with minimal
tracking needs. On a static rank-and-rent site with no active ad campaigns, they're dead weight.

**Check if GTM is present:**
```bash
grep -c "googletagmanager\|gtag" static-site/index.html
```

**Safe to remove if:**
- No active Google Ads conversion tracking (`AW-XXXXXXXXX` tag)
- No form submission tracking
- Site is purely for SEO / rank-and-rent (no PPC)

**How to remove:**
```python
import re
from pathlib import Path

# Remove GTM/gtag script tags from all HTML files
GTM_RE = re.compile(
    r'<script[^>]*(?:googletagmanager|gtag|GT-[A-Z0-9]+|G-[A-Z0-9]+|AW-[0-9]+)[^>]*>.*?</script>',
    re.DOTALL | re.IGNORECASE
)
for html in Path("static-site").rglob("*.html"):
    content = html.read_text(errors="ignore")
    patched = GTM_RE.sub("", content)
    if patched != content:
        html.write_text(patched)
        print(f"Removed GTM from {html.name}")
```

**⚠️ Ask before removing** if site has `AW-XXXXXXXXX` tags — those track Google Ads conversions.

---

## 4. Default Cloudflare Pages Cache Headers Are Too Aggressive

**Symptom:** Repeat visitors still make full requests for all assets. No performance gain
from CDN on second load.

**Root cause:** Cloudflare Pages default: `Cache-Control: public, max-age=0, must-revalidate`
on everything. This means the browser revalidates every asset on every page load.

**Fix:** Use `scripts/add_headers.py` to generate a `_headers` file at the site root.
This sets 7-day browser cache on uploads, plugins, themes, and wp-includes.

---

## 5. Elementor Hero Background Images Are CSS — Not Preloaded by Default

**Symptom:** LCP score poor even after image optimization. Hero background loads late.

**Root cause:** Elementor renders hero sections as CSS background images via inline `style=`
attributes. Browsers don't preload CSS backgrounds — they're discovered late in the render cycle.

**Detection:**
```bash
grep -o 'background-image:\s*url([^)]+)' static-site/index.html | head -5
```

**Fix:** Add a `<link rel="preload">` tag to `<head>` for the hero image:
```html
<link rel="preload" as="image" href="/wp-content/uploads/.../hero.webp" fetchpriority="high">
```

`scripts/postprocess_html.py` handles `fetchpriority="high"` on the first `<img>` tag but
**not** CSS background images (those require manual identification).
