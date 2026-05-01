#!/usr/bin/env python3
"""
analyze_site.py — Analyze a scraped prospect site and generate a rebuild brief.

Reads the raw/ folder from scrape_site.py and produces:
  - PageSpeed score (via Lighthouse CLI)
  - Issues list (slow JS, missing meta, no SSL markers, etc.)
  - Content inventory (pages, images, services mentioned)
  - rebuild_brief.md — a structured doc for the rebuild phase

Usage:
    python3 analyze_site.py <prospect_dir>
    python3 analyze_site.py ~/prospects/tanktrack

Output:
    <prospect_dir>/rebuild_brief.md
    <prospect_dir>/pagespeed.json  (if lighthouse available)
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def run_lighthouse(url: str, out_dir: Path) -> dict | None:
    lh_path = out_dir / "pagespeed.json"
    # Pin lighthouse to a known major version. Unpinned `npx lighthouse` pulls
    # whatever the registry currently serves, which is one bad publish away
    # from running attacker-controlled JS as your user every time the script
    # runs.
    lighthouse_pkg = "lighthouse@12"
    try:
        result = subprocess.run(
            ["npx", "--yes", "-p", lighthouse_pkg, "lighthouse", url,
             "--output=json", f"--output-path={lh_path}",
             "--form-factor=mobile", "--throttling-method=simulate",
             "--only-categories=performance",
             # Drop --no-sandbox: Chrome's sandbox is the main barrier between
             # a malicious page in the audited URL and the host. Lighthouse
             # works without it on macOS dev machines.
             "--chrome-flags=--headless",
             "--quiet"],
            capture_output=True, text=True, timeout=120
        )
        if lh_path.exists():
            data = json.loads(lh_path.read_text())
            score = int((data["categories"]["performance"]["score"] or 0) * 100)
            lcp = data["audits"].get("largest-contentful-paint", {}).get("displayValue", "?")
            tbt = data["audits"].get("total-blocking-time", {}).get("displayValue", "?")
            return {"score": score, "lcp": lcp, "tbt": tbt}
    except Exception as e:
        print(f"  (Lighthouse error: {e} — skipping)")
    return None


def extract_pages(raw_dir: Path) -> list[dict]:
    pages = []
    for html_file in sorted(raw_dir.rglob("*.html"))[:50]:  # cap at 50
        content = html_file.read_text(encoding="utf-8", errors="ignore")
        title = re.search(r"<title[^>]*>([^<]+)</title>", content, re.IGNORECASE)
        h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", content, re.IGNORECASE)
        rel_path = str(html_file.relative_to(raw_dir))
        pages.append({
            "path": rel_path,
            "title": title.group(1).strip() if title else "",
            "h1": h1.group(1).strip() if h1 else "",
        })
    return pages


def extract_services(raw_dir: Path) -> list[str]:
    """Scrape service keywords from all HTML — what does this contractor offer?"""
    all_text = ""
    for html_file in list(raw_dir.rglob("*.html"))[:20]:
        content = html_file.read_text(encoding="utf-8", errors="ignore")
        # Strip tags
        text = re.sub(r"<[^>]+>", " ", content)
        all_text += " " + text.lower()
    
    SERVICE_KEYWORDS = [
        "driveway", "patio", "slab", "foundation", "walkway", "sidewalk",
        "pool deck", "stamped", "decorative", "epoxy", "garage floor",
        "commercial", "residential", "repair", "replacement", "seawall",
        "dock", "retaining wall", "flatwork", "concrete", "asphalt",
        "excavation", "grading", "drainage"
    ]
    
    found = [kw for kw in SERVICE_KEYWORDS if kw in all_text]
    return found


def generate_brief(prospect_dir: Path, url: str, audit: dict,
                   pages: list, services: list, ps: dict | None) -> str:
    domain = url.replace("https://", "").replace("http://", "").split("/")[0]
    
    brief = f"""# Rebuild Brief — {domain}

## Prospect Info
- **URL:** {url}
- **Phone:** {audit.get('phone', 'Not found')}
- **Email:** {audit.get('email', 'Not found')}
- **Title tag:** {audit.get('title', 'Missing')}
- **Meta description:** {audit.get('meta_description', 'Missing')}
- **H1:** {audit.get('h1', 'Missing')}

