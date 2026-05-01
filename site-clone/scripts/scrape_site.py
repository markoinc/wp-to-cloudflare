#!/usr/bin/env python3
"""
scrape_site.py — Spider a prospect's live website and save it locally.

Uses wget to mirror the site (HTML, CSS, JS, images) into a local folder.
This becomes the raw material for analysis and rebuild.

Usage:
    python3 scrape_site.py <url> [--out <output_dir>]

Examples:
    python3 scrape_site.py https://www.exampleconcrete.com
    python3 scrape_site.py https://www.tanktrack.com --out ~/prospects/tanktrack

Output:
    <output_dir>/raw/          - mirrored site files
    <output_dir>/screenshots/  - homepage screenshots (if playwright available)
    <output_dir>/audit.json    - basic site metadata (title, meta desc, H1, contact info)

Requirements:
    wget (brew install wget)
    Optional: playwright (pip install playwright && playwright install chromium)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def slugify(url: str) -> str:
    domain = urlparse(url).netloc.replace("www.", "")
    return re.sub(r"[^a-z0-9]", "-", domain.lower()).strip("-")


def mirror_site(url: str, out_dir: Path, allow_insecure: bool = False) -> bool:
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    base_cmd = [
        "wget",
        "--mirror",
        "--convert-links",
        "--adjust-extension",
        "--page-requisites",
        "--no-parent",
        "--timeout=15",
        "--tries=2",
        "--wait=1",
        "--random-wait",
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "-P", str(raw_dir),
    ]

    print(f"Mirroring {url} → {raw_dir}")
    # First attempt: with TLS verification on. Mirrored HTML/JS is the raw
    # material for a rebuild — if any of it ever gets re-served, we don't want
    # to be shipping JS that was MITM'd in transit. Only fall back to
    # --no-check-certificate when the user explicitly opts in via --insecure
    # (e.g. an expired-cert prospect site they trust).
    result = subprocess.run(base_cmd + [url], capture_output=True, text=True, timeout=300)

    # wget exit 5 = SSL verification failure
    if result.returncode == 5 and allow_insecure:
        print("  TLS verification failed — retrying with --no-check-certificate (--insecure flag set)")
        result = subprocess.run(
            base_cmd + ["--no-check-certificate", url],
            capture_output=True, text=True, timeout=300,
        )
    elif result.returncode == 5:
        print(
            "  TLS verification failed. Re-run with --insecure to mirror anyway.\n"
            "  (Mirrored JS from a MITM'd site can backdoor any rebuild that re-serves it.)"
        )

    # wget exits 8 for server errors on some pages — still usable
    if result.returncode not in (0, 8):
        print(f"wget warning (exit {result.returncode}): {result.stderr[-300:]}")

    html_files = list(raw_dir.rglob("*.html"))
    print(f"  Captured {len(html_files)} HTML files")
    return len(html_files) > 0


def audit_site(url: str, out_dir: Path) -> dict:
    """Extract basic SEO + contact info from the raw homepage HTML."""
    domain = urlparse(url).netloc
    raw_dir = out_dir / "raw"
    
    # Find homepage HTML
    candidates = list(raw_dir.rglob("index.html")) + list(raw_dir.glob(f"**/{domain}/index.html"))
    if not candidates:
        candidates = list(raw_dir.rglob("*.html"))
    
    if not candidates:
        return {"error": "No HTML found after mirror"}
    
    html = candidates[0].read_text(encoding="utf-8", errors="ignore")
    
    # Extract key fields
    title = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    meta_desc = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
    phone = re.search(r"(\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4})", html)
    email = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html)
    
    # Count images, scripts, CSS links
    img_count = len(re.findall(r"<img", html, re.IGNORECASE))
    script_count = len(re.findall(r"<script", html, re.IGNORECASE))
    css_count = len(re.findall(r'<link[^>]*rel=["\']stylesheet["\']', html, re.IGNORECASE))
    
    audit = {
        "url": url,
        "title": title.group(1).strip() if title else None,
        "meta_description": meta_desc.group(1).strip() if meta_desc else None,
        "h1": h1.group(1).strip() if h1 else None,
        "phone": phone.group(1) if phone else None,
        "email": email.group(0) if email else None,
        "images": img_count,
        "scripts": script_count,
        "stylesheets": css_count,
        "html_files": len(list(raw_dir.rglob("*.html"))),
        "raw_dir": str(raw_dir),
    }
    
    audit_path = out_dir / "audit.json"
    audit_path.write_text(json.dumps(audit, indent=2))
    
    print(f"\n  📋 Audit:")
    print(f"     Title:     {audit['title']}")
    print(f"     H1:        {audit['h1']}")
    print(f"     Phone:     {audit['phone']}")
    print(f"     Email:     {audit['email']}")
    print(f"     Scripts:   {script_count}  CSS: {css_count}  Images: {img_count}")
    
    return audit


def screenshot_site(url: str, out_dir: Path):
    """Take a full-page screenshot using Playwright if available."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  (Playwright not installed — skipping screenshot)")
        return

    screenshots_dir = out_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=30000)
        
        # Desktop
        page.screenshot(path=str(screenshots_dir / "desktop.png"), full_page=True)
        
        # Mobile
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(screenshots_dir / "mobile.png"), full_page=True)
        
        browser.close()
    
    print(f"  📸 Screenshots saved → {screenshots_dir}")


def main():
    parser = argparse.ArgumentParser(description="Spider a prospect website for clone/rebuild")
    parser.add_argument("url", help="Full URL to scrape (e.g. https://example.com)")
    parser.add_argument("--out", help="Output directory (default: ~/prospects/{slug})")
    parser.add_argument("--no-screenshot", action="store_true", help="Skip Playwright screenshots")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Allow wget --no-check-certificate fallback if TLS verification fails. "
             "Off by default — mirrored JS from a MITM'd connection can backdoor any rebuild.",
    )
    args = parser.parse_args()

    url = args.url.rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    
    slug = slugify(url)
    out_dir = Path(args.out) if args.out else Path.home() / "prospects" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n🕷️  Scraping: {url}")
    print(f"   Output:   {out_dir}\n")
    
    ok = mirror_site(url, out_dir, allow_insecure=args.insecure)
    if not ok:
        print("❌ Mirror failed — no HTML captured")
        sys.exit(1)
    
    audit = audit_site(url, out_dir)
    
    if not args.no_screenshot:
        screenshot_site(url, out_dir)
    
    print(f"\n✅ Done. Files in: {out_dir}")
    print(f"   Next: python3 analyze_site.py {out_dir}")


if __name__ == "__main__":
    main()