## Current Site Health
"""
    
    if ps:
        brief += f"""- **Mobile PageSpeed:** {ps['score']}/100
- **LCP:** {ps['lcp']}
- **TBT:** {ps['tbt']}
"""
    else:
        brief += "- **Mobile PageSpeed:** (run Lighthouse manually)\n"
    
    brief += f"""- **HTML pages found:** {audit.get('html_files', '?')}
- **Scripts per page:** {audit.get('scripts', '?')}
- **Stylesheets per page:** {audit.get('stylesheets', '?')}
- **Images per page:** {audit.get('images', '?')}

## Issues to Fix in Rebuild
"""
    
    issues = []
    if not audit.get("meta_description"):
        issues.append("❌ No meta description — missing SEO signal")
    if audit.get("scripts", 0) > 8:
        issues.append(f"❌ {audit['scripts']} scripts on page — likely slow load")
    if ps and ps["score"] < 50:
        issues.append(f"❌ Mobile PageSpeed {ps['score']}/100 — very poor")
    elif ps and ps["score"] < 70:
        issues.append(f"⚠️  Mobile PageSpeed {ps['score']}/100 — needs work")
    if not audit.get("phone"):
        issues.append("❌ No phone number found on homepage")
    
    issues.append("📱 Not optimized for mobile (common with old contractor sites)")
    issues.append("🐢 No lazy loading on images")
    issues.append("🎨 Outdated design — no social proof, no trust signals")
    
    for issue in issues:
        brief += f"- {issue}\n"
    
    brief += f"""
## Services They Offer
{', '.join(services) if services else 'Review raw HTML — not auto-detected'}

## Pages to Recreate
"""
    for page in pages[:15]:
        brief += f"- `{page['path']}` — {page['title'] or page['h1'] or 'Untitled'}\n"
    
    if len(pages) > 15:
        brief += f"- ...and {len(pages) - 15} more\n"
    
    brief += f"""
## Rebuild Plan

1. **Clone structure** from raw/ — reuse content, fix layout
2. **Keep:** Logo, phone number, services list, service area
3. **Replace:** All images → compressed WebP; fonts → Google Fonts
4. **Add:** Hero CTA ("Get a Free Estimate"), trust badges, reviews section
5. **Remove:** All tracking scripts, unnecessary plugins
6. **Target:** 85+ mobile PageSpeed, pixel-clean on iPhone SE + desktop

## Raw Files
- Scraped site: `{prospect_dir}/raw/`
- Screenshots: `{prospect_dir}/screenshots/`
- Audit data: `{prospect_dir}/audit.json`
"""
    return brief


def main():
    parser = argparse.ArgumentParser(description="Analyze a scraped prospect site")
    parser.add_argument("prospect_dir", help="Path to prospect folder from scrape_site.py")
    parser.add_argument("--url", help="Original URL (auto-detected from audit.json if omitted)")
    args = parser.parse_args()
    
    prospect_dir = Path(args.prospect_dir)
    audit_path = prospect_dir / "audit.json"
    
    if not prospect_dir.exists():
        print(f"ERROR: {prospect_dir} not found")
        sys.exit(1)
    
    audit = {}
    if audit_path.exists():
        audit = json.loads(audit_path.read_text())
        url = args.url or audit.get("url", "")
    else:
        url = args.url or ""
    
    if not url:
        print("ERROR: URL not found. Pass --url or run scrape_site.py first.")
        sys.exit(1)
    
    print(f"\n🔍 Analyzing: {url}")
    
    raw_dir = prospect_dir / "raw"
    pages = extract_pages(raw_dir)
    services = extract_services(raw_dir)
    
    print(f"  Pages found: {len(pages)}")
    print(f"  Services detected: {', '.join(services[:8])}")
    
    print("  Running Lighthouse...")
    ps = run_lighthouse(url, prospect_dir)
    if ps:
        print(f"  📊 PageSpeed: {ps['score']}/100 (LCP {ps['lcp']}, TBT {ps['tbt']})")
    
    brief = generate_brief(prospect_dir, url, audit, pages, services, ps)
    brief_path = prospect_dir / "rebuild_brief.md"
    brief_path.write_text(brief)
    
    print(f"\n✅ Rebuild brief → {brief_path}")
    print(f"   Next: review brief, then build or present to prospect")


if __name__ == "__main__":
    main()
